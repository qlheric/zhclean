"""dedupe 工具：hash 精确去重 + rapidfuzz 语义去重。

F: 两级去重：精确（hash）+ 语义（rapidfuzz 相似度阈值）；先规范化后去重
R: tools/normalize.py（先去规范化再去重）、rapidfuzz.fuzz.ratio
A: 被 cli.py 调用；自检 `python -m zhclean.tools.dedupe [--demo]`
S: 评测口径 recall≥95%；阈值不得用测试集调参；同输入同输出（无随机源）

接口契约（脑定，TASK-008 §2.5）：
- 输入 rows: list[dict]，每行至少含 id / field / value。
- dedupe_exact(rows)            -> 组列表：规范值相同即合并
- dedupe_fuzzy(rows, threshold) -> 组列表：精确键之外，规范值 ratio/100 >= threshold 再合并
- dedupe(rows, threshold=0.85)  -> 两级综合入口（= dedupe_fuzzy）
- dedupe_fuzzy(rows, threshold, field_overrides) -> 按字段换 scorer / 阈值 / link（TASK-011）
- dedupe_adaptive(rows, threshold) -> 内置 DEFAULT_ADAPTIVE（train 实验选定）
- 返回：组内行保持输入顺序；组间按各组首行在输入中的位置排序。

口径说明（实现时定下的两条，已在 RESULT-008 申报）：
1. 只在**同一 field 内**比较：不同字段的值即使字面相同（如 person 与 company 都写「华为」）也不合并。
2. **不按 id 强制合并**：同 id 的行规范化后相同自然同组；若 id 相同而规范值不同，交给相似度判，
   不拿 id 当答案（否则下一单的 recall 评测会被 id 直接「作弊」成 100%）。
"""

from __future__ import annotations

import math
import sys
from typing import Any

from rapidfuzz import fuzz

from .normalize import normalize

DEFAULT_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# 并查集：按输入序合并，根恒为组内最小下标 ⇒ 结果确定
# ---------------------------------------------------------------------------
class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        # 路径压缩（迭代写法，避免长链递归）
        root = i
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[i] != root:
            self.parent[i], i = root, self.parent[i]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # 小下标做根：组的「代表」就是首行，不依赖合并顺序
        if ra < rb:
            self.parent[rb] = ra
        else:
            self.parent[ra] = rb


def _check_threshold(threshold: float) -> float:
    """阈值校验：必须是 [0,1] 内的有限实数（bool 不算）。"""
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise TypeError(f"threshold 必须是数字，收到 {type(threshold).__name__}")
    if math.isnan(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold 取值须在 [0,1]，收到 {threshold!r}")
    return float(threshold)


def _keys(rows: list[dict]) -> list[tuple[Any, Any]]:
    """每行的精确去重键 = (field, 规范值)。非字符串 value 由 normalize 原样返回。"""
    return [(r["field"], normalize(r["value"], r["field"])) for r in rows]


def _union_exact(uf: _UnionFind, keys: list[tuple[Any, Any]]) -> dict[tuple, int]:
    """第一级：同键（field + 规范值）的行并到首次出现的那行。返回 键 → 首行下标。"""
    first: dict[tuple, int] = {}
    for i, k in enumerate(keys):
        try:
            j = first.setdefault(k, i)
        except TypeError:  # 不可 hash 的 value（如 list）：不参与精确合并，自成一组
            continue
        if j != i:
            uf.union(j, i)
    return first


def _groups(rows: list[dict], uf: _UnionFind) -> list[list[dict]]:
    """按根收组：遍历是输入序 ⇒ 组内保序；组按首次出现排列 ⇒ 组间按首行序。"""
    buckets: dict[int, list[dict]] = {}
    for i, r in enumerate(rows):
        buckets.setdefault(uf.find(i), []).append(r)
    return list(buckets.values())


def dedupe_exact(rows: list[dict]) -> list[list[dict]]:
    """精确去重：先 normalize，同 field 下规范值完全相同即合并。"""
    uf = _UnionFind(len(rows))
    _union_exact(uf, _keys(rows))
    return _groups(rows, uf)


_LINKS = ("all", "best")
_OVERRIDE_KEYS = {"scorer", "threshold", "link"}


def _check_overrides(field_overrides: dict | None) -> dict:
    """field_overrides 校验：每项须含 scorer（可调用）+ threshold（[0,1]），link 可选（all|best）。"""
    if field_overrides is None:
        return {}
    if not isinstance(field_overrides, dict):
        raise TypeError(f"field_overrides 必须是 dict 或 None，收到 {type(field_overrides).__name__}")
    out = {}
    for field, cfg in field_overrides.items():
        if not isinstance(cfg, dict) or not {"scorer", "threshold"} <= cfg.keys():
            raise ValueError(f"field_overrides[{field!r}] 须含 scorer 与 threshold 两键")
        if cfg.keys() - _OVERRIDE_KEYS:  # 拼错键名（如 thresh）不静默忽略
            raise ValueError(f"field_overrides[{field!r}] 有未知键 {sorted(cfg.keys() - _OVERRIDE_KEYS)}")
        if not callable(cfg["scorer"]):
            raise TypeError(f"field_overrides[{field!r}]['scorer'] 必须可调用")
        link = cfg.get("link", "all")
        if link not in _LINKS:
            raise ValueError(f"field_overrides[{field!r}]['link'] 须为 {_LINKS} 之一，收到 {link!r}")
        out[field] = (cfg["scorer"], _check_threshold(cfg["threshold"]), link)
    return out


def _link_all(uf: _UnionFind, items: list[tuple[str, int]], scorer, threshold: float) -> None:
    """link=all：任意一对 score >= threshold 即合并（原 TASK-008 语义，传递闭包）。"""
    for a in range(len(items)):
        va, ia = items[a]
        for b in range(a + 1, len(items)):
            vb, ib = items[b]
            if uf.find(ia) != uf.find(ib) and scorer(va, vb) >= threshold:
                uf.union(ia, ib)


def _link_best(uf: _UnionFind, items: list[tuple[str, int]], scorer, threshold: float) -> None:
    """link=best（precision 守卫）：每个值只连向它**严格唯一**的最高分候选（且 >= threshold）。

    并列最高 ⇒ 该值一条边都不连。动机（train 实验，见 DEFAULT_ADAPTIVE 注释）：
    低阈值下「范童」同时贴近「范童言」「范童宇」⇒ 歧义，宁可漏并也不把两个人桥接成一组。
    先打完全部分数再连边 ⇒ 结果与比较顺序无关（确定）。复杂度 O(u²) 次打分。
    """
    n = len(items)
    best: list[tuple[float, list[int]]] = [(-1.0, []) for _ in range(n)]  # (最高分, 取到最高分的下标们)
    for a in range(n):
        for b in range(a + 1, n):
            s = scorer(items[a][0], items[b][0])
            if s < threshold:
                continue
            for x, y in ((a, b), (b, a)):
                top, who = best[x]
                if s > top:
                    best[x] = (s, [y])
                elif s == top:
                    who.append(y)
    for a, (_, who) in enumerate(best):
        if len(who) == 1:
            uf.union(items[a][1], items[who[0]][1])


def _ratio(a: str, b: str) -> float:
    """默认 scorer：fuzz.ratio 归一到 [0,1]。"""
    return fuzz.ratio(a, b) / 100


def dedupe_fuzzy(rows: list[dict], threshold: float = DEFAULT_THRESHOLD,
                 field_overrides: dict | None = None) -> list[list[dict]]:
    """精确 + 语义两级去重。

    语义级只在「不同的规范值」之间比（同值已由精确级合并），且只比同一 field 的字符串值。
    默认相似度 = rapidfuzz.fuzz.ratio / 100，>= threshold 即合并（并查集传递闭包）。

    field_overrides（TASK-011 §2.5）：{field: {"scorer": (a, b) -> [0,1], "threshold": float,
    "link": "all" | "best"}}。未覆盖的字段仍用全局 threshold + fuzz.ratio + link=all；
    不传时行为与 TASK-008 逐字相同。link 缺省 "all"；"best" 见 _link_best。
    复杂度：每个 field 内 O(u²)，u = 去重后的不同规范值个数。
    """
    threshold = _check_threshold(threshold)
    overrides = _check_overrides(field_overrides)
    uf = _UnionFind(len(rows))
    keys = _keys(rows)
    first = _union_exact(uf, keys)

    # 按 field 分桶；dict 保插入序 ⇒ 比较顺序 = 输入序，结果确定
    by_field: dict[Any, list[tuple[str, int]]] = {}
    for (field, val), idx in first.items():
        if isinstance(val, str):
            by_field.setdefault(field, []).append((val, idx))

    cutoff = threshold * 100  # rapidfuzz 分数是 0~100
    for field, items in by_field.items():
        if field in overrides:
            scorer, t, link = overrides[field]
            (_link_best if link == "best" else _link_all)(uf, items, scorer, t)
            continue
        # 未覆盖字段：原路径，保留 score_cutoff 剪枝（与 TASK-008 逐字等价）
        for a in range(len(items)):
            va, ia = items[a]
            for b in range(a + 1, len(items)):
                vb, ib = items[b]
                if uf.find(ia) == uf.find(ib):
                    continue  # 已在同组，省一次打分
                # score_cutoff：低于阈值时 rapidfuzz 直接返回 0，可提前剪枝
                if fuzz.ratio(va, vb, score_cutoff=cutoff) >= cutoff:
                    uf.union(ia, ib)
    return _groups(rows, uf)


# ---------------------------------------------------------------------------
# 自适应配置（TASK-011）：按字段 scorer + 阈值 + link，全部依据 train 实验选定
# ---------------------------------------------------------------------------
def same_initial_ratio(a: str, b: str) -> float:
    """person scorer：首字（姓）不同直接 0；同姓再算 fuzz.ratio/100。

    挡「王小明 / 李小明」这类异姓误并；代价是姓本身打错的那一类会漏（保守取舍）。
    """
    return fuzz.ratio(a, b) / 100 if a[:1] == b[:1] else 0.0


def ratio_or_partial(a: str, b: str) -> float:
    """company / address scorer：max(ratio, partial_ratio)/100。

    partial_ratio 抓「简称 ⊂ 全称」（「数联贸易集团有限公司」⊂「嘉兴数联贸易集团有限公司」、
    「贵阳市…」⊂「贵州省贵阳市…」）；ratio 兜「有限公司 / 有限责任公司」这类非子串改写。
    """
    return max(fuzz.ratio(a, b), fuzz.partial_ratio(a, b)) / 100


# train 实验（只读 train：每字段 160 id × 6 行；heldout 未参与）。各字段单独评，P/R 为该字段 pair 口径。
# link=all 即 TASK-008 原语义；link=best 为唯一最佳候选守卫。完整候选表见 RESULT-011 §2。
#
# person（基线 ratio@0.85/all：R59.08 P99.86 F1 74.24）
#   ratio@0.70/all            R92.92 P94.17 F1 93.54
#   ratio@0.60/all            R100   P83.68 F1 91.12   ← recall 全拿但 precision 大掉，拒
#   ratio_or_partial@0.70/all R96.67 P85.61 F1 90.80
#   ratio@0.60/best           R99.38 P97.07 F1 98.21
#   same_initial@0.60/best    R99.58 P97.08 F1 98.31   ← 选（0.50~0.65 结果相同，取中）
#   same_initial@0.60/互为唯一最佳 R80.63 P99.90（recall 掉太多，拒）
# company（基线 ratio@0.85/all：R83.96 P100 F1 91.28）
#   partial@0.90/all          R97.92 P93.29 F1 95.55
#   ratio_or_partial@0.90/all R100   P93.02 F1 96.39
#   ratio_or_partial@0.85/best R100  P94.34 F1 97.09
#   ratio_or_partial@0.90/best R100  P100   F1 100     ← 选（0.95：R96.88 P100）
# address（基线 ratio@0.85/all：R98.54 P100 F1 99.27）
#   ratio@0.80/all            R99.17 P100   F1 99.58
#   ratio_or_partial@0.85/best R100  P100   F1 100
#   ratio_or_partial@0.90/best R100  P100   F1 100     ← 选（0.85~0.95 全 100，取中；与 company 同配）
# phone：基线已 R100 P100，不覆盖（走全局 threshold + ratio）。
DEFAULT_ADAPTIVE: dict[str, dict] = {
    "person": {"scorer": same_initial_ratio, "threshold": 0.60, "link": "best"},
    "company": {"scorer": ratio_or_partial, "threshold": 0.90, "link": "best"},
    "address": {"scorer": ratio_or_partial, "threshold": 0.90, "link": "best"},
}


def dedupe_adaptive(rows: list[dict], threshold: float = DEFAULT_THRESHOLD) -> list[list[dict]]:
    """自适应入口：DEFAULT_ADAPTIVE 覆盖 person/company/address，其余字段用全局 threshold。"""
    return dedupe_fuzzy(rows, threshold, field_overrides=DEFAULT_ADAPTIVE)


def describe_adaptive(cfg: dict | None = None) -> dict:
    """把配置转成可 JSON 落盘的描述（scorer 记函数名）。"""
    cfg = DEFAULT_ADAPTIVE if cfg is None else cfg
    return {f: {"scorer": getattr(c["scorer"], "__name__", repr(c["scorer"])),
                "threshold": c["threshold"], "link": c.get("link", "all")} for f, c in cfg.items()}


def dedupe(rows: list[dict], threshold: float = DEFAULT_THRESHOLD) -> list[list[dict]]:
    """综合入口：精确 + 语义两级去重（TASK-008 §2.5）。"""
    return dedupe_fuzzy(rows, threshold)


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def _ids(groups: list[list[dict]]) -> list[list[Any]]:
    return [[r["id"] for r in g] for g in groups]


def _demo() -> None:
    """最小可运行检查：精确合并 / 阈值内合并 / 阈值外不合 / 规范化后合并 / 空输入 / 确定性。"""
    def row(i: Any, v: str, f: str = "person") -> dict:
        return {"id": i, "field": f, "value": v}

    # 1) 精确合并：同值同组，不同值分组
    assert _ids(dedupe_exact([row(1, "王小明"), row(2, "李四"), row(3, "王小明")])) == [[1, 3], [2]]

    # 2) 规范化后合并：「王 小明」经 normalize 归一为「王小明」
    assert _ids(dedupe_exact([row(1, "王小明"), row(2, "王 小明")])) == [[1, 2]]

    # 3) 阈值内合并：两串 ratio ≈ 0.909（1 字之差，各 11 字）
    a, b = "北京市海淀区中关村大街", "北京市海淀区中关村大道"
    assert fuzz.ratio(a, b) / 100 >= 0.85
    assert _ids(dedupe([row(1, a, "address"), row(2, b, "address")], 0.85)) == [[1, 2]]

    # 4) 阈值外不合：同一对，阈值抬到 0.95 就不合
    assert _ids(dedupe([row(1, a, "address"), row(2, b, "address")], 0.95)) == [[1], [2]]

    # 5) 空输入
    assert dedupe([]) == [] and dedupe_exact([]) == []

    # 6) 确定性：两次调用结果逐项相同
    rows = [row(i, v, "address") for i, v in enumerate([a, "上海市浦东新区", b, a])]
    assert _ids(dedupe(rows)) == _ids(dedupe(rows)) == [[0, 2, 3], [1]]

    # 7) 自适应：缩写 / 简称合并；异姓不并
    assert _ids(dedupe_adaptive([row(1, "范童言"), row(2, "范童")])) == [[1, 2]]
    assert _ids(dedupe_adaptive([row(1, "王小明"), row(2, "李小明")])) == [[1], [2]]
    assert _ids(dedupe_adaptive([row(1, "嘉兴数联贸易集团有限公司", "company"),
                                 row(2, "数联贸易集团有限公司", "company")])) == [[1, 2]]

    # 8) 阈值越界被拒
    for bad in (-0.1, 1.1, float("nan")):
        try:
            dedupe([], bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"threshold={bad} 应被拒")

    print("dedupe._demo: OK")


if __name__ == "__main__":
    # `--demo` 与无参等价（TASK §2.5 写带参、§3 判据写无参，两种都支持）
    if len(sys.argv) > 1 and sys.argv[1] not in ("--demo",):
        sys.exit(f"用法: python -m zhclean.tools.dedupe [--demo]，未知参数 {sys.argv[1:]}")
    _demo()

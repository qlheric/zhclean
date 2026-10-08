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


def dedupe_fuzzy(rows: list[dict], threshold: float = DEFAULT_THRESHOLD) -> list[list[dict]]:
    """精确 + 语义两级去重。

    语义级只在「不同的规范值」之间比（同值已由精确级合并），且只比同一 field 的字符串值。
    相似度 = rapidfuzz.fuzz.ratio / 100，>= threshold 即合并（并查集传递闭包）。
    复杂度：每个 field 内 O(u²)，u = 去重后的不同规范值个数。
    """
    threshold = _check_threshold(threshold)
    uf = _UnionFind(len(rows))
    keys = _keys(rows)
    first = _union_exact(uf, keys)

    # 按 field 分桶；dict 保插入序 ⇒ 比较顺序 = 输入序，结果确定
    by_field: dict[Any, list[tuple[str, int]]] = {}
    for (field, val), idx in first.items():
        if isinstance(val, str):
            by_field.setdefault(field, []).append((val, idx))

    cutoff = threshold * 100  # rapidfuzz 分数是 0~100
    for items in by_field.values():
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

    # 7) 阈值越界被拒
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

"""整表清洗工具：CSV 进出，按列映射八类字段逐格规范化（+ 可选整行去重）。

F: 整表清洗：读 CSV → 列名映射八类字段 → 逐格 normalize_with_confidence → 原位替换 + 报告
R: tools/normalize.py（逐格）、tools/dedupe.py（dedupe=True 整行去重）、loop.HITL_THRESHOLD（低置信口径）
A: 被 cli.py 的 `table` 子命令调用；自检 `python -m zhclean.tools.table [--demo]`
S: 只读不写（落盘在 cli 层）；不改 schema（原位替换格值）；同输入同输出（无随机源）

接口契约（脑定，TASK-027 §2.5）：
- clean_table(src, dst=None, columns=None, dedupe=False) -> dict
  * src       ：CSV 文件路径（str / Path）或已打开的文本流；utf-8-sig 读（容 BOM）。
  * columns   ：{CSV 列名: 字段名}，字段 ∈ 八类；缺省按「列名 == 字段名」自动匹配；不匹配的列原样保留。
  * dedupe    ：True ⇒ 先清洗、再对整行做 dedupe_adaptive 去重（组保留首行；判定见口径 5）。
  * dst       ：**仅为接口对称保留** —— 本函数是纯函数、不写任何文件（落盘由 cli 层负责），传值被忽略。
  * 返回       {"header", "rows", "rows_out", "changed_cells", "report"}：
      header / rows = 清洗后的表（与原表列对齐、原位替换）；
      report = {rows_in, cols, by_field{changed/unchanged/hitl}, unmapped_columns, dedupe}。

口径说明（契约空白处我定的，已在 RESULT-027 §5 申报）：
1. 逐格替换 = 就地改格值：列不变、行序不变（除非 dedupe）。「改动」= 规范值 != 原格值（逐字符）。
2. hitl = 置信度 < loop.HITL_THRESHOLD（0.2，与 Agent Loop 同源）的格数 = 「规则给不出证据、
   建议送 LLM / 人工复核」的格；与 changed / unchanged 是**并列**计数（一格可同时 unchanged 且 hitl）。
3. 短行 / 超长行容忍：只有与表头对齐的列参与清洗，多出来的格原样保留（不报错）。
4. columns 里出现表头没有的列名 ⇒ 抛 ValueError（防列名打错后「静默不生效」）。
5. `dedupe=True` 的「整行」判定 = **每一列都同 dedupe 组**才算重复行（各列取合取，只在共有
   映射列上比）。契约只写「对整行做 dedupe_adaptive」，未定「任一列 vs 每列」；取最窄读法，
   理由与反例见 `_dedupe_rows` docstring。
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

from .._compat import utf8_stdio
from ..loop import HITL_THRESHOLD
from ..rules import DISPATCH
from .dedupe import _UnionFind, dedupe_adaptive
from .normalize import normalize_with_confidence

# 字段名唯一真相源 = 规则库注册表（加字段只需改 rules/__init__.py，本模块自动跟随）
FIELDS: tuple[str, ...] = tuple(DISPATCH)


def _read_csv_text(src) -> str:
    """取 CSV 文本：文件路径（str / Path）读盘，文本流直接读。只读，不写。"""
    if hasattr(src, "read"):
        return src.read()
    if isinstance(src, (str, Path)):
        return Path(src).read_text(encoding="utf-8-sig")
    raise TypeError(f"src 须是 CSV 文件路径或文本流，收到 {type(src).__name__}")


def _resolve_columns(header: list[str], columns: dict | None) -> dict[str, str]:
    """定出「表头列名 → 字段名」映射。缺省按列名 == 字段名自动匹配；显式映射先校验。"""
    if columns is None:
        return {h: h for h in header if h in FIELDS}
    if not isinstance(columns, dict):
        raise TypeError(f"columns 须是 {{列名: 字段名}} 或 None，收到 {type(columns).__name__}")
    unknown = set(header)
    for col, field in columns.items():
        if field not in FIELDS:
            raise ValueError(f"列 {col!r} 映射到未知字段 {field!r}（须是八类之一：{FIELDS}）")
        if col not in unknown:
            raise ValueError(f"列名 {col!r} 不在表头中（表头：{header}）")
    return dict(columns)


def _clean_rows(header: list[str], rows: list[list[str]],
                col_map: dict[str, str]) -> tuple[list[list[str]], int, dict]:
    """逐格清洗。返回 (清洗后行, 改动格数, 报告片段)。原 rows 不被修改。"""
    by_field: dict[str, dict[str, int]] = {}
    changed_cells = 0
    out: list[list[str]] = []
    for row in rows:
        new_row = list(row)  # 拷贝：不改入参
        for i, cell in enumerate(row):
            field = col_map.get(header[i]) if i < len(header) else None
            if field is None:
                continue  # 未映射列 / 超长行的多余格：原样保留
            after, conf = normalize_with_confidence(cell, field)
            stat = by_field.setdefault(field, {"changed": 0, "unchanged": 0, "hitl": 0})
            if after != cell:
                changed_cells += 1
                stat["changed"] += 1
            else:
                stat["unchanged"] += 1
            if isinstance(conf, (int, float)) and conf < HITL_THRESHOLD:
                stat["hitl"] += 1
            new_row[i] = after
        out.append(new_row)
    return out, changed_cells, by_field


def _dedupe_rows(rows: list[list[str]], header: list[str],
                 col_map: dict[str, str]) -> tuple[list[list[str]], dict]:
    """整行去重：逐列做 dedupe_adaptive，**每一列都同组**的行才并（组保留首行）。

    为什么是「每列都同组」而非「任一列同组」：dedupe 的口径是「只在同一 field 内比较」
    （tools/dedupe.py 口径 1）⇒ 行的同一性应是各列取**合取**。反例（本单实测）：
    docs/examples/sample.csv 第 1/3 行是两个人（范童言 / 孟露峰），却同样有手机 / 身份证 /
    邮箱三列 —— 按「任一列同组」会被误并成一行。
    行间只在**共有映射列**上比（短行容忍）；没有任何共有映射列的行绝不并。输出保首行，
    行序 = 首行在输入中的次序（确定）。
    """
    n = len(rows)
    cells: list[tuple[int, int, dict]] = []  # (行下标, 列下标, 记录)
    for i, row in enumerate(rows):
        for j, h in enumerate(header):
            if h in col_map and j < len(row):
                cells.append((i, j, {"id": i, "field": col_map[h], "value": row[j]}))

    # 每格落进哪个去重组；组内是原记录对象 ⇒ 用 id() 反查（同列同字段也分得开）
    gid_of: dict[int, int] = {}
    for g, group in enumerate(dedupe_adaptive([c[2] for c in cells])):
        for r in group:
            gid_of[id(r)] = g

    per_row: dict[int, dict[int, int]] = {}
    for i, j, r in cells:
        per_row.setdefault(i, {})[j] = gid_of[id(r)]

    uf = _UnionFind(n)  # 复用 dedupe 同一套并查集（同包私有件）⇒ 根恒为组内最小下标
    # ponytail: 行两两比 O(n²)；表很大（>1e4 行）时改成「按首列分桶再组内比」即可
    for i in range(n):
        for k in range(i + 1, n):
            a, b = per_row.get(i, {}), per_row.get(k, {})
            common = a.keys() & b.keys()
            if common and all(a[c] == b[c] for c in common):
                uf.union(i, k)

    kept = [row for i, row in enumerate(rows) if uf.find(i) == i]
    return kept, {"applied": True, "groups": len({uf.find(i) for i in range(n)}),
                  "removed": n - len(kept)}


def clean_table(src, dst=None, columns: dict | None = None, dedupe: bool = False) -> dict:
    """整表清洗主入口（见模块头契约）。纯函数：只读 src、不写文件。

    `dst` 仅为接口对称保留，本函数不写任何文件 —— 落盘由 cli 层负责。
    """
    reader = csv.reader(io.StringIO(_read_csv_text(src)))
    table = [row for row in reader if any(cell.strip() for cell in row)]  # 丢全空行
    header = table[0] if table else []
    rows = table[1:]
    col_map = _resolve_columns(header, columns)
    unmapped = [h for h in header if h not in col_map]

    cleaned, changed_cells, by_field = _clean_rows(header, rows, col_map)
    report: dict = {
        "rows_in": len(rows),
        "cols": len(header),
        "by_field": by_field,
        "unmapped_columns": unmapped,
        "dedupe": {"applied": False, "groups": 0, "removed": 0},
    }
    if dedupe:
        cleaned, dd = _dedupe_rows(cleaned, header, col_map)
        report["dedupe"] = dd

    return {"header": header, "rows": cleaned, "rows_out": len(cleaned),
            "changed_cells": changed_cells, "report": report}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def _demo() -> None:
    """最小可运行检查：自动映射 / 显式映射 / 未匹配列保留 / 逐格替换 / 报告 / dedupe / 确定性 / 空输入。"""
    text = "person,phone,备注\n范 童言,+86 138-0013-8000,甲\n范童言,13800138000,乙\n"

    # 1) 按列名自动匹配（person / phone），未匹配列（备注）原样保留
    r = clean_table(io.StringIO(text))
    assert r["header"] == ["person", "phone", "备注"]
    assert r["report"]["unmapped_columns"] == ["备注"]
    assert r["rows"][0] == ["范童言", "13800138000", "甲"]   # 逐格原位替换
    assert r["rows"][1] == ["范童言", "13800138000", "乙"]   # 已干净 ⇒ 不变
    assert r["changed_cells"] == 2 and r["rows_out"] == 2

    # 2) 报告统计：person 改 1 未改 1；phone 改 1 未改 1（hitl 为 0，两条都「有把握」）
    assert r["report"]["by_field"]["person"] == {"changed": 1, "unchanged": 1, "hitl": 0}
    assert r["report"]["by_field"]["phone"] == {"changed": 1, "unchanged": 1, "hitl": 0}

    # 3) 显式列映射：中文列名 → 字段名；未列出的列（other）保留
    r2 = clean_table(io.StringIO("姓名,other\n范 童言,x\n"), columns={"姓名": "person"})
    assert r2["rows"] == [["范童言", "x"]] and r2["report"]["unmapped_columns"] == ["other"]

    # 4) 低置信计数（hitl）：未注册字段（列名即未知字段名）⇒ 原样返回、conf 0.1 < 0.2
    r3 = clean_table(io.StringIO("unknown\n随便\n"))
    assert r3["changed_cells"] == 0 and r3["report"]["by_field"] == {}  # 无映射列 ⇒ 不参与

    # 5) dedupe：清洗后两行内容相同 ⇒ 并成一行（组保留首行）
    d = clean_table(io.StringIO("person,phone\n范 童言,13800138000\n范童言,13800138000\n"), dedupe=True)
    assert d["rows_out"] == 1 and d["report"]["dedupe"] == {"applied": True, "groups": 1, "removed": 1}
    assert d["rows"][0] == ["范童言", "13800138000"]
    # 5b) 反例守卫：共有手机号但**姓名不同** ⇒ 不是重复行，不许并（「任一列同组」就会误并）
    d2 = clean_table(io.StringIO("person,phone\n范童言,13800138000\n孟露峰,13800138000\n"), dedupe=True)
    assert d2["rows_out"] == 2 and d2["report"]["dedupe"]["removed"] == 0

    # 6) 确定性：两次调用逐项相同
    assert clean_table(io.StringIO(text)) == clean_table(io.StringIO(text))

    # 7) 空输入 / 仅表头
    e = clean_table(io.StringIO(""))
    assert (e["header"], e["rows"], e["rows_out"], e["changed_cells"]) == ([], [], 0, 0)
    h = clean_table(io.StringIO("person,phone\n"))
    assert h["rows"] == [] and h["report"]["cols"] == 2

    # 8) columns 打错列名 ⇒ 抛错（不静默）
    for bad in ({"不存在": "person"}, {"person": "bogus"}):
        try:
            clean_table(io.StringIO(text), columns=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"columns={bad} 应被拒")

    print("table._demo: OK")


if __name__ == "__main__":
    utf8_stdio()  # 用法/报错含中文，Windows 控制台默认 cp936 会写坏（TASK-015）
    # `--demo` 与无参等价（TASK §2.5 写带参、§3 判据写无参，两种都支持）
    if len(sys.argv) > 1 and sys.argv[1] != "--demo":
        sys.exit(f"用法: python -m zhclean.tools.table [--demo]，未知参数 {sys.argv[1:]}")
    _demo()

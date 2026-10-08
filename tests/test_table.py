"""table 工具单测：列映射（自动 / 显式）/ 未匹配列保留 / 逐格替换 / 报告 / dedupe / 确定性 / 边界。

F: tools/table.clean_table 的行为与报告口径（八类字段）
R: src/zhclean/tools/table.py
A: uv run --project . pytest tests/test_table.py -q
S: 全用内存 CSV（io.StringIO）+ tmp_path，不依赖 benchmarks 数据、不碰 heldout
"""

from __future__ import annotations

import io

import pytest

from zhclean.tools.table import FIELDS, clean_table

CSV = "person,phone,备注\n范 童言,+86 138-0013-8000,甲\n范童言,13800138000,乙\n"


def clean(text: str, **kw):
    return clean_table(io.StringIO(text), **kw)


def test_fields_is_eight():
    assert FIELDS == ("person", "address", "phone", "company", "amount", "date", "idcard", "email")


def test_auto_map_by_column_name():
    r = clean(CSV)
    assert r["header"] == ["person", "phone", "备注"]
    assert r["report"]["unmapped_columns"] == ["备注"]           # 备注 不匹配任何字段 ⇒ 原样
    assert r["rows"] == [["范童言", "13800138000", "甲"], ["范童言", "13800138000", "乙"]]
    assert r["rows_out"] == 2 and r["changed_cells"] == 2


def test_explicit_columns_map_chinese_header():
    r = clean("姓名,手机,备注\n范 童言,+86 138-0013-8000,x\n", columns={"姓名": "person", "手机": "phone"})
    assert r["rows"] == [["范童言", "13800138000", "x"]]
    assert r["report"]["unmapped_columns"] == ["备注"]


def test_unmapped_column_kept_verbatim_even_when_it_looks_dirty():
    """未映射列（即使表头写的是字段名之外的东西）一格都不动。"""
    r = clean("工资,person\n  ￥12 345.00  ,范 童言\n")
    assert r["rows"] == [["  ￥12 345.00  ", "范童言"]]


def test_report_by_field_counts():
    r = clean(CSV)
    assert r["report"]["by_field"]["person"] == {"changed": 1, "unchanged": 1, "hitl": 0}
    assert r["report"]["by_field"]["phone"] == {"changed": 1, "unchanged": 1, "hitl": 0}
    assert r["report"]["rows_in"] == 2 and r["report"]["cols"] == 3


def test_hitl_counts_low_confidence_cells():
    """低置信（< loop.HITL_THRESHOLD）计入 hitl：无法处理的邮箱原样返回，conf 0.1。"""
    r = clean("email\nnot-an-email\n")
    assert r["rows"] == [["not-an-email"]] and r["changed_cells"] == 0
    assert r["report"]["by_field"]["email"] == {"changed": 0, "unchanged": 1, "hitl": 1}


def test_idcard_and_email_columns_are_cleaned():
    r = clean("idcard,email\n11041219760513 1500,sbe1hdy@ hotmail.com\n")
    assert r["rows"] == [["110412197605131500", "sbe1hdy@hotmail.com"]]
    assert r["changed_cells"] == 2


def test_dedupe_merges_rows_identical_after_cleaning():
    r = clean("person,phone\n范 童言,13800138000\n范童言,13800138000\n", dedupe=True)
    assert r["rows_out"] == 1 and r["rows"] == [["范童言", "13800138000"]]
    assert r["report"]["dedupe"] == {"applied": True, "groups": 1, "removed": 1}


def test_dedupe_off_keeps_all_rows():
    r = clean("person,phone\n范 童言,13800138000\n范童言,13800138000\n")
    assert r["rows_out"] == 2 and r["report"]["dedupe"]["applied"] is False


def test_dedupe_keeps_first_row_of_group():
    r = clean("person\n范 童言\n范童言\n李四\n", dedupe=True)   # 清洗后 = 范童言 / 范童言 / 李四
    assert r["rows"] == [["范童言"], ["李四"]] and r["rows_out"] == 2


def test_dedupe_requires_all_columns_to_match():
    """「整行」= 每一列都同组才并：只共有手机号、姓名不同 ⇒ 不是重复行（最窄读法）。"""
    r = clean("person,phone\n范童言,13800138000\n孟露峰,13800138000\n", dedupe=True)
    assert r["rows_out"] == 2 and r["report"]["dedupe"]["removed"] == 0


def test_dedupe_matches_on_common_columns_only():
    """短行容忍：一列的表里，只有共有列参与判定（这里是 person 一列）。"""
    r = clean("person,phone\n范 童言,13800138000\n范童言\n", dedupe=True)
    assert r["rows_out"] == 1 and r["rows"] == [["范童言", "13800138000"]]


def test_ragged_rows_tolerated():
    """短行 / 超长行：只清洗与表头对齐的列，多出的格原样保留。"""
    r = clean("person,phone\n范 童言\n范 童言,13800138000,多余格\n")
    assert r["rows"][0] == ["范童言"]
    assert r["rows"][1] == ["范童言", "13800138000", "多余格"]


def test_src_accepts_path_and_tolerates_bom(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("person,phone\n范 童言,+86 138-0013-8000\n", encoding="utf-8-sig")  # 带 BOM
    r = clean_table(p)                                       # 直接传路径
    assert r["header"] == ["person", "phone"] and r["rows"] == [["范童言", "13800138000"]]


def test_determinism():
    assert clean(CSV) == clean(CSV) and clean(CSV, dedupe=True) == clean(CSV, dedupe=True)


def test_empty_and_header_only():
    e = clean("")
    assert (e["header"], e["rows"], e["rows_out"], e["changed_cells"]) == ([], [], 0, 0)
    h = clean("person,phone\n")
    assert h["rows"] == [] and h["report"]["cols"] == 2 and h["report"]["rows_in"] == 0


@pytest.mark.parametrize("bad", [{"不存在": "person"}, {"person": "bogus"}, {"person": ""}])
def test_columns_errors_raise_valueerror(bad):
    with pytest.raises(ValueError):
        clean("person,phone\n范 童言,13800138000\n", columns=bad)


def test_columns_not_a_dict_raises_typeerror():
    with pytest.raises(TypeError):
        clean(CSV, columns=[("person", "person")])


def test_bad_src_type_raises_typeerror():
    with pytest.raises(TypeError):
        clean_table(12345)


def test_does_not_mutate_input_row_lists():
    rows = [["范 童言", "13800138000"]]
    clean_table(io.StringIO("person,phone\n范 童言,13800138000\n"), columns={"person": "person", "phone": "phone"})
    assert rows == [["范 童言", "13800138000"]]              # 入参列表不被改（clean_table 拷贝行）


def test_demo_runs_ok(capsys):
    from zhclean.tools.table import _demo
    _demo()
    assert "table._demo: OK" in capsys.readouterr().out

"""dedupe 工具的不变式测试。

F: 精确去重；规范化后去重（脏写法归一合并）；语义阈值内/外；阈值边界 [0,1] 校验；
   空输入；组内保序 + 组间按首行序；确定性；同 field 才比；dedupe 综合入口
R: src/zhclean/tools/dedupe.py、src/zhclean/tools/normalize.py
A: uv run --project . pytest tests/test_dedupe.py -q
S: 只用手写样例，不读 benchmarks 数据/词典（防留出集反推）
"""

from __future__ import annotations

import pytest
from rapidfuzz import fuzz

from zhclean.tools.dedupe import DEFAULT_THRESHOLD, dedupe, dedupe_exact, dedupe_fuzzy

# 一对 ratio ≈ 0.909 的地址（11 字差 1 字），用来卡阈值
A1 = "北京市海淀区中关村大街"
A2 = "北京市海淀区中关村大道"


def row(i, v, f="person"):
    return {"id": i, "field": f, "value": v}


def ids(groups):
    return [[r["id"] for r in g] for g in groups]


# ---- 精确去重 ---------------------------------------------------------------
def test_exact_merges_identical_values():
    assert ids(dedupe_exact([row(1, "王小明"), row(2, "李四"), row(3, "王小明")])) == [[1, 3], [2]]


def test_exact_keeps_distinct_values_apart():
    assert ids(dedupe_exact([row(1, "王小明"), row(2, "李四")])) == [[1], [2]]


@pytest.mark.parametrize("dirty", ["王 小明", "王　小明", "王-小明"])
def test_exact_merges_after_normalize(dirty):
    """脏写法经 normalize 归一后与规范值同组（先规范化后去重）。"""
    assert ids(dedupe_exact([row(1, "王小明"), row(2, dirty)])) == [[1, 2]]


def test_exact_phone_normalized_forms_merge():
    """不同书写格式的同一号码规范化后相同 ⇒ 同组。"""
    rows = [row(1, "13812345678", "phone"), row(2, "138 1234 5678", "phone"), row(3, "138-1234-5678", "phone")]
    assert ids(dedupe_exact(rows)) == [[1, 2, 3]]


def test_same_value_different_field_not_merged():
    """只在同一 field 内比较。"""
    rows = [row(1, "华为", "person"), row(2, "华为", "company")]
    assert ids(dedupe_exact(rows)) == [[1], [2]]
    assert ids(dedupe(rows, 0.0)) == [[1], [2]]


# ---- 语义去重 ---------------------------------------------------------------
def test_fixture_pair_score_is_between_thresholds():
    """前提校验：样例对的分数确实落在 0.85 与 0.95 之间，下面两条用例才有意义。"""
    assert 0.85 <= fuzz.ratio(A1, A2) / 100 < 0.95


def test_fuzzy_merges_within_threshold():
    assert ids(dedupe_fuzzy([row(1, A1, "address"), row(2, A2, "address")], 0.85)) == [[1, 2]]


def test_fuzzy_keeps_apart_outside_threshold():
    assert ids(dedupe_fuzzy([row(1, A1, "address"), row(2, A2, "address")], 0.95)) == [[1], [2]]


def test_fuzzy_is_transitive():
    """a~b、b~c 即使 a 与 c 不够像，也并进同一组（并查集闭包）。"""
    a, b, c = "ABCDEFGHIJ", "ABCDEFGHIX", "ABCDEFGHYX"
    assert fuzz.ratio(a, c) / 100 < 0.9 <= fuzz.ratio(a, b) / 100
    rows = [row(1, a, "company"), row(2, b, "company"), row(3, c, "company")]
    assert ids(dedupe_fuzzy(rows, 0.9)) == [[1, 2, 3]]


def test_threshold_one_equals_exact():
    rows = [row(1, A1, "address"), row(2, A2, "address"), row(3, A1, "address")]
    assert ids(dedupe_fuzzy(rows, 1.0)) == ids(dedupe_exact(rows)) == [[1, 3], [2]]


def test_threshold_zero_merges_whole_field():
    rows = [row(1, "王小明"), row(2, "李四"), row(3, A1, "address")]
    assert ids(dedupe_fuzzy(rows, 0.0)) == [[1, 2], [3]]


# ---- 阈值校验 ---------------------------------------------------------------
@pytest.mark.parametrize("bad", [-0.01, 1.01, 85, float("nan"), float("inf")])
def test_threshold_out_of_range_rejected(bad):
    with pytest.raises(ValueError):
        dedupe([row(1, "王小明")], bad)


@pytest.mark.parametrize("bad", ["0.85", None, True])
def test_threshold_wrong_type_rejected(bad):
    with pytest.raises(TypeError):
        dedupe([row(1, "王小明")], bad)


@pytest.mark.parametrize("ok", [0, 0.0, 0.5, 1, 1.0])
def test_threshold_boundaries_accepted(ok):
    assert ids(dedupe([row(1, "王小明")], ok)) == [[1]]


# ---- 空输入 / 保序 / 确定性 / 综合入口 ---------------------------------------
def test_empty_input():
    assert dedupe([]) == [] and dedupe_exact([]) == [] and dedupe_fuzzy([], 0.5) == []


def test_order_within_and_between_groups():
    """组内保持输入序；组间按首行在输入中的位置。"""
    rows = [row("b1", "李四"), row("a1", "王小明"), row("b2", "李四"), row("a2", "王 小明")]
    assert ids(dedupe(rows)) == [["b1", "b2"], ["a1", "a2"]]


def test_returns_original_row_objects():
    rows = [row(1, "王 小明"), row(2, "王小明")]
    g = dedupe(rows)
    assert g[0][0] is rows[0] and g[0][0]["value"] == "王 小明"  # 不改写入参


def test_deterministic_across_calls():
    rows = [row(i, v, "address") for i, v in enumerate([A1, "上海市浦东新区", A2, A1, "上海市浦东新区"])]
    first = ids(dedupe(rows))
    for _ in range(3):
        assert ids(dedupe(rows)) == first
    assert first == [[0, 2, 3], [1, 4]]


def test_dedupe_is_exact_plus_fuzzy():
    """综合入口 = 精确 + 语义：脏写法归一合并、近似值合并、无关值分开。"""
    rows = [
        row(1, "王小明"),
        row(2, A1, "address"),
        row(3, "王 小明"),
        row(4, A2, "address"),
        row(5, "上海市浦东新区", "address"),
    ]
    assert ids(dedupe(rows)) == [[1, 3], [2, 4], [5]]
    assert ids(dedupe(rows)) == ids(dedupe_fuzzy(rows, DEFAULT_THRESHOLD))


def test_default_threshold():
    assert DEFAULT_THRESHOLD == 0.85

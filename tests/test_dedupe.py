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
from zhclean.tools.dedupe import (  # TASK-011 新增
    DEFAULT_ADAPTIVE,
    dedupe_adaptive,
    describe_adaptive,
    ratio_or_partial,
    same_initial_ratio,
)

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


# ============================================================================
# TASK-011：field_overrides / link=best / dedupe_adaptive（手写样例，不读 benchmarks 数据）
# ============================================================================
MIXED = [
    row(1, "王小明"), row(2, A1, "address"), row(3, "王 小明"), row(4, A2, "address"),
    row(5, "上海市浦东新区", "address"), row(6, "范童言"), row(7, "范童"), row(8, "13812345678", "phone"),
]


# ---- 向后兼容 ---------------------------------------------------------------
@pytest.mark.parametrize("t", [0.0, 0.5, 0.85, 0.95, 1.0])
@pytest.mark.parametrize("ov", [None, {}])
def test_overrides_absent_is_backward_compatible(t, ov):
    """不传 / 传空 field_overrides ⇒ 与原两参调用逐组相同（且是同一批行对象）。"""
    assert dedupe_fuzzy(MIXED, t, field_overrides=ov) == dedupe_fuzzy(MIXED, t)
    assert ids(dedupe_fuzzy(MIXED, t, ov)) == ids(dedupe(MIXED, t))


# ---- field_overrides 生效 -----------------------------------------------------
def test_override_scorer_and_threshold_take_effect():
    """person 换成「恒 1.0」scorer ⇒ 全并；address 不覆盖 ⇒ 仍按全局 0.95 分开。"""
    ov = {"person": {"scorer": lambda a, b: 1.0, "threshold": 0.99}}
    rows = [row(1, "王小明"), row(2, "李四"), row(3, A1, "address"), row(4, A2, "address")]
    assert ids(dedupe_fuzzy(rows, 0.95, ov)) == [[1, 2], [3], [4]]


def test_override_threshold_only_lowers_one_field():
    """同一 scorer，只给 address 降阈值：address 合并、person 不受影响。"""
    ov = {"address": {"scorer": lambda a, b: fuzz.ratio(a, b) / 100, "threshold": 0.85}}
    rows = [row(1, A1, "address"), row(2, A2, "address"), row(3, "王小明"), row(4, "王小红")]
    assert ids(dedupe_fuzzy(rows, 0.95, ov)) == [[1, 2], [3], [4]]


def test_override_threshold_inclusive():
    """scorer 返回值 == threshold 时合并（>= 语义）。"""
    ov = {"person": {"scorer": lambda a, b: 0.5, "threshold": 0.5}}
    assert ids(dedupe_fuzzy([row(1, "甲"), row(2, "乙")], 1.0, ov)) == [[1, 2]]


def test_override_scorer_only_sees_same_field_strings():
    seen = []
    ov = {"person": {"scorer": lambda a, b: seen.append((a, b)) or 0.0, "threshold": 0.5}}
    dedupe_fuzzy([row(1, "王小明"), row(2, A1, "address"), row(3, "李四")], 0.85, ov)
    assert seen == [("王小明", "李四")]


@pytest.mark.parametrize("bad, exc", [
    ({"person": {"threshold": 0.5}}, ValueError),                                # 缺 scorer
    ({"person": {"scorer": abs}}, ValueError),                                   # 缺 threshold
    ({"person": {"scorer": abs, "threshold": 0.5, "thresh": 1}}, ValueError),    # 未知键
    ({"person": {"scorer": "ratio", "threshold": 0.5}}, TypeError),              # scorer 不可调用
    ({"person": {"scorer": abs, "threshold": 1.5}}, ValueError),                 # 阈值越界
    ({"person": {"scorer": abs, "threshold": "0.5"}}, TypeError),                # 阈值类型错
    ({"person": {"scorer": abs, "threshold": 0.5, "link": "any"}}, ValueError),  # link 非法
    ({"person": "ratio"}, ValueError),                                           # 配置不是 dict
    ([("person", {})], TypeError),                                               # 整体不是 dict
])
def test_override_validation(bad, exc):
    with pytest.raises(exc):
        dedupe_fuzzy([row(1, "王小明")], 0.85, bad)


# ---- link=best（precision 守卫机制） -----------------------------------------
def test_link_best_tie_blocks_merge():
    """两对各自互为唯一最佳（A~X、B~Y）+ 歧义点 C 同时贴近 A 与 B（并列）⇒ C 不连任何一边。

    对照 link=all：同阈值下 C 把两对桥接成一组（这就是守卫要挡的误并）。
    """
    tab = {frozenset("AX"): 0.95, frozenset("BY"): 0.95, frozenset("AC"): 0.8, frozenset("BC"): 0.8}
    sc = lambda a, b: tab.get(frozenset((a, b)), 0.0)  # noqa: E731
    rows = [row(v, v) for v in "AXBYC"]
    cfg = lambda link: {"person": {"scorer": sc, "threshold": 0.7, "link": link}}  # noqa: E731
    assert ids(dedupe_fuzzy(rows, 0.85, cfg("all"))) == [["A", "X", "B", "Y", "C"]]
    assert ids(dedupe_fuzzy(rows, 0.85, cfg("best"))) == [["A", "X"], ["B", "Y"], ["C"]]


def test_link_best_unique_best_merges():
    sc = lambda a, b: fuzz.ratio(a, b) / 100  # noqa: E731
    rows = [row(1, "范童言"), row(2, "范童")]
    assert ids(dedupe_fuzzy(rows, 0.85, {"person": {"scorer": sc, "threshold": 0.6, "link": "best"}})) == [[1, 2]]


def test_link_best_order_independent():
    """link=best 先打完全部分再连边 ⇒ 输入顺序打乱，分组（按 id 集合）不变。"""
    vals = ["王小明", "王小红", "王小", "范童言", "范童", "李四"]
    ov = {"person": {"scorer": same_initial_ratio, "threshold": 0.6, "link": "best"}}
    canon = lambda gs: sorted(sorted(g) for g in ids(gs))  # noqa: E731
    fwd = canon(dedupe_fuzzy([row(v, v) for v in vals], 0.85, ov))
    rev = canon(dedupe_fuzzy([row(v, v) for v in reversed(vals)], 0.85, ov))
    # 王小* 三者被桥接属已知局限（见 test_link_best_hub_limitation_documented）
    assert fwd == rev == sorted([["王小", "王小明", "王小红"], ["范童", "范童言"], ["李四"]])


# ---- scorer 本身 --------------------------------------------------------------
def test_same_initial_ratio():
    assert same_initial_ratio("王小明", "李小明") == 0.0       # 异姓直接 0
    assert same_initial_ratio("范童言", "范童") == fuzz.ratio("范童言", "范童") / 100
    assert same_initial_ratio("", "范童") == 0.0               # 空串不抛（首字不同 ⇒ 0）


def test_ratio_or_partial_catches_substring():
    full, short = "嘉兴数联贸易集团有限公司", "数联贸易集团有限公司"
    assert fuzz.ratio(full, short) / 100 < 0.95 and ratio_or_partial(full, short) == 1.0


# ---- dedupe_adaptive：主战场合并 + precision 守卫 --------------------------------
@pytest.mark.parametrize("full, dirty", [
    ("范童言", "范童"),      # person 缩写（掉末字）
    ("聂玲哲", "聂哲"),      # person 缩写（掉中字）
    ("陈思远", "陈思原"),    # person 错字（同姓，一字之差）
])
def test_adaptive_person_abbrev_and_typo_merge(full, dirty):
    rows = [row(1, full), row(2, dirty)]
    assert ids(dedupe(rows)) == [[1], [2]]            # 对照：原配置漏并
    assert ids(dedupe_adaptive(rows)) == [[1, 2]]


@pytest.mark.parametrize("full, short", [
    ("嘉兴数联贸易集团有限公司", "数联贸易集团有限公司"),   # 去地名前缀（简称 ⊂ 全称）
    ("宜春清源实业有限公司", "宜春清源实业"),               # 去后缀
    ("邯郸云栖新能源有限责任公司", "邯郸云栖新能源有限公司"),  # 有限责任 → 有限
])
def test_adaptive_company_short_name_merge(full, short):
    rows = [row(1, full, "company"), row(2, short, "company")]
    assert ids(dedupe_adaptive(rows)) == [[1, 2]]


def test_adaptive_address_province_prefix_merge():
    rows = [row(1, "贵州省贵阳市城关区建设路596号", "address"), row(2, "贵阳市城关区建设路596号", "address")]
    assert ids(dedupe_adaptive(rows)) == [[1, 2]]


@pytest.mark.parametrize("a, b, f", [
    ("王小明", "李小明", "person"),                         # 异姓同名
    ("王小明", "王大伟", "person"),                         # 同姓不同名
    ("嘉兴数联贸易有限公司", "嘉兴恒信餐饮有限公司", "company"),  # 同城同后缀、字号不同
    ("北京市朝阳区建国路88号", "北京市朝阳区光华路12号", "address"),  # 同区不同路
])
def test_adaptive_rejects_wrong_merge(a, b, f):
    """precision 守卫：这些不同实体在自适应配置下仍不合并。"""
    assert ids(dedupe_adaptive([row(1, a, f), row(2, b, f)])) == [[1], [2]]


def test_adaptive_two_people_with_typos_stay_apart():
    """两人各带一条错字变体：各自互为唯一最佳 ⇒ 各并各的，异姓之间不串。"""
    rows = [row(1, "王小明"), row(2, "王小名"), row(3, "李大红"), row(4, "李大虹")]
    assert ids(dedupe(rows, 0.6)) == [[1, 2], [3, 4]]   # 前提：两组之间本就不够像
    assert ids(dedupe_adaptive(rows)) == [[1, 2], [3, 4]]


def test_link_best_hub_limitation_documented():
    """已知局限（RESULT-011 §6 申报）：守卫只看「出边方」是否并列。

    「王小」自身并列贴近两人 ⇒ 不从它连出；但「王小明」「王小红」各自的唯一最佳都是「王小」
    ⇒ 两条出边都成立，三者仍被桥接。此用例锁定现状，防止日后改动无意改变语义而不自知。
    """
    rows = [row(1, "王小明"), row(2, "王小红"), row(3, "王小")]
    assert ids(dedupe_adaptive(rows)) == [[1, 2, 3]]


def test_adaptive_phone_uses_global_threshold():
    """phone 不在 DEFAULT_ADAPTIVE ⇒ 走全局 threshold + ratio，与 dedupe 一致。"""
    assert "phone" not in DEFAULT_ADAPTIVE
    rows = [row(1, "13812345678", "phone"), row(2, "13812345679", "phone")]
    for t in (0.85, 0.95):
        assert ids(dedupe_adaptive(rows, t)) == ids(dedupe(rows, t))


def test_adaptive_returns_original_rows_and_deterministic():
    rows = [row(1, "范童言"), row(2, "范 童"), row(3, "嘉兴数联贸易集团有限公司", "company")]
    g = dedupe_adaptive(rows)
    assert g[0][0] is rows[0] and rows[1]["value"] == "范 童"
    assert ids(g) == ids(dedupe_adaptive(rows)) == [[1, 2], [3]]


def test_describe_adaptive_is_json_ready():
    import json
    d = describe_adaptive()
    assert set(d) == set(DEFAULT_ADAPTIVE)
    assert d["person"] == {"scorer": "same_initial_ratio", "threshold": 0.6, "link": "best"}
    json.dumps(d)  # 可落盘

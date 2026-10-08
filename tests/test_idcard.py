"""身份证规则的不变式测试。

F: space/sep/noise/typo/abbrev 五类代表性用例；15 位老证 → 18 位补全 + 校验码重算；
   坏校验码不采纳；值已规范 0.95 档；置信度 ∈ [0,1]；idcard 已注册且老六类字段不受影响
R: src/zhclean/rules/idcard.py、src/zhclean/rules/__init__.py
A: uv run --project . pytest tests/ -q
S: 只测规则与注册表，不测评测管线内部（那在 test_evaluate.py）；不读 benchmark 生成器

用例取自 train 真实扰动（`benchmarks/dirty/idcard.jsonl`，只读 train 部分）；
下面的真值都独立按 GB 11643 重算过校验码。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import zhclean` 不依赖 pytest 的启动方式

import zhclean  # noqa: E402

# 三个合法 18 位证号（train 真实值），下面用例的真值
VALID = "116047198805081999"
VALID2 = "115929198911069542"
VALID3 = "113530197809077869"

# 独立重算校验码（与 rules/idcard.py 的实现无关，用于交叉验证真值本身）
_ID_W = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_C = "10X98765432"


def _check(v: str) -> str:
    return _ID_C[sum(int(c) * w for c, w in zip(v[:17], _ID_W)) % 11]


@pytest.mark.parametrize("value", [VALID, VALID2, VALID3])
def test_fixtures_are_valid_ids(value):
    """先证明夹具本身合法（否则下面的用例是假绿）。"""
    assert len(value) == 18 and value[17] == _check(value)


# ---------- space：去掉串内所有空白（半角 / 全角） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("116 047198805081999", VALID),
    ("116047198805081999 ", VALID),
    ("11592919891106　9542", VALID2),          # 全角空格
    ("1135301978090 77869", VALID3),
])
def test_space_stripped(dirty, expected):
    assert zhclean.normalize(dirty, "idcard") == expected


# ---------- sep：去掉生日段分隔符（- 及其他分隔符） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("1160471988-05-081999", VALID),
    ("116047-1988-05081999", VALID),
    ("1159291989-11-069542", VALID2),
    ("1135301978-09-077869", VALID3),
])
def test_sep_stripped(dirty, expected):
    assert zhclean.normalize(dirty, "idcard") == expected


# ---------- noise：去前缀标签 / 尾部括号备注 / 尾随标点 ----------

@pytest.mark.parametrize("dirty,expected", [
    ("身份证号：116047198805081999", VALID),
    ("身份证:113530197809077869", VALID3),
    ("证件号：115929198911069542", VALID2),
    ("116047198805081999（复印件）", VALID),
    ("116047198805081999（本人）", VALID),
    ("116047198805081999。", VALID),
])
def test_noise_stripped(dirty, expected):
    assert zhclean.normalize(dirty, "idcard") == expected


# ---------- 结构层命中即 0.9（无损、可验证） ----------

@pytest.mark.parametrize("dirty", ["116 047198805081999", "1160471988-05-081999",
                                   "身份证号：116047198805081999"])
def test_structural_hit_is_high_confidence(dirty):
    value, conf = zhclean.normalize_with_confidence(dirty, "idcard")
    assert value == VALID
    assert conf == pytest.approx(0.9)


# ---------- typo：数字形近字母修复（任意位置，闸门兜底） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("1l6047198805081999", VALID),   # l → 1（地区码位）
    ("11353019780907T869", VALID3),  # T → 7（顺序码位）
    ("11592919891l069542", VALID2),  # l → 1（生日位）
    ("11604719880SO81999", VALID),   # S → 5、O → 0（两处形近，一次闸门复核）
])
def test_confusable_digits_repaired(dirty, expected):
    assert zhclean.normalize(dirty, "idcard") == expected


def test_repair_confidence_is_infer_band():
    value, conf = zhclean.normalize_with_confidence("1l6047198805081999", "idcard")
    assert value == VALID and 0.0 < conf < 0.9


# ---------- abbrev：15 位老证 → 18 位（补「19」+ 重算校验码） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("116047880508199", VALID),
    ("113530780907786", VALID3),
    ("115929891106954", VALID2),
])
def test_abbrev_expanded_to_18(dirty, expected):
    assert len(dirty) == 15, "夹具本身应是 15 位老证"
    assert zhclean.normalize(dirty, "idcard") == expected


def test_abbrev_expansion_recomputes_check_digit():
    """展开出的第 18 位必须是按 GB 11643 重算的校验码，而不是照搬 15 位里任何数字。"""
    value, conf = zhclean.normalize_with_confidence("116047880508199", "idcard")
    assert value == VALID
    assert value[17] == _check(value)      # 交叉验证：校验码自洽
    assert value[17] == VALID[17]
    assert conf == pytest.approx(0.7)


# ---------- 坏校验码不采纳：闸门把「改坏」挡在门外 ----------

@pytest.mark.parametrize("dirty", [
    "116047198805081998",   # 末位校验码被改（应为 9）
    "11604719880508199",    # 只有 17 位
    "1160471988050819999",  # 19 位
    "11604719880508A999",   # 含无法形近还原的字母（A→4 后仍不合法）
])
def test_bad_check_digit_stays_untouched(dirty):
    assert zhclean.normalize_with_confidence(dirty, "idcard") == (dirty, 0.1)


# ---------- 值已规范：合法证号无改动 ⇒ 0.95（TASK-015 拆档） ----------

@pytest.mark.parametrize("value", [VALID, VALID2, VALID3])
def test_clean_value_untouched_and_high_confidence(value):
    assert zhclean.normalize_with_confidence(value, "idcard") == (value, 0.95)


# ---------- 置信度必须落在 [0, 1] ----------

@pytest.mark.parametrize("value", ["116 047198805081999", VALID, "1l6047198805081999",
                                   "116047880508199", "", "身份证"])
def test_confidence_in_range(value):
    _, conf = zhclean.normalize_with_confidence(value, "idcard")
    assert 0.0 <= conf <= 1.0


# ---------- 注册表：idcard 已注册，且老六类不受影响（八字段回归护栏） ----------

def test_idcard_registered():
    from zhclean.rules import DISPATCH
    assert "idcard" in DISPATCH and callable(DISPATCH["idcard"])


def test_old_six_fields_unaffected():
    """注册 idcard 后，老六类字段行为逐字不变（各 1 条代表用例）。"""
    assert zhclean.normalize("王 小明", "person") == "王小明"
    assert zhclean.normalize("广东省深圳市南山区", "address") == "广东省深圳市南山区"
    assert zhclean.normalize("13800000000", "phone") == "13800000000"
    assert zhclean.normalize("阿里巴巴（中国）有限公司", "company") == "阿里巴巴（中国）有限公司"
    assert zhclean.normalize("12,345元", "amount") == "12345元"
    assert zhclean.normalize("2020-1-2", "date") == "2020-01-02"

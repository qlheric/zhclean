"""电话规则的不变式测试。

F: space/sep/abbrev(国家码)/noise 四类代表性用例；数字形近修复；修坏不返回；置信度 ∈ [0,1]；
   phone 已注册且 person 行为不受影响
R: src/zhclean/rules/phone.py、src/zhclean/rules/__init__.py
A: uv run --project . pytest tests/ -q
S: 只测规则与注册表，不测评测管线内部（那在 test_evaluate.py）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import zhclean` 不依赖 pytest 的启动方式

import zhclean  # noqa: E402

VALID = "15745524079"  # 一个合法号码（1[3-9] 开头 11 位），下面用例的真值

# ---------- space：去掉串内所有空白（半角 / 全角） ----------

@pytest.mark.parametrize("dirty", ["15 745524079", "157　45524079", "157 4552 4079", " 15745524079 "])
def test_space_stripped(dirty):
    assert zhclean.normalize(dirty, "phone") == VALID


# ---------- sep：去掉分隔符（- · | ／ ，） ----------

@pytest.mark.parametrize("dirty", ["157-4552-4079", "157·4552·4079", "157|4552|4079",
                                   "157／4552／4079", "157，4552，4079"])
def test_sep_stripped(dirty):
    assert zhclean.normalize(dirty, "phone") == VALID


# ---------- abbrev：剥离国家码前缀（86 / +86 / 086 / 0086） ----------

@pytest.mark.parametrize("dirty", ["8615745524079", "+8615745524079",
                                   "08615745524079", "008615745524079"])
def test_country_code_stripped(dirty):
    assert zhclean.normalize(dirty, "phone") == VALID


# ---------- noise：去前缀标签 / 尾部括号备注 / 尾随标点 ----------

@pytest.mark.parametrize("dirty", ["电话：15745524079", "手机:15745524079", "15745524079（微信同号）",
                                   "15745524079（本人）", "15745524079（备用）", "15745524079。"])
def test_noise_stripped(dirty):
    assert zhclean.normalize(dirty, "phone") == VALID


# ---------- 结构清洗命中即高置信 ----------

@pytest.mark.parametrize("dirty", ["15 745524079", "157-4552-4079", "8615745524079", "电话：15745524079"])
def test_structural_hit_is_high_confidence(dirty):
    value, conf = zhclean.normalize_with_confidence(dirty, "phone")
    assert value == VALID
    assert conf == pytest.approx(0.9)


# ---------- typo：数字形近字母修复（OCR 常见） ----------
# 只在真值里字形有歧义的位上替换：VALID 的 1/5/2/0 位；含 3/8 的另用一个号码。

@pytest.mark.parametrize("dirty,expected", [
    ("l5745524079", VALID),   # l → 1
    ("1574S524079", VALID),   # S → 5
    ("15745S24079", VALID),   # S → 5（上单实际用到的位）
    ("157455Z4079", VALID),   # Z → 2
    ("15745524O79", VALID),   # O → 0（上单实际用到的位）
    ("1E834567890", "13834567890"),  # E → 3
    ("13B34567890", "13834567890"),  # B → 8
])
def test_confusable_digits_repaired(dirty, expected):
    assert zhclean.normalize(dirty, "phone") == expected


def test_repair_confidence_is_lower_than_structural():
    value, conf = zhclean.normalize_with_confidence("15745524O79", "phone")
    assert value == VALID and 0.0 < conf < 0.9


# ---------- 修坏不返回：位数 / 开头校验挡在门外 ----------

@pytest.mark.parametrize("dirty", [
    "15745524O7",    # 只有 10 位（少一位），修完仍不合法
    "15745524O729",  # 12 位（多一位）
    "05745524079",   # 11 位但 0 开头
    "12745524079",   # 11 位但 1[3-9] 不成立（12 开头）
    "O5745524079",   # 修完是 05745524079，仍非法
])
def test_invalid_stays_untouched(dirty):
    assert zhclean.normalize_with_confidence(dirty, "phone") == (dirty, 0.1)


# ---------- 国家码只在剩余恰为 11 位时才剥（不误伤号段） ----------

@pytest.mark.parametrize("dirty", ["861574552407", "861574552407912"])
def test_country_code_strip_is_length_guarded(dirty):
    # 剥了不是 11 位 ⇒ 不剥；也没法修 ⇒ 原样低置信
    assert zhclean.normalize_with_confidence(dirty, "phone") == (dirty, 0.1)


# ---------- 置信度必须落在 [0, 1] ----------

@pytest.mark.parametrize("value", ["15 745524079", VALID, "15745524O79", "", "x", "1574552"])
def test_confidence_in_range(value):
    _, conf = zhclean.normalize_with_confidence(value, "phone")
    assert 0.0 <= conf <= 1.0


# ---------- 注册表：phone 已注册，且 person 不受影响 ----------

def test_phone_registered():
    from zhclean.rules import DISPATCH
    assert "phone" in DISPATCH and callable(DISPATCH["phone"])


def test_person_unaffected_by_phone():
    # 回归：注册 phone 后人名清洗行为不变（TASK-003 的三类结构清洗仍全对）
    assert zhclean.normalize("王 小明", "person") == "王小明"
    assert zhclean.normalize("王·小明", "person") == "王小明"
    assert zhclean.normalize("姓名：王小明", "person") == "王小明"
    # 反向：电话规则不会把人名当号码（person handler 仍归属 person 字段）
    assert zhclean.normalize_with_confidence("王小明", "person") == ("王小明", 0.1)

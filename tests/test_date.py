"""日期规则的不变式测试。

F: space/sep(分隔符归一)/noise/abbrev(补缺零)/typo(数字形近) 五类代表性用例；
   不可恢复缩写（缺年 / 年月）不猜；范围闸门；值已规范 0.95 档（TASK-015）；
   置信度 ∈ [0,1]；date 已注册且其余五字段行为不受影响
R: src/zhclean/rules/date.py、src/zhclean/rules/__init__.py
A: uv run --project . pytest tests/ -q
S: 只测规则与注册表，不测评测管线内部（那在 test_evaluate.py）

口径（TASK-019 §2.5）：规范形态唯一 = ISO `YYYY-MM-DD`（年 1970–2026、月 01–12、日 01–31）。
- 只补「缺零」（`2026-1-5` → `2026-01-05`，无损格式归一）；
- **缺年（`1-5`）与年月（`2026-10`）是信息缺失 ⇒ 不猜，原样低置信**（本字段 abbrev 天花板）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import zhclean` 不依赖 pytest 的启动方式

import zhclean  # noqa: E402

VALID = "2026-10-06"  # 下面用例的真值

# ---------- space：去掉串内所有空白（半角 / 全角） ----------

@pytest.mark.parametrize("dirty", ["2026-10-0 6", "2026-10　-06", " 2026-10-06 ", "2026- 10-06"])
def test_space_stripped(dirty):
    assert zhclean.normalize(dirty, "date") == VALID


# ---------- sep：分隔符归一（/ . ／ ．） ----------

@pytest.mark.parametrize("dirty", ["2026/10/06", "2026.10.06", "2026／10／06", "2026．10．06"])
def test_separators_unified(dirty):
    assert zhclean.normalize(dirty, "date") == VALID


# ---------- noise：去前缀标签 / 尾部括号备注 / 尾随标点 ----------

@pytest.mark.parametrize("dirty", ["日期：2026-10-06", "日期:2026-10-06",
                                   "2026-10-06（录入日期）", "2026-10-06（生效日）", "2026-10-06。"])
def test_noise_stripped(dirty):
    assert zhclean.normalize(dirty, "date") == VALID


# ---------- abbrev：补缺零（无损格式归一） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("2026-1-5", "2026-01-05"),
    ("2026-10-6", "2026-10-06"),
    ("2026-1-06", "2026-01-06"),
    ("2026-01-5", "2026-01-05"),
])
def test_missing_leading_zero_padded(dirty, expected):
    assert zhclean.normalize(dirty, "date") == expected


# ---------- abbrev 不可恢复：缺年 / 年月 ⇒ 不猜，原样低置信 ----------

@pytest.mark.parametrize("dirty", ["2026-10", "1-5", "10-06", "2026"])
def test_unrecoverable_abbrev_stays_untouched(dirty):
    assert zhclean.normalize_with_confidence(dirty, "date") == (dirty, 0.1)


# ---------- typo：数字形近字母修复 ----------

@pytest.mark.parametrize("dirty,expected", [
    ("2026-10-0T", "2026-10-07"),   # T → 7
    ("2026-l0-06", "2026-10-06"),   # l → 1
    ("2026-1O-06", "2026-10-06"),   # O → 0
    ("ZO26-10-06", "2026-10-06"),   # Z → 2
    ("2026-10-0Z", "2026-10-02"),   # Z → 2
])
def test_confusable_letters_repaired(dirty, expected):
    assert zhclean.normalize(dirty, "date") == expected


def test_repair_confidence_is_lower_than_structural():
    value, conf = zhclean.normalize_with_confidence("2026-1O-06", "date")
    assert value == VALID and 0.0 < conf < 0.9


# ---------- 结构清洗命中即高置信（含补缺零） ----------

@pytest.mark.parametrize("dirty", ["2026/10/06", "日期：2026-10-06", "2026-10-0 6", "2026-1-5"])
def test_structural_hit_is_high_confidence(dirty):
    _, conf = zhclean.normalize_with_confidence(dirty, "date")
    assert conf == pytest.approx(0.9)


# ---------- 值已规范：合法 ISO 无改动 ⇒ 0.95（TASK-015 拆档） ----------

@pytest.mark.parametrize("value", ["2026-10-06", "1970-01-01", "2026-12-31"])
def test_clean_value_untouched_and_high_confidence(value):
    assert zhclean.normalize_with_confidence(value, "date") == (value, 0.95)


# ---------- 范围闸门：越界不返回 ----------

@pytest.mark.parametrize("dirty", [
    "2019-13-01",   # 月 13
    "2026-10-32",   # 日 32
    "1969-01-01",   # 年 < 1970
    "2027-01-01",   # 年 > 2026
])
def test_out_of_range_stays_untouched(dirty):
    assert zhclean.normalize_with_confidence(dirty, "date") == (dirty, 0.1)


# ---------- 置信度必须落在 [0, 1] ----------

@pytest.mark.parametrize("value", ["2026/10/06", VALID, "2026-1O-06", "2026-1-5", "2026-10", "", "x"])
def test_confidence_in_range(value):
    _, conf = zhclean.normalize_with_confidence(value, "date")
    assert 0.0 <= conf <= 1.0


# ---------- 注册表：date 已注册，且其余五字段不受影响（六字段回归护栏） ----------

def test_date_registered():
    from zhclean.rules import DISPATCH
    assert "date" in DISPATCH and callable(DISPATCH["date"])


def test_other_fields_unaffected():
    # 回归：注册 date 后，已有五类的代表用例行为不变
    assert zhclean.normalize("王 小明", "person") == "王小明"
    assert zhclean.normalize("157-4552-4079", "phone") == "15745524079"
    assert zhclean.normalize("公司名称：嘉兴数联贸易集团有限公司", "company") == "嘉兴数联贸易集团有限公司"
    assert zhclean.normalize("广东省 深圳市 南山区人民路1号", "address") == "广东省深圳市南山区人民路1号"
    assert zhclean.normalize("12 800元", "amount") == "12800元"

"""金额规则的不变式测试。

F: space/sep(千分位)/noise/abbrev(万元展开)/typo(数字形近) 五类代表性用例；修坏不返回；
   值已规范 0.95 档（TASK-015）；置信度 ∈ [0,1]；amount 已注册且其余五字段行为不受影响
R: src/zhclean/rules/amount.py、src/zhclean/rules/__init__.py
A: uv run --project . pytest tests/ -q
S: 只测规则与注册表，不测评测管线内部（那在 test_evaluate.py）

口径（TASK-019 §2.5）：规范形态唯一 = `<数值>元`（纯数字，**不含千分位逗号**）。
→ `12,800元` 与 `12800元` 收敛到 `12800元`；万元记法展开为元。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import zhclean` 不依赖 pytest 的启动方式

import zhclean  # noqa: E402

VALID = "12800元"  # 下面用例的真值

# ---------- space：去掉串内所有空白（半角 / 全角） ----------

@pytest.mark.parametrize("dirty", ["12 800元", "128　00元", "1 2 8 0 0 元", " 12800元 ", "12800 元"])
def test_space_stripped(dirty):
    assert zhclean.normalize(dirty, "amount") == VALID


# ---------- sep：千分位归一——逗号（半角 / 全角 / 乱插）一律去掉 ----------

@pytest.mark.parametrize("dirty", ["12,800元", "12，800元", "1,2,800元", "128,00元", "1280,0元"])
def test_thousands_separators_removed(dirty):
    assert zhclean.normalize(dirty, "amount") == VALID


# ---------- noise：去前缀标签 / 尾部括号备注 / 尾随标点 ----------

@pytest.mark.parametrize("dirty", ["金额：12800元", "金额:12800元", "费用：12800元",
                                   "12800元（含税）", "12800元（未税）", "12800元。"])
def test_noise_stripped(dirty):
    assert zhclean.normalize(dirty, "amount") == VALID


# ---------- abbrev：万元记法展开（×10000，保留 4 位小数去尾零） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("1.28万元", "12800元"),
    ("1万元", "10000元"),
    ("0.5万元", "5000元"),
    ("2.0001万元", "20001元"),
])
def test_wan_expanded(dirty, expected):
    assert zhclean.normalize(dirty, "amount") == expected


# ---------- typo：数字形近字母修复（O→0 l→1 Z→2 …，OCR 常见） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("1280O元", "12800元"),   # O → 0
    ("l2800元", "12800元"),   # l → 1
    ("12B00元", "12800元"),   # B → 8
    ("12qOO元", "12900元"),   # q → 9、O → 0
    ("Z800元", "2800元"),     # Z → 2
])
def test_confusable_letters_repaired(dirty, expected):
    assert zhclean.normalize(dirty, "amount") == expected


def test_repair_confidence_is_lower_than_structural():
    value, conf = zhclean.normalize_with_confidence("1280O元", "amount")
    assert value == VALID and 0.0 < conf < 0.9


# ---------- 结构清洗命中即高置信 ----------

@pytest.mark.parametrize("dirty", ["12 800元", "12,800元", "金额：12800元", "12800元（含税）"])
def test_structural_hit_is_high_confidence(dirty):
    value, conf = zhclean.normalize_with_confidence(dirty, "amount")
    assert value == VALID
    assert conf == pytest.approx(0.9)


# ---------- 值已规范：无法改动 ⇒ 0.95（TASK-015 拆档） ----------

@pytest.mark.parametrize("value", ["12800元", "0.5元", "12800.50元", "1元"])
def test_clean_value_untouched_and_high_confidence(value):
    assert zhclean.normalize_with_confidence(value, "amount") == (value, 0.95)


# ---------- 修坏不返回：闸门 `^\d+(\.\d+)?元$` 挡在门外 ----------

@pytest.mark.parametrize("dirty", [
    "12800元整",    # 多余字符「整」
    "12元3角",      # 多单位
    "1280O元整",    # 修完仍不过闸门
    "约12800元",    # 前缀「约」不在噪声表里
    "",             # 空串
    "abc",          # 非数字
])
def test_invalid_stays_untouched(dirty):
    assert zhclean.normalize_with_confidence(dirty, "amount") == (dirty, 0.1)


# ---------- 置信度必须落在 [0, 1] ----------

@pytest.mark.parametrize("value", ["12 800元", VALID, "1280O元", "1.28万元", "12800元整", "", "x"])
def test_confidence_in_range(value):
    _, conf = zhclean.normalize_with_confidence(value, "amount")
    assert 0.0 <= conf <= 1.0


# ---------- 注册表：amount 已注册，且其余五字段不受影响（六字段回归护栏） ----------

def test_amount_registered():
    from zhclean.rules import DISPATCH
    assert "amount" in DISPATCH and callable(DISPATCH["amount"])


def test_other_fields_unaffected():
    # 回归：注册 amount 后，已有五类的代表用例行为不变
    assert zhclean.normalize("王 小明", "person") == "王小明"
    assert zhclean.normalize("157-4552-4079", "phone") == "15745524079"
    assert zhclean.normalize("公司名称：嘉兴数联贸易集团有限公司", "company") == "嘉兴数联贸易集团有限公司"
    assert zhclean.normalize("广东省 深圳市 南山区人民路1号", "address") == "广东省深圳市南山区人民路1号"
    assert zhclean.normalize("2024.10.18", "date") == "2024-10-18"

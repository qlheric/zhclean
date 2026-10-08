"""邮箱规则的不变式测试。

F: space/noise/typo 三类代表性用例；形近还原**双向**（数字→字母 / 字母→数字）；
   sep 与 abbrev 按「不猜」原样返回；闸门；值已规范 0.95 档；置信度 ∈ [0,1]；
   email 已注册；**八字段回归护栏**（老六类各 1 条代表用例不受影响）
R: src/zhclean/rules/email.py、src/zhclean/rules/__init__.py
A: uv run --project . pytest tests/ -q
S: 只测规则与注册表，不测评测管线内部（那在 test_evaluate.py）；不读 benchmark 生成器

用例取自 train 真实扰动（`benchmarks/dirty/email.jsonl`，只读 train 部分）。
⚠ 断言的是**本模块的设计口径**：user 段内部的错字、sep、abbrev 都**故意不猜**
  （见 rules/email.py 模块头）——这些用例期望「原样返回」，不是「能修对」。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import zhclean` 不依赖 pytest 的启动方式

import zhclean  # noqa: E402

# 三个干净邮箱（train 真实值）
CLEAN = "a232zxb3s@139.com"
CLEAN2 = "um7dy@hotmail.com"
CLEAN3 = "w0avx@126.com"        # user 里本就有 `0`（合法数字）—— 用于验证「不误改」


# ---------- space：去掉串内所有空白（@ 前后） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("a232zxb3s@ 139.com", CLEAN),
    ("a232zxb3s @139.com", CLEAN),
    ("um7dy@ hotmail.com", CLEAN2),
    ("w0avx@ 126.com", CLEAN3),
])
def test_space_stripped(dirty, expected):
    assert zhclean.normalize(dirty, "email") == expected


# ---------- noise：去前后缀标签（大小写不敏感）/ 尾随标点 ----------

@pytest.mark.parametrize("dirty,expected", [
    ("Email:a232zxb3s@139.com", CLEAN),
    ("E-mail:a232zxb3s@139.com", CLEAN),
    ("eMAIL：a232zxb3s@139.com", CLEAN),
    ("邮箱:um7dy@hotmail.com", CLEAN2),
    ("邮箱：w0avx@126.com", CLEAN3),
    ("a232zxb3s@139.com。", CLEAN),
])
def test_noise_stripped(dirty, expected):
    assert zhclean.normalize(dirty, "email") == expected


# ---------- 结构层命中即 0.9（无损、可验证） ----------

@pytest.mark.parametrize("dirty", ["a232zxb3s@ 139.com", "邮箱:um7dy@hotmail.com"])
def test_structural_hit_is_high_confidence(dirty):
    _, conf = zhclean.normalize_with_confidence(dirty, "email")
    assert conf == pytest.approx(0.9)


# ---------- typo：形近还原，**双向**（只修位置本身可判定的字符） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("um7dy@h0tmail.com", CLEAN2),      # 域名主体：0 → o（数字→字母）
    ("w0avx@l26.com", CLEAN3),          # 域名主体：l → 1（字母→数字）
    ("a232zxb3s@139.c0m", CLEAN),       # TLD：0 → o（TLD 必是字母）
    ("1abc123@139.com", "labc123@139.com"),  # user 首位：1 → l（user 必字母开头）
])
def test_confusable_repaired_both_directions(dirty, expected):
    assert zhclean.normalize(dirty, "email") == expected


def test_repair_confidence_is_infer_band():
    value, conf = zhclean.normalize_with_confidence("um7dy@h0tmail.com", "email")
    assert value == CLEAN2 and 0.0 < conf < 0.9


# ---------- 不猜之一：user 段内部的错字（形态闸门管不到，无从判定） ----------

@pytest.mark.parametrize("dirty", [
    "a232zx83s@139.com",   # user 内部 8 ↔ b，真值 CLEAN，但无法判定 ⇒ 不猜
    "w0avx@126.com",       # 干净值：user 里的 `0` 也可能是真数字 ⇒ 绝不能改
])
def test_user_internal_typo_not_guessed(dirty):
    assert zhclean.normalize(dirty, "email") == dirty


# ---------- 不猜之二：sep（多余下划线 / 点，与合法 `a.b` 无从区分） ----------

@pytest.mark.parametrize("dirty", [
    "a232zx_b3s@139.com",
    "um7d.y@hotmail.com",
    "w_0avx@126.com",
])
def test_sep_not_guessed(dirty):
    assert zhclean.normalize(dirty, "email") == dirty


# ---------- 不猜之三：abbrev（信息已丢，不可恢复） ----------

@pytest.mark.parametrize("dirty", [
    "a232zxb3s@139.co",    # 去 TLD 末位
    "um7dy@hotmail",       # 整个 TLD 没了
])
def test_abbrev_not_guessed(dirty):
    assert zhclean.normalize(dirty, "email") == dirty


# ---------- 闸门：不像邮箱的原样低置信 ----------

@pytest.mark.parametrize("dirty", ["", "not-an-email", "a@b", "@x.com", "a@@b.com"])
def test_gate_rejects_non_email(dirty):
    assert zhclean.normalize_with_confidence(dirty, "email") == (dirty, 0.1)


# ---------- 值已规范：过闸门且无改动 ⇒ 0.95（TASK-015 拆档） ----------

@pytest.mark.parametrize("value", [CLEAN, CLEAN2, CLEAN3])
def test_clean_value_untouched_and_high_confidence(value):
    assert zhclean.normalize_with_confidence(value, "email") == (value, 0.95)


# ---------- 置信度必须落在 [0, 1] ----------

@pytest.mark.parametrize("value", ["a232zxb3s@ 139.com", CLEAN, "um7dy@h0tmail.com",
                                   "a232zxb3s@139.co", "", "邮箱"])
def test_confidence_in_range(value):
    _, conf = zhclean.normalize_with_confidence(value, "email")
    assert 0.0 <= conf <= 1.0


# ---------- 注册表 + 八字段回归护栏 ----------

def test_email_registered():
    from zhclean.rules import DISPATCH
    assert "email" in DISPATCH and callable(DISPATCH["email"])


def test_all_eight_fields_registered():
    from zhclean.rules import DISPATCH
    assert set(DISPATCH) == {"person", "address", "phone", "company",
                             "amount", "date", "idcard", "email"}


def test_old_six_fields_unaffected():
    """注册 idcard/email 后，老六类字段行为逐字不变（各 1 条代表用例）。"""
    assert zhclean.normalize("王 小明", "person") == "王小明"
    assert zhclean.normalize("广东省深圳市南山区", "address") == "广东省深圳市南山区"
    assert zhclean.normalize("13800000000", "phone") == "13800000000"
    assert zhclean.normalize("阿里巴巴（中国）有限公司", "company") == "阿里巴巴（中国）有限公司"
    assert zhclean.normalize("12,345元", "amount") == "12345元"
    assert zhclean.normalize("2020-1-2", "date") == "2020-01-02"

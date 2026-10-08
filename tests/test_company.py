"""公司名规则的不变式测试。

F: space/sep/noise 三类结构清洗代表用例；组织形式缩写补全（可猜的）；不可靠 abbrev 不猜；
   通用错字修复；值已规范 0.95 档（TASK-015）；置信度 ∈ [0,1]；company 已注册且 person/phone 不受影响
R: src/zhclean/rules/company.py、src/zhclean/rules/__init__.py
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

# 一个规范公司名（城市 焦作 + 字号 嘉禾 + 行业 智能 + 组织形式 有限责任公司），下面用例的真值
VALID = "焦作嘉禾智能有限责任公司"
VALID_GROUP = "焦作嘉禾集团有限公司"      # 形式：…集团有限公司
VALID_CORP = "焦作嘉禾股份有限公司"       # 形式：…股份有限公司
VALID_TECH = "焦作嘉禾科技有限责任公司"    # 行业词「科技」型

# ---------- space：去掉串内所有空白（半角 / 全角） ----------

@pytest.mark.parametrize("dirty", ["焦作嘉禾智能 有限责任公司", "焦作　嘉禾智能有限责任公司",
                                   "焦 作 嘉 禾 智 能 有 限 责 任 公 司", " 焦作嘉禾智能有限责任公司 "])
def test_space_stripped(dirty):
    assert zhclean.normalize(dirty, "company") == VALID


# ---------- sep：去掉分隔符（城市/字号/行业/后缀之间） ----------

@pytest.mark.parametrize("dirty", ["焦作-嘉禾-智能-有限责任公司", "焦作·嘉禾·智能·有限责任公司",
                                   "焦作|嘉禾|智能|有限责任公司", "焦作／嘉禾／智能／有限责任公司",
                                   "焦作，嘉禾，智能，有限责任公司"])
def test_sep_stripped(dirty):
    assert zhclean.normalize(dirty, "company") == VALID


# ---------- noise：去前缀标签 / 尾部括号备注 / 尾随标点 ----------

@pytest.mark.parametrize("dirty", ["单位：焦作嘉禾智能有限责任公司", "公司名称:焦作嘉禾智能有限责任公司",
                                   "焦作嘉禾智能有限责任公司（总部）", "焦作嘉禾智能有限责任公司（分公司）",
                                   "焦作嘉禾智能有限责任公司（原单位）", "焦作嘉禾智能有限责任公司。"])
def test_noise_stripped(dirty):
    assert zhclean.normalize(dirty, "company") == VALID


# ---------- 结构清洗命中即高置信（0.9） ----------

@pytest.mark.parametrize("dirty", ["焦作嘉禾智能 有限责任公司", "焦作-嘉禾-智能-有限责任公司",
                                   "单位：焦作嘉禾智能有限责任公司", "焦作嘉禾智能有限责任公司。"])
def test_structural_hit_is_high_confidence(dirty):
    value, conf = zhclean.normalize_with_confidence(dirty, "company")
    assert value == VALID
    assert conf == pytest.approx(0.9)


# ---------- abbrev：只补「无歧义可猜」的组织形式缩写 ----------

def test_ambiguous_free_abbrev_expanded():
    # 「股份公司」无歧义地只对应「股份有限公司」⇒ 补全，推断档 0.7
    value, conf = zhclean.normalize_with_confidence("焦作嘉禾智能股份公司", "company")
    assert value == "焦作嘉禾智能股份有限公司"
    assert conf == pytest.approx(0.7)


@pytest.mark.parametrize("dirty", [
    "嘉禾智能有限责任公司",    # 去城市（不可恢复：无从知道原城市）
    "焦作嘉禾智能有限公司",    # 有限责任 → 有限（本身合法，无从判断原本是不是有限责任）
])
def test_unreliable_abbrev_not_guessed(dirty):
    # 不猜：值原样返回（仍成立）；置信度 0.95 = 「像合法公司名」而非「处理不了」。
    # ⚠ 已知语义阴影（TASK-015 契约的副作用，见 RESULT-015 §5）：这两条真值其实 ≠ 原值
    #    （原值含城市 / 含「责任」），却因 _looks_like_company 只看「以组织形式全称结尾」而落 0.95。
    assert zhclean.normalize_with_confidence(dirty, "company") == (dirty, 0.95)


def test_unrecoverable_abbrev_without_org_form_stays_low():
    # 去组织形式**整段** ⇒ 不像公司名 ⇒ 仍是 0.1 —— 这条与 0.95 分得干净
    dirty = "焦作嘉禾智能"
    assert zhclean.normalize_with_confidence(dirty, "company") == (dirty, 0.1)


# ---------- typo：公司名必现字 / 行业词的通用错字修复 ----------
# 生成器原表的错字形式（正→错）；这里按通用知识收全，不针对测试集裁剪。

@pytest.mark.parametrize("dirty,expected", [
    ("焦作嘉禾智能有限责任工司", VALID),   # 工 → 公
    ("焦作嘉禾智能有限责任公词", VALID),   # 词 → 司
    ("焦作嘉禾智能友限责任公司", VALID),   # 友 → 有
    ("焦作嘉禾智能有线责任公司", VALID),   # 线 → 限
    ("焦作嘉禾智能有限则任公司", VALID),   # 则 → 责
    ("焦作嘉禾股分有限公司", VALID_CORP),  # 分 → 份
    ("焦作嘉禾积团有限公司", VALID_GROUP),  # 积 → 集
    ("焦作嘉禾集困有限公司", VALID_GROUP),  # 困 → 团
    ("焦作嘉禾志能有限责任公司", VALID),   # 志 → 智（行业词位置）
    ("焦作嘉禾科记有限责任公司", VALID_TECH),  # 记 → 技（行业词位置）
    ("焦作嘉禾芯息有限责任公司", "焦作嘉禾信息有限责任公司"),  # 芯 → 信
])
def test_typos_repaired(dirty, expected):
    assert zhclean.normalize(dirty, "company") == expected


def test_typo_confidence_is_infer_level():
    value, conf = zhclean.normalize_with_confidence("焦作嘉禾志能有限责任公司", "company")
    assert value == VALID and conf == pytest.approx(0.7)


# ---------- 多收的通用条目也能修（证明表不是照抄测试集） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("测试公伺", "测试公司"),          # 伺 → 司（生成器没有这对）
    ("测试有限泽任公司", "测试有限责任公司"),  # 泽 → 责（生成器没有这对）
])
def test_extra_generic_typos_repaired(dirty, expected):
    assert zhclean.normalize(dirty, "company") == expected


# ---------- 闸门：洗出来「不像公司名」就宁可原样返回 ----------

def test_cleaning_to_non_company_returns_original():
    # 去标签后剩下「你好」，不是公司名 ⇒ 不返回半成品，原样低置信
    assert zhclean.normalize_with_confidence("单位：你好", "company") == ("单位：你好", 0.1)


# ---------- 值已规范：本就规范的值无改动 ⇒ 0.95（TASK-015 拆档；TASK-004 台账里的待细化项） ----------

def test_clean_value_untouched_and_high_confidence():
    # TASK-015：已规范值不再报 0.1，改报 0.95「值已规范」。
    for v in (VALID, VALID_GROUP, VALID_CORP, VALID_TECH):
        assert zhclean.normalize_with_confidence(v, "company") == (v, 0.95)


# ---------- 置信度必须落在 [0, 1] ----------

@pytest.mark.parametrize("value", ["焦作嘉禾智能 有限责任公司", VALID, "焦作嘉禾智能股份公司",
                                   "焦作嘉禾志能有限责任公司", "单位：你好", "", "x", "测试公伺"])
def test_confidence_in_range(value):
    _, conf = zhclean.normalize_with_confidence(value, "company")
    assert 0.0 <= conf <= 1.0


# ---------- 注册表：company 已注册，且 person / phone 行为不受影响（回归护栏） ----------

def test_company_registered():
    from zhclean.rules import DISPATCH
    assert "company" in DISPATCH and callable(DISPATCH["company"])


def test_person_unaffected_by_company():
    # 回归：注册 company 后人名清洗行为不变（TASK-003 的三类结构清洗仍全对）
    assert zhclean.normalize("王 小明", "person") == "王小明"
    assert zhclean.normalize("王·小明", "person") == "王小明"
    assert zhclean.normalize("姓名：王小明", "person") == "王小明"
    # 反向：公司名不会被当人名（person handler 仍归属 person 字段）
    assert zhclean.normalize_with_confidence(VALID, "person") == (VALID, 0.1)


def test_phone_unaffected_by_company():
    # 回归：注册 company 后电话清洗行为不变（TASK-004 的结构清洗仍全对）
    assert zhclean.normalize("157-4552-4079", "phone") == "15745524079"
    assert zhclean.normalize("电话：15745524079", "phone") == "15745524079"
    assert zhclean.normalize("8615745524079", "phone") == "15745524079"
    # 反向：电话号码不会被当公司名（company handler 仍归属 company 字段）
    assert zhclean.normalize_with_confidence("15745524079", "company") == ("15745524079", 0.1)

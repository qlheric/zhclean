"""人名规则 + normalize 接口的不变式测试。

F: space/sep/noise 三类代表性用例；typo 通用表（错→正）；abbrev 不猜（原值返回）；
   值已规范 0.95 档（TASK-015）；未知 field 恒等；confidence ∈ [0,1]；
   evaluate 的 rules 键存在且可跑
R: src/zhclean/rules/person.py、src/zhclean/tools/normalize.py、benchmarks/evaluate.py
A: uv run --project . pytest tests/ -q
S: 只测规则与接口，不测评测管线内部（那在 test_evaluate.py）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import benchmarks` 不依赖 pytest 的启动方式

import zhclean  # noqa: E402
from benchmarks import evaluate as ev  # noqa: E402

# ---------- space：去掉串内所有空白（半角 / 全角） ----------

@pytest.mark.parametrize("dirty", ["王 小明", "王　小明", "王 小 明", " 王小明 "])
def test_space_stripped(dirty):
    assert zhclean.normalize(dirty, "person") == "王小明"


# ---------- sep：去掉分隔符 ----------

@pytest.mark.parametrize("dirty", ["王-小明", "王·小明", "王|小明", "王／小明", "王，小明"])
def test_sep_stripped(dirty):
    assert zhclean.normalize(dirty, "person") == "王小明"


# ---------- noise：去前缀标签 / 后缀敬称 / 尾随标点 / 括号备注 ----------

@pytest.mark.parametrize("dirty", ["姓名：王小明", "名字:王小明", "王小明先生", "王小明女士",
                                   "王小明老师", "王小明。", "王小明（本人）"])
def test_noise_stripped(dirty):
    assert zhclean.normalize(dirty, "person") == "王小明"


# ---------- 结构清洗三类的置信度：命中即高置信 ----------

@pytest.mark.parametrize("dirty", ["王 小明", "王·小明", "姓名：王小明", "王小明女士"])
def test_structural_hit_is_high_confidence(dirty):
    value, conf = zhclean.normalize_with_confidence(dirty, "person")
    assert value == "王小明"
    assert conf == pytest.approx(0.9)


# ---------- typo：通用同音/形近字表（错 → 正） ----------

@pytest.mark.parametrize("dirty,expected", [
    ("王净", "王静"), ("李至钢", "李志刚"), ("张庭", "张婷"), ("王同", "王童"),
])
def test_typo_general_table(dirty, expected):
    assert zhclean.normalize(dirty, "person") == expected


def test_typo_confidence_is_lower_than_structural():
    value, conf = zhclean.normalize_with_confidence("王净", "person")
    assert value == "王静" and 0.0 < conf < 0.9


# ---------- 双向有歧义的字不许改写（防误伤本来正确的名字） ----------

@pytest.mark.parametrize("name", ["王佳明", "王宇豪", "张丽华", "李君豪", "赵雨欣"])
def test_ambiguous_chars_left_alone(name):
    assert zhclean.normalize(name, "person") == name


# ---------- abbrev：缺字无法可靠恢复 → 不猜，原值返回 ----------

@pytest.mark.parametrize("dirty", ["王明", "李华", "范童"])
def test_abbrev_not_guessed(dirty):
    # 不猜：值原样返回（仍成立）；置信度 0.95 = 「像合法人名」而非「处理不了」。
    # ⚠ 已知语义阴影（TASK-015 契约的副作用，见 RESULT-015 §5）：abbrev 缺字后的串
    #    （「王明」来自「王小明」）与真·两字名**无法区分**，故也落 0.95（过誉）。
    assert zhclean.normalize_with_confidence(dirty, "person") == (dirty, 0.95)


# ---------- 未知 field / 未注册 field：恒等 ----------

def test_unknown_field_identity():
    assert zhclean.normalize("随便什么", "不存在的字段") == "随便什么"
    assert zhclean.normalize_with_confidence("随便什么", "不存在的字段") == ("随便什么", 0.1)


def test_unregistered_known_field_identity():
    # 四个字段都已注册（TASK-004/005/006）；这里用「本来就合法」的值，走恒等路径（值不变）
    assert zhclean.normalize("13800000000", "phone") == "13800000000"
    assert zhclean.normalize("广东省深圳市南山区", "address") == "广东省深圳市南山区"


# ---------- 置信度必须落在 [0, 1] ----------

@pytest.mark.parametrize("value,field", [
    ("王 小明", "person"), ("王明", "person"), ("王净", "person"),
    ("", "person"), ("x", "不存在的字段"), ("13800000000", "phone"),
])
def test_confidence_in_range(value, field):
    _, conf = zhclean.normalize_with_confidence(value, field)
    assert 0.0 <= conf <= 1.0


# ---------- 注册表 ----------

def test_dispatch_registry_has_person():
    from zhclean.rules import DISPATCH
    assert "person" in DISPATCH and callable(DISPATCH["person"])


# ---------- 评测接入：IMPLS 里 rules 键存在且可跑 ----------

def test_evaluate_rules_impl_is_wired():
    assert "rules" in ev.IMPLS
    row = {"id": "person-0001", "field": "person", "value": "姓名：王 小明",
           "truth": "王小明", "perturbation": "noise", "split": "heldout"}
    assert ev.IMPLS["rules"](row) == "王小明"

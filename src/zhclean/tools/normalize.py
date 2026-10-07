"""normalize 工具：字段类型 + 脏值 → 规范值 + 置信度（Tool Design #3 件功夫）。

F: 规则打底 80% 确定性清洗；schema 显式；置信度必填
R: rules/*（六类规则词典）
A: 被 loop.py（act 首选）调用
S: 置信度必填；规则失败可回退 LLM，但结果结构不变

接口契约（脑定）：
- normalize(value, field) -> str         主接口（评测接入点）
- normalize_with_confidence(value, field) -> (规范值, 置信度 0~1)
  未知 field 或规则无法处理时返回原值，不猜（置信度 0.1）。
"""

from __future__ import annotations

from ..rules import normalize_field

# 规则无法处理时的兜底置信度（与 rules/person.py 的 CONF_NONE 同义）
CONF_FALLBACK = 0.1


def normalize_with_confidence(value: str, field: str) -> tuple[str, float]:
    """脏值 + 字段类型 → (规范值, 置信度)。未注册字段 / 非字符串 → 原样返回。"""
    if not isinstance(value, str):
        return value, 0.0
    return normalize_field(value, field)


def normalize(value: str, field: str) -> str:
    """主接口：只要规范值。置信度用 normalize_with_confidence 取。"""
    return normalize_with_confidence(value, field)[0]

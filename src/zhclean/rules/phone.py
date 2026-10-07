"""电话规则词典与清洗函数（结构清洗打底，数字形近修复兜底）。

F: 电话脏值 → 规范值 + 置信度；去国家码/空白/分隔符/前后缀噪声 + 数字形近字母修复
R: rules/__init__.py（注册表 DISPATCH）
A: zhclean.normalize(value, "phone")
S: 形近表取自通用 OCR 知识，不得针对测试扰动模式调参（留出集纪律）

置信度阶梯（沿用 person 档位）：
    0.9  结构清洗命中（去国家码 / 空白 / 分隔符 / 前后缀）—— 无损、可验证
    0.7  数字形近修复命中（O→0 之类）—— 有依据，但本质仍是推断
    0.1  什么都没做（无证据）→ 原样返回，交给上层（LLM / HITL）

设计取舍（与 person 的关键差异，写清楚免得下一个人照抄错）：
person 是「结构层命中即返回、不叠加推断层」，因为人名洗出来没有客观判据。
电话号码有客观判据 —— **11 位、1[3-9] 开头**。故这里改成单管道 + 校验闸门：
结构清洗后若已合法就直接返回（0.9）；不合法才上推断层修形近字母，修完**再过一次校验**，
还不合法就原样低置信返回。校验把「推断修坏」的风险挡在门外 —— 修坏了根本不返回。
"""

from __future__ import annotations

import re

from .common import (
    CONF_INFER,
    CONF_NONE,
    CONF_STRUCTURAL,
    apply_table,
    strip_noise,
    strip_ws_sep,
)

# ============================================================ 词典

# 中国大陆手机号：11 位、1[3-9] 开头（校验闸门，判据见模块头）
_CN_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")

# 数字形近字母（OCR / 手写常见）：字母 → 数字。
# 只收通用混淆，且**入库前必须过校验**才返回，故宁多收一点也不会改坏正确号码。
# 注：不收 `|` —— 它在「分隔符」与「形近 1」两义之间冲突，而 `_strip_ws_sep` 先行、
#     必然把它当分隔符删掉，收在这里是永不触达的死条目。
CONFUSABLE_TO_DIGIT: dict[str, str] = {
    "O": "0", "o": "0", "D": "0",
    "l": "1", "I": "1", "i": "1",
    "Z": "2", "z": "2",
    "E": "3", "e": "3",
    "S": "5", "s": "5",
    "B": "8", "b": "8",
}

# 国家码前缀（剥掉后才可能是 11 位国内号）。**只在剩余恰为 11 位时才剥**，避免误伤号段。
_COUNTRY_CODES = ("0086", "086", "86")

# 形近表是「错 → 正」，逐字直替；结构清洗 / 置信度档位在 rules/common.py（四字段共用）

# ============================================================ 内部步骤


def _is_valid(digits: str) -> bool:
    """是否像一个中国大陆手机号（11 位、1[3-9] 开头）。校验闸门。"""
    return bool(_CN_MOBILE_RE.match(digits))


def _lstrip_plus(s: str) -> tuple[str, bool]:
    """去掉国家码常带的前导 `+`（`+86`）。返回 (结果, 是否改动)。"""
    out = s.lstrip("+")
    return out, out != s


def _strip_country(s: str) -> tuple[str, bool]:
    """剥国家码前缀；**仅在剩余恰为 11 位时剥**。返回 (结果, 是否改动)。"""
    for cc in _COUNTRY_CODES:
        if s.startswith(cc) and len(s) - len(cc) == 11:
            return s[len(cc):], True
    return s, False

# ============================================================ 主入口


def normalize_phone(value: str) -> tuple[str, float]:
    """电话 → (规范值, 置信度)。认不出 / 修完仍不合法时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。产物必须过校验才算命中。
    out, noise_hit = strip_noise(value)
    out, sep_hit = strip_ws_sep(out)
    out, plus_hit = _lstrip_plus(out)
    out, cc_hit = _strip_country(out)
    if (noise_hit or sep_hit or plus_hit or cc_hit) and _is_valid(out):
        return out, CONF_STRUCTURAL

    # 第 2 层：数字形近修复（推断）。结构清洗后仍不合法时才试，修完再过校验。
    fixed, typo_hit = apply_table(out, CONFUSABLE_TO_DIGIT)
    if typo_hit and _is_valid(fixed):
        return fixed, CONF_INFER

    # 没证据（含缺位、位数不对、修完仍不合法）：原样返回，交上层。
    return value, CONF_NONE

"""金额规则：结构清洗 + 万元展开 + 数字形近修复（单管道 + 校验闸门）。

F: 金额脏值 → (规范值, 置信度)；去空白 / 去前后缀噪声 / 去千分位逗号 + 万元→元展开 + 数字形近字母修复
R: rules/__init__.py（注册表 DISPATCH）
A: zhclean.normalize(value, "amount")
S: 规范形态唯一（`<数值>元`，纯数字无逗号）；任何一步不过闸门都原样返回，不猜。留出集纪律。

置信度阶梯（TASK-015 拆档：0.95 与 0.1 语义互斥）：
    0.95 值已规范（本就匹配 `<数值>元`）⇒ 无需改动
    0.9  结构清洗命中（去空白 / 去千分位逗号 / 去前后缀噪声）—— 无损、可验证
    0.7  推断命中（万元展开 / 数字形近修复）—— 有依据，但本质仍是推断
    0.1  认不出 / 修完不过闸门（含缺位、多单位、乱七八糟）→ 原样返回，交给上层（LLM / HITL）

设计取舍（与 phone / person 的关系，写清楚免得下一个人照抄错）：
- **与 phone 同宗：单管道 + 校验闸门。** 金额有客观判据（`^\\d+(\\.\\d+)?元$`），
  故结构清洗 / 推断修完都**必须过闸门**才采纳 —— 修坏了根本不返回（对齐 phone 的 `_is_valid`）。
- **与 person 不同：** person 结构层命中即返回、不叠加推断（人名无客观判据）；金额可叠加，
  因为闸门把「推断修坏」的风险挡在门外。
- **闸门不含千分位逗号** ⇒ 规范形态是「纯数字 + 元」。故「千分位归一」= **一律去逗号**：
  这不是"多改"，而是把 `12,800.5元` 与 `12800.5元` 两种写法收敛到唯一形态。
  （口径来源：TASK-019 §2.5 的闸门与 sep 规则；与 TASK-018 干净集的分组形态冲突见 RESULT-019 §5。）
"""

from __future__ import annotations

import re

from .common import (
    CONF_CLEAN,
    CONF_INFER,
    CONF_NONE,
    CONF_STRUCTURAL,
    apply_table,
    strip_noise,
)

# ============================================================ 词典与判据

# 校验闸门：纯数字（可带小数）+ 「元」。**不含千分位逗号**（口径见模块头）。
_AMOUNT_RE = re.compile(r"^\d+(\.\d+)?元$")

# 万元记法：`1.28万元`（数值可带小数）。换算口径：×10000。
_WAN_RE = re.compile(r"^(\d+(?:\.\d+)?)万元$")

# 数字形近字母（OCR / 手写常见）：字母 → 数字。口径由 TASK-019 §2.5 给定（DIGIT_TYPOS 的反向）。
# 只在**过闸门**后才返回，故宁多收一点也不会改坏正确金额。
CONFUSABLE_TO_DIGIT: dict[str, str] = {
    "O": "0", "l": "1", "Z": "2", "E": "3", "A": "4",
    "S": "5", "G": "6", "T": "7", "B": "8", "q": "9",
}

# 只去空白（半角 + 全角 U+3000）。**与 phone 的 `strip_ws_sep` 不同**：这里刻意不动逗号，
# 逗号交给下面的 `_COMMA_RE` 单独处理 —— 目的是把「去空白」和「去千分位」两件事分开，
# 便于追溯是哪一步改了值。
_WS_RE = re.compile(r"[\s　]+")
# 千分位逗号：半角 + 全角。一律去掉（口径见模块头）。
_COMMA_RE = re.compile(r"[,，]")

# ============================================================ 内部步骤


def _expand_wan(s: str) -> tuple[str, bool]:
    """万元记法展开为元：`1.28万元` → `12800元`。返回 (结果, 是否改动)。"""
    m = _WAN_RE.match(s)
    if not m:
        return s, False
    n = float(m.group(1)) * 10000
    # 数值 ×10000，保留 4 位小数、去尾零（对齐 TASK-019 §2.5 的换算口径）
    return f"{n:.4f}".rstrip("0").rstrip(".") + "元", True

# ============================================================ 主入口


def normalize_amount(value: str) -> tuple[str, float]:
    """金额 → (规范值, 置信度)。认不出 / 修完仍不过闸门时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。产物必须过闸门才算命中。
    out, noise_hit = strip_noise(value)
    ws_hit = _WS_RE.search(out) is not None
    out = _WS_RE.sub("", out)
    comma_hit = _COMMA_RE.search(out) is not None
    out = _COMMA_RE.sub("", out)
    if (noise_hit or ws_hit or comma_hit) and _AMOUNT_RE.match(out):
        return out, CONF_STRUCTURAL

    # 第 2 层：推断（万元展开 / 数字形近修复）。结构清洗后仍不过闸门时才试，修完再过闸门。
    expanded, wan_hit = _expand_wan(out)
    fixed, typo_hit = apply_table(expanded, CONFUSABLE_TO_DIGIT)
    if typo_hit and _AMOUNT_RE.match(fixed):
        return fixed, CONF_INFER
    if wan_hit and _AMOUNT_RE.match(expanded):
        return expanded, CONF_INFER

    # 第 3 层：没改动，但值本身已规范 ⇒ 「值已规范」（TASK-015）。输出仍是 value，字节不变。
    if _AMOUNT_RE.match(value):
        return value, CONF_CLEAN

    # 没证据（含缺位、多单位、修完仍不过闸门）：原样返回，交上层。
    return value, CONF_NONE

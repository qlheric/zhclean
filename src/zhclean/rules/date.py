"""日期规则：分隔符归一 + 去噪声 + 数字形近修复 + 补缺零（单管道 + 校验闸门）。

F: 日期脏值 → (规范值, 置信度)；`/ . ／` 归一为 `-`，去空白/前后缀噪声，数字形近修复，补缺零
R: rules/__init__.py（注册表 DISPATCH）
A: zhclean.normalize(value, "date")
S: 只补「缺零」这一种可无损还原的缩写；缺年（1-5）、年月（2026-10）不可恢复 ⇒ 原样低置信（不猜）
   规范形态唯一：ISO `YYYY-MM-DD`（年 1970–2026、月 01–12、日 01–31）。留出集纪律。

置信度阶梯（TASK-015 拆档：0.95 与 0.1 语义互斥）：
    0.95 值已规范（本就匹配 `YYYY-MM-DD` 且范围合法）⇒ 无需改动
    0.9  结构清洗命中（去空白 / 分隔符归一 / 去前后缀噪声 / **补缺零**）—— 无损、可验证
    0.7  推断命中（数字形近修复）—— 有依据，但本质仍是推断
    0.1  认不出 / 不可恢复（缺年、年月、越界）→ 原样返回，交给上层（LLM / HITL）

设计取舍（与 phone / person 的关系，写清楚免得下一个人照抄错）：
- **与 phone 同宗：单管道 + 校验闸门。** 日期有客观判据（ISO 形态 + 年/月/日范围），
  故结构清洗 / 推断修完都**必须过闸门**才采纳 —— 修坏了根本不返回。
- **与 person 不同：** person 结构层命中即返回、不叠加推断；日期可叠加，闸门兜底。
- **「补缺零」归结构层（0.9）而非推断层（0.7）**：`2026-1-5` → `2026-01-05` 是**无损**的
  格式归一（补零不改变任何数值信息，也不猜任何缺内容），与「缩写补全」那种要**猜内容**的
  推断不同。**缺年（`1-5`）与年月（`2026-10`）是真正的信息缺失**，不猜，原样低置信 ——
  这是本字段 abbrev 的天花板（= 缺零型占比），不是实现缺陷（见 RESULT-019 §5）。
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

# 判据：ISO `YYYY-MM-DD`（月/日允许 1–2 位，便于补缺零后再校验）
_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")

# 分隔符归一：这些一律换成 `-`
_SEP_MAP = {"／": "-", "/": "-", "．": "-", ".": "-"}

# 数字形近字母：字母 → 数字（与 amount 同表同口径，TASK-019 §2.5 给定）
CONFUSABLE_TO_DIGIT: dict[str, str] = {
    "O": "0", "l": "1", "Z": "2", "E": "3", "A": "4",
    "S": "5", "G": "6", "T": "7", "B": "8", "q": "9",
}

_WS_RE = re.compile(r"[\s　]+")

YEAR_MIN, YEAR_MAX = 1970, 2026

# ============================================================ 内部步骤


def _unify_sep(s: str) -> tuple[str, bool]:
    """分隔符归一（`/ . ／ ．` → `-`）。返回 (结果, 是否改动)。"""
    out = "".join(_SEP_MAP.get(ch, ch) for ch in s)
    return out, out != s


def _canon_date(s: str) -> str | None:
    """补缺零 + 范围校验。合法返回 ISO（`YYYY-MM-DD`），否则返回 None（不猜）。"""
    m = _DATE_RE.match(s)
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    if not (YEAR_MIN <= y <= YEAR_MAX and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"

# ============================================================ 主入口


def normalize_date(value: str) -> tuple[str, float]:
    """日期 → (规范值, 置信度)。认不出 / 不可恢复（缺年、年月、越界）时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）—— 去前后缀噪声 + 分隔符归一 + 去空白 + 补缺零。
    out, noise_hit = strip_noise(value)
    out, sep_hit = _unify_sep(out)
    ws_hit = _WS_RE.search(out) is not None
    out = _WS_RE.sub("", out)
    canon = _canon_date(out)
    if canon is not None and (noise_hit or sep_hit or ws_hit or canon != out):
        return canon, CONF_STRUCTURAL

    # 第 2 层：推断（数字形近修复）。结构清洗后仍不合法时才试，修完再过闸门。
    fixed, typo_hit = apply_table(out, CONFUSABLE_TO_DIGIT)
    canon2 = _canon_date(fixed)
    if typo_hit and canon2 is not None:
        return canon2, CONF_INFER

    # 第 3 层：没改动，但值本身已规范 ⇒ 「值已规范」（TASK-015）。输出仍是 value，字节不变。
    if _canon_date(value) is not None:
        return value, CONF_CLEAN

    # 没证据（含缺年、年月、越界）：原样返回，交上层。
    return value, CONF_NONE

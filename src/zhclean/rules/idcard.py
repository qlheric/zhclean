"""身份证号规则（结构清洗打底，GB 11643 校验码闸门兜底，15 位老证补全）。

F: 身份证脏值 → 18 位规范值 + 置信度；去空白/分隔符/前后缀噪声 + 数字形近修复 + 15→18 补全
R: rules/common.py（strip_noise / strip_ws_sep / apply_table / CONF_*）、rules/__init__.py
A: zhclean.normalize(value, "idcard")
S: 形近表取自通用 OCR 知识；GB 11643 权重表/查表**独立实现**，不抄 benchmark 生成器

置信度阶梯（与全库统一）：
    0.95 值已规范（18 位且校验码本就正确）⇒ 无需改动
    0.9  结构清洗命中（去空白 / 分隔符 / 前后缀）—— 无损、可验证
    0.7  推断层命中（数字形近修复 / 15 位补「19」重算校验码）—— 有依据，但本质仍是推断
    0.1  无法处理 / 拿不准 → 原样返回，交给上层（LLM / HITL）

设计取舍（与 phone 的异同 —— 照抄 phone 前先读这段）：
* **同**：都是「单管道 + 校验闸门」。结构清洗后已合法就直接返回（0.9）；不合法才上推断层，
  修完**再过一次闸门**才返回，否则原样低置信。推断修坏的值根本返回不出去。
* **异**：phone 的闸门是**形态正则**（11 位 / `1[3-9]` 开头），是弱判据；
  idcard 的闸门是**校验码重算**（GB 11643 加权和 mod 11 查表），是**强判据** ——
  猜错的 18 位串只有约 1/11 的概率蒙对校验码，所以这里敢把「形近修复」放宽到**任意位置**
  （地区码 / 生日 / 顺序码都行），根本不需要知道错在哪一位：猜错就过不了闸门。
  同理，15→18 补全也敢直接「补 19 + 重算」，因为出生年份落在 1970–1999（见下）。

**15 位老证为什么可按「补 19」还原**：15 位身份证等于把 18 位的出生年省去世纪两位
（`YYMMDD` 而非 `YYYYMMDD`）。本库口径下出生年恒在 **1970–1999**（TASK-024 §2.5 契约；
RESULT-023 §5-a 的「最窄读法」裁决），世纪位唯一 ⇒ 补「19」是无损可逆的，不是猜。
若将来口径放开到全世纪，这里要改成枚举候选世纪并逐个过闸门。
"""

from __future__ import annotations

from .common import (
    CONF_CLEAN,
    CONF_INFER,
    CONF_NONE,
    CONF_STRUCTURAL,
    apply_table,
    strip_noise,
    strip_ws_sep,
)

# ============================================================ 判据（GB 11643-1999）

# 前 17 位的加权因子（固定表，属国标，不是可调参数）
_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
# 加权和 mod 11 → 校验码（下标 0..10 依序查这张表）
_ID_CHECK_CODES = "10X98765432"

# 数字形近字母（OCR / 手写常见）：字母 → 数字。
# 只收通用混淆；因为入库前**必须过校验码闸门**，宁多收一点也不会改坏正确号码。
# 注：`X` 是合法校验码，刻意不在表内 ⇒ 第 18 位永不被本表改动。
CONFUSABLE_TO_DIGIT: dict[str, str] = {
    "O": "0", "o": "0", "D": "0",
    "l": "1", "I": "1", "i": "1",
    "Z": "2", "z": "2",
    "E": "3", "e": "3",
    "A": "4", "a": "4",
    "S": "5", "s": "5",
    "G": "6", "g": "6",
    "T": "7", "t": "7",
    "B": "8", "b": "8",
    "q": "9",
}

# 15 位老证补全时插入的世纪位（口径见模块头）
_CENTURY = "19"


def _check_digit(first17: str) -> str:
    """算第 18 位校验码（GB 11643-1999 加权因子 + mod 11 查表）。"""
    total = sum(int(ch) * w for ch, w in zip(first17, _ID_WEIGHTS))
    return _ID_CHECK_CODES[total % 11]


def _valid18(s: str) -> bool:
    """校验闸门：18 位、前 17 全数字、第 18 位 == 按 GB 11643 重算的校验码。"""
    return (
        len(s) == 18
        and s[:17].isdigit()
        and s[17] == _check_digit(s[:17])
    )


def _expand15(s: str) -> str | None:
    """15 位老证 → 18 位（补「19」+ 重算校验码）。不是 15 位纯数字则返回 None。"""
    if len(s) != 15 or not s.isdigit():
        return None
    first17 = s[:6] + _CENTURY + s[6:]
    return first17 + _check_digit(first17)


# ============================================================ 主入口


def normalize_idcard(value: str) -> tuple[str, float]:
    """身份证号 → (规范值, 置信度)。认不出 / 修完过不了闸门时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。产物必须过闸门才算命中。
    out, noise_hit = strip_noise(value)
    out, sep_hit = strip_ws_sep(out)
    if (noise_hit or sep_hit) and _valid18(out):
        return out, CONF_STRUCTURAL

    # 第 2 层：推断。先试数字形近修复（任意位置，闸门兜底），
    #         再试 15 位老证补全（补「19」+ 重算校验码），两者都要过闸门才采纳。
    fixed, typo_hit = apply_table(out, CONFUSABLE_TO_DIGIT)
    if typo_hit and _valid18(fixed):
        return fixed, CONF_INFER
    expanded = _expand15(fixed)
    if expanded is not None and _valid18(expanded):
        return expanded, CONF_INFER

    # 第 3 层：没改动，但值本身已是合法 18 位 ⇒ 「值已规范」。输出仍是 value，字节不变。
    if _valid18(value):
        return value, CONF_CLEAN

    # 没证据（位数不对 / 校验码不符 / 修完仍不合法）：原样返回，交上层。
    return value, CONF_NONE


# ============================================================ 自检（供 `python -m` 直接跑）


def _demo() -> None:
    """最小可运行检查：四层各一条 + 坏校验码不被采纳。"""
    assert normalize_idcard("116047198805081999") == ("116047198805081999", CONF_CLEAN)
    assert normalize_idcard("116 047198805081999") == ("116047198805081999", CONF_STRUCTURAL)
    assert normalize_idcard("1l6047198805081999") == ("116047198805081999", CONF_INFER)
    assert normalize_idcard("116047880508199") == ("116047198805081999", CONF_INFER)
    # 坏校验码：改一位数字后闸门必拒，原样低置信
    assert normalize_idcard("116047198805081998") == ("116047198805081998", CONF_NONE)
    print("idcard._demo: OK")


if __name__ == "__main__":
    _demo()

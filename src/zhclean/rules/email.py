"""邮箱规则（去空白/前缀打底，形近还原只修「位置可判定」的字，@ 与点不动）。

F: 邮箱脏值 → 规范值 + 置信度；去空白 + 去前后缀标签 + 形近数字/字母双向还原
R: rules/common.py（strip_noise / apply_table / CONF_*）、rules/__init__.py
A: zhclean.normalize(value, "email")
S: 形近表取自通用 OCR 知识；不得针对测试扰动模式调参（留出集纪律）

置信度阶梯（与全库统一）：
    0.95 值已规范（过形态闸门）⇒ 无需改动
    0.9  结构清洗命中（去空白 / 去「邮箱：Email:」标签 / 去括号备注 / 尾随标点）
    0.7  形近还原命中（仅限「位置本身可判定」的字符，见下）—— 有依据，但本质仍是推断
    0.1  无法处理 / 拿不准 → 原样返回，交给上层（LLM / HITL）

设计取舍（**别照抄 phone** —— 差异是这份规则的全部难点）：
* phone / idcard 敢做「先猜后验」，是因为它们有**强闸门**（形态正则 `1[3-9]\\d{9}` / 校验码重算），
  猜错根本过不去。email 的闸门是**宽松形态**（`名字@带点的域名`）—— 它只保证「像个邮箱」，
  **对单个字符的形近替换没有判别力**：`a232zxb3s@139.com`（干净）和 `a232zxb3s@139.c0m`（脏）
  同样过闸门。所以在这里做**盲修**（照表逐字替换）会把干净值的 `.com` 改成 `.c0m` 并当作
  「推断命中 0.7」返回 —— 那是**改坏**，直接违反本库「宁可漏改，绝不改坏」。
* 故本模块的还原层只施加在**位置本身可判定**的字符上（判据都是契约里就有的形态约束）：
    ① TLD 必是**字母** ⇒ TLD 里的形近数字（0/1/2/5/6/8）即错，修成字母；
    ② 域名主体**黑白分明**（要么全字母、要么全数字）⇒ 混进去的「异类」字符即错；
       但**恰有 1 个异类**才敢修 —— 有 2 个以上就分不清错的是哪个，不猜；
    ③ user **首字符必是字母**（契约：user 字母开头）⇒ 首字符若是形近数字，修成字母。
  这三条都**只动字母数字位，`@` 与 `.` 一律不动**，且都不会命中任何规范值（干净域名
  主体本就黑白分明、TLD 本就无反例），故**零改坏**。
* **user 段内部的错字不修**：`w0avx` 里的 `0` 可能是真数字、也可能是 `o` 打错，
  形态闸门与域名证据都管不到 user 段内部 —— 分不清 ⇒ 不猜（这是 email 的已知天花板）。
* **sep / abbrev 不猜**（契约明示，属**正确口径**，不是没做完）：
  - `sep`：`a_b@x.com` 与合法的 `a.b@x.com` 无从区分，多余下划线**去不掉**；
  - `abbrev`：`.com→.co`、`@gmail.com→@gmail` 信息已丢，**不可恢复**。
  这两类原样返回（可能落到 0.95 档 —— 形态闸门认不出「截断」，见 common.py 的 0.95 说明），
  交上层。评测回环数字会因此有天花板，是设计选择而非缺陷。
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

# ============================================================ 判据

# 形态闸门：恰一个 `@`、两边非空、域名带点。**宽松**是刻意的 —— 见模块头设计取舍。
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# 前后缀标签：「邮箱：」「Email:」「E-mail:」（大小写不敏感）。
# strip_noise 的通用标签正则只认中日韩汉字，认不出拉丁词，故这里单独补一条。
_LABEL_RE = re.compile(r"^\s*(?:邮\s*箱|E-?mail)\s*[：:]\s*", re.IGNORECASE)

# 空白（含全角空格）。**不能**用 common.strip_ws_sep —— 它会连 `.` `_` 一起删掉，
# 而这两个字符在邮箱里是有意义的分隔（`a.b@x.com` 合法、`x_y` 用户名合法）。
_WS_RE = re.compile(r"[\s　]+")

# 形近对（双向，通用 OCR 知识）：数字 ↔ 小写字母
DIGIT_TO_ALPHA: dict[str, str] = {"0": "o", "1": "l", "2": "z", "5": "s", "6": "g", "8": "b"}
ALPHA_TO_DIGIT: dict[str, str] = {v: k for k, v in DIGIT_TO_ALPHA.items()}


def _is_email(s: str) -> bool:
    """形态闸门（宽松）：像个邮箱即可，不判真假。"""
    return bool(_EMAIL_RE.match(s))


def _repair_heterogeneous(name: str) -> tuple[str, bool]:
    """域名主体黑白分明 ⇒ **恰 1 个**异类字符才修。返回 (结果, 是否改动)。

    全字母 / 全数字视为常态；混入的异类就是形近错字的方向。
    异类 ≥2 个时分不清错在哪一个 ⇒ 原样返回（宁可漏改）。
    """
    alpha = [i for i, c in enumerate(name) if c.isalpha()]
    digit = [i for i, c in enumerate(name) if c.isdigit()]
    if not alpha or not digit:
        return name, False
    if len(digit) == 1 and name[digit[0]] in DIGIT_TO_ALPHA:
        i = digit[0]
        return name[:i] + DIGIT_TO_ALPHA[name[i]] + name[i + 1:], True
    if len(alpha) == 1 and name[alpha[0]] in ALPHA_TO_DIGIT:
        i = alpha[0]
        return name[:i] + ALPHA_TO_DIGIT[name[i]] + name[i + 1:], True
    return name, False


def _repair_domain(dom: str) -> tuple[str, bool]:
    """域名段的形近还原：① TLD 必是字母 ② 域名主体黑白分明。返回 (结果, 是否改动)。"""
    if "." in dom:
        name, tld = dom.rsplit(".", 1)
    else:
        name, tld = dom, ""       # 无点（如 abbrev 的 `@gmail`）：整体当主体
    hit = False
    if tld:
        new_tld, tld_hit = apply_table(tld, DIGIT_TO_ALPHA)
        if tld_hit:
            tld, hit = new_tld, True
    new_name, name_hit = _repair_heterogeneous(name)
    if name_hit:
        name, hit = new_name, True
    return (f"{name}.{tld}" if hit else dom), hit


def _repair_forced(value: str) -> tuple[str, bool]:
    """只修「位置本身可判定」的形近字（判据见模块头）。`@` 与 `.` 一律不动。"""
    user, sep, dom = value.partition("@")
    if not sep:
        return value, False
    hit = False
    # ③ user 首字符必是字母（契约）。只在首位是形近数字时替换。
    if user and user[0] in DIGIT_TO_ALPHA:
        user = DIGIT_TO_ALPHA[user[0]] + user[1:]
        hit = True
    new_dom, dom_hit = _repair_domain(dom)
    if not (hit or dom_hit):
        return value, False
    return f"{user}@{new_dom}", True


# ============================================================ 主入口


def normalize_email(value: str) -> tuple[str, float]:
    """邮箱 → (规范值, 置信度)。判不出 / 信息已丢时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。产物必须过形态闸门才算命中。
    out, label_hit = _LABEL_RE.subn("", value)
    label_hit = label_hit > 0
    out, noise_hit = strip_noise(out)
    ws_stripped = _WS_RE.sub("", out)
    ws_hit = ws_stripped != out
    out = ws_stripped
    if (label_hit or noise_hit or ws_hit) and _is_email(out):
        return out, CONF_STRUCTURAL

    # 第 2 层：形近还原（推断，仅限位置可判定的字符）。改完仍要过闸门。
    fixed, forced_hit = _repair_forced(out)
    if forced_hit and _is_email(fixed):
        return fixed, CONF_INFER

    # 第 3 层：没改动，但值本身已过闸门 ⇒ 「值已规范」。输出仍是 value，字节不变。
    if _is_email(value):
        return value, CONF_CLEAN

    # 没证据（含 sep / abbrev 这类不可恢复的）：原样返回，交上层。
    return value, CONF_NONE


# ============================================================ 自检（供 `python -m` 直接跑）


def _demo() -> None:
    """最小可运行检查：结构清洗 / 三条可判定还原 / 不可恢复的不猜 / 零改坏。"""
    clean = "a232zxb3s@139.com"
    assert normalize_email(clean) == (clean, CONF_CLEAN)
    assert normalize_email("a232zxb3s@ 139.com") == (clean, CONF_STRUCTURAL)
    assert normalize_email("Email:a232zxb3s@139.com") == (clean, CONF_STRUCTURAL)
    # ① TLD 形近数字；② 域名主体异类；③ user 首位形近数字
    assert normalize_email("a232zxb3s@139.c0m") == (clean, CONF_INFER)
    assert normalize_email("um7dy@h0tmail.com") == ("um7dy@hotmail.com", CONF_INFER)
    assert normalize_email("um7dy@l26.com") == ("um7dy@126.com", CONF_INFER)
    assert normalize_email("1abc123@139.com") == ("labc123@139.com", CONF_INFER)  # 1→l（user 首位）
    # 不可恢复的：原样返回，不猜
    assert normalize_email("a232zxb3s@139.co")[0] == "a232zxb3s@139.co"
    assert normalize_email("a232zx_b3s@139.com")[0] == "a232zx_b3s@139.com"
    print("email._demo: OK")


if __name__ == "__main__":
    _demo()

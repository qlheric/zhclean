"""规则库公共件：结构清洗、通用错字修复、置信度档位（四类字段共用）。

F: 供 rules/{person,phone,company,address}.py 复用；本模块**不含字段专有词典**
R: rules/__init__.py、各字段规则模块
A: 不直接对外；经 normalize_<field> 暴露
S: 只放「与字段无关」的机制。字段专有的词典 / 判据集合 / 守卫名单留在各自模块，
   通过参数传进来 —— 这样加字段不必改这里，改这里也不会动到字段口径。

置信度档位（全库统一，TASK-015 拆档）：
    0.95 值已规范：结构上本就干净 + 值本身就像本字段合法值 ⇒ 无需改动
    0.9  结构清洗命中（去空白 / 分隔符 / 前后缀噪声）—— 无损、可验证
    0.7  推断层命中（错字修复 / 缩写补全 / 行政区划标记补全）—— 有依据，但本质仍是推断
    0.1  无法处理 / 拿不准（无证据）→ 原样返回，交给上层（LLM / HITL）

为什么要把「已规范」和「拿不准」分开（TASK-015 契约）：拆档前两者都是 0.1，
导致 loop 的 HITL 队列被「本来就干净」的行淹没（RESULT-014 §5-1）。
拆档后 0.95 与 0.1 语义互斥：**0.95 = 这条没事干**，0.1 = **这条我处理不了**。
注意：0.95 的判据是「像本字段合法值」（`_looks_like_*` / `_is_valid`），所以
「看起来合法、其实是截断/缺段」的脏值也会落进 0.95（见 RESULT-015 §5-2）。

设计取舍（错字修复为什么长这样）：
通用机制是「滑窗轮 + 单字轮」，两轮都**宁可漏改，绝不改坏**：
* **滑窗轮**（窗口 ≥2 字，从长到短）：窗口内逐字修，**修完必须恰等于某个已知词组**
  才采纳 —— 这就是闸门。品牌名 / 小区名 / 道路名是**开集**，修完不构成已知词组，
  天然被挡在门外（这也是为什么闸门的判据集合只放常识闭集）。
* **单字轮**：纠正后的字本身是结构字（区 / 路 / 号 / 栋…）时无需专名作证，但必须过守卫，
  否则会把合法地名 / 路名改坏（「曲阜」→「区阜」、「雨露路」→「雨路路」）。
  守卫由调用方通过 `guards` 传入，三类含义见 `repair_typos_by_known_words` 的 docstring。

为什么把两条独立机制（滑窗 / 单字）放在同一个函数里：它们的**顺序有语义**
—— 滑窗轮先跑且**命中即返回**（一次只修一处），后跑的单字轮只在滑窗没命中时才介入。
拆成两个函数会让调用方有机会把顺序写反，而顺序写反的后果是「该修的不修 / 不该修的修了」，
很难在 review 里看出来。
"""

from __future__ import annotations

import re

# ============================================================ 置信度档位

CONF_CLEAN = 0.95      # 值已规范：结构干净 + 值本身像本字段合法值 ⇒ 无需改动
CONF_STRUCTURAL = 0.9  # 结构清洗命中
CONF_INFER = 0.7       # 推断层命中（错字修复 / 缩写补全 / 标记补全）
CONF_NONE = 0.1        # 无证据 / 拿不准：原样返回

# ============================================================ 结构清洗

# 前后缀噪声：前缀标签 / 尾部括号备注 / 尾随标点
_LABEL_RE = re.compile(r"^[一-鿿]{1,4}[：:]")                    # 「地址：」「电话:」
_PAREN_RE = re.compile(r"[（(][^）)]{1,10}[）)]\s*$")             # 「（收货地址）」「（本人）」
_PUNCT = "。，,.、！!?？；;～~“”\"'’‘"                            # 首尾标点
# 空白（含全角空格 U+3000）+ 常见分隔符，出现在哪里都去掉
_WS_SEP_RE = re.compile(r"[\s\-－—–·・|｜/／,，、\\_~～]+")


def strip_noise(s: str, honorifics: tuple[str, ...] = ()) -> tuple[str, bool]:
    """去前缀标签 / 尾部（敬称 · 括号备注）/ 尾随标点（循环到稳定）。返回 (结果, 是否改动)。

    `honorifics` 是人名专用的**可选**尾部敬称表（「先生」「女士」…），缺省为空 ⇒
    其余字段调它时行为与重构前逐字相同（等价于只做标签 / 括号 / 标点三种剥离）。
    """
    out = s
    for _ in range(3):
        before = out
        out = _LABEL_RE.sub("", out, count=1)
        for h in honorifics:
            if out.endswith(h):
                out = out[: -len(h)]
                break
        out = _PAREN_RE.sub("", out)
        out = out.strip(_PUNCT)
        if out == before:
            break
    return out, out != s


def strip_ws_sep(s: str) -> tuple[str, bool]:
    """去掉串内所有空白与分隔符（无损）。返回 (结果, 是否改动)。"""
    out = _WS_SEP_RE.sub("", s)
    return out, out != s

# ============================================================ 错字修复

# 结构字守卫表：默认给**地址类**字段用（省市区路号栋 是地址的结构字）。
# 放在 common 是因为它是「结构字」这个通用概念的落点；其他字段若要单字轮，
# 传自己的表即可 —— 本模块不假设任何字段一定用这三张表。
SINGLE_CHAR_STRUCT_OK = frozenset("省市区县路道街巷栋座幢层楼室号市")
NEED_PREV_DIGIT = frozenset({"号", "室"})   # 门牌 / 房号永远跟在数字后面
DIGIT_AFTER_SRC = frozenset("露洞到")       # 这些**原形字**修成 路/栋/道 时，后一位必须是数字


def apply_table(s: str, table: dict[str, str]) -> tuple[str, bool]:
    """按表逐字直替（表里没有的字符原样保留）。返回 (结果, 是否改动)。

    这是各类「错 → 正」字符表的最简语义：**不做闸门、不做守卫**，照表替换。
    带闸门的场景（滑窗 / 单字轮）见 `repair_typos_by_known_words`；两者不要混用 ——
    直替用于调用方**已有别的保证**的时候（人名只在名部分替换、电话替换完还要过校验）。
    """
    out = "".join(table.get(ch, ch) for ch in s)
    return out, out != s


def _trailing_ok(s: str, nxt: int, fixed_word: str, trailing) -> bool:
    """滑窗轮的**位置约束**：修出来的词若属于受约束集合，则要求其后一位在允许集内。

    用途见 address 的 DISTRICT_COMPONENT_WORDS：方位构词（城东 / 河西…）只有后面
    紧跟「区」或「城」时才是行政区名（「城东区」），否则多半是小区名（「城东雅苑」）。
    `trailing` 为 None ⇒ 该约束关闭。返回 True 表示**允许**这次修复。
    """
    if not trailing:
        return True
    words, allowed = trailing
    if fixed_word not in words:
        return True
    return nxt < len(s) and s[nxt] in allowed


def _single_char_trailing_ok(s: str, i: int, new: str, trailing) -> bool:
    """单字轮的同一个位置约束：新字若**新造出**一个受约束词，要求该词后一位在允许集内。

    单字轮只改一个字符，故只需看**盖住位置 i、且修复前不是这个词**的那些词。
    """
    if not trailing:
        return True
    words, allowed = trailing
    cand = s[:i] + new + s[i + 1:]
    for w in words:
        j = cand.find(w)
        while j != -1:
            covers = j <= i < j + len(w)
            is_new = w != s[j:j + len(w)]          # 修复前此处不是这个词 ⇒ 是修出来的
            if covers and is_new and not (j + len(w) < len(cand) and cand[j + len(w)] in allowed):
                return False
            j = cand.find(w, j + 1)
    return True


def repair_typos_by_known_words(
    s: str,
    typo_table: dict[str, str],
    known_words,
    single_char_ok=frozenset(),
    guards: dict | None = None,
) -> tuple[str, bool]:
    """通用错字修复：滑窗轮（≥2 字）+ 单字轮。返回 (结果, 是否改动)；未命中返回原串。

    一次调用**最多修一处**（第一处命中即返回）—— 与本库其余层的口径一致：
    宁可分多次调用，也不要一次性猜一串。

    参数：
      typo_table      错 → 正 的字表
      known_words     滑窗轮的判据集合（修完必须**恰等于**其中之一才采纳）
      single_char_ok  单字轮的放行集合（纠正后的字属于此集才无需专名作证）
      guards          单字轮的三类守卫 + 位置约束，可选键（缺省 = 关闭）：
        ``guard_names``     这些地名开头的位置一律不动
                            —— 否则地级市「曲靖」会被拆成「区靖」
        ``need_prev_digit`` 纠正成这些字时要求**前一位是数字**
                            —— 门牌 / 房号永远跟在数字后面，防路名里的「豪」变「号」
        ``need_next_digit`` 这些**原形字**被纠正时要求**后一位是数字**
                            —— 真地址里 路/栋/道 后面必跟门牌号，否则该字多半是专名
                            （「雨露路」「洞庭路」「报到路」）⇒ 不动
        ``trailing``        ``(受约束词集, 允许的后续字集)`` —— 见 `_trailing_ok`
    """
    guards = guards or {}
    guard_names = guards.get("guard_names", frozenset())
    need_prev_digit = guards.get("need_prev_digit", frozenset())
    need_next_digit = guards.get("need_next_digit", frozenset())
    trailing = guards.get("trailing")

    max_len = max((len(w) for w in known_words), default=1)

    # ---- 滑窗轮：窗口从长到短，先命中最长的词组（避免被短词截断） ----
    for k in range(min(max_len, len(s)), 1, -1):
        for start in range(0, len(s) - k + 1):
            window = s[start:start + k]
            fixed = apply_table(window, typo_table)[0]
            if fixed == window or fixed not in known_words:
                continue                                    # 没修动 / 修完不在判据集合 ⇒ 不是它
            if not _trailing_ok(s, start + k, fixed, trailing):
                continue
            return s[:start] + fixed + s[start + k:], True

    # ---- 单字轮：放行集合 + 三类守卫 + 位置约束 ----
    for i, ch in enumerate(s):
        new = typo_table.get(ch)
        if new is None or new not in single_char_ok:
            continue
        # 守卫 1：此位置不是某个已知词组 / 受保护地名的开头
        if any(s[i:i + m] in known_words or s[i:i + m] in guard_names
               for m in range(2, max_len + 1) if i + m <= len(s)):
            continue
        # 守卫 2：门牌 / 房号永远跟在数字后面
        if new in need_prev_digit and not (i > 0 and s[i - 1].isdigit()):
            continue
        # 守卫 3：结构字（路 / 栋 / 道）后面必跟门牌数字，否则该字多半是专名的一部分
        if ch in need_next_digit and not (i + 1 < len(s) and s[i + 1].isdigit()):
            continue
        # 位置约束：新造出的方位构词后面必须紧跟「区」或「城」
        if not _single_char_trailing_ok(s, i, new, trailing):
            continue
        return s[:i] + new + s[i + 1:], True

    return s, False

# ============================================================ 自检（供 `python -m` 直接跑）


def _demo() -> None:
    """最小可运行检查：滑窗闸门挡住开集、单字轮守卫生效、位置约束两轮都生效。"""
    # 表是「错 → 正」
    table = {"洲": "州", "冬": "东", "曲": "区", "式": "市", "中": "钟"}
    words = frozenset({"苏州", "城东", "城西", "市中"})
    # 滑窗闸门：修完恰等于已知词 ⇒ 采纳
    assert repair_typos_by_known_words("苏州", table, words) == ("苏州", False)   # 本就正确
    assert repair_typos_by_known_words("苏洲", table, words) == ("苏州", True)
    assert repair_typos_by_known_words("苏洲路", table, words) == ("苏州路", True)  # 窗口内修
    # 闸门：修完不构成已知词 ⇒ 不动（开集保护）
    assert repair_typos_by_known_words("杭洲", table, words) == ("杭洲", False)
    # 单字轮守卫 1：地名开头不动（否则「曲阜」→「区阜」）
    assert repair_typos_by_known_words(
        "曲阜大道", table, words, frozenset("区"),
        {"guard_names": frozenset({"曲阜"})}) == ("曲阜大道", False)
    # 位置约束（滑窗轮）：城东 只有后跟 区/城 才修
    tr = (frozenset({"城东", "市中"}), frozenset("区城"))
    assert repair_typos_by_known_words(
        "城冬区", table, words, frozenset(), {"trailing": tr}) == ("城东区", True)
    assert repair_typos_by_known_words(
        "城冬雅苑", table, words, frozenset(), {"trailing": tr}) == ("城冬雅苑", False)
    # 位置约束（单字轮）：滑窗轮被「市中」里的中又会被表改掉而失配，只剩单字轮这条路
    assert repair_typos_by_known_words(
        "式中区", table, words, frozenset("市"), {"trailing": tr}) == ("市中区", True)
    assert repair_typos_by_known_words(
        "式中苑", table, words, frozenset("市"), {"trailing": tr}) == ("式中苑", False)
    print("common._demo: OK")


if __name__ == "__main__":
    _demo()

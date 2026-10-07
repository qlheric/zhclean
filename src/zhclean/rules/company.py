"""公司名规则词典与清洗函数（结构清洗打底，组织形式缩写补全 + 错字修复兜底）。

F: 公司名脏值 → 规范值 + 置信度；去空白/分隔符/前后缀噪声 + 组织形式缩写补全 + 通用错字修复
R: rules/__init__.py（注册表 DISPATCH）
A: zhclean.normalize(value, "company")
S: 词典取自通用知识，不得针对测试扰动模式调参（留出集纪律）

置信度阶梯（沿用 person/phone 档位）：
    0.9  结构清洗命中（去空白 / 分隔符 / 前后缀噪声）—— 无损、可验证
    0.7  推断层命中（组织形式缩写补全 / 错字修复）—— 有依据，但本质仍是推断
    0.1  什么都没做（无证据）→ 原样返回，交给上层（LLM / HITL）

设计取舍（与 person / phone 的差异，写清楚免得下一个人照抄错）：
1. 公司名**没有**电话那样的客观校验闸门（「11 位、1[3-9] 开头」），故沿用 person 的
   「**结构层命中即返回、不叠加推断层**」—— 避免两层推断互相误伤。
2. 但公司名的推断层有一条 person 没有的强判据：**规范的中文公司名必定以某个组织形式
   全称结尾**（有限公司 / 有限责任公司 / 股份有限公司 / 集团有限公司）。据此推断层设
   「**产物必须恰是某个已知词组**」的闸门（已知词组 = 组织形式全称 ∪ 通用行业词）：
     * 缩写补全：补完必须**恰好等于**某个组织形式全称（「股份公司」→「股份有限公司」）
     * 错字修复：在**已知词组**的窗口内逐字修，修完必须**恰好等于**某个已知词组
   为什么判据集合要含行业词：错字不落在组织形式上（「科记」「志能」「信希」）时，
   只认组织形式会漏修；而**行业词是常识闭集**（品牌名才是开集），加它不会误伤——
   品牌名里的同形字（如品牌「环宇」的「宇」）修完不构成任何已知词组，因此**不会被误伤**。
   这条闸门保证「宁可漏改，绝不改坏」。
3. 「去城市」「去组织形式」这类缩写**不可可靠恢复**（「XX有限公司」本身合法，
   无从判断它原本是不是「XX有限责任公司」）⇒ 一律不猜、原样低置信返回。
   与 person/abbrev（名缺字不可恢复 → 0%）口径一致。
"""

from __future__ import annotations

import re

# ============================================================ 词典

# 组织形式全称（通用知识）。既用于判「像不像公司名」，也是推断层闸门的判据集合。
ORG_FORMS = frozenset({
    "股份有限公司", "有限责任公司", "集团有限公司", "有限公司", "公司", "集团",
})

# 通用行业词（中文企业名常见，通用知识整理；不针对测试扰动调参）。
# 用于给错字修复提供第二个可验证锚点：**行业词是常识闭集**（品牌名才是开集）。
INDUSTRY_WORDS = frozenset({
    "科技", "网络", "信息", "教育", "文化", "传媒", "贸易", "实业", "电子", "生物",
    "医药", "环保", "智能", "数据", "软件", "物流", "建筑", "机械", "食品", "农业",
    "咨询", "能源", "地产", "装饰", "广告", "旅游", "餐饮", "服装", "汽车", "金融",
})

# 已知词组 = 组织形式 ∪ 行业词。错字修复的**唯一判据集合**（修完必须恰等于其中之一）。
_KNOWN_WORDS = ORG_FORMS | INDUSTRY_WORDS

# 组织形式缩写 → 全称。**只收可可靠推断的**：缩写无歧义地只对应一个全称。
# 「有限公司」不收 —— 它本身就是全称，无从判断原本是不是「有限责任公司」。
SUFFIX_EXPANSIONS: dict[str, str] = {
    "股份公司": "股份有限公司",
}

# 通用错字表（错 → 正）。来源：常见中文公司名的形近/同音混淆（通用知识整理）。
# 前 10 条是组织形式必现字（每个公司名都有），后 10 条是行业/通用词常见字。
# 安全性由推断层闸门保证（修完必须恰是某个已知词组），故多收不会改坏正确公司名 ——
# 品牌名里的同形字（如「环宇」的「宇」）修完不构成已知词组，因此**不会被误伤**。
TYPO_TO_CORRECT: dict[str, str] = {
    "工": "公", "词": "司", "伺": "司",
    "友": "有", "线": "限",
    "则": "责", "泽": "责",
    "分": "份",
    "积": "集", "困": "团",
    "记": "技", "意": "易", "叶": "业", "落": "络",
    "芯": "信", "希": "息", "店": "电", "宇": "子",
    "志": "智", "资": "咨",
}

# 前后缀噪声：前缀标签 / 尾部括号备注 / 尾随标点
_LABEL_RE = re.compile(r"^[一-鿿]{1,4}[：:]")                    # 「单位：」「公司名称:」
_PAREN_RE = re.compile(r"[（(][^）)]{1,10}[）)]\s*$")                # 「（总部）」「（分公司）」
_PUNCT = "。，,.、！!?？；;～~“”\"'’‘"                               # 首尾标点
# 空白（含全角空格 U+3000）+ 常见分隔符，出现在哪里都去掉
_WS_SEP_RE = re.compile(r"[\s\-－—–·・|｜/／,，、\\_~～]+")

CONF_STRUCTURAL = 0.9  # 结构清洗命中
CONF_INFER = 0.7       # 推断层命中（缩写补全 / 错字修复）
CONF_NONE = 0.1        # 无证据：原样返回

# ============================================================ 内部步骤


def _looks_like_company(s: str) -> bool:
    """清洗后是否「像公司名」：长度合理 + 以某个组织形式全称结尾。"""
    return len(s) >= 4 and s.endswith(tuple(ORG_FORMS))


def _strip_noise(s: str) -> tuple[str, bool]:
    """去前缀标签 / 尾部括号备注 / 尾随标点（循环到稳定）。返回 (结果, 是否改动)。"""
    out = s
    for _ in range(3):
        before = out
        out = _LABEL_RE.sub("", out, count=1)
        out = _PAREN_RE.sub("", out)
        out = out.strip(_PUNCT)
        if out == before:
            break
    return out, out != s


def _strip_ws_sep(s: str) -> tuple[str, bool]:
    """去掉串内所有空白与分隔符（无损）。返回 (结果, 是否改动)。"""
    out = _WS_SEP_RE.sub("", s)
    return out, out != s


def _expand_suffix(s: str) -> tuple[str, bool]:
    """组织形式缩写补全。返回 (结果, 是否改动)。

    只补「缩写无歧义」的（「股份公司」→「股份有限公司」）；
    「有限公司」等本身已是全称的形式不在此处理（不叠加推断）。
    """
    for short, full in SUFFIX_EXPANSIONS.items():
        if s.endswith(short) and not s.endswith(full):
            return s[: -len(short)] + full, True
    return s, False


def _repair_typos(s: str) -> tuple[str, bool]:
    """错字修复：在**已知词组**（组织形式 / 行业词）的窗口内逐字修。

    只在「修完恰好等于某个已知词组」时才采纳 —— 这就是闸门。窗口从长到短扫，
    先命中的是更大的词组（如「股份有限公司」优先于「公司」），避免被短词截断。
    品牌名里的同形字修完不构成已知词组 ⇒ 天然不会被误伤。
    返回 (结果, 是否改动)；未命中返回原串。
    """
    max_len = max(len(w) for w in _KNOWN_WORDS)
    for k in range(min(max_len, len(s)), 1, -1):
        for start in range(0, len(s) - k + 1):
            window = s[start:start + k]
            fixed = "".join(TYPO_TO_CORRECT.get(ch, ch) for ch in window)
            if fixed != window and fixed in _KNOWN_WORDS:
                return s[:start] + fixed + s[start + k:], True
    return s, False

# ============================================================ 主入口


def normalize_company(value: str) -> tuple[str, float]:
    """公司名 → (规范值, 置信度)。认不出/无证据时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。命中即返回，不叠加第二层推断。
    stripped, noise_hit = _strip_noise(value)
    core, sep_hit = _strip_ws_sep(stripped)
    if noise_hit or sep_hit:
        if _looks_like_company(core):
            return core, CONF_STRUCTURAL
        return value, CONF_NONE  # 洗出来不像公司名：宁可原样返回

    # 第 2 层：结构上本就干净，只剩「缩写」或「错字」两种可能。都是推断，降一档。
    expanded, exp_hit = _expand_suffix(core)
    if exp_hit and _looks_like_company(expanded):
        return expanded, CONF_INFER
    repaired, rep_hit = _repair_typos(core)
    if rep_hit and _looks_like_company(repaired):
        return repaired, CONF_INFER

    # 没证据（含不可恢复的缩写、品牌/行业位置的错字）：原样返回，交上层。
    return value, CONF_NONE

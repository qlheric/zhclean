"""人名规则词典与清洗函数（规则打底，五类扰动各有着落）。

F: 人名脏值 → 规范值 + 置信度；结构清洗（空白/分隔符/前后缀噪声）+ 通用同音形近字纠正
R: rules/__init__.py（注册表 DISPATCH）
A: zhclean.normalize(value, "person")
S: 词典取自通用知识，不得针对测试扰动模式调参（留出集纪律）

置信度阶梯（本单「简单版」，loop/HITL 后续任务再细化）：
    0.9  结构清洗命中（去空白 / 去分隔符 / 去前后缀标签）—— 无损、可验证
    0.7  同音/形近字纠正命中 —— 有依据，但本质仍是推断
    0.1  什么都没做（无证据）→ 原样返回，交给上层（LLM / HITL）

设计取舍（两条铁律派生出来的）：
1. 结构清洗一旦命中就不再叠加错别字纠正 —— 不做「两层推断」。这样
   space / sep / noise 三类是纯无损操作，不会被错字表误伤（如「李 君豪」）。
2. 错字表只收「错字几乎不可能当名用字」的条目（如 墙→强、净→静），
   双向都有歧义的（佳/嘉、宇/羽、丽/莉、军/君）一律不收 —— 宁可漏改
   （低置信交上层），也不能把本来正确的名字改坏。
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

# 常见姓氏（含复姓）：用于判断「清洗后像不像人名」以及切出名字部分
SURNAMES_SINGLE = frozenset(
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕"
    "丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦傅方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严"
    "覃武戴莫孔向汤常温康施洪翟殷颜邢舒纪童欧聂甘齐岳伍祝申"
)
COMPOUND_SURNAMES = ("欧阳", "上官", "司马", "诸葛", "东方", "独孤",
                     "慕容", "皇甫", "尉迟", "长孙", "南宫", "夏侯")

# 通用同音/形近字表（错 → 正）。来源：常见中文人名的同音/形近混淆（通用知识整理）。
# 收录标准见模块头「设计取舍 2」：错字本身不得是常见名用字，避免误伤正确名字。
TYPO_TO_CORRECT: dict[str, str] = {
    "鸣": "明", "炜": "伟", "玮": "伟", "纬": "伟", "墙": "强", "蔷": "强",
    "桦": "华", "骅": "华", "净": "静", "滔": "涛", "拨": "波", "菠": "波",
    "庭": "婷", "亭": "婷", "朋": "鹏", "恺": "凯", "铠": "凯", "嵩": "松",
    "淞": "松", "量": "亮", "晾": "亮", "纹": "文", "至": "志", "果": "国",
    "帼": "国", "键": "建", "晖": "辉", "蕾": "磊", "垒": "磊", "涌": "勇",
    "涓": "娟", "鹃": "娟", "瑕": "霞", "峡": "霞", "凭": "平", "钢": "刚",
    "冈": "刚", "瑛": "英", "应": "英", "育": "玉", "虹": "红", "铃": "玲",
    "纷": "芬", "蓝": "兰", "篮": "兰", "结": "洁", "赢": "颖", "营": "颖",
    "京": "晶", "路": "露", "鹭": "露", "微": "薇", "蒙": "梦", "摇": "瑶",
    "谣": "瑶", "峻": "俊", "竣": "俊", "折": "哲", "伯": "博", "搏": "博",
    "烁": "硕", "匆": "聪", "同": "童", "木": "沐", "尘": "辰", "含": "涵",
    "函": "涵", "燃": "然", "绪": "旭", "叙": "旭", "非": "飞", "凝": "宁",
    "柠": "宁", "率": "帅", "师": "诗", "闵": "敏", "田": "天", "隆": "龙",
}

# 尾部敬称/称谓（**人名独有**：其余字段没有这一种噪声）。顺序即匹配优先级。
_HONORIFICS = ("先生", "女士", "小姐", "老师", "医生", "教授", "同志", "同学", "大人")
_NAME_RE = re.compile(r"^[一-鿿]{2,6}$")

# 清洗/置信度档位在 rules/common.py（四字段共用）

# ============================================================ 内部步骤


def _looks_like_name(s: str) -> bool:
    """清洗后是否「像个人名」：全中文、长度合理、且开头是可识别姓氏。"""
    if not _NAME_RE.match(s):
        return False
    surname, given = _split_surname(s)
    return bool(surname) and len(given) >= 1


def _split_surname(s: str) -> tuple[str, str]:
    """切出 (姓氏, 名)；认不出姓氏时姓氏为空串。"""
    for cs in COMPOUND_SURNAMES:
        if s.startswith(cs):
            return cs, s[len(cs):]
    if s and s[0] in SURNAMES_SINGLE:
        return s[0], s[1:]
    return "", s


def _strip_noise(s: str) -> tuple[str, bool]:
    """去前缀标签 / 尾部敬称·括号备注·标点。敬称表是本字段独有的，透传给公共件。"""
    return strip_noise(s, _HONORIFICS)

# ============================================================ 主入口


def normalize_person(value: str) -> tuple[str, float]:
    """人名 → (规范值, 置信度)。认不出/无证据时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。命中即返回，不叠加第二层推断。
    stripped, noise_hit = _strip_noise(value)
    core, sep_hit = strip_ws_sep(stripped)
    if noise_hit or sep_hit:
        if _looks_like_name(core):
            return core, CONF_STRUCTURAL
        return value, CONF_NONE  # 洗出来不像人名：宁可原样返回

    # 第 2 层：结构上本就干净，只可能剩「错别字」。这是推断，置信度降一档。
    # 人名的错字层是**逐字直替**（不是滑窗闸门）：安全靠「只替名部分 + 替完仍像人名」，
    # 见模块头「设计取舍 2」——表里已排除双向歧义字，故无需 known_words 闸门。
    surname, given = _split_surname(core)
    fixed, typo_hit = apply_table(given, TYPO_TO_CORRECT)
    if typo_hit and _looks_like_name(surname + fixed):
        return surname + fixed, CONF_INFER

    # 没证据（含 abbrev 缺字、名字用字不认识）：原样返回，交上层。
    return value, CONF_NONE

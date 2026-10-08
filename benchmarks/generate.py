"""程序化扰动生成脏数据（benchmark 先行，可核是命门）。

F: 干净集 → 扰动（加空格/错别字/简称/格式乱）→ 脏集；ground truth = 扰动前原值
R: src/zhclean/tools/normalize.py（评测对象）
A: python benchmarks/generate.py
S: 留出集独立划分；规则库不得针对测试扰动模式调参

数据契约（后续任务都靠它，勿改）：
- clean 行：{"id": "person-0001", "field": "person", "value": "王小明"}
- dirty 行：{"id": "person-0001", "field": "person", "value": "王 小明",
             "truth": "王小明", "perturbation": "space", "split": "train"}
- 扰动五类（每个字段都覆盖）：
    space  加空格（半角/全角；金额在数字间、日期同理）
    typo   常见错别字（同音/形近字替换；电话号码用数字→形近字母）
    abbrev 简称·后缀变异（漏字 / 去省去市 / 加国家码 / 组织形式后缀简化）
    sep    结构边界插分隔符（- · | ／ ，）
    noise  冗余噪声（前缀标签 / 后缀称谓 / 尾随标点）
- 确定性：同 seed 两次运行产物逐字节一致（utf-8 + LF + ensure_ascii=False）
- 划分：按 id 洗牌后前 split-ratio 为 heldout，其余 train；同一 clean id 的所有
        脏变体与其干净值同属一个 split（防泄漏）
- 词典全部内置（不联网、不装包），干净值由真实语素拼成，禁纯随机字符

用法：
    python -m benchmarks.generate --seed 42
    python benchmarks/generate.py --per-field 50 --out /tmp/x
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# ============================================================ 内置词典

# 常见姓氏（含复姓）
SURNAMES = list(
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕"
    "丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦傅方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严"
    "覃武戴莫孔向汤常温康施洪翟殷颜邢舒纪童欧聂甘齐岳伍祝申"
)
COMPOUND_SURNAMES = ["欧阳", "上官", "司马", "诸葛", "东方", "独孤",
                     "慕容", "皇甫", "尉迟", "长孙", "南宫", "夏侯"]

# 名用字 → 常见错别字（池子直接取自本表键，保证每个名字都能造出 typo）
GIVEN_CHAR_TYPOS = {
    "明": "铭", "伟": "炜", "强": "墙", "华": "桦", "军": "君", "丽": "莉",
    "静": "净", "燕": "艳", "杰": "捷", "涛": "滔", "波": "拨", "峰": "锋",
    "慧": "惠", "婷": "庭", "鑫": "新", "鹏": "朋", "凯": "恺", "松": "嵩",
    "亮": "量", "文": "纹", "志": "智", "国": "果", "建": "健", "辉": "晖",
    "磊": "蕾", "洋": "扬", "勇": "涌", "娟": "涓", "敏": "闵", "霞": "瑕",
    "平": "萍", "刚": "钢", "英": "应", "玉": "育", "萍": "苹", "红": "虹",
    "玲": "铃", "芬": "纷", "兰": "蓝", "洁": "捷", "颖": "赢", "晶": "京",
    "露": "路", "薇": "微", "梦": "蒙", "瑶": "摇", "佳": "家", "俊": "骏",
    "哲": "折", "睿": "瑞", "博": "伯", "硕": "烁", "聪": "匆", "云": "芸",
    "月": "玥", "星": "兴", "语": "雨", "若": "洛", "诗": "师", "亦": "易",
    "可": "柯", "心": "欣", "思": "丝", "童": "同", "言": "岩", "沐": "木",
    "辰": "晨", "宇": "羽", "轩": "宣", "涵": "含", "然": "燃", "嘉": "家",
    "旭": "绪", "昊": "浩", "天": "田", "龙": "隆", "飞": "非", "翔": "祥",
    "宁": "凝", "怡": "仪", "帅": "率",
}
GIVEN_CHARS = list(GIVEN_CHAR_TYPOS)

# 省 / 自治区 / 直辖市 → 地级行政区划（合计 100+，公司名也复用这批城市）
PROVINCE_CITIES: dict[str, list[str]] = {
    "北京市": ["北京"],
    "上海市": ["上海"],
    "天津市": ["天津"],
    "重庆市": ["重庆"],
    "河北省": ["石家庄", "唐山", "保定", "邯郸", "廊坊", "沧州"],
    "山西省": ["太原", "大同", "长治", "临汾", "运城"],
    "辽宁省": ["沈阳", "大连", "鞍山", "抚顺", "锦州", "营口"],
    "吉林省": ["长春", "吉林", "四平", "通化", "松原"],
    "黑龙江省": ["哈尔滨", "齐齐哈尔", "大庆", "牡丹江", "佳木斯"],
    "江苏省": ["南京", "苏州", "无锡", "常州", "南通", "徐州", "扬州", "盐城",
               "镇江", "泰州", "淮安", "连云港", "宿迁"],
    "浙江省": ["杭州", "宁波", "温州", "嘉兴", "绍兴", "金华", "台州", "湖州",
               "丽水", "衢州", "舟山"],
    "安徽省": ["合肥", "芜湖", "蚌埠", "安庆", "马鞍山", "阜阳", "滁州"],
    "福建省": ["福州", "厦门", "泉州", "漳州", "莆田", "三明", "龙岩"],
    "江西省": ["南昌", "赣州", "九江", "上饶", "宜春", "吉安"],
    "山东省": ["济南", "青岛", "烟台", "潍坊", "淄博", "临沂", "济宁", "泰安",
               "威海", "日照", "德州", "聊城"],
    "河南省": ["郑州", "洛阳", "开封", "南阳", "新乡", "许昌", "安阳", "焦作", "信阳"],
    "湖北省": ["武汉", "宜昌", "襄阳", "荆州", "黄石", "十堰", "荆门"],
    "湖南省": ["长沙", "株洲", "湘潭", "衡阳", "岳阳", "常德", "郴州", "益阳"],
    "广东省": ["广州", "深圳", "珠海", "佛山", "东莞", "中山", "惠州", "汕头",
               "江门", "湛江", "肇庆", "茂名"],
    "广西壮族自治区": ["南宁", "柳州", "桂林", "北海", "玉林", "梧州"],
    "海南省": ["海口", "三亚"],
    "四川省": ["成都", "绵阳", "德阳", "宜宾", "南充", "泸州", "乐山", "内江"],
    "贵州省": ["贵阳", "遵义", "六盘水", "安顺", "毕节"],
    "云南省": ["昆明", "曲靖", "玉溪", "大理", "丽江", "红河"],
    "陕西省": ["西安", "宝鸡", "咸阳", "渭南", "榆林", "汉中"],
    "甘肃省": ["兰州", "天水", "白银", "酒泉", "庆阳"],
    "青海省": ["西宁", "海东"],
    "内蒙古自治区": ["呼和浩特", "包头", "鄂尔多斯", "赤峰", "通辽"],
    "宁夏回族自治区": ["银川", "石嘴山", "吴忠"],
    "新疆维吾尔自治区": ["乌鲁木齐", "克拉玛依", "喀什", "伊宁"],
    "西藏自治区": ["拉萨", "日喀则"],
    "香港特别行政区": ["香港"],
    "澳门特别行政区": ["澳门"],
}

# 区县名（通用型：多座城市真实存在同名区，配任何城市都不违和）
DISTRICT_POOL = ["城关区", "新城区", "东城区", "西城区", "朝阳区", "鼓楼区",
                 "滨江区", "高新区", "经济开发区", "城南区", "城北区", "城东区",
                 "城西区", "河东区", "河西区", "江南区", "江北区", "市中区",
                 "市南区", "市北区", "新区", "开发区", "高新技术产业开发区", "中山区"]

ROAD_POOL = ["人民路", "中山路", "解放路", "建设路", "新华路", "长江路", "黄河路",
             "北京路", "文化路", "光明路", "幸福路", "和平路", "青年路", "迎宾大道",
             "世纪大道", "科技大道", "创业路", "兴业路", "环城路", "滨江路",
             "花园路", "学院路", "朝阳路", "民主路", "团结路", "胜利路", "育才路",
             "振兴路", "富民路", "望江路"]

# 手机号段（现行有效性不作校验，只保证号段形状真实）
PHONE_PREFIXES = [
    "130", "131", "132", "133", "134", "135", "136", "137", "138", "139",
    "145", "147", "149",
    "150", "151", "152", "153", "155", "156", "157", "158", "159",
    "165", "166", "167",
    "170", "171", "172", "173", "175", "176", "177", "178",
    "180", "181", "182", "183", "184", "185", "186", "187", "188", "189",
    "190", "191", "192", "193", "195", "196", "197", "198", "199",
]

# 公司字号（两字，像真品牌名）
BRAND_WORDS = [
    "云栖", "华宇", "恒信", "天工", "明远", "卓越", "盛世", "华夏", "东方", "中天",
    "联创", "启明", "拓普", "博远", "弘毅", "智联", "汇通", "远景", "星河", "蓝海",
    "绿洲", "磐石", "天翼", "木森", "宏图", "万邦", "精诚", "拓维", "新元", "昌隆",
    "益丰", "广厦", "润泽", "开元", "鼎盛", "立信", "卓远", "光谷", "未来", "云图",
    "数联", "智远", "慧通", "环宇", "泰和", "恒通", "众诚", "一诺", "金诚", "众和",
    "星辰", "岩松", "清源", "嘉禾", "骏驰", "鹏程", "思创", "维信", "中科", "天成",
    "瑞泰", "德胜", "信达", "康泰", "鑫源", "利丰", "华瑞", "润和", "三江", "九鼎",
]

# 公司行业词 / 组织形式
INDUSTRY_WORDS = ["科技", "网络", "信息", "教育", "文化", "传媒", "贸易", "实业",
                  "电子", "生物", "医药", "环保", "智能", "数据", "软件", "物流",
                  "供应链", "建筑", "机械", "食品", "农业", "新能源", "数智", "咨询"]
COMPANY_SUFFIXES = ["有限公司", "有限责任公司", "股份有限公司", "集团有限公司"]

# ============================================================ 错别字表（各字段）

# 地址：这些字几乎必现（市/区/路/号），保证 typo 一定可造
ADDRESS_TYPOS = {
    "市": "式", "区": "曲", "路": "露", "号": "豪", "栋": "洞", "室": "式",
    "楼": "搂", "城": "诚", "湖": "胡", "州": "洲", "阳": "杨", "江": "姜",
    "山": "杉", "新": "欣", "东": "冬", "西": "茜", "南": "楠", "北": "贝",
    "大": "太", "道": "到", "街": "介", "苑": "园", "滨": "宾", "桥": "乔",
}
# 公司：靠「公/司/有/限」兜底，保证每家公司名都能造 typo
COMPANY_TYPOS = {
    "公": "工", "司": "词", "有": "友", "限": "线", "责": "则", "份": "分",
    "集": "积", "团": "困", "技": "记", "易": "意", "业": "叶", "络": "落",
    "信": "芯", "息": "希", "电": "店", "子": "宇", "智": "志", "咨": "资",
}
# 电话：数字 → 形近字母（首位必为 1，保证可造）
PHONE_TYPOS = {"0": "O", "1": "l", "2": "Z", "3": "E", "5": "S", "8": "B"}

# 金额 / 日期：0–9 全量数字 → 形近字母（OCR 常见；保证任意数值串都能造 typo）
DIGIT_TYPOS = {"0": "O", "1": "l", "2": "Z", "3": "E", "4": "A",
               "5": "S", "6": "G", "7": "T", "8": "B", "9": "q"}
# 身份证：只用数字表（校验码可能是 X，不在表内 ⇒ 天然不被 typo 命中）
IDCARD_TYPOS = DIGIT_TYPOS

# 邮箱：user = 小写字母 + 数字；domain = 固定常见域（com/cn/net/org/edu 都在）
EMAIL_LOCAL_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
EMAIL_DOMAINS = ["gmail.com", "qq.com", "163.com", "126.com", "sina.com", "sohu.com",
                 "foxmail.com", "outlook.com", "hotmail.com", "yahoo.com", "aliyun.com",
                 "139.com", "189.cn", "example.com", "company.net", "school.edu",
                 "test.org", "mail.cn"]
# 邮箱：数字 ↔ 形近字母（双向；任意域名里都有可替换字，保证「至少 1 处」恒成立）
EMAIL_TYPOS = {"0": "o", "1": "l", "2": "z", "5": "s", "6": "g", "8": "b",
               "o": "0", "l": "1", "z": "2", "s": "5", "g": "6", "b": "8"}

SEPARATORS = ["-", "·", "|", "／", "，"]
SPACES = [" ", "　"]  # 半角 / 全角

# 冗余噪声：前缀标签 / 后缀称谓 / 尾随标点
NOISE_AFFIXES: dict[str, list[tuple[str, str]]] = {
    "person": [("姓名：", "prefix"), ("名字:", "prefix"), ("先生", "suffix"),
               ("女士", "suffix"), ("老师", "suffix"), ("（本人）", "suffix")],
    "address": [("地址：", "prefix"), ("住址:", "prefix"), ("（收货地址）", "suffix"),
                ("（已搬迁）", "suffix"), ("（老地址）", "suffix"), ("。", "suffix")],
    "phone": [("电话：", "prefix"), ("手机:", "prefix"), ("（微信同号）", "suffix"),
              ("（本人）", "suffix"), ("（备用）", "suffix"), ("。", "suffix")],
    "company": [("单位：", "prefix"), ("公司名称:", "prefix"), ("（总部）", "suffix"),
                ("（原单位）", "suffix"), ("（分公司）", "suffix"), ("。", "suffix")],
    "amount": [("金额：", "prefix"), ("金额:", "prefix"), ("费用：", "prefix"),
               ("（含税）", "suffix"), ("（未税）", "suffix"), ("。", "suffix")],
    "date": [("日期：", "prefix"), ("日期:", "prefix"), ("（录入日期）", "suffix"),
             ("（生效日）", "suffix"), ("。", "suffix")],
    "idcard": [("身份证号：", "prefix"), ("身份证:", "prefix"), ("证件号：", "prefix"),
               ("（复印件）", "suffix"), ("（本人）", "suffix"), ("。", "suffix")],
    "email": [("邮箱：", "prefix"), ("邮箱:", "prefix"), ("Email:", "prefix"),
              ("（工作邮箱）", "suffix"), ("（常用）", "suffix"), ("。", "suffix")],
}

FIELDS = ("person", "address", "phone", "company", "amount", "date", "idcard", "email")
PERTURBATIONS = ("space", "typo", "abbrev", "sep", "noise")

# ============================================================ 干净值生成


def gen_person(rng: random.Random) -> tuple[str, list[str]]:
    """生成人名：单姓/复姓 + 双字名。返回 (值, 结构段)。"""
    surname = rng.choice(SURNAMES + COMPOUND_SURNAMES)
    given = "".join(rng.choice(GIVEN_CHARS) for _ in range(2))
    return surname + given, [surname, given]


def gen_address(rng: random.Random) -> tuple[str, list[str]]:
    """生成地址：省 + 市(+区) + 路名 + 门牌 [ + 楼栋]。返回 (值, 结构段)。"""
    province, cities = rng.choice(list(PROVINCE_CITIES.items()))
    city = rng.choice(cities)
    parts = [province]
    # 直辖市 / 港澳：市名已含在行政区名里，不重复加
    if city not in province:
        parts.append(city + "市")
    parts.append(rng.choice(DISTRICT_POOL))
    parts.append(rng.choice(ROAD_POOL))
    parts.append(f"{rng.randint(1, 1999)}号")
    if rng.random() < 0.6:
        parts.append(f"{rng.randint(1, 30)}栋{rng.randint(1, 6)}单元{rng.randint(101, 2508)}室")
    return "".join(parts), parts


def gen_phone(rng: random.Random) -> tuple[str, list[str]]:
    """生成手机号：3 位号段 + 4 + 4。返回 (值, 结构段)。"""
    prefix = rng.choice(PHONE_PREFIXES)
    mid = f"{rng.randint(0, 9999):04d}"
    tail = f"{rng.randint(0, 9999):04d}"
    return prefix + mid + tail, [prefix, mid, tail]


def gen_company(rng: random.Random) -> tuple[str, list[str]]:
    """生成公司名：城市 + 字号 + 行业 + 组织形式。返回 (值, 结构段)。"""
    cities = [c for cs in PROVINCE_CITIES.values() for c in cs]
    city = rng.choice(cities)
    brand = rng.choice(BRAND_WORDS)
    industry = rng.choice(INDUSTRY_WORDS)
    suffix = rng.choice(COMPANY_SUFFIXES)
    return f"{city}{brand}{industry}{suffix}", [city, brand, industry, suffix]


def _group(numeral: str) -> str:
    """给数字串的整数部分加千分位（半角逗号）；传入已带逗号的串也能用。"""
    intpart, dot, frac = numeral.partition(".")
    return f"{int(intpart.replace(',', '')):,}" + dot + frac


def gen_amount(rng: random.Random) -> tuple[str, list[str]]:
    """生成金额：数值 + 「元」；形态含整数 / 小数(1–2 位)。返回 (值, 结构段)。

    干净值**一律纯数字、不带千分位**（TASK-020 §2.5-A）：千分位只作为 `sep` 扰动出现，
    与规则侧闸门 `^\\d+(\\.\\d+)?元$` 自洽 —— 否则两种干净形态会把单值 normalize 锁死。
    **小数末位取 1–9**（TASK-021）：尾随零（`88982.0`）是冗余写法，万元记法经 float 后
    必然丢失该位 ⇒ truth 与规范值逐字符不等。排除末位零后 amount 可无损回环。
    """
    intpart = rng.randint(1, 9_999_999)
    numeral = str(intpart)
    ndigits = rng.choice([0, 0, 1, 2])  # 多数整数，少数带小数
    if ndigits:
        digits = [str(rng.randint(0, 9)) for _ in range(ndigits - 1)]
        digits.append(str(rng.randint(1, 9)))  # 末位 1–9：杜绝尾随零
        numeral += "." + "".join(digits)
    return numeral + "元", [numeral, "元"]


def gen_date(rng: random.Random) -> tuple[str, list[str]]:
    """生成 ISO 日期 YYYY-MM-DD（1970–2026，日取 1–28 避开月长问题）。返回 (值, 结构段)。"""
    y = rng.randint(1970, 2026)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}", [str(y), f"{m:02d}", f"{d:02d}"]


# GB 11643-1999 校验码：前 17 位加权求和 mod 11 → 查表（'10X98765432'）
_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK_CODES = "10X98765432"


def _id_check_digit(first17: str) -> str:
    """算第 18 位校验码（GB 11643-1999 加权因子 + mod 11 查表）。"""
    total = sum(int(ch) * w for ch, w in zip(first17, _ID_WEIGHTS))
    return _ID_CHECK_CODES[total % 11]


def gen_idcard(rng: random.Random) -> tuple[str, list[str]]:
    """生成 18 位身份证号（GB 11643 形态，组合合成）：6 地区码 + 8 生日 + 3 顺序码 + 1 校验码。

    - 地区码以「11」打头（北京，合法结构即可，不做真实性查询）；
    - **生日取 1970–1999**：TASK-023 §2.5 既写「生日同 date 范围」又写 abbrev「19xx 年补『19』」，
      取两者交集（同 date 的月/日范围 + 19xx 世纪）才能让 18↔15 缩写无损可逆（见 RESULT-023 §5）；
    - 校验码按 GB 11643 真实算法算，让规则侧的格式闸门有的放矢。
    """
    region = f"11{rng.randint(0, 9999):04d}"
    y = rng.randint(1970, 1999)
    birthday = f"{y:04d}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"
    seq = f"{rng.randint(0, 999):03d}"
    first17 = region + birthday + seq
    check = _id_check_digit(first17)
    return first17 + check, [region, birthday, seq, check]


def gen_email(rng: random.Random) -> tuple[str, list[str]]:
    """生成邮箱 user@domain——user 为 3–12 位字母数字混合（字母开头且含数字），domain 取固定常见域。"""
    n = rng.randint(3, 12)
    for _ in range(1000):
        user = "".join(rng.choice(EMAIL_LOCAL_CHARS) for _ in range(n))
        if user[0].isalpha() and any(c.isdigit() for c in user):
            break
    else:
        raise RuntimeError("造不出「字母开头且含数字」的邮箱用户名")
    domain = rng.choice(EMAIL_DOMAINS)
    return f"{user}@{domain}", [user, domain]


GENERATORS = {"person": gen_person, "address": gen_address, "phone": gen_phone,
              "company": gen_company, "amount": gen_amount, "date": gen_date,
              "idcard": gen_idcard, "email": gen_email}

# ============================================================ 扰动

def _choose(rng: random.Random, candidates: list[str], clean: str) -> str:
    """从候选里挑一个与干净值不同的写法；全废则报错（生成器有 bug）。"""
    ok = [c for c in candidates if c and c != clean]
    if not ok:
        raise ValueError(f"造不出与干净值不同的扰动：{clean!r}")
    return rng.choice(ok)


def _space(rng: random.Random, value: str) -> str:
    """加空格（半角或全角），插在中间某处。"""
    cut = rng.randint(1, len(value) - 1)
    return value[:cut] + rng.choice(SPACES) + value[cut:]


def _typo_at(rng: random.Random, s: str, mapping: dict[str, str]) -> str:
    """在 s 里挑一个可替换的字，换成表里的错别字。"""
    hits = [i for i, ch in enumerate(s) if ch in mapping]
    if not hits:
        raise ValueError(f"串里没有可替换的字（错别字表未覆盖）：{s!r}")
    i = rng.choice(hits)
    return s[:i] + mapping[s[i]] + s[i + 1:]


def _sep(rng: random.Random, parts: list[str]) -> str:
    """在结构边界插分隔符。"""
    return rng.choice(SEPARATORS).join(parts)


def _noise(rng: random.Random, value: str, affixes: list[tuple[str, str]]) -> str:
    """前缀标签 / 后缀称谓 / 尾随标点。"""
    affix, where = rng.choice(affixes)
    return affix + value if where == "prefix" else value + affix


def perturb_person(rng: random.Random, value: str, parts: list[str]) -> dict[str, str]:
    surname, given = parts
    return {
        "space": _space(rng, value),
        "typo": surname + _typo_at(rng, given, GIVEN_CHAR_TYPOS),
        # 简称：省掉名里的一个字（「王小明」→「王明」）
        "abbrev": _choose(rng, [surname + given[:i] + given[i + 1:] for i in range(len(given))], value),
        "sep": _sep(rng, parts),
        "noise": _noise(rng, value, NOISE_AFFIXES["person"]),
    }


def perturb_address(rng: random.Random, value: str, parts: list[str]) -> dict[str, str]:
    province = parts[0]  # 省级段（可能带「省 / 市 / 自治区 / 特别行政区」）
    abbrev_candidates = [
        value[len(province):],                            # 去掉整个省级段
        value.replace("省", "", 1),                       # 去掉「省」字样
        value.replace("省", "", 1).replace("市", "", 1),  # 去掉「省」「市」字样
    ]
    return {
        "space": _space(rng, value),
        "typo": _typo_at(rng, value, ADDRESS_TYPOS),
        "abbrev": _choose(rng, abbrev_candidates, value),
        "sep": _sep(rng, parts),
        "noise": _noise(rng, value, NOISE_AFFIXES["address"]),
    }


def perturb_phone(rng: random.Random, value: str, parts: list[str]) -> dict[str, str]:
    return {
        "space": _space(rng, value),
        "typo": _typo_at(rng, value, PHONE_TYPOS),  # 数字→形近字母（OCR 常见）
        # 后缀变异：补国家码（86 / +86 / 086）
        "abbrev": _choose(rng, ["86" + value, "+86" + value, "086" + value], value),
        "sep": _sep(rng, parts),
        "noise": _noise(rng, value, NOISE_AFFIXES["phone"]),
    }


def perturb_company(rng: random.Random, value: str, parts: list[str]) -> dict[str, str]:
    city, _brand, _industry, suffix = parts
    abbrev_candidates = [
        value.replace("股份有限公司", "股份公司", 1),   # 组织形式简化
        value.replace("有限责任公司", "有限公司", 1),   # 组织形式简化
        value[len(city):],                              # 去掉城市前缀
        value[: -len(suffix)],                          # 去掉组织形式后缀
    ]
    return {
        "space": _space(rng, value),
        "typo": _typo_at(rng, value, COMPANY_TYPOS),
        "abbrev": _choose(rng, abbrev_candidates, value),
        "sep": _sep(rng, parts),
        "noise": _noise(rng, value, NOISE_AFFIXES["company"]),
    }


def _wan(numeral: str) -> str:
    """把数值改写成「万元」记法（如 12800 → 1.28万元）。

    用 `:.10g` 保留足够有效位（旧版 `:.4f` 会截断，带小数金额 ×10000 后还原不回去，
    见 RESULT-019 §5-B）；`%g` 自带去尾零。数值 ≥ 1 元 ⇒ 结果 ≥ 0.0001，不会走科学计数法。
    TASK-020 §2.5-B：本单只改生成器，规则侧 `_expand_wan` 不动。
    """
    n = float(numeral.replace(",", ""))
    return f"{n / 10000:.10g}" + "万元"


def _insert_sep(rng: random.Random, s: str) -> str:
    """在数字串里乱插一个千分位分隔符（半角/全角逗号）。"""
    i = rng.randint(1, max(1, len(s) - 1))
    return s[:i] + rng.choice([",", "，"]) + s[i:]


def perturb_amount(rng: random.Random, value: str, parts: list[str]) -> dict[str, str]:
    numeral = parts[0]
    return {
        "space": _space(rng, value),
        "typo": _typo_at(rng, value, DIGIT_TYPOS),   # 数字→形近字母（OCR 常见）
        # 单位缩写：元 → 万元（如 12800 元 → 1.28 万元）
        "abbrev": _choose(rng, [_wan(numeral)], value),
        # 千分位分隔符乱：正确分组 / 去分组 / 乱插分隔符（候选必有一个 ≠ 干净值）
        "sep": _choose(rng, [_group(numeral) + "元", numeral.replace(",", "") + "元",
                             _insert_sep(rng, numeral) + "元"], value),
        "noise": _noise(rng, value, NOISE_AFFIXES["amount"]),
    }


def perturb_date(rng: random.Random, value: str, parts: list[str]) -> dict[str, str]:
    y, m, d = parts
    return {
        "space": _space(rng, value),
        "typo": _typo_at(rng, value, DIGIT_TYPOS),   # 数字→形近字母
        # 缩写：缺零（2026-1-5）/ 缺年（1-5）/ 年月（2026-10）
        "abbrev": _choose(rng, [f"{int(y)}-{int(m)}-{int(d)}",
                                f"{int(m)}-{int(d)}",
                                f"{int(y)}-{int(m)}"], value),
        # 分隔符变体：/ . ／
        "sep": _choose(rng, [value.replace("-", "/"), value.replace("-", "."),
                             value.replace("-", "／")], value),
        "noise": _noise(rng, value, NOISE_AFFIXES["date"]),
    }


def perturb_idcard(rng: random.Random, value: str, parts: list[str]) -> dict[str, str]:
    region, birthday, seq, check = parts
    return {
        "space": _space(rng, value),                 # 段间 / 数字间空格
        "typo": _typo_at(rng, value, IDCARD_TYPOS),  # 数字→形近字母（校验位 X 不在表内，不受影响）
        # 缩写：18 位 → 15 位老证（丢掉世纪「19」与校验码）：RRRRRR + YYMMDD + SSS
        "abbrev": region + birthday[2:] + seq,
        # 分隔：只给生日段加分隔（19900315 → 1990-03-15）
        "sep": region + f"{birthday[:4]}-{birthday[4:6]}-{birthday[6:]}" + seq + check,
        "noise": _noise(rng, value, NOISE_AFFIXES["idcard"]),
    }


def _insert_local_sep(rng: random.Random, user: str) -> str:
    """在邮箱用户名里插一个多余的点 / 下划线。"""
    i = rng.randint(1, max(1, len(user) - 1))
    return user[:i] + rng.choice([".", "_"]) + user[i:]


def perturb_email(rng: random.Random, value: str, parts: list[str]) -> dict[str, str]:
    user, domain = parts
    head, tld = domain.rsplit(".", 1)
    return {
        "space": user + rng.choice([" @", "@ "]) + domain,   # @ 前后空格
        "typo": _typo_at(rng, value, EMAIL_TYPOS),           # 数字↔形近字母（至少 1 处）
        # 缩写：去 TLD 末位（.com → .co）/ 去整个 TLD（@gmail.com → @gmail）；不可恢复靠不猜
        "abbrev": _choose(rng, [f"{user}@{head}.{tld[:-1]}", f"{user}@{head}"], value),
        # 分隔：user 里插多余的点 / 下划线
        "sep": f"{_insert_local_sep(rng, user)}@{domain}",
        "noise": _noise(rng, value, NOISE_AFFIXES["email"]),
    }


PERTURBERS = {"person": perturb_person, "address": perturb_address,
              "phone": perturb_phone, "company": perturb_company,
              "amount": perturb_amount, "date": perturb_date,
              "idcard": perturb_idcard, "email": perturb_email}

# ============================================================ 组装与落盘


def _unique_value(rng: random.Random, field: str, used: set[str]) -> tuple[str, list[str]]:
    """拒绝采样拿到不重复的干净值。"""
    for _ in range(20000):
        value, parts = GENERATORS[field](rng)
        if value not in used:
            used.add(value)
            return value, parts
    raise RuntimeError(f"{field} 词典太小：20000 次都没造出唯一值")


def build(seed: int, per_field: int, split_ratio: float) -> dict[str, dict[str, list[dict]]]:
    """生成各字段干净集 + 脏集，并按 id 确定性划分 train / heldout。"""
    out: dict[str, dict[str, list[dict]]] = {}
    for field in FIELDS:
        rng = random.Random(f"{seed}:{field}")  # 每字段独立流：字段间互不影响顺序
        used: set[str] = set()
        clean_rows: list[dict] = []
        variants: list[tuple[str, dict[str, str]]] = []
        for i in range(1, per_field + 1):
            value, parts = _unique_value(rng, field, used)
            rid = f"{field}-{i:04d}"
            clean_rows.append({"id": rid, "field": field, "value": value})
            dirty = PERTURBERS[field](rng, value, parts)
            for ptype in PERTURBATIONS:  # 五类各造一条，顺序固定 ⇒ 输出确定
                if dirty[ptype] == value:
                    raise ValueError(f"{field} {rid} 的 {ptype} 扰动没有改变值")
                variants.append((rid, {"value": dirty[ptype], "truth": value,
                                       "perturbation": ptype}))

        # 划分：按 id 洗牌，前 split-ratio 为 heldout
        shuffled = [r["id"] for r in clean_rows]
        rng.shuffle(shuffled)
        n_heldout = round(per_field * split_ratio)
        heldout = set(shuffled[:n_heldout])
        split_of = {r["id"]: ("heldout" if r["id"] in heldout else "train")
                    for r in clean_rows}

        dirty_rows = [{"id": rid, "field": field, **body, "split": split_of[rid]}
                      for rid, body in variants]
        out[field] = {"clean": clean_rows, "dirty": dirty_rows, "split_of": split_of}
    return out


def dump(path: Path, rows: list[dict]) -> None:
    """写 jsonl：utf-8 + LF + ensure_ascii=False（逐字节可复现）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(data: dict[str, dict[str, list[dict]]]) -> str:
    """每类每 split 的行数汇总（stdout 用）。"""
    lines = [f"{'field':<9}{'split':<9}{'clean':>7}{'dirty':>7}"]
    for field in FIELDS:
        for split in ("train", "heldout"):
            clean = sum(1 for s in data[field]["split_of"].values() if s == split)
            dirty = sum(1 for r in data[field]["dirty"] if r["split"] == split)
            lines.append(f"{field:<9}{split:<9}{clean:>7}{dirty:>7}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 benchmark 干净集/脏集（确定性）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")
    parser.add_argument("--per-field", type=int, default=200, help="每类干净值条数（默认 200）")
    parser.add_argument("--split-ratio", type=float, default=0.2,
                        help="heldout 占比（默认 0.2）")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent),
                        help="输出根目录（默认 benchmarks/）")
    args = parser.parse_args(argv)
    if args.per_field < 1:
        parser.error("--per-field 必须 >= 1")
    if not 0.0 <= args.split_ratio < 1.0:
        parser.error("--split-ratio 必须落在 [0, 1)")

    data = build(args.seed, args.per_field, args.split_ratio)
    out_root = Path(args.out)
    for field in FIELDS:
        dump(out_root / "clean" / f"{field}.jsonl", data[field]["clean"])
        dump(out_root / "dirty" / f"{field}.jsonl", data[field]["dirty"])
    print(f"seed={args.seed} per_field={args.per_field} split_ratio={args.split_ratio}")
    print(f"out={out_root}")
    print(summarize(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""地址规则的不变式测试。

F: space/sep/noise 三类结构清洗代表用例；行政区划标记补全（可无歧义补的）；
   不可靠 abbrev 不猜；通用错字修复 + 三条单字守卫的**误伤回归**；
   置信度 ∈ [0,1]；「值已规范 0.95」档（TASK-015）；address 已注册且其余字段不受影响
R: src/zhclean/rules/address.py、src/zhclean/rules/__init__.py
A: uv run --project . pytest tests/ -q
S: 只测规则与注册表，不测评测管线内部（那在 test_evaluate.py）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import zhclean` 不依赖 pytest 的启动方式

import zhclean  # noqa: E402

# 一个规范地址（省 贵州 + 市 贵阳 + 区 城关 + 路 建设 + 门牌 596号），下面用例的真值
VALID = "贵州省贵阳市城关区建设路596号"
VALID_ROOM = "贵州省贵阳市城关区建设路596号1栋6单元241室"

# ---------- space：去掉串内所有空白（半角 / 全角） ----------

@pytest.mark.parametrize("dirty", ["贵州省贵阳市城关区建设路 596号", "贵州省　贵阳市　城关区　建设路596号",
                                   "贵 州 省 贵 阳 市 城 关 区 建 设 路 5 9 6 号", " 贵州省贵阳市城关区建设路596号 "])
def test_space_stripped(dirty):
    assert zhclean.normalize(dirty, "address") == VALID


# ---------- sep：去掉分隔符（省/市/区/路/门牌之间） ----------

@pytest.mark.parametrize("dirty", ["贵州省-贵阳市-城关区-建设路-596号", "贵州省·贵阳市·城关区·建设路596号",
                                   "贵州省|贵阳市|城关区|建设路596号", "贵州省／贵阳市／城关区／建设路596号",
                                   "贵州省，贵阳市，城关区，建设路596号"])
def test_sep_stripped(dirty):
    assert zhclean.normalize(dirty, "address") == VALID


# ---------- noise：去前缀标签 / 尾部括号备注 / 尾随标点 ----------

@pytest.mark.parametrize("dirty", ["地址：贵州省贵阳市城关区建设路596号", "住址:贵州省贵阳市城关区建设路596号",
                                   "贵州省贵阳市城关区建设路596号（收货地址）", "贵州省贵阳市城关区建设路596号（已搬迁）",
                                   "贵州省贵阳市城关区建设路596号（收货）", "贵州省贵阳市城关区建设路596号。"])
def test_noise_stripped(dirty):
    assert zhclean.normalize(dirty, "address") == VALID


# ---------- 结构清洗命中即高置信（0.9） ----------

@pytest.mark.parametrize("dirty", ["贵州省贵阳市城关区建设路 596号", "贵州省-贵阳市-城关区-建设路-596号",
                                   "地址：贵州省贵阳市城关区建设路596号", "贵州省贵阳市城关区建设路596号。"])
def test_structural_hit_is_high_confidence(dirty):
    value, conf = zhclean.normalize_with_confidence(dirty, "address")
    assert value == VALID
    assert conf == pytest.approx(0.9)


# ---------- abbrev：只补「串里已写着、只缺标记字」的行政区划 ----------

@pytest.mark.parametrize("dirty,expected", [
    ("贵州贵阳城关区建设路596号", "贵州省贵阳市城关区建设路596号"),          # 省、市都缺后缀
    ("广西梧州滨江区新华路1号", "广西壮族自治区梧州市滨江区新华路1号"),      # 自治区全称
    ("内蒙古呼和浩特回民区新华西街1号", "内蒙古自治区呼和浩特市回民区新华西街1号"),
    ("西藏拉萨城关区北京中路1号", "西藏自治区拉萨市城关区北京中路1号"),
    ("北京海淀区中关村路1号", "北京市海淀区中关村路1号"),                    # 直辖市
])
def test_ambiguous_free_abbrev_expanded(dirty, expected):
    value, conf = zhclean.normalize_with_confidence(dirty, "address")
    assert value == expected
    assert conf == pytest.approx(0.7)


@pytest.mark.parametrize("dirty", [
    "贵阳市城关区建设路596号",                    # 整段省级单位被删：无从知道原省 ⇒ 不可恢复
    "深圳市南山区科技园2栋3单元401室",            # 同上（去省段）
    "海淀中关村路1号",                            # 区名不在闭集（海淀不是地级市）⇒ 不补省
    "吉林市船营区北京路1号",                      # 「吉林」省名同市名，已是市 ⇒ 不补成「吉林省」
    "香港特别行政区中西区皇后大道1号",            # 已带后缀 ⇒ 不重复补
])
def test_unreliable_abbrev_not_guessed(dirty):
    # 不猜：值原样返回（仍成立）；置信度 0.95 = 「像合法地址」而非「处理不了」。
    # ⚠ 已知语义阴影（TASK-015 契约的副作用，见 RESULT-015 §5）：「去省段」型（前两条）
    #    真值其实不等于原值，却因 _looks_like_address 只判「有数字 + 有标记字」而落 0.95。
    assert zhclean.normalize_with_confidence(dirty, "address") == (dirty, 0.95)


def test_looks_valid_but_truncated_reports_clean_shadow():
    """把上面那条阴影**显式钉住**：值没被改（正确），但置信度 0.95 声称「已规范」（过誉）。

    TASK-015 契约要求判据用「已有的 _looks_like_*」，故这是**照契约实现**的预期结果，
    不是回归。若日后收严 `_looks_like_address`（如要求含省段 / 要求以号室结尾），
    本用例应随之改；改前它是「已知阴影」的守卫，防止有人误以为 0.95 ⇒ 一定正确。
    """
    truncated = "贵阳市城关区建设路596号"          # 真值应为「贵州省」+ 此串
    value, conf = zhclean.normalize_with_confidence(truncated, "address")
    assert (value, conf) == (truncated, 0.95)     # 没猜（值不变），但报了「已规范」
    assert value != "贵州省" + truncated          # 真值确实没被恢复 —— 阴影在此


# ---------- typo：行政区划名 / 道路门牌结构字的通用错字修复 ----------
# 通用知识收表，不针对测试扰动裁剪；安全性由推断层闸门保证。

@pytest.mark.parametrize("dirty,expected", [
    ("浙江省杭州市西湖区长江路180豪", "浙江省杭州市西湖区长江路180号"),        # 豪 → 号
    ("贵州省贵阳市城关区建设露596号", VALID),                                  # 露 → 路
    ("湖北省武汉市洪山区452号23洞2单元145室", "湖北省武汉市洪山区452号23栋2单元145室"),  # 洞 → 栋
    ("山西省太原市世纪大到899号", "山西省太原市世纪大道899号"),                # 到 → 道
    ("山西省太原市世纪太道101号", "山西省太原市世纪大道101号"),                # 太 → 大
    ("湖北省武汉市江北曲人民路758号", "湖北省武汉市江北区人民路758号"),        # 曲 → 区
    ("福建省漳洲市高新区环城路1号", "福建省漳州市高新区环城路1号"),            # 洲 → 州
    ("青海省茜宁市高新区学院路1号", "青海省西宁市高新区学院路1号"),            # 茜 → 西
    ("安徽省安庆式朝阳区黄河路12号", "安徽省安庆市朝阳区黄河路12号"),          # 式 → 市
    ("山东省青岛市宾江区新华路1号", "山东省青岛市滨江区新华路1号"),            # 宾 → 滨
    ("重庆市河冬区建设路16号", "重庆市河东区建设路16号"),                      # 冬 → 东
    ("湖南省岳阳市西诚区育才路16号", "湖南省岳阳市西城区育才路16号"),          # 诚 → 城
    ("湖南省吉安市高欣区迎宾大道8号", "湖南省吉安市高新区迎宾大道8号"),        # 欣 → 新
    ("湖北省十堰市江楠区北京路19号", "湖北省十堰市江南区北京路19号"),          # 楠 → 南
    ("青海省海东市姜北区振兴路1号", "青海省海东市江北区振兴路1号"),            # 姜 → 江
    ("宁夏回族自治区石嘴杉市河东区世纪路1号", "宁夏回族自治区石嘴山市河东区世纪路1号"),  # 杉 → 山
    ("甘肃省庆杨市开发区建设路1号", "甘肃省庆阳市开发区建设路1号"),            # 杨 → 阳
    ("湖北省荆州市湖贝省道1号", "湖北省荆州市湖北省道1号"),                    # 贝 → 北
])
def test_typos_repaired(dirty, expected):
    assert zhclean.normalize(dirty, "address") == expected


# ---------- 约束②：方位构词的位置约束（TASK-007）----------
# 方位构词（城东 / 河西…）只有后面紧跟「区」或「城」才是行政区名；否则多为小区 / 道路名。
# 出处：TASK-006 §8 脑裁决「保留 15 词 + 加位置约束」，见 RESULT-006 §6-1。

@pytest.mark.parametrize("dirty, expected", [
    ("湖北省武汉市洪山区城茜区建设路1号", "湖北省武汉市洪山区城西区建设路1号"),  # 城西 后跟「区」⇒ 修
    ("重庆市河冬区建设路16号",            "重庆市河东区建设路16号"),             # 河东 后跟「区」⇒ 修
])
def test_district_word_repaired_only_before_district_suffix(dirty, expected):
    assert zhclean.normalize(dirty, "address") == expected


@pytest.mark.parametrize("value", [
    "湖北省武汉市洪山区城冬雅苑3栋1单元101室",   # 城冬 后跟「雅」⇒ 小区名，不修（位置约束挡住）
    "北京市朝阳区城楠花园5号楼302室",            # 楠→南 会造出「城南」，但后跟「花」⇒ 不修
])
def test_district_word_not_repaired_when_not_before_district_suffix(value):
    # 不修（值不变）；置信度 0.95：这些是**合法小区名**，不修=正确 ⇒ 落「值已规范」
    assert zhclean.normalize_with_confidence(value, "address") == (value, 0.95)


def test_one_to_many_typo_disambiguated_by_position():
    # 「式」一对多：串尾且前面是数字 ⇒ 房间号「室」；否则 ⇒ 行政区划「市」
    assert zhclean.normalize("湖北省武汉市洪山区452号23栋2单元145式", "address") == \
        "湖北省武汉市洪山区452号23栋2单元145室"
    assert zhclean.normalize("安徽省安庆式朝阳区黄河路12号", "address") == \
        "安徽省安庆市朝阳区黄河路12号"


def test_typo_confidence_is_infer_level():
    value, conf = zhclean.normalize_with_confidence("浙江省杭州市西湖区长江路180豪", "address")
    assert value == "浙江省杭州市西湖区长江路180号"
    assert conf == pytest.approx(0.7)


# ---------- 三条单字守卫的**误伤回归**：合法的地名/路名必须原样不动 ----------
# 这些不是「干净值」，而是**含错字表中字、但它本身是合法专名**的地址。
# 守卫若失效，这里会被改坏（雨露路→雨路路、洞庭路→栋庭路、曲阜→区阜）。

@pytest.mark.parametrize("value", [
    "贵州省贵阳市雨露路596号1栋6单元241室",   # 守卫 3：露 后面不是数字（路名而非结构字）
    "湖南省岳阳市洞庭路12号",                  # 守卫 3：洞 后面不是数字
    "陕西省西安市报到路8号",                  # 守卫 3：到 后面不是数字
    "重庆市曲阜大道99号",                     # 守卫 1：曲阜 在 _TYPO_GUARD_NAMES
    "云南省曲靖市南区世纪大道1号",            # 守卫 1：曲靖 在 CITY_NAMES
    "广东省深圳市南山区科技园2栋3单元401室",  # 无错字
])
def test_single_char_guards_do_not_damage_real_names(value):
    # 守卫按预期**没动**这些合法专名；置信度 0.95（没改 = 值已规范）
    assert zhclean.normalize_with_confidence(value, "address") == (value, 0.95)


def test_single_char_guards_still_fix_real_typos():
    # 守卫没误挡：真错字照修
    assert zhclean.normalize("贵州省贵阳市城关区建设露596号", "address") == VALID  # 露 后跟数字
    assert zhclean.normalize("湖北省武汉市洪山区452号23洞2单元145室", "address") == \
        "湖北省武汉市洪山区452号23栋2单元145室"                                     # 洞 后跟数字


# ---------- 闸门：洗出来「不像地址」就宁可原样返回 ----------

def test_cleaning_to_non_address_returns_original():
    # 去标签后剩下「你好」，没有数字也不是地址 ⇒ 不返回半成品，原样低置信
    assert zhclean.normalize_with_confidence("地址：你好", "address") == ("地址：你好", 0.1)


def test_address_shape_not_conflated_with_other_fields():
    # 反向：人名 / 电话 / 公司名不该被当地址乱改
    for value in ("王小明", "15745524079", "焦作嘉禾智能有限责任公司"):
        assert zhclean.normalize_with_confidence(value, "address") == (value, 0.1)


# ---------- 值已规范：本就规范的值无改动 ⇒ 0.95（TASK-015 拆档；TASK-004 台账里的待细化项） ----------

def test_clean_value_untouched_and_high_confidence():
    # TASK-015：已规范值不再报 0.1（那是「处理不了」的档），改报 0.95「值已规范」。
    assert zhclean.normalize_with_confidence(VALID, "address") == (VALID, 0.95)
    assert zhclean.normalize_with_confidence(VALID_ROOM, "address") == (VALID_ROOM, 0.95)


# ---------- 置信度必须落在 [0, 1] ----------

@pytest.mark.parametrize("value", ["贵州省贵阳市城关区建设路 596号", VALID, "贵州贵阳城关区建设路596号",
                                   "浙江省杭州市西湖区长江路180豪", "地址：你好", "", "x", "王小明"])
def test_confidence_in_range(value):
    _, conf = zhclean.normalize_with_confidence(value, "address")
    assert 0.0 <= conf <= 1.0


# ---------- 注册表：address 已注册，且 person / phone / company 行为不受影响（回归护栏） ----------

def test_address_registered():
    from zhclean.rules import DISPATCH
    assert "address" in DISPATCH and callable(DISPATCH["address"])


def test_person_unaffected_by_address():
    # 回归：注册 address 后人名清洗行为不变（TASK-003 的三类结构清洗仍全对）
    assert zhclean.normalize("王 小明", "person") == "王小明"
    assert zhclean.normalize("王·小明", "person") == "王小明"
    assert zhclean.normalize("姓名：王小明", "person") == "王小明"
    # 反向：地址不会被当人名
    assert zhclean.normalize_with_confidence(VALID, "person") == (VALID, 0.1)


def test_phone_unaffected_by_address():
    # 回归：注册 address 后电话清洗行为不变（TASK-004 的结构清洗仍全对）
    assert zhclean.normalize("157-4552-4079", "phone") == "15745524079"
    assert zhclean.normalize("电话：15745524079", "phone") == "15745524079"
    assert zhclean.normalize("8615745524079", "phone") == "15745524079"
    # 反向：地址不会被当电话
    assert zhclean.normalize_with_confidence(VALID, "phone") == (VALID, 0.1)


def test_company_unaffected_by_address():
    # 回归：注册 address 后公司名清洗行为不变（TASK-005 的缩写补全仍对）
    assert zhclean.normalize("焦作嘉禾智能 有限责任公司", "company") == "焦作嘉禾智能有限责任公司"
    assert zhclean.normalize("焦作嘉禾智能股份公司", "company") == "焦作嘉禾智能股份有限公司"
    # 反向：地址不会被当公司名
    assert zhclean.normalize_with_confidence(VALID, "company") == (VALID, 0.1)

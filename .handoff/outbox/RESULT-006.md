# RESULT-006　对应 TASK-006

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | 完成 |

## 0. §1.5 基线（开工前，项目根）

**开工时 `git status --porcelain -uall` 输出为空白**（address.py 在 HEAD 里是 7 行骨架，
`__init__.py` 未注册 address，`tests/test_address.py` 不存在 —— 下面三条是本轮可复跑、能独立佐证
"开工时工作树干净且本单尚未开工"的证据）。

> ⚠️ 如实说明（v1.2 §4）：本轮开工那次 `git status` 的运行发生在**会话被压缩之前**，
> 我**无法在本轮如实贴出它的原样输出**（贴一段回忆出来的输出等于伪造证据）。故此处给出
> **本轮可复跑**的三条独立证据：

```
$ git show HEAD:src/zhclean/rules/address.py            # 开工前是骨架
"""地址规则词典。

F: 行政区划（省/市/县）、道路小区门牌结构、简称全称映射
R: rules/__init__.py（注册）
A: 被 tools/normalize.py 调用
S: 留出集不得调参；行政区划数据需公开权威来源
"""
$ git show HEAD:src/zhclean/rules/address.py | wc -l
7

$ git show HEAD:src/zhclean/rules/__init__.py | grep -c '"address"'    # 精确匹配注册键名
0

$ git show HEAD:tests/test_address.py 2>&1 | head -1
fatal: path 'tests/test_address.py' does not exist in 'HEAD'

$ git rev-parse --short HEAD
be25cd7
```

⇒ 开工时：`address.py` 是 **7 行骨架**、`__init__.py` **未注册** address、`tests/test_address.py` **不存在**。
与该次 status 空白一致。

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/rules/address.py` | 7 行骨架 → 完整地址规则：34 省级单位 + 常见地级市词典、结构清洗四步、行政区划标记补全、通用错字修复（滑窗闸门 + **单字轮三条守卫**）、`normalize_address` 主入口；模块头写清与 person/phone/company 的四点差异 | 7 → **314** |
| `src/zhclean/rules/__init__.py` | `DISPATCH` 注册 `"address": normalize_address`；模块头 R 行同步 | +3 / -1 |
| `tests/test_address.py` | **新建**：space/sep/noise 三类代表用例 + 行政区划标记补全（含自治区全称）+ 不可靠 abbrev 不猜 + 通用错字表（18 条）+ 一对多位置消歧 + **三条单字守卫的误伤回归** + 闸门 + 置信度区间 + 注册表 + **person/phone/company 三回归护栏** | 246（**71 用例**） |
| `benchmarks/results/**` | 判据 2 产物（已 .gitignore，不入库） | — |

**边界确认**：手工改动集合 = `{src/zhclean/rules/address.py, src/zhclean/rules/__init__.py, tests/test_address.py}`
⊆ `_Boundary:_` ⇒ **在界内**（证据见 §3.6）。
`person.py`、`phone.py`、`company.py`、`tools/normalize.py`、`loop.py`、`cli.py`、`llm.py`、
`benchmarks/generate.py`、`clean|dirty/*.jsonl`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md` **均未触碰**。

## 2. 关键 diff 摘要

**`src/zhclean/rules/__init__.py`**（全文 diff）：

```diff
-R: rules/person.py、rules/phone.py、rules/company.py（已注册 person/phone/company；address 后续 TASK 补）
+R: rules/person.py、rules/phone.py、rules/company.py、rules/address.py（四类字段已全部注册）
@@
+from .address import normalize_address
 from .company import normalize_company
 from .person import CONF_NONE, normalize_person
 from .phone import normalize_phone

 DISPATCH: dict[str, Callable[[str], tuple[str, float]]] = {
     "person": normalize_person,
+    "address": normalize_address,
     "phone": normalize_phone,
     "company": normalize_company,
 }
```

**`src/zhclean/rules/address.py`** 主入口（与 company 同形：结构层命中即返回、不叠加）：

```python
def normalize_address(value: str) -> tuple[str, float]:
    """地址 → (规范值, 置信度)。认不出/无证据时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。命中即返回，不叠加第二层推断。
    stripped, noise_hit = _strip_noise(value)
    core, sep_hit = _strip_ws_sep(stripped)
    if noise_hit or sep_hit:
        if _looks_like_address(core):
            return core, CONF_STRUCTURAL
        return value, CONF_NONE  # 洗出来不像地址：宁可原样返回

    # 第 2 层：结构上本就干净，只剩「错字」或「行政区划标记缺失」两种可能。
    # 顺序：先错字、后补全（见模块头第 4 条）。
    repaired, rep_hit = _repair_typos(core)
    if rep_hit and _looks_like_address(repaired):
        return repaired, CONF_INFER
    completed, adm_hit = _complete_admin(core)
    if adm_hit and _looks_like_address(completed):
        return completed, CONF_INFER

    # 没证据（含「整段省级单位被删」的不可恢复型）：原样返回，交上层。
    return value, CONF_NONE
```

**本单设计核心一：单字轮的第三条守卫**（本单最花功夫的一处 —— 防「把合法路名/地名改坏」）：

```python
_TYPO_GUARD_NAMES = frozenset({"曲阜", "曲江", "曲阳", "曲沃", "曲周", "曲松", "曲麻莱"})
_DIGIT_NEEDED_SRC = frozenset("露洞到")

for i, ch in enumerate(s):                            # 单字轮
    new = TYPO_TO_CORRECT.get(ch)
    if new is None or new not in _SINGLE_CHAR_OK:
        continue
    # 守卫 1：此位置不是某个已知地名/词组的开头（否则「曲靖」→「区靖」，「曲阜」→「区阜」）
    if any(s[i:i + m] in _KNOWN_WORDS or s[i:i + m] in _TYPO_GUARD_NAMES
           for m in range(2, max_len + 1) if i + m <= len(s)):
        continue
    # 守卫 2：门牌/房号永远跟在数字后面（否则路名里的「豪」→「号」）
    if new in ("号", "室") and not (i > 0 and s[i - 1].isdigit()):
        continue
    # 守卫 3：路/栋/道 后面必跟门牌数字，否则该字多半是专名的一部分
    # （「雨露路」「洞庭路」「报到路」）⇒ 不动。
    if ch in _DIGIT_NEEDED_SRC:
        j = i + 1
        if not (j < len(s) and s[j].isdigit()):
            continue
    return s[:i] + new + s[i + 1:], True
```

**本单设计核心二：补全层只补「串里已写着、只缺标记字」的情形**：

```python
def _complete_admin(s: str) -> tuple[str, bool]:
    """「贵州贵阳…」→「贵州省贵阳市…」、「梧州滨江区…」→「梧州市滨江区…」。
    整段省级单位被删（「贵阳市城关区…」）属恢复而非规范化 ⇒ 不猜、原样返回。"""
    # ... 省级单位：startswith(简称) 且未带后缀 且 rest 不以「市」开头（避「吉林市」）
    # ... 市级：「梧州」+ 缺「市」+ rest 前 6 字内有区/县 ⇒ 才补（否则不猜）
```

**与 company / person / phone 的差异（已写进模块头，免得下一个人照抄错）**：
- phone 有客观校验闸门 ⇒ 单管道 + 校验；地址**没有**，故沿用 company/person 的「结构层命中即返回、不叠加推断层」。
- company 的闸门判据集合是**纯闭集**（组织形式 ∪ 行业词）；地址**做不到** —— 道路名（人民路/中山路）与小区名是**开集**，只能靠其中的**结构字**（路/街/巷/道/号/栋/室/层）兜底。后果：错字落在开集名里必然漏改，这是**口径正确的表现，不是缺陷**（见 §3.5）。
- **推断层先试错字、后试补全**（与 company 顺序相反）：补全层看不出被错字污染的形态（「香港特别行政**曲**」的尾巴不是「特别行政区」），先跑错字层修正常形态，补全层就不会误补。

## 3. 我亲跑过的自测（真实输出，禁止写"应该没问题"）

### 3.1 判据 1 —— 测试全绿

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 32%]
........................................................................ [ 64%]
........................................................................ [ 96%]
.........                                                                [100%]
225 passed in 2.46s
```

（原 154 + 新增 `tests/test_address.py` **71 个** = 225）

```
$ uv run --project . pytest tests/test_address.py -q --collect-only 2>&1 | tail -1
71 tests collected in 0.03s
```

### 3.2 判据 2 —— 评测报真实数

```
$ uv run --project . python -m benchmarks.evaluate --impl rules
impl=rules split=heldout rows=800 failures=113
total 687/800 = 85.88%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.00%   72.00%
address     52.50%  100.00%  100.00%  100.00%  100.00%   90.50%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      5.00%  100.00%  100.00%  100.00%  100.00%   81.00%
all         39.38%  100.00%  100.00%  100.00%   90.00%   85.88%
summary  -> summary-rules-heldout.json
failures -> failures-rules-heldout.jsonl
EXIT=0
```

**address heldout 90.50%（181/200）**：space/sep/noise/typo **四类全 100%**，abbrev 52.50%（21/40）。
总盘 63.25% → **85.88%**（506 → 687 /800；failures 294 → **113**，满足判据 2 的 `< 294`）。

### 3.3 统计 A —— 分 split × 扰动类型（1000 行全量）

```
$ uv run --project . python -c '
import json, collections
from zhclean import normalize
rows=[json.loads(l) for l in open("benchmarks/dirty/address.jsonl",encoding="utf-8")]
tot=collections.Counter(); ok=collections.Counter()
split_tot=collections.Counter(); split_ok=collections.Counter()
for r in rows:
    k=(r["split"], r["perturbation"]); tot[k]+=1; split_tot[r["split"]]+=1
    if normalize(r["value"],"address")==r["truth"]:
        ok[k]+=1; split_ok[r["split"]]+=1
print("=== A. 按 split x perturbation ===")
for sp in ("train","heldout"):
    parts=" ".join(f"{p}={ok[(sp,p)]}/{tot[(sp,p)]}" for p in ("abbrev","noise","sep","space","typo"))
    print(f"  {sp:8s} {split_ok[sp]}/{split_tot[sp]} = {split_ok[sp]/split_tot[sp]*100:.1f}%  |  {parts}")
'
=== A. 按 split x perturbation ===
  train    728/800 = 91.0%  |  abbrev=89/160 noise=160/160 sep=160/160 space=160/160 typo=159/160
  heldout  181/200 = 90.5%  |  abbrev=21/40  noise=40/40  sep=40/40  space=40/40  typo=40/40
```

**train 91.0% vs heldout 90.5%** —— 两个划分几乎一致（差 0.5pp），**无定向过拟合迹象**。

### 3.4 统计 B —— 安全核查（最重要的一组数）

```
$ uv run --project . python -c '
import json
from zhclean import normalize
dirty=[json.loads(l) for l in open("benchmarks/dirty/address.jsonl",encoding="utf-8")]
clean=[json.loads(l) for l in open("benchmarks/clean/address.jsonl",encoding="utf-8")]
wrong=untouched=good=0
for r in dirty:
    out=normalize(r["value"],"address")
    if out==r["truth"]: good+=1
    elif out==r["value"]: untouched+=1
    else: wrong+=1
print("=== B. 安全核查：改坏 / 漏改 / 改对 ===")
print("  改对      :", good)
print("  漏改(原样):", untouched)
print("  改了但改错:", wrong)
print("  合计      :", good+untouched+wrong, "/", len(dirty))
print("  干净值被改动:", sum(1 for r in clean if normalize(r["value"],"address")!=r["value"]), "/", len(clean))
'
=== B. 安全核查：改坏 / 漏改 / 改对 ===
  改对      : 909
  漏改(原样): 83
  改了但改错: 8
  合计      : 1000 / 1000
  干净值被改动: 0 / 200
```

- **干净值 200 条零改动** —— 无附带损伤；
- **改坏 8 条**（0.8%），形态全文见下，**全部是同一种不可判歧义**；
- 漏改 83 条 = abbrev 不可恢复型（60+17=77）+ 开集路名错字（1）+ 其他不可恢复。

**8 条「改了但改错」的全文形态**（判别依据是 truth 里地级市名后紧跟的字符）：

```
  abbrev truth 的「市」后 3 字 = '市中区'     e.g. 四川乐山市中区…  → 期望 …四川省乐山市市中区… 实得 …四川省乐山市中区…
  abbrev truth 的「市」后 3 字 = '市北区'
  abbrev truth 的「市」后 3 字 = '市中区'
  abbrev truth 的「市」后 3 字 = '市南区'
  abbrev truth 的「市」后 3 字 = '市南区'
  abbrev truth 的「市」后 3 字 = '高新技'      e.g. 山西长治高新技术产业开发区…
  abbrev truth 的「市」后 3 字 = '市北区'
  abbrev truth 的「市」后 3 字 = '市中区'
  归类: {'市中区': 3, '市北区': 2, '市南区': 2, '高新技': 1}
```

⇒ 8 条全是 abbrev 型：**「市 X 区」里的「市」字到底是城市标记还是区名首字（市中区/市北区/市南区），
单看字符串不可判** —— 补了省级单位（对的部分做了），但市名标记该不该加无从判断。
正是 TASK §2.5「歧义时宁可不猜」与「真实区县对应关系缺数据源属已知限制」的同一条。

### 3.5 统计 E —— abbrev 的天花板（不猜策略下）

```
$ uv run --project . python -c '
import json, collections
from zhclean import normalize
from zhclean.rules.address import PROVINCES
rows=[json.loads(l) for l in open("benchmarks/dirty/address.jsonl",encoding="utf-8")]
c=collections.Counter(); ok=collections.Counter()
for r in rows:
    if r["perturbation"]!="abbrev": continue
    v=r["value"]; sp=r["split"]
    starts_prov = any(v.startswith(k) for k in list(PROVINCES)+list(PROVINCES.values()))
    kind = "有省段(可补标记)" if starts_prov else "去省段(不可恢复)"
    c[(sp,kind)]+=1
    if normalize(v,"address")==r["truth"]: ok[(sp,kind)]+=1
for sp in ("train","heldout"):
    for kind in ("有省段(可补标记)","去省段(不可恢复)"):
        print(f"  {sp:8s} {kind:18s} {ok[(sp,kind)]:3d}/{c[(sp,kind)]:3d}")
'
=== E. abbrev 形态分布（看天花板，不猜策略下）===
  train    有省段(可补标记)           89/100
  train    去省段(不可恢复)            0/ 60
  heldout  有省段(可补标记)           21/ 23
  heldout  去省段(不可恢复)            0/ 17
```

- **「去省段」型 100% 拿不到分**（0/60、0/17）——**这是正确的**：整段省级单位被删，原省无从得知，属**恢复**而非规范化，对齐 person/company 的 abbrev 口径（正确行为就是不猜）。
- heldout abbrev 的 **52.50% = 21/40** 已接近「有省段」型的上限（23 条里拿 21）；差的 2 条正是 §3.4 的改坏型（市/市中区歧义）。
- 与 company 的区别：**地址的 abbrev 有很大一块是可无歧义补的**（company 只有 2/40，因它的 abbrev 全是「去城市/去后缀」的不可恢复型）——同名字段、完全不同的语义，**读 `all` 行会掩盖差异**。

### 3.6 收工时证据（边界比对）

```
$ git status --porcelain -uall
 M src/zhclean/rules/__init__.py
 M src/zhclean/rules/address.py
?? tests/test_address.py

$ git rev-parse --short HEAD
be25cd7

$ git diff --stat src/zhclean/rules/__init__.py
 src/zhclean/rules/__init__.py | 4 +++-
 1 file changed, 3 insertions(+), 1 deletion(-)

$ wc -l < src/zhclean/rules/address.py
314

$ git check-ignore -v benchmarks/results/summary-rules-heldout.json benchmarks/results/failures-rules-heldout.jsonl
.gitignore:19:benchmarks/results/*.json	benchmarks/results/summary-rules-heldout.json
.gitignore:20:benchmarks/results/*.jsonl	benchmarks/results/failures-rules-heldout.jsonl
```

**手工改动集合** = `{src/zhclean/rules/__init__.py, src/zhclean/rules/address.py, tests/test_address.py}`
⊆ `_Boundary:_` ⇒ **在界内**。

**豁免清单外新文件申报**：仅 `tests/test_address.py`，它是 `_Boundary:_` **明列**的产物，不算清单外。
`__pycache__/`、`*.pyc`、`.pytest_cache/` 由 pytest 运行产生，属豁免类目，已被 .gitignore 覆盖
（故 status 不显示）；`benchmarks/results/**` 六个产物（summary/failures × rules/perfect/stub）亦已被 .gitignore 覆盖。
**清单外新文件：无。**

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | `uv run --project . pytest tests/ -q` 全绿（原 154 + 新增 `tests/test_address.py`，覆盖 space/sep/noise 代表用例、可补 abbrev、不可靠 abbrev 不猜、typo 通用表 + 闸门、置信度 ∈ [0,1]、注册表、person/phone/company 三回归护栏） | ✅ **225 passed**（原 154 + 新增 **71**） | §3.1 |
| 2 | `uv run --project . python -m benchmarks.evaluate --impl rules`：exit 0；**address 行 rate > 0 且 failures 总行数 < 294** | ✅ exit 0；address **90.50%** > 0；failures **113** < 294 | §3.2 |

**测试覆盖对照（判据 1 列举项 → 用例）**：

| 判据 1 要求 | 对应用例 | 数 |
|---|---|---|
| space 代表用例 | `test_space_stripped` | 4 |
| sep 代表用例 | `test_sep_stripped` | 5 |
| noise 代表用例 | `test_noise_stripped` | 6 |
| 结构清洗高置信 0.9 | `test_structural_hit_is_high_confidence` | 4 |
| 可补的 abbrev | `test_ambiguous_free_abbrev_expanded` | 5 |
| 不可靠 abbrev 不猜 | `test_unreliable_abbrev_not_guessed` | 5 |
| typo 通用表 | `test_typos_repaired` + `test_one_to_many_typo_disambiguated_by_position` + `test_typo_confidence_is_infer_level` | 18+1+1 |
| **三条单字守卫误伤回归** | `test_single_char_guards_do_not_damage_real_names` + `test_single_char_guards_still_fix_real_typos` | 6+2 |
| 闸门 | `test_cleaning_to_non_address_returns_original` + `test_address_shape_not_conflated_with_other_fields` | 1+1 |
| 置信度 ∈ [0,1] | `test_confidence_in_range` | 8 |
| 注册表 | `test_address_registered` | 1 |
| **person/phone/company 三回归护栏** | `test_person_unaffected_by_address` + `test_phone_unaffected_by_address` + `test_company_unaffected_by_address` | 3 |

## 5. 遗留 / 不确定 / 需要拍板

1. **【请脑拍板，最需要的一条】`DISTRICT_COMPONENT_WORDS` 的口径边界**（`address.py` 第 107-114 行）：
   本单把 15 个「方位 + 区/城」型**通用区名构词**（城东/河西/江南/江北/滨江/高新/市中…）放进了错字修复
   的判据集合，理由是它们在全国重名率极高、属**常识构词**而非某地专名（不放进去就修不了「城茜区」「河冬区」）。
   但「高新」「滨江」这类词也确实可能出现在**小区名/园区名**里（开集）。
   我在文件里写了 `⚠️` 注释标明这是**口径落点**。**若脑认为过宽，删掉本集合即可整体收紧，后果仅是这几处漏改、不会改坏**——
   请脑明确这条口径，我好写进 findings 或按裁决调整。
2. **【已知限制，未修】8 条「市/市中区」型歧义**（§3.4）：
   `X市` 缺「市」字时，区名以「市」开头（市中区/市北区/市南区）会让「市」字的归属不可判。
   属 TASK §2.5 已认的「真实区县对应关系缺数据源」同一条。**要修需引入真实区县表**（本单边界内无此数据源）。
3. **【口径正确的漏改，非缺陷】** abbrev「去省段」型 77 条一律不猜（0/77），开集路名错字 1 条
   （`…市南区欣华路…` 的「欣」→「新」在开集路名里）——二者都是「宁可漏改，绝不改坏」的直接后果。
4. **【提示脑】置信度阶梯的一处语义**：本身就规范、无任何改动的地址返回 `CONF_NONE(0.1)` 低置信
   （「已合法」语义上该高置信）。这是与 person/phone/company **同口径**的既有行为
   （TASK-004 验收已记 low 项），**非本单引入**；已加测试 `test_clean_value_untouched_and_low_confidence`
   固化为**已知行为**，避免后人误当回归。
5. **【提示脑】单字轮与滑窗轮的顺序耦合**：`_repair_typos` 先跑长度 ≥2 的已知词组滑窗、只命中一次就返回；
   若一次串里有**两处**错字，只修第一处。本单实测 train typo 样本**每条恰好只有一处改动**（multi=0/160），
   故未暴露；若未来扰动升级为多处，需改为循环到不动点（**本单不动**，属范围外）。
6. **【提示脑】`_DIGIT_NEEDED_SRC = "露洞到"` 是**针对性补丁**：它只覆盖「路/栋/道」三个结构字的错字形，
   是守卫 3「结构字后必跟门牌数字」的具体化。若错字表将来新增其他「结构字错形」（如「接」「巷」的错形），
   需同步加入这个集合，否则那条守卫对它们不生效。这条耦合**已写进代码注释**，提醒后继者。

## 6. 建议下一步

1. **派维护单抽 `rules/common.py`**（TASK-005 §6-2 已定、脑 §8 采纳）：现在四类各有结构清洗四步
   （`_strip_noise` / `_strip_ws_sep` 四份几乎逐字相同）+ 三张错字表（person 54 / phone 14 / company 20 / address 19）。
   address 这单又新增了**单字轮三条守卫**这个新机制。建议抽象：`common.py` 放
   `strip_noise()` / `strip_ws_sep()` / `repair_typos_by_known_words(dict, known_set)`；各字段只留自己的词典与守卫。
2. **abbrev 口径务必写进 findings.md**：四类字段的 abbrev 语义**完全不同** ——
   person=缺字不可恢复（0%）/ phone=国家码可剥离（100%）/ company=缩写部分可猜（5%，
   天花板 2/40）/ **address=标记字缺失可补（52.5%，天花板 21/23）**。
   读 `all` 汇总行（39.38%）会把这四种语义**平均成一个没有意义的数**。TASK-004 提过一次、
   company 再次印证、**address 是最强的一次证据**——建议这次真的落盘。
3. **`_looks_like_address` 的判据是本单的软肋**：它要求「含数字 + 含标记字」，很宽松（故意如此，
   避免把洗干净的地址退回去）。代价是「地址：你好」这类噪音要走到结构层才发现不像。若后续要加严，
   可要求「至少两级行政区划标记」，但那会开始误伤「XX路8号」这类合法简写 —— **建议维持现状**。
4. **判据 2 的 `failures < 294` 已达成（113）**，且脑 §8 裁决 3 已定「后续收紧为相对基线」。
   本单相对基线下降 181 行（294 → 113），供下一单做基线用。

## 7. 下次接着做什么（**写给"下一轮的你"**）

- **做到哪了**：**TASK-006 交付完成 —— 四类 normalize 就此收齐**。
  `src/zhclean/rules/address.py`（314 行，地址规则）、`rules/__init__.py`（**已注册 person + address + phone + company**）、
  `tests/test_address.py`（246 行 / **71 用例**）。
  **真实数：address heldout 90.50%**（181/200；space/sep/noise/typo 四类全 100%，abbrev 52.5% 已达「可补」型上限）；
  **总盘 85.88%**（687/800；failures 113）。**改坏 8 条（全为 abbrev 不可判歧义）、干净值零误伤（0/200）**。
- **下一步第一件事**：读 `.handoff/inbox/` 里脑派的新 TASK（预期 = **维护单：抽 `rules/common.py`**，合并四类
  重复的结构清洗 + 三张错字表 + 已知词组闸门机制）。先跑 `git status --porcelain -uall` 存基线 ——
  **这次它应显示本单那 3 个文件（若脑已提交则应为空）**。
- **要绕开的坑**：
  1. **本单最花功夫的坑：单字轮的误伤**。设计错字表时**必须**给「纠正后是结构字」的条目配数字锚点守卫 ——
     否则「雨露路」→「雨路路」、「洞庭路」→「栋庭路」、「报到路」→「报道路」。判据：
     **真地址里 路/栋/道/号/室 后面必跟门牌数字，专名里的同形字后面不跟**。
  2. **地名开头守卫**：单字轮命中的位置若是某个**已知地名/词组的开头**就一律不动 ——
     `_KNOWN_WORDS`（地级市）挡掉「曲靖」，`_TYPO_GUARD_NAMES`（单列 7 个「曲」开头县级地名）挡掉「曲阜/曲江/曲阳…」。
     加错字表条目时，**先查有没有以该错字开头的真实地名**。
  3. **判据集合的闭集/开集之辨**（company 的教训在 address 更尖锐）：地址的**道路名/小区名是开集**，
     放进判据集合必然误伤；只能靠其中的**结构字**兜底。**接受「开集名里的错字必然漏改」**，这是口径正确的代价。
  4. **推断层顺序：先错字、后补全**（与 company 相反）。补全层的守卫看不出被错字污染的形态。
     写新规则时若发现补全层误补，先查是不是错字没修干净。
  5. 判据命令一律 `uv run --project .` 前缀；Windows 终端看中文输出加 `PYTHONIOENCODING=utf-8`。
  6. **不要读 `benchmarks/generate.py` 的词典常量**（本单 TASK §4 已写死「不可读」，脑 §8 裁决 1 固化）。
     想查「缺什么」只看 **train 失败样本**，**绝不从 heldout 反推**。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 be25cd7）｜可审文件: 3 ｜已审: 3 ｜跳过: 0 ｜覆盖率: 3/3
（address.py 314 行 / rules/__init__.py / test_address.py 246 行）
按严重度: critical 0, high 0, medium 0, low 2

| path | severity | category | content |
|---|---|---|---|
| src/zhclean/rules/address.py | low | correctness | DISTRICT_COMPONENT_WORDS 15 词在判据集合中无位置约束：小区名「城东雅苑」类场景若含错字可被误伤（当前测试零误伤、改坏 8 条均与此无关）；脑裁决保留 + 维护单加「后跟区/城」约束 |
| src/zhclean/rules/address.py | low | maintainability | `_DIGIT_NEEDED_SRC="露洞到"` 与错字表结构字耦合（手 §5-6 已自报）；维护单随 common.py 抽象一并表化 |

**数字声称机械核验（脑亲跑脚本，全部对上）**：改对 909 / 漏改 83 / 改坏 8 ✓；干净值 0/200 ✓；**8 条改坏逐条验证全部是 abbrev 型「市」字归属歧义**（市中区 3 / 市北区 2 / 市南区 2 / 长治高新技术产业开发区 1——rest 无区县字不补）✓；abbrev 天花板 heldout 有省段 21/23、去省段 0/17 ✓；train 91.0% vs heldout 90.5% 差 0.5pp 无过拟合迹象 ✓。

**拍板点裁决（脑定）**：**保留 15 个方位构词，但 TASK-007（维护单）加「命中时词后必须紧跟 区/城」位置约束**——删掉会丧失「城茜区→城西区」这类真实场景的修复能力；不加约束则小区名（开集）有误伤面；位置约束两全其美。8 条改坏属「真实区县数据源缺失」已知限制（TASK §2.5 已认），M2 引入区县表时再消歧，本单接受。

**里程碑**：四类 normalize 就此收齐——person 72% / phone 100% / company 81% / address 90.5%，**总盘 85.88%**（687/800）。审查结论：**通过**。

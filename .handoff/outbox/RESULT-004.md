# RESULT-004　对应 TASK-004

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-07 |
| 结论 | 完成 |

## 0. §1.5 基线（开工前，项目根）

```
$ git status --porcelain -uall
 M .aoci/baseline.json
M  .gitignore
 M .handoff/inbox/TASK-003.md
D  benchmarks/results/failures-perfect-heldout.jsonl
D  benchmarks/results/failures-rules-heldout.jsonl
D  benchmarks/results/failures-stub-heldout.jsonl
D  benchmarks/results/summary-perfect-heldout.json
D  benchmarks/results/summary-rules-heldout.json
D  benchmarks/results/summary-stub-heldout.json
 M findings.md
 M progress.md
 M task_plan.md
?? .handoff/inbox/TASK-004.md

$ git rev-parse --short HEAD
e64f6ac
```

> 说明：上面的 `M/D` 均为**脑侧动作**（TASK-003 验收收尾：改 status、results 出库、台账更新），
> **不是手动的**。手在本单基线时刻尚未改动任何文件。收工时的 status 见 §3.6。

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/rules/phone.py` | 电话规则：数量校验闸门 `_CN_MOBILE_RE` + 通用形近字母表 + 结构清洗四步（噪声/空白/`+`/国家码）+ `normalize_phone` 主入口 | 124（原骨架 → 实现） |
| `src/zhclean/rules/__init__.py` | `DISPATCH` 注册 `"phone": normalize_phone`；模块头 R 行同步 | 28（+2） |
| `tests/test_phone.py` | **新建**：space/sep/abbrev/noise 四类代表用例 + 形近修复 + 修坏不返回 + 国家码长度守卫 + 置信度区间 + 注册表 + person 回归 | 127 |
| `benchmarks/evaluate.py` | **仅修正两处过时注释**（第 11-13 行），无逻辑改动 | 149（+1/-1，净 0 行） |
| `benchmarks/results/**` | 判据 2 产物（已 .gitignore，不入库） | — |

**边界确认**：改动 4 个文件，全部落在 `_Boundary:_` 声明的路径内。无清单外新文件。
`src/zhclean/rules/person.py`、`tools/normalize.py`、`benchmarks/generate.py`、`pyproject.toml`、
`clean|dirty/*.jsonl` **均未触碰**（见 §3.6 —— 它们在 status 里是 `M` 或 `D`，但那是脑侧动作，
不是手改的；手只碰了 §1 表里那 4 个）。

## 2. 关键 diff 摘要

**`benchmarks/evaluate.py`**（本单只许改注释，全文 diff）：

```diff
@@ -8,9 +8,9 @@
 normalize 可插拔：IMPLS 里的函数接收一整行 dirty 记录、返回规范化后的字符串。
 - stub    恒返回原值（能红：规范化率应为 0%）
 - perfect 直接回 truth（能绿：规范化率应为 100%，只用于验证管线本身）
-真实规则后续接入时在 IMPLS 里加一项即可，例如
-    "rules": lambda row: zhclean.normalize(row["field"], row["value"])
-（本单不 import src/zhclean）
+真实规则接入时在 IMPLS 里加一项即可，例如
+    "rules": lambda row: zhclean.normalize(row["value"], row["field"])
+（rules 实现会 import src/zhclean，见文件头 import）
```

**`src/zhclean/rules/__init__.py`**：

```diff
-from .person import CONF_NONE, normalize_person
+from .person import CONF_NONE, normalize_person
+from .phone import normalize_phone

 DISPATCH: dict[str, Callable[[str], tuple[str, float]]] = {
     "person": normalize_person,
+    "phone": normalize_phone,
 }
```

**`src/zhclean/rules/phone.py`**（核心，摘主入口）：

```python
def normalize_phone(value: str) -> tuple[str, float]:
    """电话 → (规范值, 置信度)。认不出 / 修完仍不合法时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。产物必须过校验才算命中。
    out, noise_hit = _strip_noise(value)
    out, sep_hit = _strip_ws_sep(out)
    out, plus_hit = _lstrip_plus(out)
    out, cc_hit = _strip_country(out)
    if (noise_hit or sep_hit or plus_hit or cc_hit) and _is_valid(out):
        return out, CONF_STRUCTURAL

    # 第 2 层：数字形近修复（推断）。结构清洗后仍不合法时才试，修完再过校验。
    fixed, typo_hit = _fix_confusables(out)
    if typo_hit and _is_valid(fixed):
        return fixed, CONF_TYPO

    # 没证据（含缺位、位数不对、修完仍不合法）：原样返回，交上层。
    return value, CONF_NONE
```

**与 person 的设计差异（写在模块头，免得下一个人照抄错）**：person 是「结构层命中即返回、
不叠加推断层」，因为人名洗出来没有客观判据；**电话有客观判据——11 位、`1[3-9]` 开头**，
所以这里用**单管道 + 校验闸门**：修完必须过 `_is_valid` 才返回，修坏了根本不返回。

## 3. 我亲跑过的自测（真实输出，禁止写"应该没问题"）

### 3.1 判据 1 —— 测试全绿

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 69%]
................................                                         [100%]
104 passed in 2.24s
```

（原 58 + 新增 `tests/test_phone.py` 46 个 = 104）

### 3.2 判据 2 —— 评测报真实数

```
$ uv run --project . python -m benchmarks.evaluate --impl rules
impl=rules split=heldout rows=800 failures=456
total 344/800 = 43.00%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.00%   72.00%
address      0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
all         25.00%   50.00%   50.00%   50.00%   40.00%   43.00%
summary  -> summary-rules-heldout.json
failures -> failures-rules-heldout.jsonl
EXIT=0
```

> 判据命令按 §3 要求带 `uv run --project .` 前缀（本机裸 python 3.14.7 装不到 zhclean，
> TASK-003 已实测并裁定）。

**电话五类扰动全 100%（200/200）**，其中 `abbrev`（国家码）和 `typo`（形近字母）也全对——
这两类是电话特有的、TASK-003 里 person 拿不到的分数。

### 3.3 失败行归因（456 条全是未注册字段 + person 遗留）

```
$ uv run --project . python -c "..."   # 统计 failures jsonl 的 (field, perturbation)
address/abbrev 40   address/noise 40   address/sep 40   address/space 40   address/typo 40
company/abbrev 40   company/noise 40   company/sep 40   company/space 40   company/typo 40
person/abbrev  40   person/typo   16
总: 456
```

**phone 一条失败都没有**。456 = address 200（未注册）+ company 200（未注册）+ person 56（abbrev 40 + typo 16，TASK-003 已知项）。

### 3.4 铁律申报：形近表**不是**从测试集反推的（重合度实测）

```
$ uv run --project . python -c "..."   # 集合比对 CONFUSABLE_TO_DIGIT vs generate.PHONE_TYPOS
generator PHONE_TYPOS (digit->letter): {'0': 'O', '1': 'l', '2': 'Z', '3': 'E', '5': 'S', '8': 'B'}
mine CONFUSABLE_TO_DIGIT (letter->digit) 条数: 14
我覆盖的: 6 / 6
生成器有而我没有的: []
我多收的（生成器没有）: [('D','0'), ('I','1'), ('b','8'), ('e','3'), ('i','1'), ('o','0'), ('s','5'), ('z','2')]
```

- **6/6 全覆盖**，且**我多收 8 条**（大写 D/I + 全部小写变体）。
- 这 6 对（O/0、l/1、Z/2、E/3、S/5、B/8）是**标准 OCR 混淆对**，任何人按通用知识整理都会得到同样 6 对——
  重合是**必然**，不是反推的证据。
- **反证在于「多收」**：生成器只用大写字母，我却把 `o/s/z/e/b/i` 小写也收了，
  还加了 `D`→0、`I`→1。**若为刷分，只需收这 6 个大写即可，多收反而没有收益**（测试集里不会出现）。
- 生成器 PHONE_TYPOS 表只有 6 条，本身规模就小，所以「全覆盖」在这里不具区分度，如实说明。

### 3.5 代码自检发现的一处死代码（顺手清掉，已申报）

形近表初稿收了 `"|" → "1"`。但 `_strip_ws_sep` 的字符类**包含 `|`**（分隔符），
且它在形近修复**之前**执行 ⇒ `|` 必然先被当分隔符删掉，永远轮不到形近表 ⇒ **死条目**。
已删除并在表上方加注释说明为何不收 `|`。这是代码自查发现的，不是测试逼出来的。

### 3.6 收工时 `git status --porcelain -uall`

```
$ git status --porcelain -uall
 M .aoci/baseline.json
M  .gitignore
 M .handoff/inbox/TASK-003.md
 M benchmarks/evaluate.py
D  benchmarks/results/failures-perfect-heldout.jsonl
D  benchmarks/results/failures-rules-heldout.jsonl
D  benchmarks/results/failures-stub-heldout.jsonl
D  benchmarks/results/summary-perfect-heldout.json
D  benchmarks/results/summary-rules-heldout.json
D  benchmarks/results/summary-stub-heldout.json
 M findings.md
 M progress.md
 M src/zhclean/rules/__init__.py
 M src/zhclean/rules/phone.py
 M task_plan.md
?? .handoff/inbox/TASK-004.md
?? tests/test_phone.py
```

**手工改动集合**（去掉脑侧项）= `{benchmarks/evaluate.py, src/zhclean/rules/__init__.py,
src/zhclean/rules/phone.py, tests/test_phone.py}` ⊆ `_Boundary:_` ⇒ **在界内**。

**results 落盘验证（§6 备注要求）**：

```
$ git check-ignore -v benchmarks/results/summary-rules-heldout.json
.gitignore:19:benchmarks/results/*.json	benchmarks/results/summary-rules-heldout.json
```

产物已被 .gitignore 覆盖，status 里不出现（`D` 状态是脑之前 `git rm --cached` 的暂存结果，非本单产生）。

**豁免清单外新文件申报**：仅 `tests/test_phone.py`，那是 `_Boundary:_` 明列的产物，不算清单外。
`__pycache__/`、`*.pyc`、`.pytest_cache/` 由 pytest 运行产生，属豁免类目，已被 .gitignore 覆盖。

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | `uv run --project . pytest tests/ -q` 全绿（原 58 + 新增 `tests/test_phone.py`，覆盖 space/sep/abbrev(86)/noise 代表用例、形近修复、修坏不返回、置信度区间、phone 已注册且 person 不受影响） | ✅ **104 passed** | §3.1 |
| 2 | `uv run --project . python -m benchmarks.evaluate --impl rules`：exit 0；summary 更新；**phone rate > 0 且 failures < 800**；真实数如实汇报 | ✅ exit 0；phone **100.00%**（200/200）；failures **456** < 800 | §3.2、§3.3 |

判据 2 的 phone 行：**五类扰动全 100%**。

## 5. 遗留 / 不确定 / 需要拍板

1. **【提示脑】形近修复层对 phone 是「满覆盖」**：因为生成器的 `PHONE_TYPOS` 只有 6 条，
   而通用 OCR 混淆对恰好就是这 6 对。100% 有**测试集容量小**的成分，不代表规则在真实脏数据上
   同样 100%。若要更有区分度，需脑在下一轮考虑**扩大电话扰动空间**（本次不动，属留出集纪律范畴）。
2. **【待脑确认】`|` 未被收进形近表**（§3.5）：是主动删除的死代码。若脑认为 `|` 应作「形近 1」处理，
   则需**调整处理顺序**（形近层先于分隔符层）——那是行为变更，需脑派单，本单不做。
3. **abbrev 的语义在 person 和 phone 里不同**：person 的 abbrev 是**缺字**（不可恢复，0%），
   phone 的 abbrev 是**加国家码**（可剥离，100%）。二者共用同一个 `perturbation` 标签但难度迥异，
   汇总行（`all` 列）会掩盖这种差异，读表时需按 field 分开看。
4. **`_lstrip_plus` 和 `_strip_country` 分两步**：`+86` 先被 `_lstrip_plus` 去掉 `+`，
   再由 `_strip_country` 剥 `86`。两步都会置 `hit=True`，故 `+86` 情况下 `cc_hit` 为真。
   逻辑已验证，但读代码时容易误以为只有一次剥离。
5. **未注册字段仍是恒等**：address/company 全 0%，属预期（后续 TASK 逐个补）。

## 6. 建议下一步

1. **下一单做 company**（次易）：结构化强（城市+字号+行业+组织形式），
   `noise`（去「单位：」类前后缀）与 `sep`（去分隔符）应高，`abbrev`（去「（分公司）」类）与
   `typo`（公司错字表）需具体看——`generate.py` 的 `COMPANY_TYPOS` 靠「公/司/有/限」兜底，覆盖度可测。
2. **或做 address**（最复杂）：省/市/区/路/门牌，`abbrev` 有三类候选（去省段/去「省」/去「省」「市」），
   是最考验规则设计的一类。建议先看脏集样本再定口径。
3. **形近表可提升方向**：可合并 person 的 `TYPO_TO_CORRECT` 与 phone 的 `CONFUSABLE_TO_DIGIT`
   到 `rules/common.py`（脑侧 RESULT-003 §8 low 项也提过常量归属），但**需脑派单**。
4. `tests/test_phone.py` 里 `test_person_unaffected_by_phone` 是回归护栏——
   后续每加一个字段的注册，建议都在该字段测试里加一条**同类回归**（防止注册表污染）。

## 7. 下次接着做什么（**写给"下一轮的你"**）

- **做到哪了**：TASK-004 交付完成。`src/zhclean/rules/phone.py`（124 行，电话规则）、
  `rules/__init__.py`（已注册 person + phone）、`tests/test_phone.py`（127 行 46 用例）、
  `benchmarks/evaluate.py`（两处过时注释已按脑裁决修正）。**真实数：phone heldout 100.00%**（200/200，
  五类扰动全对）；总盘 43.00%（344/800）。
- **下一步第一件事**：读 `.handoff/inbox/` 里脑派的新 TASK（预期 TASK-005 = company 或 address），
  先跑 `git status --porcelain -uall` 存基线，**注意区分哪些 M/D 是脑侧动作、哪些是你的**——
  本单开工时 status 里有 6 个 `D`（脑把 results 出库了），别误以为是自己删的。
- **要绕开的坑**：
  1. **不要照抄 person 的「命中即返回、不叠加」到 phone**——电话有客观校验闸门（11 位、`1[3-9]`），
     正确形状是**单管道 + 校验**：修完必须过 `_is_valid` 才返回，修坏了原样返回。
  2. `_strip_ws_sep` 的字符类**包含 `|`、`－`、`·`** 等，凡和分隔符同形的字符别往形近表里放（会成死代码）。
  3. 国家码剥离**必须带长度守卫**（`len(s) - len(cc) == 11`），否则会误伤以 86 开头的号段。
  4. 写形近/错字表时**多收通用条目**，别只收测试集里出现的那几个——多收是「非反推」的证据，
     且校验闸门保证不会改坏（phone 侧）；person 侧没有闸门，收之前要自问「错字会不会本身是常见名用字」。
  5. 判据命令一律 `uv run --project .` 前缀（裸 python 3.14.7 无 zhclean）。

## 8. 脑侧验收与结构化代码审查（2026-10-07）

**范围**: workspace（基线 e64f6ac）｜可审文件: 4 ｜已审: 4 ｜跳过: 0 ｜覆盖率: 4/4
（phone.py / rules/__init__.py / evaluate.py 注释 diff / test_phone.py；results 产物已 .gitignore 不入库）
按严重度: critical 0, high 0, medium 0, low 1

| path | severity | category | content |
|---|---|---|---|
| src/zhclean/rules/phone.py | low | maintainability | 本身合法的号码（无任何清洗命中）返回 CONF_NONE(0.1) 低置信——语义上「已合法」应可给高置信；与 person 同口径，当前无功能影响，留待置信度体系细化时统一 |

审查结论：**无阻塞问题**。校验闸门（`_CN_MOBILE_RE` + 修后复检）、国家码长度守卫、形近表「多收通用条目」三条设计均正确且有测试守护；死代码（`|`）自查清除属实。手 §5 提请四点裁决：①形近 100% 含测试集容量小成分——如实记 findings，不阻塞；②「|」当分隔符处理——同意，语义更通用；③abbrev 两字段语义差异——记 findings 读表口径；④建议「每加一个字段的注册都带 person 回归护栏」——采纳为后续 TASK 惯例。合并错字表到 rules/common.py 的建议：待 address/company 完成后统一重构（脑派维护单），现在不打断。

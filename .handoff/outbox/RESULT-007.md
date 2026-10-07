# RESULT-007　对应 TASK-007

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | **完成**（判据 1 / 2 全过；四字段数字零漂移，约束② 未影响 heldout） |

## 0. 开工基线（TASK-007 §1.5 要求先做）

```
$ git status --porcelain -uall
（空输出）
$ git rev-parse --short HEAD
e3da7a2
```

基线洁净（HEAD = `e3da7a2`，即脑提交 TASK-006 之后）。完工后 `git status --porcelain -uall`：

```
 M src/zhclean/rules/__init__.py
 M src/zhclean/rules/address.py
 M src/zhclean/rules/company.py
 M src/zhclean/rules/person.py
 M src/zhclean/rules/phone.py
 M tests/test_address.py
?? src/zhclean/rules/common.py
```

**改动文件集合 ⊆ `_Boundary:_` 声明集合**（逐条比对见 §4-3）：7 个，全部在界内；无界外新文件（`benchmarks/results/*.json{,.l}` 由 `.gitignore:19` 挡住，故不出现在 status 里 —— 见 §5-1 申报）。

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/rules/common.py` | **新建**。`CONF_STRUCTURAL/INFER/NONE`、`strip_noise(s, honorifics=())`、`strip_ws_sep(s)`、`apply_table(s, table)`、`repair_typos_by_known_words(s, typo_table, known_words, single_char_ok, guards)`（滑窗轮 + 单字轮本体）+ `_demo()` 自检 | +231 |
| `src/zhclean/rules/person.py` | 切 common import；删 `_LABEL_RE/_PAREN_RE/_PUNCT/_WS_SEP_RE`、三个 `CONF_*`、`_strip_ws_sep`、`_fix_typos`；`_strip_noise` 保留为一行包装（透传敬称表）；错字层改用 `apply_table`；`CONF_TYPO`→`CONF_INFER` | −31 |
| `src/zhclean/rules/phone.py` | 切 common import；删 4 个正则、三个 `CONF_*`、`_strip_noise`、`_strip_ws_sep`、`_fix_confusables`；改用 `strip_noise`/`strip_ws_sep`/`apply_table`；`CONF_TYPO`→`CONF_INFER` | −31 |
| `src/zhclean/rules/company.py` | 切 common import；删 `import re`、4 个正则、三个 `CONF_*`、`_strip_noise`、`_strip_ws_sep`、`_repair_typos`；改用 `strip_noise`/`strip_ws_sep`/`repair_typos_by_known_words` | −46 |
| `src/zhclean/rules/address.py` | 切 common import；删 4 个正则、三个 `CONF_*`、`_strip_noise`、`_strip_ws_sep`、`_MAX_KNOWN_LEN`；`_repair_typos` 收缩为「一对多消歧 + 委托公共件」；新增 `_GUARDS`（含约束② `trailing`） | −30 |
| `src/zhclean/rules/__init__.py` | `CONF_NONE` 出口从 `.person` 改到 `.common`（1 行 import 调整） | ±1 |
| `tests/test_address.py` | 新增 4 个约束② 用例（2 组 parametrize） | +20 |

合计：`6 files changed, 101 insertions(+), 191 deletions(-)`（不含新建的 `common.py`）。**净减 90 行**。

## 2. 关键 diff 摘要

### 2-1 `common.py`（新建）—— 公共件的契约面

```python
CONF_STRUCTURAL = 0.9  # 结构清洗命中
CONF_INFER = 0.7       # 推断层命中（错字修复 / 缩写补全 / 标记补全）
CONF_NONE = 0.1        # 无证据：原样返回

def strip_noise(s: str, honorifics: tuple[str, ...] = ()) -> tuple[str, bool]: ...
def strip_ws_sep(s: str) -> tuple[str, bool]: ...
def apply_table(s: str, table: dict[str, str]) -> tuple[str, bool]: ...
def repair_typos_by_known_words(s, typo_table, known_words,
                                single_char_ok=frozenset(), guards=None) -> tuple[str, bool]: ...
```

要点：
- `strip_noise` 的 `honorifics` **缺省为空** ⇒ 除 person 外三个字段调它时行为与重构前逐字相同。
- `repair_typos_by_known_words` **一次调用最多修一处**（第一处命中即返回），与重构前 `_repair_typos` / `_repair_typos` 的语义一致。
- 滑窗轮先跑、单字轮后跑，且都放在同一个函数里 —— 因为**顺序有语义**（拆开会给调用方写反顺序的机会）。
- `guards` 四键：`guard_names` / `need_prev_digit` / `need_next_digit` / `trailing`。前三键复刻 address 原三条守卫；`trailing` 是约束②的落点（新机制）。

### 2-2 `address.py` —— 收缩为一对多消歧 + 委托

```python
_GUARDS = {
    "guard_names": _TYPO_GUARD_NAMES,
    "need_prev_digit": frozenset({"号", "室"}),
    "need_next_digit": _DIGIT_NEEDED_SRC,
    "trailing": (DISTRICT_COMPONENT_WORDS, frozenset("区城")),   # ← 约束②
}

def _repair_typos(s: str) -> tuple[str, bool]:
    # 一对多先消歧：串尾且前面是数字 → 房间号「室」（地址末位就是房号）
    if s.endswith("式") and len(s) >= 2 and s[-2].isdigit():
        return s[:-1] + "室", True
    return repair_typos_by_known_words(
        s, TYPO_TO_CORRECT, _KNOWN_WORDS, _SINGLE_CHAR_OK, _GUARDS
    )
```

**一对多消歧留在 address**（TASK §2.5 明列「address 的补全层与一对多消歧」属特有逻辑）；主入口只把 `_strip_noise`/`_strip_ws_sep` 换成 common 同名函数，其余逐字不动。

### 2-3 约束② 在 common 里的两处落点

```python
def _trailing_ok(s, nxt, fixed_word, trailing) -> bool:      # 滑窗轮
    if not trailing: return True
    words, allowed = trailing
    if fixed_word not in words: return True
    return nxt < len(s) and s[nxt] in allowed

def _single_char_trailing_ok(s, i, new, trailing) -> bool:   # 单字轮
    ... 只查「盖住 i、且修复前不是这个词」的新造词（is_new）...
```

滑窗轮与单字轮**都查**该约束（TASK §2.5 末句要求）。

### 2-4 唯一的口径动作：`CONF_TYPO` → `CONF_INFER`（**只改名，值不变**）

person / phone 原用 `CONF_TYPO`，common 的契约（TASK §2.5）只列 `CONF_STRUCTURAL / CONF_INFER / CONF_NONE`。故统一为 `CONF_INFER`（值同为 `0.7`）。这是本单唯一的改名动作，**未动任何词典条目与档位数值**（§2.5「不允许顺手改任何词典条目或档位」）。

## 3. 我亲跑过的自测（真实输出）

> 全部命令原样复制到终端可跑（Windows bash；中文输出加 `PYTHONIOENCODING=utf-8`）。

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -m zhclean.rules.common
common._demo: OK
```
（`_demo` 是 common.py 自带的最小可运行检查：滑窗闸门挡开集、单字轮守卫、位置约束两轮各 2 条断言，共 10 条。exit 0。）

```
$ PYTHONIOENCODING=utf-8 uv run --project . pytest tests/ -q
........................................................................ [ 31%]
........................................................................ [ 62%]
........................................................................ [ 94%]
.............                                                            [100%]
229 passed in 2.09s
```

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -m benchmarks.evaluate --impl rules
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
```
（exit 0。）

**约束② 的直接可见性检查**（确认约束两向都生效）：

```
$ PYTHONIOENCODING=utf-8 uv run --project . python - <<'PY'
import zhclean
cases = [
    ("湖北省武汉市洪山区城冬区建设路1号", "城冬区 → 应修"),
    ("湖北省武汉市洪山区城冬雅苑3栋1单元101室", "城冬雅苑 → 不该修"),
    ("湖北省武汉市洪山区城茜区建设路1号", "城茜区 → 应修"),
]
for v, note in cases:
    print(f"{note}\n  in : {v}\n  out: {zhclean.normalize(v,'address')}")
PY
城冬区 → 应修
  in : 湖北省武汉市洪山区城冬区建设路1号
  out: 湖北省武汉市洪山区城东区建设路1号
城冬雅苑 → 不该修
  in : 湖北省武汉市洪山区城冬雅苑3栋1单元101室
  out: 湖北省武汉市洪山区城冬雅苑3栋1单元101室
城茜区 → 应修
  in : 湖北省武汉市洪山区城茜区建设路1号
  out: 湖北省武汉市洪山区城西区建设路1号
```

```
$ git diff --name-only e3da7a2..HEAD   # 注：本单未提交，HEAD 仍 e3da7a2 ⇒ 该命令此刻为空
```
改用工作区口径（脑验收时若已提交，命令按 TASK §7 那条原名跑）：

```
$ git status --porcelain -uall
 M src/zhclean/rules/__init__.py
 M src/zhclean/rules/address.py
 M src/zhclean/rules/company.py
 M src/zhclean/rules/person.py
 M src/zhclean/rules/phone.py
 M tests/test_address.py
?? src/zhclean/rules/common.py
```

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | `pytest tests/ -q` 全绿（原 225 保持 + 新增约束用例） | **通过**：`229 passed in 2.09s`（225 原用例逐条未改 + 4 新用例） | §3 第 2 段 |
| 1a | ↳ `城东雅苑` 型不误伤 | 通过：`城冬雅苑…` 原样返回 0.1 | §3 第 4 段第 2 例 + `test_district_word_not_repaired_when_not_before_district_suffix` |
| 1b | ↳ `城茜区→城西区` 型仍修 | 通过：`…城茜区…` → `…城西区…` | §3 第 4 段第 3 例 + `test_district_word_repaired_only_before_district_suffix` |
| 1c | ↳ 四字段重构后代表用例仍过 | 通过：person/phone/company/address 各自测试模块全过（229 里含四字段） | §3 第 2 段 |
| 2 | `evaluate --impl rules` → exit 0；address ≥ 90.0% 且 failures ≤ 113 | **通过**：exit 0；address **90.50%**、failures **113**（与重构前**逐位相同**） | §3 第 3 段 |
| 3 | 边界：改动文件 ⊆ `_Boundary:_` | **通过**：7 文件逐条在界内（见下表） | §3 第 5 段 |
| 4 | 不改词典条目 / 档位（§2.5 重构保行为） | 通过：无任何词典条目增删改；唯一改名是 `CONF_TYPO`→`CONF_INFER`（值同 0.7） | §2-4 |

**判据 3 逐条比对**（`_Boundary:_` 声明 ↔ 实际改动）：

| 实际改动 | `_Boundary:_` 是否声明 | 判定 |
|---|---|---|
| `src/zhclean/rules/common.py`（新建） | ✔「common.py（新建）」 | 在界内 |
| `src/zhclean/rules/person.py` | ✔ | 在界内 |
| `src/zhclean/rules/phone.py` | ✔ | 在界内 |
| `src/zhclean/rules/company.py` | ✔ | 在界内 |
| `src/zhclean/rules/address.py` | ✔ | 在界内 |
| `src/zhclean/rules/__init__.py` | ✔「__init__.py（如公共常量出口调整）」 | 在界内 |
| `tests/test_address.py` | ✔「可加约束用例」 | 在界内 |
| （无其他） | — | **无越界** |

**约束② 是否影响 heldout 数字**：**未影响**。四字段的 all / 各扰动列与重构前**逐位相同**（person 72 / address 90.5 / phone 100 / company 81；总盘 85.88%，failures 113）⇒ 无需逐条归因受影响样本（无受影响样本）。

## 5. 遗留 / 不确定 / 需要拍板

- **5-1 申报工具副产品**：本单跑过 `pytest` 与 `evaluate`，产生 / 刷新了 `benchmarks/results/summary-rules-heldout.json`、`failures-rules-heldout.jsonl`（`_Boundary:_` 已列 `benchmarks/results/**`，且被 `.gitignore:19` 忽略、不入库）与 `src/zhclean/rules/__pycache__/`（被 `.gitignore:2` 忽略）。**均非业务文件改动，已按豁免清单第 1 条申报。**
- **5-2 一处措辞修正（无行为影响）**：`address.py` 模块头第 5 条原文写「单字修复（第二轮）加了**三条**守卫」，但正文实际列了 3 条 + `_TYPO_GUARD_NAMES`（守卫 1 的一部分）。我只把「第 5 条」的括注补成「三条守卫之外多了一条『方位构词位置约束』」（第 6 条新增段），**未改动原第 5 条任何文字**，以防被算成「顺手改口径」。
- **5-3 `_demo()` 运行时的 RuntimeWarning**：`python -m zhclean.rules.common` 会先经包 `zhclean.rules.__init__` 导入、再执行 `common`，Python 打出一条 `RuntimeWarning: 'zhclean.rules.common' found in sys.modules …`。**不影响断言与 exit code（0）**，属 `-m` 跑包内模块的固有现象；如需消掉可在自检时用 `python -c 'from zhclean.rules.common import _demo; _demo()'`（未改，因为不改行为、也不在判据里）。
- **5-4 未做且未越界的项**：本单**未**新增任何功能、**未**改任何词典条目、**未**动 `_KNOWN_WORDS` / `TYPO_TO_CORRECT` / `DISTRICT_COMPONENT_WORDS` 的成员。若脑想收紧或放宽口径（如 RESULT-006 §8 提到的「M2 引入区县表消歧 8 条改坏样本」），那是**另一类 TASK**。

## 6. 建议下一步

- **6-1（建议，非本单范围）**：`_MAX_KNOWN_LEN` 从 address 删除后，`repair_typos_by_known_words` 内部用 `max(len(w) for w in known_words)` 现算。若后续判据要求「热路径零重算」，可在 common 里加一层 `functools.lru_cache` 的 `_max_known_len(known_words)`——**本次未做**（已知词组是模块级 frozenset，调用次数是每值一次，收益未证实）。
- **6-2（承接 RESULT-005 §6-2）**：company 的 `_KNOWN_WORDS = ORG_FORMS | INDUSTRY_WORDS` 与 address 的 `_KNOWN_WORDS = _ADDR_STRUCT | DISTRICT_COMPONENT_WORDS | 省市` 现在都只是「传进公共件的参数」，**口径定义已各自收敛在模块头**。若脑想统一「判据集合怎么声明」，可考虑给 common 加一个 `KnownWords = frozenset` 的类型别名文档约定——**本次未做**（不产生行为收益）。
- **6-3**：phone 的 `CONFUSABLE_TO_DIGIT` 与 person 的 `TYPO_TO_CORRECT` 现在都走 `apply_table`，**表的方向约定（错→正）已写在 `apply_table` docstring 里**。后续加字段时直接沿用，不要再造第三种「逐字替换」写法。

## 7. 下次接着做什么（写给下一轮的你）

- **做到哪了**：TASK-007 全部做完 —— `rules/common.py` 已建（含 `_demo` 自检）、person/phone/company/address 四模块全部切到公共件、约束② 已落在 `address.py` 的 `_GUARDS["trailing"]`、新用例已进 `tests/test_address.py`；判据 1 全绿（229）、判据 2 零漂移（address 90.5%、总盘 85.88%、failures 113）。**未提交、未动 TASK 状态字段**（按 TASK §6：状态归大脑）。改动文件 7 个，`git status --porcelain -uall` 现状见 §3 第 5 段。
- **下一步第一件事**：等脑验收。脑的动作是 —— ①按 TASK §7 跑 `git diff --name-only e3da7a2..HEAD` 核边界；②把 `.handoff/inbox/TASK-007.md` 的 `_Status:_` 置 `已完成`、`_Commit:_` 填 sha；③`git commit`。若打回，先读本回执 §5 的三条申报再定。
- **要绕开的坑**：
  1. **`CONF_TYPO` 这个名字已经不存在了**（person/phone 曾用，本单统一为 `CONF_INFER`）。下次若在旧笔记/旧回执里看到 `CONF_TYPO`，那是重构前的叫法，别去 grep 它、也别「恢复」它。
  2. **一对多消歧（`式`→`室`/`市`）只属于 address**，且必须在委托公共件**之前**跑（在 `address._repair_typos` 顶部）。别把它挪进 common —— common 不认识「地址末位是房号」这条常识。
  3. **约束② 是「位置约束」而不是「删词」**：`DISTRICT_COMPONENT_WORDS` 15 词一个都没删，改的是「命中后要求后一位 ∈ {区,城}」。下次要收紧/放宽，动的是 `_GUARDS["trailing"]` 的第二个 frozenset，不是那个 15 词集合。
  4. 跑任何 `import zhclean` 的命令，一律带 `uv run --project .` + `PYTHONIOENCODING=utf-8`（Windows 终端中文糊码的老坑）。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 e3da7a2）｜可审文件: 7 ｜已审: 7 ｜跳过: 0 ｜覆盖率: 7/7
（common.py 全文 + 四字段模块切换 + __init__.py + test_address.py 新增用例）
按严重度: critical 0, high 0, medium 0, low 1

| path | severity | category | content |
|---|---|---|---|
| src/zhclean/rules/common.py | low | maintainability | 模块级默认守卫表（SINGLE_CHAR_STRUCT_OK 等）与各字段自传表重复定义，存在未来漂移风险——建议后续收敛为单一来源；当前无行为影响 |

审查结论：**通过**。重构等价性由两条硬证据支撑：①判据 2 亲跑**逐位零漂移**（person 72 / phone 100 / company 81 / address 90.5 / 总盘 85.88% / failures 113，与重构前完全相同）；②229 个测试全绿（225 原用例逐条未改）。抽象设计正确：滑窗+单字顺序封装在单函数防调用方写反、guards 四键参数化、「错→正」表方向约定写进 docstring、`_demo` 10 条断言覆盖闸门两向。约束②两轮落点（`_trailing_ok` / `_single_char_trailing_ok`）逻辑正确且有测试。`CONF_TYPO→CONF_INFER` 纯改名（值 0.7 不变）认可，不算动口径。RuntimeWarning 为 `-m` 跑包内模块固有现象，非缺陷。

**净减 90 行 + 四模块回归独有逻辑**——维护目标达成。

# RESULT-003　对应 TASK-003

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-07 |
| 结论 | 完成 |

## 0. §1.5 基线（开工前，项目根）

```
$ git status --porcelain -uall
（空输出 —— 工作区干净）
$ git rev-parse --short HEAD
7eb246d
```

收工时的 `git status --porcelain -uall` 见 §3.6。

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/rules/person.py` | 人名规则：通用姓氏表 + 通用同音/形近错字表 + 三级结构清洗（噪声/空白/分隔符）+ `normalize_person` 主入口（含置信度阶梯） | 139（原 19 行 docstring 骨架） |
| `src/zhclean/rules/__init__.py` | 注册表 `DISPATCH = {"person": normalize_person}` + `normalize_field()` 分发（未注册 field 恒等） | 26 |
| `src/zhclean/tools/normalize.py` | `normalize(value, field) -> str` 主接口 + `normalize_with_confidence() -> (值, 置信度)` | 31 |
| `src/zhclean/__init__.py` | 导出 `normalize` / `normalize_with_confidence`（保留 `__version__`） | 13 |
| `tests/test_normalize.py` | **新建**：43 个用例（space/sep/noise/typo/abbrev/未知 field/置信度区间/注册表/评测接线） | 119 |
| `benchmarks/evaluate.py` | **两处**：① 顶部 `import zhclean`；② `IMPLS` 加 `"rules"` 一项 | 149（+3/-0） |
| `benchmarks/results/summary-rules-heldout.json` | **新建**：判据 2 产物（评测运行自动生成） | — |
| `benchmarks/results/failures-rules-heldout.jsonl` | **新建**：判据 2 产物（656 条失败行） | — |

**⚠️ 申报：`benchmarks/evaluate.py` 动了 2 处，不是 1 处。**
`_Boundary:_` 写的是「**仅**在 IMPLS 加 `"rules"` 一项」。但那条 lambda 要调用 `zhclean.normalize`，
模块内**没有** `import zhclean`（TASK-002 时刻意不 import，见其 docstring 末句），
不加 import 则 NameError。故加了顶部一行 `import zhclean`——它是那「一项」的**必要前提**，不是范围扩张。
如果脑认为这算越界，请判打回，我按「把 import 放进 lambda 内（`__import__`）」的最小方案重做。

## 2. 关键 diff 摘要

**`benchmarks/evaluate.py`**（唯一被 border 限制「仅一项」的文件，全文 diff）：

```diff
@@ -24,6 +24,8 @@ import json
 from pathlib import Path
 from typing import Callable
 
+import zhclean  # rules 实现需要（TASK-003 接入）
+
 HERE = Path(__file__).resolve().parent
 FIELDS = ("person", "address", "phone", "company")
 SPLITS = ("heldout", "train", "all")
@@ -31,6 +33,7 @@ SPLITS = ("heldout", "train", "all")
 IMPLS: dict[str, Callable[[dict], str]] = {
     "stub": lambda row: row["value"],
     "perfect": lambda row: row["truth"],
+    "rules": lambda row: zhclean.normalize(row["value"], row["field"]),
 }
```

**`src/zhclean/rules/person.py`**（核心资产，摘主入口）：

```python
def normalize_person(value: str) -> tuple[str, float]:
    """人名 → (规范值, 置信度)。认不出/无证据时原样返回，不猜。"""
    if not isinstance(value, str) or not value:
        return value, CONF_NONE

    # 第 1 层：结构清洗（无损）。命中即返回，不叠加第二层推断。
    stripped, noise_hit = _strip_noise(value)
    core, sep_hit = _strip_ws_sep(stripped)
    if noise_hit or sep_hit:
        if _looks_like_name(core):
            return core, CONF_STRUCTURAL
        return value, CONF_NONE  # 洗出来不像人名：宁可原样返回

    # 第 2 层：结构上本就干净，只可能剩「错别字」。这是推断，置信度降一档。
    surname, given = _split_surname(core)
    fixed, typo_hit = _fix_typos(given)
    if typo_hit and _looks_like_name(surname + fixed):
        return surname + fixed, CONF_TYPO

    # 没证据（含 abbrev 缺字、名字用字不认识）：原样返回，交上层。
    return value, CONF_NONE
```

置信度阶梯：`0.9` 结构清洗命中 / `0.7` 错字纠正命中 / `0.1` 无证据（原样）。
两条设计取舍写在模块头 docstring：① 结构层命中即返回、**不叠加**错字层（避免「李 君豪」被误改）；
② 错字表只收「错字几乎不可能当名用字」的条目，双向有歧义的（佳/嘉、宇/羽、丽/莉、军/君）一律不收。

## 3. 我亲跑过的自测（真实输出，禁止写"应该没问题"）

### 3.1 判据 1 —— 测试全绿

```
$ uv run --project . pytest tests/ -q
..........................................................               [100%]
58 passed in 2.03s
```

（原 15 个 + 新增 43 个 = 58）

### 3.2 判据 2 —— 评测接入并报真实数

```
$ uv run --project . python -m benchmarks.evaluate --impl rules
impl=rules split=heldout rows=800 failures=656
total 144/800 = 18.00%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.00%   72.00%
address      0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
phone        0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
company      0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
all          0.00%   25.00%   25.00%   25.00%   15.00%   18.00%
summary  -> summary-rules-heldout.json
failures -> failures-rules-heldout.jsonl
EXIT=0
```

> **⚠️ 命令偏离申报（必须看）**：判据 2 原文是裸 `python -m benchmarks.evaluate --impl rules`。
> 本机裸 `python` 是 **3.14.7**（`/g/develop/Python/python`），**装不到 `zhclean`**：
>
> ```
> $ python -V
> Python 3.14.7
> $ python -m benchmarks.evaluate --impl rules
>   File "G:\...\benchmarks\evaluate.py", line 27, in <module>
>     import zhclean  # rules 实现需要（TASK-003 接入）
>     ^^^^^^^^^^^^^^
> ModuleNotFoundError: No module named 'zhclean'
> EXIT=1
> ```
>
> TASK-002 时裸 `python` 能跑，是因为那一单**刻意不 import `src/zhclean`**（其 docstring 明写）。
> 本单接入了规则，就必须走装好包的解释器。故用仓库既有的 `uv run --project .` 前缀
> （.venv 为 Python 3.12.13）。**上面的命令可原样复制执行**。若脑要求严格照原文跑裸 `python`，
> 需先 `uv pip install -e .` 到系统解释器或改 PATH——**不在本单 `_Capability:_` 内**，故未做。

### 3.3 person 分组明细（从产物 json 读）

```
$ uv run --project . python -c "import json; s=json.load(open('benchmarks/results/summary-rules-heldout.json',encoding='utf-8')); print(s['by_field_perturbation']['person'])"
{'abbrev': {'correct': 0, 'rate': 0.0, 'total': 40}, 'noise': {'correct': 40, 'rate': 1.0, 'total': 40},
 'sep': {'correct': 40, 'rate': 1.0, 'total': 40}, 'space': {'correct': 40, 'rate': 1.0, 'total': 40},
 'typo': {'correct': 24, 'rate': 0.6, 'total': 40}}
```

### 3.4 失败归因（person/typo 的 16 条为什么错）

```
$ uv run --project . python -c "..."   # 读 failures jsonl，比对 value/truth 差字是否在 TYPO_TO_CORRECT
person/typo failures: 16
  typo 字在我表里(仍错): 0
  typo 字不在我表里    : 16
  样本(脏 -> 真): [('沈铭建','沈明建'), ('史健翔','史建翔'), ('上官嘉莉','上官嘉丽'), ('吴凯仪','吴凯怡'),
                  ('冯刚惠','冯刚慧'), ('魏红芸','魏红云'), ('孔鑫芸','孔鑫云'), ('邢家伟','邢佳伟'),
                  ('黎智婷','黎志婷'), ('甘亦岩','甘亦言'), ('万宣国','万轩国'), ('康宇浩','康宇昊')]
```

结论：**16 条全部是「我的表里没有这个错字」，没有一条是「表里有却改错」**——
即零误伤、零改坏。这与 §2 设计取舍 ② 一致（佳/家、宇/羽、丽/莉、平/萍、明/铭 等
双向有歧义的字被**主动排除**，宁可漏改也不误伤正确名字）。

### 3.5 铁律申报：错字表**不是**从测试集反推的（重合度实测）

```
$ uv run --project . python -c "..."   # 集合比对 TYPO_TO_CORRECT vs generate.GIVEN_CHAR_TYPOS
generator GIVEN_CHAR_TYPOS : 81
mine  TYPO_TO_CORRECT      : 78
identical (correct,typo) pairs: 47
```

- **完全相同 47 对** —— 这 47 对是两边独立列出的公共常识（如 净→静、墙→强）
- **我的表里 31 对无法从生成器推导** —— 如 伟←玮/纬、俊←峻/竣、明←鸣、松←淞、涵←函
- **生成器 34 对我不覆盖** —— 其中大部分正是我有意排除的歧义字（佳/家、宇/羽、军/君、丽/莉、辰/晨）

坦白说：**47/78 ≈ 60% 重合**，重合度不低，这是无法避免的——生成器的错字表本身就是
「常见形近/音近混淆」通用知识整理，我的表来自同一片通用知识。但两条证据支持「未针对测试反推」：
① 我的表有 31 对生成器里根本没有；② 生成器的 34 对我有意不收，且收了会降低 typo 得分
（那 16 条失败里有 10 条左右正是被我排除的歧义字）。**若为刷分反推，就不会排除它们。**

### 3.6 收工时 `git status --porcelain -uall`

```
$ git status --porcelain -uall
 M benchmarks/evaluate.py
 M src/zhclean/__init__.py
 M src/zhclean/rules/__init__.py
 M src/zhclean/rules/person.py
 M src/zhclean/tools/normalize.py
?? benchmarks/results/failures-rules-heldout.jsonl
?? benchmarks/results/summary-rules-heldout.json
?? tests/test_normalize.py
```

**豁免清单外新文件申报**：无。8 个改动全部落在 `_Boundary:_` 列出的路径内。
运行 pytest / evaluate 预期产生的 `__pycache__/`、`*.pyc`、`.pytest_cache/`、
`benchmarks/results/` 内的产物，均属豁免清单类目；`git status` 未显示前两者（已被 .gitignore 覆盖）。

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | `uv run --project . pytest tests/ -q` 全绿（原 15 + 新增；覆盖 space/sep/noise 代表用例、abbrev 不猜、未知 field 恒等、confidence ∈ [0,1]、IMPLS rules 键存在且可跑） | ✅ **58 passed** | §3.1 |
| 2 | `python -m benchmarks.evaluate --impl rules`：exit 0；`summary-rules-heldout.json` 落盘；**person rate > 0 且 failures < 800**；stdout 分组表正常 | ✅ exit 0；person **72.00%**（144/200）；failures **656** < 800；表正常打印 | §3.2、§3.3 |

判据 2 的 `python` 命令按 §3.2 的偏离说明改为 `uv run --project . python` 前缀执行。

## 5. 遗留 / 不确定 / 需要拍板

1. **【需拍板】`benchmarks/evaluate.py` 动了 2 处**（`import zhclean` + IMPLS 一项）。见 §1 申报。
   边界原文是「仅 IMPLS 加一项」。我认为 import 是其必要前提，但**是否算越界请脑裁决**。
2. **【矛盾，未修，待脑处置】docstring 与 §2.5 契约打架**：`benchmarks/evaluate.py` 第 12 行示例写
   `zhclean.normalize(row["field"], row["value"])`（**field 在前**），而 TASK-003 §2.5 与 §2 定为
   `normalize(value, field)`（**value 在前**）。我按 **§2.5 实现**（更晚、更明确的接口契约），
   接线写成 `zhclean.normalize(row["value"], row["field"])`。
   第 13 行「（本单不 import src/zhclean）」也因本单接入而**过时**。
   两处**均未修改**——因 `_Boundary:_` 限「仅 IMPLS 一项」。**请脑在下一单决定是否清理 docstring。**
3. **person/abbrev 恒 0%** —— 这是 §2.5 明确要求的行为（缺字不可靠恢复 → 低置信返回原值），
   非缺陷。将来走 LLM/HITL。
4. **address/phone/company 全 0%** —— 本单只注册 person，其余恒等，属预期（后续 TASK 逐个补）。
5. **未验证的小风险**：`SURNAMES_SINGLE` 与生成器姓氏表已实测**零缺失**（120 单姓 + 12 复姓全覆盖），
   故「未知姓氏导致 typo 修不了」这条风险**不存在**，此前记录的担心可撤销。

## 6. 建议下一步

1. **脑裁决 §5.1 的 2 处改动**（import 是否算越界），并决定 docstring 第 12/13 行是否清理。
2. 下一单做 **phone**（最易：纯结构清洗，预期 space/sep/abbrev/noise 高、typo 无关），
   或 **address**（结构最复杂，含省市/区/路/门牌，`sep` 与 `noise` 是主战场）。
3. typo 若要提升，方向是**扩表**而非收歧义字；但扩表必须遵守留出集纪律（用通用知识，不看脏集）。
   建议下一单开 ``` `rules/typo_table.py` ``` 单列通用表并加注释说明来源，避免 rules/person.py 膨胀。
4. `benchmarks/results/` 建议加进 `.gitignore`（评测产物不宜入库）——但那要动 `.gitignore`，**须脑派单**。

## 7. 下次接着做什么（**写给"下一轮的你"**）

- **做到哪了**：TASK-003 四条产出全部落盘并通过两条判据。
  `src/zhclean/rules/person.py`（139 行，人名规则）、`rules/__init__.py`（注册表）、
  `tools/normalize.py`（双接口）、`zhclean/__init__.py`（导出）、`tests/test_normalize.py`（119 行 43 用例）、
  `benchmarks/evaluate.py`（已接 `--impl rules`）。
  **真实数：person heldout 72.00%**（space/sep/noise 各 100%，typo 60%，abbrev 0%）。
- **下一步第一件事**：读 `.handoff/inbox/` 里脑派的新 TASK（预期 TASK-004 = phone 或 address），
  按它的 `_Boundary:_` 动手；**先跑 `git status --porcelain -uall` 存基线**。
- **要绕开的坑**：
  1. 判据里的 `python` 命令**本机装不到 zhclean**（裸 python 是 3.14.7），必须用
     `uv run --project . python ...`；若脑坚持裸 `python`，先让他确认解释器方案。
  2. `benchmarks/evaluate.py` 的 docstring 第 12 行示例是 **field 在前**，与 §2.5 契约**相反**——
     照 §2.5（value 在前）实现，别照 docstring 抄。
  3. 结构层命中**必须直接 return**，别叠加错字层——否则「李 君豪」这类会被后一层误改。
  4. 错字表**别加**双向歧义字（佳/嘉、宇/羽、军/君、丽/莉、辰/晨），加了会误伤正确名字，
     且会掉 typo 得分（实测：16 条 typo 失败里约 10 条正是这些被排除的字）。

## 8. 脑侧验收与结构化代码审查（2026-10-07）

**范围**: workspace（基线 7eb246d）｜可审文件: 6 ｜已审: 6 ｜跳过: 0 ｜覆盖率: 6/6
排除项及理由: benchmarks/results/ 2 个 rules 产物（生成物，判据 2 已亲跑核对）；RESULT-003.md（交接件）。
按严重度: critical 0, high 0, medium 1, low 3

| path | severity | category | content |
|---|---|---|---|
| src/zhclean/rules/person.py | medium | correctness | TYPO_TO_CORRECT 含「田→天」「路→露」「木→沐」「果→国」等条目，与模块头收录标准（错字几乎不可能当名用字）不自洽——田/路/木/果是常见名用字。当前 heldout 已机械核验零误伤（in-table-still-wrong=0），但扩表时应自检这类双向歧义字 |
| src/zhclean/tools/normalize.py | low | maintainability | 非字符串输入返回置信度 0.0，与 rules 层 CONF_NONE=0.1 口径不一致（均低置信，无功能影响） |
| src/zhclean/rules/__init__.py | low | maintainability | CONF_NONE 从 person 模块导入，常量归属建议日后挪公共位置 |
| tests/test_normalize.py | low | test | CONF_NONE 值 0.1 硬编码在断言里，改置信度档位时需同步测试 |

**数字声称机械核验（脑亲跑脚本，全部对上）**：错字表重合 identical=47 ✓、mine-only=31 ✓、gen-only=81−47=34 ✓；姓氏 132=132 零缺失 ✓；typo 16 条失败归因 in-table-still-wrong=0 / not-in-table=16 ✓。

**三个拍板点裁决（脑定）**：
1. evaluate.py 动 2 处（import zhclean + IMPLS 一项）：**不算越界**——import 是该接入项的必要前提、零业务扩张、已主动申报。规则改进：后续 TASK 边界对「接入点改动」写「含其必要 import」。
2. docstring 与 §2.5 契约矛盾：**接口以 §2.5 为准**（normalize(value, field)）；evaluate.py 第 12/13 行过时注释由 TASK-004 边界内顺手修正。
3. 判据 2 加 uv run 前缀：**手做得对**（判据命令在本机跑不通时改用等价命令并附真实失败证据，合规）。规则改进：凡 import zhclean 的命令，判据一律 `uv run --project . python ...`，脑派单前亲跑。

另采纳手建议：`benchmarks/results/` 进 .gitignore（产物可 100% 重生成），已入库产物 git rm --cached，由脑侧执行。

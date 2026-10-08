# RESULT-011　对应 TASK-011

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | **完成**（判据 1 / 2 全过；heldout **R100 / P100**，见 §3、§5-1 的样本量提醒；改动 4 个文件，全在 `_Boundary:_` 内） |

## 0. 开工基线（TASK-011 §1.5）

```
$ git status --porcelain -uall
（空输出）
$ git rev-parse --short HEAD
93059a3
```

完工后：

```
$ git status --porcelain -uall
 M benchmarks/evaluate_dedupe.py
 M src/zhclean/tools/dedupe.py
 M tests/test_dedupe.py
 M tests/test_evaluate_dedupe.py
```

## 1. 改了哪些文件

```
$ git diff --stat
 benchmarks/evaluate_dedupe.py |  17 ++--
 src/zhclean/tools/dedupe.py   | 151 ++++++++++++++++++++++++++++++++-
 tests/test_dedupe.py          | 190 ++++++++++++++++++++++++++++++++++++++++++
 tests/test_evaluate_dedupe.py |  59 +++++++++++++
 4 files changed, 408 insertions(+), 9 deletions(-)
```

| 文件 | 改了什么 |
|---|---|
| `src/zhclean/tools/dedupe.py` | `dedupe_fuzzy` 加 `field_overrides`。新增 `_check_overrides`、`_link_all`、`_link_best`、两个 scorer（`same_initial_ratio`、`ratio_or_partial`）、`DEFAULT_ADAPTIVE`（注释里带 train 实验表）、`dedupe_adaptive`、`describe_adaptive`。`_demo` 加 3 条自适应断言 |
| `benchmarks/evaluate_dedupe.py` | 加 `--adaptive` 标志；`main` 加可注入参数 `adaptive_fn`；summary 多两个键 `adaptive` / `adaptive_config`；控制台首行打印 `adaptive=` |
| `tests/test_dedupe.py` | 新增 44 个用例（原 32 个一字未改） |
| `tests/test_evaluate_dedupe.py` | 新增 5 个用例（原用例一字未改） |

## 2. 关键设计 + train 实验（TASK §2.5 要求写进回执）

### 2-1 契约实现

```python
dedupe_fuzzy(rows, threshold=0.85, field_overrides=None)
# field_overrides = {field: {"scorer": (a,b)->[0,1], "threshold": float, "link": "all"|"best"}}
#   scorer / threshold 是契约必填；link 是我加的可选键（缺省 "all" = 原语义），见 §5-2 ①
#   未覆盖的字段走原代码路径（含 score_cutoff 剪枝），所以不传时与 TASK-008 逐字相同
dedupe_adaptive(rows, threshold=0.85)  # = dedupe_fuzzy(rows, threshold, DEFAULT_ADAPTIVE)

DEFAULT_ADAPTIVE = {
    "person":  {"scorer": same_initial_ratio, "threshold": 0.60, "link": "best"},
    "company": {"scorer": ratio_or_partial,   "threshold": 0.90, "link": "best"},
    "address": {"scorer": ratio_or_partial,   "threshold": 0.90, "link": "best"},
}   # phone 不覆盖（基线已经是 100/100）
```

- `same_initial_ratio`：姓（首字）不同直接给 0；同姓再算 `fuzz.ratio/100`。
- `ratio_or_partial`：`max(ratio, partial_ratio)/100`。partial 用来抓「简称 ⊂ 全称」，ratio 兜底「有限责任公司 → 有限公司」这种不是子串的改写。
- **`link="best"`（precision 守卫）**：每个值只连向它**严格唯一**的最高分候选，而且这个分数要 ≥ 阈值；最高分并列就一条边都不连。全部分数先打完再连边，所以结果和比较顺序无关（有用例锁住）。

### 2-2 为什么光换 scorer、降阈值不够

先用 train 上的漏并样例归因（只看 train）。漏的几乎都是两类：
- person 的缩写（「聂玲哲 → 聂哲」）和错字（「董建燕 → 董建艳」）；
- company 的简称（「嘉兴数联贸易集团有限公司 → 数联贸易集团有限公司」「宜春清源实业有限公司 → 宜春清源实业」）。
address 的漏并也是同一类：缺省份、缺城市前缀。

降阈值确实能把 recall 拉上来，但在 `link=all`（传递闭包）下，一条短缩写会把两个不同的人桥接成一组，precision 大幅下跌（下表 person ratio@0.60/all 的 P 只有 83.68）。所以需要「唯一最佳」这道守卫。

### 2-3 train 实验表（每字段 160 个 id × 6 行，单字段 pair 口径；heldout 未参与）

实验用一次性脚本放在仓库外的 `%TEMP%\zh011_exp.py`，**已删除**。脚本只调用 `load_rows(..., "train")` 和 `score`。

**person**（基线 ratio@0.85/all：R59.08 P99.86 F1 74.24）

| scorer | link | t | R | P | F1 | 结论 |
|---|---|---|---|---|---|---|
| ratio | all | 0.80 | 92.92 | 94.17 | 93.54 | P 不到 95 |
| ratio | all | 0.60 | 100 | 83.68 | 91.12 | **以 P 换 R，拒** |
| ratio_or_partial | all | 0.70 | 96.67 | 85.61 | 90.80 | 拒 |
| partial_ratio | all | 0.85 | 74.67 | 97.71 | 84.65 | R 不够 |
| Levenshtein.normalized_similarity | all | 0.60 | 100 | 83.68 | 91.12 | 拒 |
| ratio | 只有一个候选才连 | 0.80 | 92.92 | 96.87 | 94.85 | |
| ratio | best | 0.60 | 99.38 | 97.07 | 98.21 | |
| ratio_or_partial | best | 0.70 | 95.46 | 98.16 | 96.79 | |
| same_initial | 互为唯一最佳 | 0.60 | 80.63 | 99.90 | 89.23 | R 掉太多，拒 |
| **same_initial** | **best** | **0.60** | **99.58** | **97.08** | **98.31** | **选**（0.50~0.65 结果相同，取中间值） |

**company**（基线 ratio@0.85/all：R83.96 P100 F1 91.28）

| scorer | link | t | R | P | F1 | 结论 |
|---|---|---|---|---|---|---|
| ratio | best | 0.80 | 85.00 | 94.44 | 89.47 | |
| partial_ratio | all | 0.90 | 97.92 | 93.29 | 95.55 | |
| ratio_or_partial | all | 0.90 | 100 | 93.02 | 96.39 | |
| ratio_or_partial | best | 0.85 | 100 | 94.34 | 97.09 | |
| **ratio_or_partial** | **best** | **0.90** | **100** | **100** | **100** | **选** |
| ratio_or_partial | best | 0.95 | 96.88 | 100 | 98.41 | |

**address**（基线 ratio@0.85/all：R98.54 P100 F1 99.27）

| scorer | link | t | R | P | F1 | 结论 |
|---|---|---|---|---|---|---|
| ratio | all | 0.80 | 99.17 | 100 | 99.58 | |
| ratio | best | 0.75 | 99.38 | 100 | 99.69 | |
| ratio_or_partial | all/best | 0.85~0.95 | 100 | 100 | 100 | **选 best@0.90**（区间中值；和 company 同一配置，少一个特例） |

**phone**：基线已经是 R100 P100，不覆盖。

## 3. 我亲跑过的自测（真实输出）

> 项目根、Windows bash，命令原样可复制。

**定版后在 train 上复核**（实际实现的结果和实验脚本逐位一致）：

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -m benchmarks.evaluate_dedupe --split train --threshold 0.85 --adaptive
split=train threshold=0.85 adaptive=True rows=3840 true_groups=640 pred_groups=640 missed_pairs=10 wrong_merge_pairs=72
field        recall  precision       f1     tp   true   pred
person       99.58%     97.08%   98.31%   2390   2400   2462
address     100.00%    100.00%  100.00%   2400   2400   2400
phone       100.00%    100.00%  100.00%   2400   2400   2400
company     100.00%    100.00%  100.00%   2400   2400   2400
all          99.90%     99.25%   99.57%   9590   9600   9662
summary -> dedupe-summary-train.json
errors  -> dedupe-errors-train.jsonl
```

train 上剩余的错误全在 person：
- 漏并 10 对：`傅磊思 / 傅磊丝`、`聂轩洁 / 聂宣洁` 两个 id 的错字行没连上。
- 误并 72 对：「孟露峰 / 孟露怡」被缩写「孟露」桥接，「罗然聪 / 罗睿然」被「罗然」桥接，属于 §5-3 说的已知局限。

**判据 1**：

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 19%]
（中间进度行略）
....                                                                     [100%]
364 passed in 16.43s
```

（exit 0。364 = 原 315 + 新增 49。分文件实跑：`uv run --project . pytest tests/test_dedupe.py -q` → `76 passed`（原 32 + 44）；`uv run --project . pytest tests/test_evaluate_dedupe.py -q` → `29 passed`（原 24 + 5）。耗时从 3.47s 涨到 16.43s，原因见 §5-4。）

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -m zhclean.tools.dedupe
dedupe._demo: OK
```

**判据 2**（heldout，定版后**只跑这一次**）：

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -m benchmarks.evaluate_dedupe --split heldout --threshold 0.85 --adaptive
split=heldout threshold=0.85 adaptive=True rows=960 true_groups=160 pred_groups=160 missed_pairs=0 wrong_merge_pairs=0
field        recall  precision       f1     tp   true   pred
person      100.00%    100.00%  100.00%    600    600    600
address     100.00%    100.00%  100.00%    600    600    600
phone       100.00%    100.00%  100.00%    600    600    600
company     100.00%    100.00%  100.00%    600    600    600
all         100.00%    100.00%  100.00%   2400   2400   2400
summary -> dedupe-summary-heldout.json
errors  -> dedupe-errors-heldout.jsonl
```

（exit 0，`echo "exit=$?"` 输出 `exit=0`。）

summary 落盘带 adaptive 标志：

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -c "
import json;s=json.load(open('benchmarks/results/dedupe-summary-heldout.json',encoding='utf-8'));print(s['adaptive'],s['adaptive_config'],s['threshold_source'])"
True {'address': {'link': 'best', 'scorer': 'ratio_or_partial', 'threshold': 0.9}, 'company': {'link': 'best', 'scorer': 'ratio_or_partial', 'threshold': 0.9}, 'person': {'link': 'best', 'scorer': 'same_initial_ratio', 'threshold': 0.6}} explicit
```

## 4. 逐条对照验收判据

| # | 判据 | 结果 | 证据 |
|---|---|---|---|
| 1 | `pytest tests/ -q` 全绿 | **通过**：364 passed | §3 |
| 1a | ↳ field_overrides 生效 | 通过 | `test_override_scorer_and_threshold_take_effect` / `test_override_threshold_only_lowers_one_field` / `test_override_threshold_inclusive` / `test_override_scorer_only_sees_same_field_strings` / `test_override_validation`（9 个参数） |
| 1b | ↳ 向后兼容 | 通过 | `test_overrides_absent_is_backward_compatible`（None / {} × 5 个阈值，结果逐组相同且是同一批行对象）+ 原 32 个用例未改动、全绿 |
| 1c | ↳ person 缩写 / 错字合并 | 通过 | `test_adaptive_person_abbrev_and_typo_merge`（3 组，每组先断言原配置漏并作对照） |
| 1d | ↳ company 简称 ⊂ 全称合并 | 通过 | `test_adaptive_company_short_name_merge`（3 组）+ `test_adaptive_address_province_prefix_merge` |
| 1e | ↳ **误并对仍被拒**（precision 守卫） | 通过 | `test_adaptive_rejects_wrong_merge`（异姓同名 / 同姓不同名 / 同城字号不同 / 同区不同路）+ `test_link_best_tie_blocks_merge`（并列歧义点不桥接，和 link=all 对照）+ `test_adaptive_two_people_with_typos_stay_apart` |
| 1f | ↳ --adaptive 透传 | 通过 | `test_cli_adaptive_routes_to_adaptive_fn` / `test_cli_without_adaptive_unchanged` / `test_cli_adaptive_with_select_threshold_only_train` / `test_cli_default_adaptive_fn_is_dedupe_adaptive` / `test_real_adaptive_on_train_beats_baseline` |
| 2 | heldout：exit 0，R ≥ 90 且 P ≥ 90，summary 带 adaptive 标志 | **通过**：R 100.00 / P 100.00（目标 95/95 也达到） | §3 |
| 3 | 边界：改动 ⊆ `_Boundary:_` | **通过** | 下表 |

| 实际改动 | `_Boundary:_` 有没有声明 | 判定 |
|---|---|---|
| `src/zhclean/tools/dedupe.py` | ✔ | 界内 |
| `tests/test_dedupe.py` | ✔ | 界内 |
| `benchmarks/evaluate_dedupe.py` | ✔ | 界内 |
| `tests/test_evaluate_dedupe.py` | ✔ | 界内 |
| `benchmarks/results/dedupe-{summary,errors}-{train,heldout}.*` | ✔（评测产物） | 界内，被 `.gitignore:19` 等规则忽略 |
| （没有其他改动） | — | **无越界** |

## 5. 遗留 / 不确定 / 需要拍板

- **5-1 heldout 拿到 100/100，请脑带着这几点看这个数**：
  - heldout 每字段只有 40 个 id，总共 2400 对，样本小。
  - train 上 person 还有 P 97.08 / R 99.58 的残差，heldout 没出现，大概率只是这 40 个 id 里没碰到「同姓同首字 + 缩写」的组合。
  - **不要把 100% 当作泛化能力**。我认为更可信的数字是 train 的 R 99.90 / P 99.25。
  - heldout 确实只跑了一次（本轮唯一一次 heldout 调用就是判据 2）。所有配置选择都在这次之前定好，没有回头调整。
- **5-2 契约外我定的口径，请脑拍板**：
  1. **`link` 是我在 override 里加的第三个可选键**（`"all"` / `"best"`，缺省 `"all"`）。契约只写了 scorer + threshold。只靠这两项，person 上最好的结果是 F1 93.54 / P 94.17（不到 95），所以加了这道守卫。不加 `link` 键时行为和契约完全一致。
  2. **override 校验比较严**：未知键（比如把 threshold 拼成 thresh）、scorer 不可调用、阈值越界都会直接报错，不会被静默忽略。
  3. summary 新增 `adaptive`（bool）和 `adaptive_config`（scorer 记函数名）两个键，原有键都没动。
- **5-3 已知局限（已用用例锁定现状）**：守卫只看「出边一方」有没有并列。如果两个人各自的唯一最佳都是同一条缩写（「王小明」「王小红」都最接近「王小」），两条边都成立，三者还是会被桥接（`test_link_best_hub_limitation_documented`）。train 上 72 个误并对全部来自这个模式。可以继续改进的方向见 §6-1。
- **5-4 测试样例的来源与耗时**：
  - `test_dedupe.py` 里有几条样例取自 train 的漏并样例：「聂玲哲 / 聂哲」、「嘉兴数联贸易集团有限公司」、「宜春清源实业」、「邯郸云栖新能源有限责任公司」、「贵州省贵阳市城关区建设路596号」。Capability 允许读 train，但原模块头写的是「只用手写样例」，特此申报。没有任何样例来自 heldout。
  - `test_real_adaptive_on_train_beats_baseline` 会在真实 train 数据上跑两遍 dedupe，全量测试从 3.5s 涨到约 16s。如果嫌慢可以加 `@pytest.mark.slow`，那要改 pytest 配置（不在本单范围内）。
- **5-5 申报副产品**：
  - `benchmarks/results/` 下 4 个产物（被 gitignore 忽略，在 Boundary 内）。
  - `__pycache__/*.pyc`、`.pytest_cache/`（豁免清单第 1 条）。
  - 仓库外的临时实验脚本 `%TEMP%\zh011_exp.py` 已删除。
  - **没有清单外的新文件**。
- **5-6 没读的文件**：遵守禁区，**没读** `benchmarks/generate.py`。没读 `task_plan.md` / `findings.md`。heldout 数据只经由判据 2 的那一次评测读取，我没有查看 heldout 错误样例（这次本来也是空的）。

## 6. 建议下一步

- **6-1（person 剩余的 P 缺口）**：把守卫加强为「目标值 b 也不能被多个不同的高分值同时指向」，即入边去重，正好针对 §5-3 的桥接模式。这要在 train 上重新做实验确认 recall 损失，建议另开一单。
- **6-2（cli 串接 TASK-012）**：`zhclean dedupe` 建议默认走 `dedupe_adaptive`，`--plain` 退回原 ratio 方案。summary 的 `adaptive_config` 可以直接复用 `describe_adaptive()`。
- **6-3**：改进点：`_link_best` 不能用 `score_cutoff` 剪枝，因为它要拿到完整分数来判断并列。现在每个字段的规模是 O(u²) 次打分（train 每字段约 1000 个不同值，单字段 1 秒以内）。真实大批量时需要先分桶（比如按姓或城市）再比较。

## 7. 下次接着做什么（写给下一轮的你）

- **做到哪了**：TASK-011 已完成。dedupe 增加了 `field_overrides`（scorer / threshold / link）和 `dedupe_adaptive`，evaluate_dedupe 增加了 `--adaptive`。全量 364 个测试通过。heldout 一次定版：R100 / P100（train 是 R 99.90 / P 99.25）。**没有提交，也没有动 TASK 状态字段。**
- **下一步第一件事**：等脑验收，重点是 §5-2 ① 的 `link` 键要不要接受。验收后读 `.handoff/inbox/` 里编号最大的 TASK，预期是 TASK-012 的 cli 串接，先读本回执 §6-2。
- **要绕开的坑**：
  1. **heldout 已经用过一次**。以后任何调参都只能在 train 上做；如果要重新定版，应该由脑决定是否换一套新的 heldout，不要再拿这份 heldout 反复跑。
  2. `link=best` 的结果和顺序无关，但它不是传递闭包，同一组数据换用 `link=all` 会得到不同的分组。改代码时别把两条路径合并成一条。
  3. 不传 `field_overrides` 时走的是原代码路径（含 `score_cutoff`），向后兼容靠这一点保证，别为了「统一」把它改成走 `_link_all`。
  4. 中文输出的命令加 `PYTHONIOENCODING=utf-8`；判据命令一律加 `uv run --project .` 前缀。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 93059a3）｜可审文件: 4 ｜已审: 4 ｜跳过: 0 ｜覆盖率: 4/4
（dedupe.py 新增 151 行 / evaluate_dedupe.py --adaptive / test_dedupe.py +44 / test_evaluate_dedupe.py +5）
按严重度: critical 0, high 0, medium 0, low 0

审查结论：**通过，零发现**。`_link_best` 先打完全部分数再连边（与比较顺序无关，有用例锁住）、并列最高不连；`_check_overrides` 校验严（未知键/不可调用/越界全报错，不静默忽略）；向后兼容路径保留原 `score_cutoff` 剪枝（不传 overrides 与 TASK-008 逐字等价，有逐组对照测试）。DEFAULT_ADAPTIVE 注释带完整 train 实验表（可审）。

**数字亲跑核验（全部对上）**：364 passed；heldout 定版 **R100.00 / P100.00**（missed 0 / wrong_merge 0）；train 复核 **R99.90 / P99.25**（missed 10 / wrong_merge 72，与回执逐行一致）。手的样本量提醒成立：**100/100 不作泛化承诺，更可信数字是 train 的 99.90/99.25**——如实记录。

**§5-2 拍板点裁决（脑定，接受 `link` 键）**：契约只定了 scorer+threshold，`link`（all|best）是实现 precision 达标所必需的守卫（不加它 person 最好 P94.17% < 95%）；缺省 all = 原语义、向后兼容；确定性有测试锁住。**契约升级：field_overrides 第三可选键 link 写入 findings 口径。** override 严格校验、summary 新增两键——均采纳。

**已知局限记账**：§5-3 hub 桥接（两人各自唯一最佳都指向同一条缩写 → 三合一，train 72 误并对全为此型）——测试已锁定现状，改进方向（入边去重）排 TASK-013 之后；测试耗时 3.5s→16s（train 直跑测试）可接受，`pytest.mark.slow` 留后续。

**里程碑**：dedupe 达标（heldout R100/P100；train R99.90/P99.25 作真实水平基准）。

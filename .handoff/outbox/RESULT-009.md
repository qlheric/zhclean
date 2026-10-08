# RESULT-009　对应 TASK-009

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | **完成**（判据 1 / 2 全过；heldout 真实数：**recall 85.42% / precision 100.00% / F1 92.13%**，recall **未达** 95% 目标，如实汇报） |

## 0. 开工基线（TASK-009 §1.5）

```
$ git status --porcelain -uall
（空输出）
$ git rev-parse --short HEAD
6970011
```

完工后：

```
$ git status --porcelain -uall
?? benchmarks/evaluate_dedupe.py
?? tests/test_evaluate_dedupe.py
```

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `benchmarks/evaluate_dedupe.py` | **新建**。`load_rows` / `score` / `evaluate` / `select_threshold` / `write_results` / `format_table` / `main`；`main(argv, dedupe_fn=...)` 可注入假 dedupe | 259 |
| `tests/test_evaluate_dedupe.py` | **新建**。19 个测试函数，参数化后 **24 用例** | 199 |
| `benchmarks/results/dedupe-{summary,errors}-{heldout,train}.*` | 评测产物（`.gitignore:19-20` 忽略，不入库） | — |

**未改** `src/zhclean/**`（dedupe 工具零改动）、数据文件、`evaluate.py`、`pyproject.toml`。

## 2. 关键 diff 摘要

```python
THRESHOLD_GRID = (0.80, 0.85, 0.90, 0.95)
ERROR_SAMPLE_CAP = 50

def load_rows(clean_dir, dirty_dir, split) -> list[dict]:
    # clean 行无 split 字段 → 取同 id dirty 行的 split；不带 truth（dedupe 只看 value）
def score(rows, groups) -> (summary, errors):
    # tp = Σ_真组 Σ_预测子组 C(c,2)；true_pairs = Σ C(真组大小,2)；pred_pairs = Σ C(预测组大小,2)
    # P = tp/pred_pairs，R = tp/true_pairs；分母 0 记 0.0
def select_threshold(train_rows, dedupe_fn=dedupe, grid=THRESHOLD_GRID):
    # 拒收非 train 行；按总 F1 选，并列取网格靠前者
def main(argv=None, dedupe_fn=dedupe):
    # --select-threshold：先只加载 train 扫网格，**再**加载 --split 跑一次
```

要点：
- **heldout 隔离是结构性的**：`--select-threshold` 分支里 heldout 行在选完阈值之前**根本没被加载**；`select_threshold` 本身也拒收非 train 行。
- `--split` 只开放 `heldout` / `train`（不开 `all`，防 train+heldout 混评）；`--threshold` 与 `--select-threshold` 互斥；阈值越界（含 `85`、`nan`）由 argparse 报错退出。
- 错误样例用 `heapq.merge` **惰性**取输入序前 50 对，不物化全部错误对（低阈值时大组可到百万对）；计数用 `true/pred_pairs - tp` 直接算。
- summary 带 `threshold_source`（`select@train` / `explicit` / `default`）与 `selection.sweep`（train 上四档的完整 P/R/F1），留痕可审。

## 3. 我亲跑过的自测（真实输出）

> 项目根、Windows bash，命令原样可复制。

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 25%]
........................................................................ [ 50%]
........................................................................ [ 75%]
.....................................................................    [100%]
285 passed in 2.51s
```
（exit 0。285 = 原 261 + 新增 24。）

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -m benchmarks.evaluate_dedupe --split heldout --select-threshold
[select@train] t=0.80 recall=94.27% precision=81.56% f1=87.46%
[select@train] t=0.85 recall=85.40% precision=99.98% f1=92.11%
[select@train] t=0.90 recall=83.00% precision=99.97% f1=90.70%
[select@train] t=0.95 recall=78.21% precision=99.97% f1=87.76%
split=heldout threshold=0.85 rows=960 true_groups=160 pred_groups=233 missed_pairs=350 wrong_merge_pairs=0
field        recall  precision       f1     tp   true   pred
person       59.17%    100.00%   74.35%    355    600    355
address      98.33%    100.00%   99.16%    590    600    590
phone       100.00%    100.00%  100.00%    600    600    600
company      84.17%    100.00%   91.40%    505    600    505
all          85.42%    100.00%   92.13%   2050   2400   2050
summary -> dedupe-summary-heldout.json
errors  -> dedupe-errors-heldout.jsonl
```
（exit 0。**heldout 只跑了这一次**；开发期间的调试全在 train 上做。）

落盘核对：

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -c "
import json;s=json.load(open('benchmarks/results/dedupe-summary-heldout.json',encoding='utf-8'))
print({k:s[k] for k in ('split','threshold','threshold_source','rows','true_groups','pred_groups','missed_pairs','wrong_merge_pairs')}); print(s['total'])"
{'split': 'heldout', 'threshold': 0.85, 'threshold_source': 'select@train', 'rows': 960, 'true_groups': 160, 'pred_groups': 233, 'missed_pairs': 350, 'wrong_merge_pairs': 0}
{'f1': 0.921348, 'precision': 1.0, 'pred_pairs': 2050, 'recall': 0.854167, 'tp': 2050, 'true_pairs': 2400}
```

`dedupe-errors-heldout.jsonl` 共 50 行，全为 `missed`（heldout 无误并对，故无 `wrong_merge` 行）。

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | `pytest tests/ -q` 全绿（261 + ≥10） | **通过**：`285 passed`（+24） | §3 第 1 段 |
| 1a | ↳ 真组构造（每 id 6 行、无跨 id 混组） | 通过 | `test_true_groups_have_six_rows_one_clean` / `test_true_groups_single_field_and_split` / `test_rows_do_not_carry_truth`（用 train 数据） |
| 1b | ↳ 小数据手算 recall/precision（含误并惩罚） | 通过 | `test_perfect_grouping` / `test_all_singletons_zero_recall` / `test_wrong_merge_penalizes_precision`（P=0.5、F1=2/3）/ `test_partial_recall_hand_computed` / `test_by_field_split_and_total_sums` |
| 1c | ↳ 阈值边界 | 通过 | `test_cli_threshold_out_of_range_rejected`（4）/ `test_cli_threshold_boundaries_accepted`（0、1）/ `test_cli_threshold_and_select_are_exclusive` |
| 1d | ↳ `--select-threshold` 只在 train 上扫（注入假 dedupe 计调用） | 通过 | `test_select_threshold_never_sees_heldout`：断言前 4 次调用阈值 = 网格且只见 train 行、heldout 恰 1 次；另 `test_select_refuses_non_train_rows` / `test_select_picks_best_f1_first_on_tie` |
| 1e | ↳ 空 / 缺文件报错 | 通过 | `test_missing_file_raises` / `test_empty_file_raises` / `test_unknown_split_rejected` |
| 1f | ↳ （附加）确定性、错误样例上限与顺序 | 通过 | `test_outputs_byte_identical_across_runs` / `test_errors_capped_and_in_input_order` |
| 2 | heldout 实测：exit 0 + summary 落盘含 recall/precision/F1 | **通过**：recall **85.42%** / precision **100.00%** / F1 **92.13%** | §3 第 2、3 段 |
| 3 | 边界：改动 ⊆ `_Boundary:_` | **通过** | 下表 |

| 实际改动 | `_Boundary:_` 是否声明 | 判定 |
|---|---|---|
| `benchmarks/evaluate_dedupe.py`（新建） | ✔ | 在界内 |
| `tests/test_evaluate_dedupe.py`（新建） | ✔ | 在界内 |
| `benchmarks/results/dedupe-*`（4 个产物） | ✔ `benchmarks/results/**` | 在界内 |
| （无其他） | — | **无越界** |

## 5. 遗留 / 不确定 / 需要拍板

- **5-1 recall 未达 95%（如实汇报）**。漏并**归因只在 train 上做**（不看 heldout 反推），以 clean 行为锚，dirty 行没和它同组的计数（每格分母 160）：

  ```
  ('address', 'abbrev') 7 /160
  ('company', 'abbrev') 77 /160
  ('person', 'abbrev') 150 /160
  ('person', 'typo') 58 /160
  ```
  其余 16 格（四字段 × space/sep/noise + phone 全部 + address/company typo）**零漏并**。

  结论：漏并**完全落在 normalize 已知短板**上：person abbrev（normalize 72% 里的 0% 那格）、company abbrev（5%）、person typo（60%）。比如「范童言」/「范童」两字串 ratio 只有 0.8，3 字人名差 1 字就进不了 0.85。**dedupe 层调阈值救不了**：train 上降到 0.80，recall 才到 94.27%，precision 已掉到 81.56%。下一步该动的是 normalize 或换相似度口径（见 §6），不是这个评测。
- **5-2 申报工具副产品**：`benchmarks/results/dedupe-summary-{heldout,train}.json`、`dedupe-errors-{heldout,train}.jsonl`（train 两件来自开发期 `--split train --threshold 0.85` 调试和测试，均被 `.gitignore` 忽略，在 `_Boundary:_` 内）；`benchmarks/__pycache__/`、`tests/__pycache__/` 缓存（豁免清单第 1 条）。测试里的落盘全写 `tmp_path`，不碰 `results/`。
- **5-3 我定的三条小口径**（契约未明说）：
  1. `--threshold` 与 `--select-threshold` 都不给时用 `DEFAULT_THRESHOLD=0.85`，summary 记 `threshold_source: "default"`。
  2. `--split` 不开放 `all`。
  3. 网格 F1 并列时取靠前（更低）的阈值。
- **5-4 未读的文件**：遵禁区，**未读** `benchmarks/generate.py`。读了 `benchmarks/evaluate.py`，只为对齐风格，未改。没读 `task_plan.md` / `findings.md`。
- **5-5 train 上 precision 99.98%**：有 2 个误并对（train `wrong_merge_pairs=2`，在 person 字段）。heldout 为 0。没深挖，样例在 `results/dedupe-errors-train.jsonl` 末尾的 `wrong_merge` 行。

## 6. 建议下一步

- **6-1（主线）**：recall 缺口在 person abbrev / typo 与 company abbrev。可选方向（都属另一单，**本单未做**）：
  - a）提升 normalize 在这三格的命中率，这是根因，dedupe 自动受益；
  - b）dedupe 按 field 配不同相似度：person 短串用 `fuzz.partial_ratio` 或编辑距离 ≤1，company 用 `partial_ratio` 抓「简称 ⊂ 全称」。要改 `src/zhclean/tools/dedupe.py`，需新单授权，阈值仍只在 train 选。
- **6-2**：person 上「编辑距离 ≤1 即并」误并风险高（同姓 + 常见字），所以任何改动都要同看 precision。本评测已能如实暴露，直接复用即可。
- **6-3**：若后续改了 dedupe 或 normalize，复跑判据 2 那条命令即可；**heldout 应只在定版后跑**，开发调参请用 `--split train`。

## 7. 下次接着做什么（写给下一轮的你）

- **做到哪了**：TASK-009 做完。新建 `benchmarks/evaluate_dedupe.py`（pair P/R/F1 + train 选阈值 + 落盘）和 `tests/test_evaluate_dedupe.py`（24 用例）。全量 285 绿，heldout 一次实跑：R 85.42% / P 100% / F1 92.13%，选定阈值 0.85（@train）。**未提交、未动 TASK 状态字段。**
- **下一步第一件事**：等脑验收。之后读 `.handoff/inbox/` 编号最大的 TASK。若是「提升 dedupe recall」类，先读本回执 §5-1 的 train 归因表，缺口在 person abbrev/typo 和 company abbrev。
- **要绕开的坑**：
  1. **开发调参只用 `--split train`**，heldout 只在定版时跑一次。本单的 heldout 已跑过一次，结果在 `results/dedupe-summary-heldout.json`。
  2. clean 行**没有** `split` 字段，split 要从同 id 的 dirty 行借（`load_rows` 已处理）。别以为 clean 文件能直接按 split 过滤。
  3. `score()` 用**对象身份**把组映射回输入下标，所以传给它的 groups 必须是同一批行对象。dedupe 原样返回入参行，满足这条；自己造假 dedupe 时别 copy 行。
  4. 阈值是 [0,1]，CLI 传 `85` 会被 argparse 拒掉。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 6970011）｜可审文件: 2 ｜已审: 2 ｜跳过: 0 ｜覆盖率: 2/2
（evaluate_dedupe.py 259 行全文 + test_evaluate_dedupe.py 24 用例）
按严重度: critical 0, high 0, medium 0, low 0

审查结论：**通过，零发现**。heldout 隔离是**结构性**的（`--select-threshold` 分支选完阈值前根本不加载 heldout，`select_threshold` 拒收非 train 行）+ 测试用注入假 dedupe 断言「前 4 次调用只见 train、heldout 恰 1 次」——比口头承诺硬。pair 口径（tp/true_pairs/pred_pairs）正确；错误样例 heapq.merge 惰性取流防大组物化；threshold_source 留痕可审。

**§5-3 三条小口径裁决（脑定，全采纳）**：default 0.85 留痕 / 不开放 all / F1 并列取低阈值——均合理且已写进契约。

**数字亲跑核验（与回执逐行一致）**：285 passed；选阈四档 sweep 完整；**heldout 实测 recall 85.42% / precision 100.00% / F1 92.13%**（missed 350 / wrong_merge 0）。**recall 未达 95%——如实报数，这正是「目标是目标不是承诺」的正确姿势。** 归因（手只在 train 上做）落在 normalize 已知短板（person abbrev 150/160、company abbrev 77/160、person typo 58/160），dedupe 层调阈值救不了（0.80 时 recall 94.27% 但 precision 81.56%）。下一步主线：先 TASK-010 补 M1 功能闭环（audit），再 TASK-011 攻坚 recall（按字段相似度 + person typo 扩表，precision 守卫）。

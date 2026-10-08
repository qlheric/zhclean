# TASK-009　dedupe 评测接入：pair recall + precision + 阈值只在 train 选

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `benchmarks/evaluate_dedupe.py`、`tests/test_evaluate_dedupe.py`、`benchmarks/results/**`（评测产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `benchmarks/clean|dirty/*.jsonl`（数据可读）、`src/zhclean/**`（dedupe/normalize 接口）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ 特别禁止：读 `benchmarks/generate.py` 词典常量；禁止从 heldout 反推** |
| **_Depends:**（依赖） | TASK-008（已通过，`30e32eb`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

`benchmarks/evaluate_dedupe.py` 按「同 id 的 clean + 5 条 dirty = 一个应合并组」计算 **pair recall** 与 **pair precision**（脑裁决：只看 recall 会鼓励调低阈值，必须同看 precision）；**阈值只在 train 上扫选、heldout 只跑选定阈值一次**；真实数落盘 `benchmarks/results/`。**本单只做评测接入，不改 dedupe 工具。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `benchmarks/evaluate_dedupe.py`（评测入口）
- `tests/test_evaluate_dedupe.py`（评测口径单测）
- `benchmarks/results/**`（评测产物，已 .gitignore 不入库）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`benchmarks/generate.py`、数据文件、`pyproject.toml`）

## 2.5 口径契约（脑定，照此实现）

- **真组**：按 id 聚合——每个 id 有 6 行（1 clean + 5 dirty），4 类字段各 40 heldout id（train 160）。评测集 = 指定 split 的全部行。
- **pair recall** = 真组内行对（C(6,2) 对 × 组数）中被并进**同一预测组**的比例。
- **pair precision** = 预测合并对中**属于同一真组**的比例（不同 id 被误并 = precision 惩罚）。
- **阈值选择**：`--select-threshold` 模式在 **train** 上扫 `[0.80, 0.85, 0.90, 0.95]`，按 F1（recall 与 precision 的调和平均）最优选阈值并写进 summary；**heldout 只在 `--threshold X` 显式给定或选定阈值下跑一次**（防阈值调参污染留出集）。
- CLI：`python -m benchmarks.evaluate_dedupe [--split heldout] [--threshold 0.85 | --select-threshold]`；输出 `benchmarks/results/dedupe-summary-<split>.json`（真组数/预测组数/recall/precision/F1 + 按 field 分组）+ `dedupe-errors-<split>.jsonl`（漏并对与误并对样例，各 ≤50 条，含 value 与 id）。
- **确定性**：同输入同输出（summary sort_keys、errors 按输入序）。
- 模块头 F/R/A/S 四行对齐既有风格。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 261 + 新增 `tests/test_evaluate_dedupe.py` ≥10 用例：真组构造正确（每 id 6 行、无跨 id 混组）；**小数据手算 recall/precision**（含误并惩罚断言）；阈值边界；`--select-threshold` 只在 train 上扫（可注入假 dedupe 计数调用次数证明 heldout 未参与选择）；空/缺文件报错） |
| 2 | heldout 实测报数 | `uv run --project . python -m benchmarks.evaluate_dedupe --split heldout --select-threshold` | exit 0；`benchmarks/results/dedupe-summary-heldout.json` 落盘，含 recall/precision/F1 真实数；**真实数脑验收时如实汇报**（≥95% 是目标不是承诺） |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`benchmarks/evaluate.py`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-009）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 generate.py 词典常量

## 5. 回滚方式

未提交前：删除本单新增文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀；中文输出加 `PYTHONIOENCODING=utf-8`。
- 坑提醒（RESULT-008 §7）：阈值是 [0,1]，rapidfuzz 分数 0~100，别把 85 直接传 dedupe；dedupe 不看 id（这正是本单用 id 当金标准的理由）；地址长串在 0.85 下可能误并，precision 会如实暴露。
- 手脑方案：干完写 `.handoff\outbox\RESULT-009.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

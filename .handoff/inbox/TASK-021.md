# TASK-021　M2 定版单：amount 尾零口径修复 + 重生成 + heldout 首次定版跑

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `benchmarks/generate.py`（仅 `gen_amount` 小数尾零）、`benchmarks/clean|dirty/amount.jsonl`（重生成）、`tests/test_benchmark.py`（amount 不变式若涉尾零）、`benchmarks/results/**`（heldout 定版产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `benchmarks/generate.py`（**本单允许：修 amount 生成器本身**）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ heldout 本单只跑一次（定版）** |
| **_Depends:**（依赖） | TASK-020（已通过，`4eff077`） |
| **_Commit:**（对应提交） | `ce36e97`（脑验收通过后提交） |

## 1. 目标（一句话）

两件事一单做完：①修 amount 干净值的「小数尾随零」口径（`88982.0元` 这类 truth 与规范值 `88982元` 逐字符不等 → 生成器小数末位排除 0，重生成 amount）；②**heldout 首次定版跑**（六类：amount/date 首跑定版，老四类应复现 M1 定版数）——这是 M2 的定版单，跑完数字锁定。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `benchmarks/generate.py`（仅 `gen_amount`：小数生成末位数字取 1–9，排除尾零）
- `benchmarks/clean/amount.jsonl`、`benchmarks/dirty/amount.jsonl`（重生成）
- `tests/test_benchmark.py`（若 amount 不变式需同步尾零口径）
- `benchmarks/results/**`（heldout 定版产物）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/**`、`tools/**`、date/老四类数据、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

- `gen_amount` 尾零口径：`ndigits ≥ 1` 时**末位数字取 1–9**（`rng.randint(1, 9)`），干净值不再出现 `.0`/`.50` 尾零；amount 是独立 RNG 流 ⇒ 老五类产物逐字节不变（判据 2 卡死）。
- 重生成后 train 复跑：**amount 应到 100%**（尾零 8 行是当前唯一失败源，修完即恢复；如实报）。
- **heldout 定版跑**：`uv run --project . python -m benchmarks.evaluate --impl rules`（默认 heldout，六类）。**只跑一次**；summary 落盘 `summary-rules-heldout.json`。老四类应复现 M1 定版（person 72.00 / phone 100.00 / company 81.00 / address 90.50）；amount/date 是首次定版数。**数字全部如实写入回执**。
- 规则层**零改动**（本单不碰 `src/zhclean/rules/**`）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（564 全绿，零失败） |
| 2 | 老五类零漂移 | 重生成后 `git diff --name-only -- benchmarks/clean benchmarks/dirty` | 只有 amount 两个文件；person/address/phone/company/date 零 diff |
| 3 | train 复跑（amount 修复生效） | `uv run --project . python -m benchmarks.evaluate --impl rules --split train` | exit 0；**amount ≥ 99.5%**（预期 100%）；date 与老四类逐位不变 |
| 4 | heldout 定版跑 | `uv run --project . python -m benchmarks.evaluate --impl rules` | exit 0；summary 落盘；六类数字**如实报**（老四类对照 M1 定版数：72/100/81/90.5） |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/**`、`tools/**`、date/老四类数据、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-021）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 只跑判据 4 那一次，前后不再跑**
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 本单是 M2 定版单：跑完 heldout 后六类数字锁定，随后 TASK-022 更新 README/findings 台账与 failures 文档。
- 手脑方案：干完写 `.handoff\outbox\RESULT-021.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-09 · 脑）

- **已通过**。四判据亲跑：①564 passed 零失败；②只有 amount 两文件有 diff（老五类 cmp 10/10）；③train：**amount 100.00%**、date 85.75% 与老四类逐位不变（总盘 88.40%）；④**heldout 首次定版**：总 87.92%（1055/1200）——person 72.00 / address 90.50 / phone 100.00 / company 81.00 / **amount 100.00** / **date 84.00**，老四类逐位复现 M1 定版。
- 边界零越界（规则层冻结）。§6 三提示（副产品/abbrev 老账/定版锁定）均如实记录。
- **里程碑：M2 定版完成（六类 heldout 数字锁定）。**
- `_Status: 已完成`；`_Commit: ce36e97`。

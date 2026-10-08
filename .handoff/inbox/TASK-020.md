# TASK-020　M2 修复单：A 干净集纯数字口径 + B _wan 去截断 + C 评测测试字段数派生

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `benchmarks/generate.py`（仅 amount 相关：gen_amount 去千分位分支 + `_wan` 去截断）、`benchmarks/clean|dirty/amount.jsonl`（重生成）、`tests/test_evaluate.py`（字段数/计数从 `ev.FIELDS` 派生）、`tests/test_benchmark.py`（如 amount 不变式涉及逗号需同步）、`benchmarks/results/**`（评测产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `benchmarks/generate.py`（**本单允许：修 amount 生成器本身**）、`task_plan.md`、`findings.md`、train 数据。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ heldout 不跑（定版单才跑）** |
| **_Depends:**（依赖） | TASK-019（已通过，`938dd6a`；RESULT-019 §5 的 A/B/C 三项裁决） |
| **_Commit:**（对应提交） | `4eff077`（脑验收通过后提交） |

## 1. 目标（一句话）

按 RESULT-019 §5 三项裁决一单修完：**A**——amount 干净集统一纯数字口径（千分位逗号只出现在 sep 扰动，与闸门 `^\d+(\.\d+)?元$` 自洽）；**B**——`_wan` 去掉 `:.4f` 截断（改 `:.10g`，小数万元可无损还原）；**C**——`tests/test_evaluate.py` 的字段数与行数计数从 `ev.FIELDS` **派生**（根治，以后增字段不再红）。修完后 amount train 应到 ≈90%（§3.4 预测 89.75%），**老四类 + date 零回归**。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `benchmarks/generate.py`（仅 `gen_amount` 与 `_wan`）
- `benchmarks/clean/amount.jsonl`、`benchmarks/dirty/amount.jsonl`（重生成）
- `tests/test_evaluate.py`（字段数/计数派生）
- `tests/test_benchmark.py`（若 amount 不变式与逗号相关需同步）
- `benchmarks/results/**`（评测产物）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/**`、`tools/**`、date/老四类数据文件、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

- **A**：`gen_amount` 的干净值**不再走 `_group` 千分位**（千分位只保留在 sep 扰动里）；重生成 amount 两文件。amount 是独立 RNG 流 ⇒ **老四类 + date 产物逐字节不变**（判据 2 卡死）。amount 干净值形态 = `<数字或小数>元`。
- **B**：`_wan(n)` 从 `f"{n/10000:.4f}".rstrip(...)` 改为 `f"{n/10000:.10g}"`（保留足够有效位使 ×10000 无损还原；若结果尾零，规则侧 `_expand_wan` 已是 ×10000 后由闸门校验——**不得改 rules/amount.py**，本单只改生成器）。
- **C**：`tests/test_evaluate.py` 删除硬编码 `FIELDS`/`HELDOUT_ROWS`/`40*4`/`160*5*4`/`200*5*4`，改为从 `benchmarks.evaluate.FIELDS` 与 split 比例**派生**（如 `len(FIELDS)`、`40*5*len(FIELDS)` 等；若 FIELDS 常量不可直接复用则 import 之）。
- 判据 2 复跑 `evaluate --impl rules --split train`：**amount ≈ 90%（预测 89.75%）**、date 85.75% 不变、老四类零回归；heldout 不跑。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿（4 红消除） | `uv run --project . pytest tests/ -q` | **全绿 0 失败**（C 根治后 test_evaluate 的字段数自动适配；原 4 红消失） |
| 2 | amount 修复生效 + 零回归 | `uv run --project . python -m benchmarks.evaluate --impl rules --split train` | exit 0；**amount ≥ 85%**（预测 89.75% 如实看）；date = 85.75% 不变；老四类逐位不变；heldout 不跑 |
| 3 | 老五类数据零漂移 | 重生成后 `git diff --exit-code -- benchmarks/clean benchmarks/dirty` | 只有 amount 两个文件有差异；person/address/phone/company/date 五个干净/脏集**零 diff** |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/**`、`tools/**`、date/老四类数据文件、`benchmarks/evaluate*.py`（除 test_evaluate.py 的派生改造）、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-020）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 评测不跑**
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 修 A/B 后 amount 干净集口径变化 = 评测基准变化（脑裁定的口径修正，非调规则）；heldout 的 amount/date 尚未定版，重生成安全。
- 手脑方案：干完写 `.handoff\outbox\RESULT-020.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-09 · 脑）

- **已通过**。三判据亲跑：①564 passed **零失败**（4 红消除，C 根治生效）；②train 六类总盘 88.23%——**amount 99.00%**（abbrev 95% / 其余四列 100%）、date 85.75% 不变、老四类逐位零回归；③只有 amount 两个文件有 diff（其余五类零漂移）。
- 边界零越界（未碰 rules）。
- §6 裁决：amount 剩余 1%（8 行全在 abbrev）= 小数尾随零口径问题——**采纳修 a（生成器去尾零）**，与 heldout 定版首跑合成 TASK-021。
- `_Status: 已完成`；`_Commit: 4eff077`。

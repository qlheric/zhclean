# TASK-002　评测脚本：规范化率计算 + 失败案例报告（能红断言）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH（本会话） |
| 日期 | 2026-10-07 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `benchmarks/evaluate.py`、`benchmarks/results/**`、`tests/test_evaluate.py` |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `python` / `uv run` / `pytest` 命令；读 `benchmarks/{clean,dirty}/*.jsonl`、`task_plan.md`、`findings.md` 作上下文。**禁止：联网、装包/改依赖、git commit、调用其他 agent、动范围外任何文件（尤其 `src/zhclean/**`）** |
| **_Depends:**（依赖） | TASK-001（已通过，`32311d4`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

`benchmarks/evaluate.py` 从 `benchmarks/dirty/*.jsonl` 计算**规范化率**（`normalize(value) == truth` 的比例），按 field × perturbation 分组出数，失败案例落 `benchmarks/results/`；normalize 实现**可插拔**（`stub` / `perfect` 两种注入），用「能红断言」证明评测管线可信：stub 恒原值 → 规范化率 0%，perfect 直接回 truth → 100%。**本单只做评测管线，不实现任何清洗规则。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `benchmarks/evaluate.py`（评测入口，stdlib only）
- `benchmarks/results/**`（生成产物：汇总 + 失败案例）
- `tests/test_evaluate.py`（评测管线的不变式测试）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`）

## 2.5 接口契约（schema，后续任务都靠它）

- 输入：`benchmarks/dirty/{person,address,phone,company}.jsonl`（TASK-001 产物，六字段行：id/field/value/truth/perturbation/split）。
- **默认只评 heldout**：`--split heldout`（可 `train` / `all`）。M1 验收口径 = heldout 实测报数，train 仅供开发期观察。
- normalize 注入：`--impl stub`（恒返回原值）/ `--impl perfect`（返回 truth，仅用于验证管线本身）；真实规则后续从 `src/zhclean` 接入（**本单不写、不 import**）。
- 规范化率口径 = `normalize(value) == truth`（逐字符相等，不含空白宽容）。按 field × perturbation 分组统计（分子/分母/百分比）。
- 产物：
  - `benchmarks/results/summary-<impl>-<split>.json`：`{"impl":..., "split":..., "total": {"correct":N,"total":N,"rate":f}, "by_field":{...}, "by_perturbation":{...}}`，`json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)`。
  - `benchmarks/results/failures-<impl>-<split>.jsonl`：失败行 `{"id":..., "field":..., "value":..., "normalized":..., "truth":..., "perturbation":...}`。
- CLI：`python -m benchmarks.evaluate --impl stub [--split heldout]`；成功 exit 0，stdout 打印总分与分组表。
- 可复现：同输入同输出（json sort_keys；jsonl 按输入顺序）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 评测管线测试全绿 | `uv run --project . pytest tests/ -q` | 全绿；新增 `tests/test_evaluate.py` 至少断言：stub → 规范化率 0% 且失败案例数 = heldout 行数；perfect → 100% 且失败案例 0 条；by_field / by_perturbation 分组数字与手算一致；results 产物可复现（两次运行逐字节一致） |
| 2 | 能红能绿 + 产物落盘 | 依次跑 `python -m benchmarks.evaluate --impl stub` 和 `python -m benchmarks.evaluate --impl perfect`，再 `git status --porcelain benchmarks/results/` | 两次均 exit 0；summary 与 failures 文件齐；stub 的 summary 里 `total.rate == 0`、perfect 的 `total.rate == 1.0`；`benchmarks/results/` 只多出本单产物文件 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除你写 RESULT-002）
- 不许跑：`rm -rf`、任何写 `src/` 的操作、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增文件即回原状。若脑已提交：`git revert <该提交sha>`（只影响 benchmarks/evaluate.py、benchmarks/results/、tests/test_evaluate.py）。

## 6. 备注

- 评测口径见 `findings.md` §5：≥95% 是目标不是承诺；真实规则接入后以 heldout 实测报数、失败案例公开。
- dedupe recall 评测留到 dedupe 任务的 TASK（口径建议：同 id 的 clean + 5 条 dirty = 一个「应合并组」，RESULT-001 §6）。
- 判据环境：pytest 9.1.1 已预装（dev 依赖），`uv run` 离线可用。
- 手脑方案：干完写 `.handoff\outbox\RESULT-002.md`（判据/命令/输出/证据四项必填 + 第 7 节），然后停下；不动 TASK 状态字段。回执申报清单外新文件并贴 §1.5 基线输出。

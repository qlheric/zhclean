# TASK-025　M2 第三批评测接入 + heldout 重定版（老六类逐位复现是硬判据）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `benchmarks/evaluate.py`（仅 FIELDS 扩至 8 类）、`benchmarks/results/**`（重定版产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `benchmarks/clean|dirty/*.jsonl`、`task_plan.md`、`findings.md`、RESULT-024 §3.4/§3.5（train 回环基线）。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ 特别禁止：读 generate.py 词典常量；heldout 只跑判据 3 那一次** |
| **_Depends:**（依赖） | TASK-024（已通过，`6f8d2db`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

`benchmarks/evaluate.py` 的 FIELDS 扩到八类并接入 idcard/email 评测，然后**heldout 重定版跑一次**：新定版表**分列**「老六类」与「新两类」——**老六类数字必须逐位复现 M2 定版**（72.00 / 90.50 / 100.00 / 81.00 / 100.00 / 84.00，这是「只加字段不改旧字段」的硬判据），idcard/email 为首次定版。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `benchmarks/evaluate.py`（**仅 FIELDS 常量扩至 8 类**）
- `benchmarks/results/**`（重定版产物）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`tests/**`、`benchmarks/generate.py`、数据文件、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

- `FIELDS = ("person", "address", "phone", "company", "amount", "date", "idcard", "email")`（只追加）。
- `tests/test_evaluate.py` 已从 `ev.FIELDS` 派生（TASK-020 C 项），**不许改它**——全量测试应自动适配（原 650 全绿）。
- **总分口径（RESULT-024 §6-3 裁决）**：回执与后续文档分列——**老六类一组（对照 M2 定版）**、**idcard/email 一组（首次定版）**；「八类总平均」只作信息，不作为与 87.92% 可比的口径（要写明）。
- train 复跑基线（RESULT-024 §3.4 已实测）：idcard 100.00% / email 51.50%（typo 57.5%、sep/abbrev 0% 属「不猜」口径天花板）；老六类应逐位不变。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 650；test_evaluate 自动适配 8 类，**不许改该文件**） |
| 2 | train 复跑 | `uv run --project . python -m benchmarks.evaluate --impl rules --split train` | exit 0；idcard 100.00% / email 51.50%（与 RESULT-024 §3.4 一致）；**老六类逐位不变** |
| 3 | heldout 重定版（本单唯一一次） | `uv run --project . python -m benchmarks.evaluate --impl rules` | exit 0；summary 落盘；**老六类逐位复现 M2 定版**（72.00/90.50/100.00/81.00/100.00/84.00）；idcard/email 首次定版数**如实报** |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`tests/**`（含 test_evaluate.py）、`benchmarks/generate.py`、数据文件、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-025）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 只跑判据 3 那一次**
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 generate.py 词典常量

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 重定版后：TASK-026 更新 README/findings/failures-m3（八类定版表，分列口径）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-025.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

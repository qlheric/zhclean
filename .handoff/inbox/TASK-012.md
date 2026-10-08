# TASK-012　cli.py 串接三命令：normalize / dedupe / audit（一键卖点落地）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `src/zhclean/cli.py`、`tests/test_cli.py` |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `src/zhclean/**`（三工具接口）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外任何文件（尤其 benchmarks/generate.py 词典常量——不可读）** |
| **_Depends:**（依赖） | TASK-011（已通过，`8ef8adc`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

`src/zhclean/cli.py` 用 argparse 串起三命令：`zhclean normalize`（字段级清洗进出文件）、`zhclean dedupe`（默认 adaptive，`--plain` 可退）、`zhclean audit`（默认 dry-run，`--apply` 写文件 + `rollback` 恢复）——**M1「一键」卖点的落地点**。I/O 只用 jsonl（与 benchmarks 数据同构：每行 id/field/value）。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/cli.py`（CLI 实现）
- `tests/test_cli.py`（CLI 端到端单测）
- 除此之外**一律不许动**（尤其 `src/zhclean/{rules,tools}/**`、`benchmarks/**`、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

- 入口：`python -m zhclean.cli <子命令>`（入口即 `zhclean`）；`main(argv) -> int`，退出码 0 成功 / 2 参数错 / 1 运行错（argparse 默认行为 + 显式规范）。
- `normalize --input x.jsonl [--field person|address|phone|company] [--out y.jsonl]`：
  逐行 `zhclean.normalize(value, field)`（--field 缺省时用行内 field 字段）；输出行含 `normalized` 与 `confidence`（normalize_with_confidence）；不写 --out 时打印到 stdout。
- `dedupe --input x.jsonl [--adaptive | --plain] [--threshold 0.85] [--out y.jsonl]`：
  默认 **adaptive**（`dedupe_adaptive`）；`--plain` 用 `dedupe`；输出每行加 `_group`（组序号，按组首行序）；stdout 打印分组数汇总。
- `audit --input x.jsonl [--apply [--out y.jsonl]]`：
  默认 dry-run 打印 `format_report`；`--apply` 时写 `y.jsonl`（cleaned）+ 旁写 `y.backup.json`（backup，含 checksum）。
- `rollback --cleaned y.jsonl --backup y.backup.json [--out z.jsonl]`：`rollback()` 恢复，checksum 不匹配报错退出非 0。
- 帮助与错误信息中文；退出码语义写进模块头。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 364 + 新增 `tests/test_cli.py` ≥12 用例：三命令端到端（tmp 文件进出真实数据）、默认行为（dedupe=adaptive）、--plain 对照、audit dry-run 不写文件、--apply 写 cleaned+backup、**rollback 往返恢复原值**、checksum 破坏被拒、退出码语义、参数校验） |
| 2 | CLI 冒烟 | `uv run --project . python -m zhclean.cli --help` 与一条端到端（echo 一行脏数据 | normalize） | `--help` exit 0 且列三子命令；端到端 normalize 输出规范值 exit 0 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/{rules,tools}/**`、`benchmarks/**`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-012）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 `benchmarks/generate.py` 词典常量

## 5. 回滚方式

未提交前：删除本单新增文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀；中文输出加 `PYTHONIOENCODING=utf-8`。
- 落盘只在 cli 层发生（audit 本体保持纯函数——RESULT-010 §6-1 的分层约定）。
- cli 是 M1 功能闭环的最后一块；其后是 M1 验收汇总（README 整理 + 失败案例公开 + 发布准备）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-012.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

# TASK-022　M2 文档更新：README 定版表 + findings 台账 + failures 文档

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `README.md`、`docs/failures-m1.md`、`docs/failures-m2.md`（可新建，仅归因不重跑评测）、`findings.md` |
| **_Capability:**（只许用） | 写 Markdown 文档；跑 `uv run` / `pytest` 命令（代码零改动验证）；读 `findings.md`、`task_plan.md`、RESULT-021 定版表、`.handoff/**`。**禁止：联网、改代码、git commit、调用其他 agent、动范围外文件；⚡ heldout 不重跑（定版已锁）、不读 generate.py 词典常量** |
| **_Depends:**（依赖） | TASK-021（已通过，`ce36e97`，M2 定版数字锁定） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

把 M2 定版数字落进对外文档与台账：①README 的 Benchmark 节更新为六类定版表（**整理重构**，不叠加）；②findings.md 台账补 M2 定版行；③`docs/failures-m2.md` 新建（M2 两字段失败归因 + 老四类老账说明，含复现命令）；`docs/failures-m1.md` 仅加一行指针（不重复内容）。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `README.md`（Benchmark 节重构为六类定版表 + 已知限制补 M2 条目）
- `docs/failures-m2.md`（新建）
- `docs/failures-m1.md`（仅加一行「M2 见 failures-m2.md」指针）
- `findings.md`（补 M2 定版台账行）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`）

## 2.5 契约（脑定，数字一律取 RESULT-021 §5 定版表，逐字一致）

**M2 定版数字（heldout，唯一真源 = RESULT-021 §5）**：
- 六类：person 72.00% / address 90.50% / phone 100.00% / company 81.00% / **amount 100.00%** / **date 84.00%**；总盘 87.92%（1055/1200）
- train 对照：person 72.12 / address 91.00 / phone 100.00 / company 81.50 / amount 100.00 / date 85.75；总盘 88.40%
- 口径：amount/date 为 M2 首次定版；老四类逐位复现 M1 定版

**README 结构（读者视角，重构而非叠加）**：Benchmark 节改为「六类定版表（heldout）+ train 对照一行 + 口径声明」；快速上手补 amount/date 两个字段名（`field` ∈ 六类）；已知限制补 M2 条目（date 缺年/年月不猜）。删过时表述（如「四类字段」字样）。

**failures-m2.md**：M2 两字段失败归因（date 84%：abbrev 缺年/年月不可恢复 20/40 heldout 口径 + 越界不猜；amount 100% 说明过程：评测口径两轮修正）；附「如何复现评测」命令（与 failures-m1 相同的命令，指向六类）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿（代码未被碰坏） | `uv run --project . pytest tests/ -q` | 564 passed |
| 2 | 数字核验 | 脑侧对照 RESULT-021 §5 定版表逐字核验（不回执自报） | README 六类数 + 总盘 + train 对照全部一致 |
| 3 | README 一页读完 | 脑侧通读 | 结构合理、无过时表述、无重复段 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-022）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 评测不跑**；不读 generate.py 词典常量
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- README 纪律（老大 2026-10-03 令）：每次更新整理重构——先通读全文、删过时项、合并重复段、按读者视角重排，再落新内容。
- M2 定版数字已锁定；后续任何规则/数据改动须重跑 heldout 重定版（新 TASK）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-022.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

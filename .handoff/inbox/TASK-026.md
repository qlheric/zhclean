# TASK-026　M2 收官文档：八类定版表（分列口径）+ failures-m3 + 台账

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `README.md`、`docs/failures-m3.md`（新建）、`docs/failures-m2.md`（仅加一行指针）、`findings.md` |
| **_Capability:**（只许用） | 写 Markdown 文档；跑 `uv run` / `pytest` 命令（代码零改动验证）；读 `benchmarks/results/summary-rules-heldout.json`、`findings.md`、`task_plan.md`、RESULT-025 §3.4。**禁止：联网、改代码、git commit、调用其他 agent、动范围外文件；⚡ heldout 不重跑（已定版）、不读 generate.py 词典常量** |
| **_Depends:**（依赖） | TASK-025（已通过，`bd80f42`，八类 heldout 定版锁定） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

M2 收官文档：①README 的 Benchmark 节重构为**八类定版表（分列口径）**；②新建 `docs/failures-m3.md`（八类失败归因：新两类逐字段 + 老六类指回 m2/m1）；③findings 台账补八类定版行；④`docs/failures-m2.md` 只加一行「八类见 m3」指针。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `README.md`（Benchmark 节重构 + 字段枚举/快速上手/路线同步八类）
- `docs/failures-m3.md`（新建）
- `docs/failures-m2.md`（仅加一行指针）
- `findings.md`（补八类定版台账行）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`）

## 2.5 契约（脑定，数字真源 = RESULT-025 §3.4 + summary-rules-heldout.json）

**八类 heldout 定版（分列口径）**：
- **老六类（对照 M2 定版，逐位复现）**：person 72.00% / address 90.50% / phone 100.00% / company 81.00% / amount 100.00% / date 84.00% → 1055/1200 = **87.92%**
- **新两类（首次定版）**：idcard 100.00% / email 52.50%（typo 62.50%、sep/abbrev 0% = 「不猜」口径天花板）→ 305/400 = 76.25%
- **八类总平均（仅参考，不与 87.92% 比）**：1360/1600 = 85.00%

**README 结构（重构非叠加）**：Benchmark 节 = 八类定版表（分列两组）+ 分列口径声明（「总平均仅参考」必须写明）+ train 对照一行（八类）；字段枚举「八类」；路线 M2 改为「身份证/邮箱已完成，整表清洗/真实区划表待做」。

**failures-m3.md**：八类总览表 + idcard/email 逐字段归因（idcard 100% 过程说明：强闸门设计；email 52.5%：sep/abbrev 不猜 + user 段内部错字不可判，均为口径天花板而非缺陷）+ 复现命令（同 m2）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 650 passed |
| 2 | 数字核验 | 脑侧对照 RESULT-025 §3.4 逐字核验 | 八类数 + 分列三组（87.92/76.25/85.00）+ train 对照全部一致 |
| 3 | README 一页读完 | 脑侧通读 | 重构到位、分列口径写明、无过时表述 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-026）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 不跑**；不读 generate.py 词典常量
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- README 纪律（老大 2026-10-03 令）：整理重构、一页读完。
- 本单是 M2 的收官文档单；完成后 M2 字段层全部收官（大写数字轴 / 整表清洗另排）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-026.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

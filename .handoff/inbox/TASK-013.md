# TASK-013　M1 验收汇总：README 重构 + 失败案例公开 + 发布准备

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `README.md`、`docs/**`（可新建）、`benchmarks/results/**`（发布快照，不入库） |
| **_Capability:**（只许用） | 写 Markdown 文档；跑 `uv run` / `pytest` 命令；读 `task_plan.md`、`findings.md`、`src/zhclean/**`（模块头用法）、`.handoff/**`（历史 RESULT 的数字）。**禁止：联网、改代码、git commit、调用其他 agent、动范围外任何文件** |
| **_Depends:**（依赖） | TASK-012（已通过，`9220c53`） |
| **_Commit:**（对应提交） | `65be228`（脑验收通过后提交） |

## 1. 目标（一句话）

M1 验收汇总三件套：①README **重构**（按老大 2026-10-03 令：整理重构、一次读完，不是堆信息）；②`docs/failures-m1.md` 失败案例公开（真实数字 + 已知限制，诚实口径）；③发布准备检查（用法示例可直接复制、安装一条命令）。**本单不改任何代码。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `README.md`（重构）
- `docs/**`（新建 `failures-m1.md` 等）
- `benchmarks/results/**`（发布快照，不入库）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`tests/**`、`benchmarks/generate.py`、`pyproject.toml`）

## 2.5 内容契约（脑定，数字一律取自下方台账，不得重跑 heldout）

README 结构（读者视角一次读完）：
1. 一句话卖点：**给你的 agent 一个中文脏数据净化器——人名/地址/电话/公司名，一键规范化 + 去重 + 清洗报告。**
2. 安装：`uv tool install .` 或 `pip install -e .`（一条命令）+ `zhclean --help`。
3. 快速上手：3 条可复制命令（normalize / dedupe / audit）。
4. **benchmark 真实数（M1 实测台账，必须与下列数字逐字一致）**：
   - 规范化率（heldout，规则版）：人名 72.00% / 电话 100.00% / 公司名 81.00% / 地址 90.50%，总盘 85.88%
   - 去重（heldout）：recall 100.00% / precision 100.00%（样本小；train 复核 recall 99.90% / precision 99.25%，作真实水平基准）
   - 口径声明：≥95% 是目标不是承诺；评测 = 程序化扰动 + 留出集（ground truth = 扰动前原值）；数字可复现（同 seed）。
5. 失败案例公开（指针到 docs/failures-m1.md）。
6. 已知限制：人名缩写缺字不猜（abbrev 0%）、公司名缩写天花板 2/40、地址「市/市中区」歧义 8 条改坏（真实区县表缺失）、dedupe hub 桥接局限（train 72 误并对）、合成数据区划组合不真实。

`docs/failures-m1.md`：按字段 × 扰动类型列出失败归因与代表性案例（来源 = findings 台账与历史 RESULT，**不许重跑 heldout、不许读 generate.py**）；含「如何复现评测」的命令。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿（代码未被碰坏） | `uv run --project . pytest tests/ -q` | 405 passed |
| 2 | README 与失败案例数字核验 | 脑侧对照 findings 台账逐字核验（不回执自报） | README 中 4 个规范化率、2 个去重数、已知限制列表与台账一致 |
| 3 | 安装/用法一条命令可跑 | `uv run --project . zhclean --help` | exit 0（README 里的用法示例逐条可复制） |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`tests/**`、`benchmarks/generate.py`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-013）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；**不重跑 heldout 评测、不读 generate.py 词典常量**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- README 纪律（老大 2026-10-03 令）：每次更新必须整理重构——先通读全文、删过时项、合并重复段、按读者视角重排，再落新内容；判据是「方便人能读懂」。
- 数字出处：findings.md「真实数台账」+ 各 RESULT 的脑侧审查段；M1 数字已由脑验收锁死，任何出入都以台账为准。
- 手脑方案：干完写 `.handoff\outbox\RESULT-013.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。判据亲跑：①405 passed；②`zhclean --help` exit 0（乱码复现属实，已排 TASK-014 修复）；③边界零越界。
- **判据 2 数字核验（脑侧对照台账逐项通过）**：规范化 72/100/81/90.5/85.88、dedupe heldout 100/100 + train 99.90/99.25、失败 113 行分解、8 条改坏全量口径标注——全部一致。
- 四拍板裁决：①乱码修复排 TASK-014 第一件事；②安装命令发布时再验（联网禁区）；③audit 明细保持现状（--verbose 增强排后续）；④失败案例带真值保持并如实声明（合成数据无隐私，「公开」是评测透明性核心）——记 findings。
- **里程碑：M1 文档交付完成（README 一页读完 + 失败案例公开）。**
- `_Status: 已完成`；`_Commit: 65be228`。

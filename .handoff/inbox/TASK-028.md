# TASK-028　发布前文档收尾：README 补 table 节（发布检查单逐项）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `README.md`、`docs/release-checklist.md`（发布前逐项打勾状态更新，可加条目） |
| **_Capability:**（只许用） | 写 Markdown 文档；跑 `uv run` / `pytest` 命令（零代码改动验证）；读 `README.md`、`docs/examples/sample.csv`、`src/zhclean/cli.py`（table 用法）、`task_plan.md`、`findings.md`。**禁止：联网、改代码、git commit、调用其他 agent、动范围外文件** |
| **_Depends:**（依赖） | TASK-027（已通过，`edca08f`） |
| **_Commit:**（对应提交） | `0613911`（脑验收通过后提交） |

## 1. 目标（一句话）

发布前文档收尾：①README 补 **`zhclean table` 一节**（快速上手加第 4 条命令 + 用法说明），并把此前拍板的**「老六类」措辞统一改为「M1+M2 六类」**（RESULT-026 §8 已定，发布前兑现）；②`docs/release-checklist.md` 更新：勾掉已可核项、注明发布前剩余动作。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `README.md`（table 一节 + 「老六类」措辞统一 + 快速上手 4 条命令）
- `docs/release-checklist.md`（发布检查单更新）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

- README 快速上手加第 4 条：`zhclean table --input docs/examples/sample.csv [--columns 列=字段,...] [--dedupe] [--out clean.csv]`，说明「CSV 整表清洗：按列名自动映射八类字段（或 --columns 显式指定），未映射列原样保留，可整行去重；XLSX 待支持」。
- **措辞统一**：「老六类」→「M1+M2 六类」（README 全文；failures-m3 若也用了同词，一并改）。
- release-checklist：逐项核对现状——测试全绿（689）、heldout 八类定版已锁、README 数字与台账一致、快速上手命令实跑（4 条）、License 存在、CI 已配（首跑待 GitHub）；把已可核项勾掉，未完成的注明「待办」（如安装命令干净机器实跑、git tag、GitHub 建仓）。
- 文档纪律（老大 2026-10-03 令）：先通读 README 全文再改，整理重构不叠加。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 689 passed |
| 2 | 快速上手 4 条命令逐条实跑 | 回执贴 4 条命令真实输出（含新增 table 一条） | 4 条 exit 0 |
| 3 | 措辞与检查单核验 | 脑侧通读 | 「老六类」零残留；检查单勾选与事实相符；README 一页读完 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-028）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 不跑**
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- README 纪律：每次更新整理重构。
- 本单是发布前最后一单文档；完成后按老大口径「全部完成一起发布」——发布动作（建仓/tag/推送）由维护者（老大/脑）执行。
- 手脑方案：干完写 `.handoff\outbox\RESULT-028.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-09 · 脑）

- **已通过**。判据亲跑：①689 passed（零代码改动）；②快速上手 4 条逐条实跑 exit 0；③脑侧核验——README「老六类」零残留、三处数字逐格一致、README 一页读完。
- 边界零越界（2 文档）。
- §5-1 裁决：TASK 自相矛盾（契约要求改 failures-m3、边界未列）——手守边界正确；**授权补改已由脑侧执行**（failures-m3 的 4 处「老六类」→「M1+M2 六类」）。历史台账不改。
- **里程碑：M2 全部完成——八类字段 + 五子命令 + 文档三线 + 发布检查单就绪。**
- `_Status: 已完成`；`_Commit: 0613911`。

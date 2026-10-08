# TASK-027　整表清洗：tools/table.py（CSV）+ cli table 子命令（发布前最后一块功能）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `src/zhclean/tools/table.py`（新建）、`src/zhclean/cli.py`（加 table 子命令）、`tests/test_table.py`（新建）、`tests/test_cli.py`（table 用例）、`docs/examples/sample.csv`（新建样例） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `src/zhclean/**`（normalize/dedupe/audit 接口、cli 现有子命令模式）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件（尤其 benchmarks/generate.py 词典常量——不可读）** |
| **_Depends:**（依赖） | TASK-026（已通过，`14d0d23`） |
| **_Commit:**（对应提交） | `edca08f`（脑验收通过后提交） |

## 1. 目标（一句话）

`src/zhclean/tools/table.py` 实现**整表清洗**（CSV 进出：按列名映射八类字段 → 逐格 normalize → 输出清洗后 CSV + 报告），并接 `zhclean table` 子命令——「一键清洗整张表」是发布前最后一块功能。**本单只做 CSV（stdlib，零新依赖）；XLSX 排后（需加 openpyxl 依赖，另单）。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/tools/table.py`（新建）
- `src/zhclean/cli.py`（加 `table` 子命令；其余子命令零改动）
- `tests/test_table.py`（新建）、`tests/test_cli.py`（加 table 用例）
- `docs/examples/sample.csv`（新建，供快速上手）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/**`、`tools/{normalize,dedupe,audit,llm}.py`、`benchmarks/**`、`pyproject.toml`、`README.md`）

## 2.5 契约（脑定，照此实现）

- `clean_table(src, dst=None, columns=None, dedupe=False) -> dict`：
  - 读 CSV（stdlib csv，utf-8-sig 容 BOM）；`columns` = {CSV 列名: 字段名}（字段 ∈ 八类），缺省时按**列名 == 字段名**自动匹配（如列「person」「phone」）；不匹配的列原样保留。
  - 逐格 `normalize_with_confidence`；输出 CSV 新增 `_before` 列只对真改过的行有意义？——**口径：不改 schema，逐格替换原列值**（清洗 = 原位替换），报告 dict 记统计（总行/总列/每字段 changed/unchanged/hitl 低置信计数）。
  - `dedupe=True`：先清洗后对整行做 `dedupe_adaptive` 去重，输出去重后行集（组保留首行）。
  - 返回 `{"rows_out": n, "changed_cells": n, "report": {...}}`；纯函数不写文件（写盘是 cli 层）。
- `zhclean table --input x.csv [--columns 列=字段,...] [--out y.csv] [--dedupe]`：落盘 + 打印汇总（改了 N 格 / 输出 M 行）；`--out` 缺省 = stdout 打 CSV、汇总走 stderr（对齐现有流分工）。
- 模块头 F/R/A/S；`python -m zhclean.tools.table --demo` 自检（≥6 断言：列映射、未匹配列保留、置信度报告、dedupe、确定性、空输入）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 650 + 新增：列映射（显式/按列名自动）、未匹配列原样、逐格替换正确、报告统计、dedupe 路径、cli table 端到端（tmp 文件往返）、退出码、确定性） |
| 2 | demo 自检 | `uv run --project . python -m zhclean.tools.table` | `table._demo: OK`，exit 0 |
| 3 | cli 端到端 | `uv run --project . zhclean table --input docs/examples/sample.csv` | exit 0；汇总正确；stdout 是合法 CSV（列对齐） |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/**`、`tools/{normalize,dedupe,audit,llm}.py`、`benchmarks/**`、`pyproject.toml`、`README.md`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-027）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 `benchmarks/generate.py` 词典常量

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀；中文输出加 `PYTHONIOENCODING=utf-8`。
- CSV 是本单全部范围（stdlib 零依赖）；XLSX 待脑侧加 openpyxl 依赖后另单。
- 本单是发布前最后一块功能；完成后 = 大写数字轴（可选）+ 发布（按老大口径：全部完成一起发布）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-027.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-09 · 脑）

- **已通过**。三判据亲跑：①689 passed；②`table._demo: OK`（8 组断言）；③cli 端到端 exit 0、8 格对账一致、stdout 合法 CSV。
- 边界零越界。**结构化代码审查**（5/5 覆盖 100%）：critical/high/medium/low 全 0。
- §5 三裁决：①dst 保留不写采纳（纯函数分层，契约自相矛盾是脑侧疏漏）；②**dedupe「每一列都同组」采纳**（跨字段合取唯一正确；「任一列」会误并共手机号的不同人，手的实证过程有说服力）；③基线命令后跑接受不记失分（如实申报）。
- **里程碑：整表清洗落地（zhclean 五子命令齐全）——发布前最后一块功能完成。**
- `_Status: 已完成`；`_Commit: edca08f`。

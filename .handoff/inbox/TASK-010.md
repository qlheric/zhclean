# TASK-010　audit 工具：清洗报告 + dry-run 预览 + 可回滚

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `src/zhclean/tools/audit.py`、`tests/test_audit.py` |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `src/zhclean/**`（normalize 接口）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外任何文件（尤其 benchmarks/generate.py 词典常量——不可读）** |
| **_Depends:**（依赖） | TASK-009（已通过，`5229d99`） |
| **_Commit:**（对应提交） | `c40fc9b`（脑验收通过后提交） |

## 1. 目标（一句话）

`src/zhclean/tools/audit.py` 实现三工具里的最后一个：**清洗报告**（改了什么/为什么/置信度）、**dry-run 预览**（只报告不落盘）、**可回滚**（应用清洗时留备份、可恢复原值）。**本单只做 audit 工具本体，不做 CLI 串接（cli.py 是后续 TASK）。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/tools/audit.py`（audit 工具实现）
- `tests/test_audit.py`（audit 单测）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/**`、`tools/{normalize,dedupe}.py`、`cli.py`、`benchmarks/**`、`pyproject.toml`）

## 2.5 接口契约（脑定，照此实现）

- `audit(rows, dry_run=True) -> dict`：对每行跑 `zhclean.normalize_with_confidence(value, field)`，产出报告 dict：
  - `total` / `changed` / `unchanged`（改动 = 规范值 != 原值）
  - `by_field`：每字段 {total, changed, unchanged}
  - `by_confidence`：置信度档位分布（0.9 / 0.7 / 0.1 / 其他，各计数）
  - `changes`：逐行明细 list（id/field/before/after/confidence），**只有 changed 的行**；行数上限 `max_changes`（默认 1000，超出截断并记 `truncated: true`）
- `apply(rows) -> (cleaned_rows, backup)`：把清洗实际应用到行（`value` 替换为规范值，保留原值于备份）：
  - `cleaned_rows`：每行 `value` = 规范值（changed 与否都保留原 value？——**口径：changed 行 value 替换为规范值，并加 `_before` 字段存原值**；unchanged 行不动）
  - `backup`：`{"rows": 原行列表, "checksum": sha256}`（供回滚校验）
- `rollback(cleaned_rows, backup) -> list[dict]`：用备份恢复原值；**checksum 不匹配即抛错拒绝回滚**（防拿错备份）。
- `format_report(report) -> str`：人读版报告文本（总数/改动数/按字段/按置信度）。
- 模块头 F/R/A/S 四行对齐既有风格；`python -m zhclean.tools.audit --demo` 自检（`_demo()` ≥6 断言：报告计数、dry-run 不改数据、apply 替换正确、rollback 恢复、checksum 拒绝、空输入）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 285 + 新增 `tests/test_audit.py` ≥12 用例：报告计数正确（含 changed/unchanged/by_field）、dry-run 不落盘不改数据、apply 后 value 替换 + `_before` 留存、rollback 恢复原值、**checksum 不匹配拒绝回滚**、max_changes 截断、空输入、确定性） |
| 2 | demo 自检 | `uv run --project . python -m zhclean.tools.audit` | 输出 `audit._demo: OK`，exit 0 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/**`、`tools/{normalize,dedupe}.py`、`cli.py`、`benchmarks/**`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-010）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 `benchmarks/generate.py` 词典常量

## 5. 回滚方式

未提交前：删除本单新增文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀；中文输出加 `PYTHONIOENCODING=utf-8`。
- audit 是 M1 功能闭环的最后一块；cli.py 串接（normalize/dedupe/audit 三命令）是下一阶段的 TASK。
- 手脑方案：干完写 `.handoff\outbox\RESULT-010.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。两条判据均经脑亲跑：①`uv run --project . pytest tests/ -q` → 315 passed；②`uv run --project . python -m zhclean.tools.audit` → `audit._demo: OK` exit 0。
- 边界检查：2 个改动文件 ⊆ `_Boundary:_`（零越界）。
- **结构化代码审查**（2/2 覆盖 100%）：critical/high/medium 0、low 1（dry_run=False 时 normalize 跑两遍，cli 串接时优化），不阻塞。
- §5-2 四处口径（dry_run=False 附结果不写文件 / checksum 双绑定 / reason 字段 / 非字符串 other）全采纳。
- **里程碑：M1 三工具（normalize / dedupe / audit）本体齐。**
- `_Status: 已完成`；`_Commit: c40fc9b`。

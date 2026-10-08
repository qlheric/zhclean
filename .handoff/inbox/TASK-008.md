# TASK-008　dedupe 工具：hash 精确去重 + rapidfuzz 语义去重（先规范化后去重）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端，新会话） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `src/zhclean/tools/dedupe.py`、`tests/test_dedupe.py` |
| **_Capability:**（只许用） | 写 Python 代码（可用已声明的依赖 rapidfuzz）；跑 `uv run` / `pytest` 命令；读 `src/zhclean/**`（normalize 接口）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外任何文件（尤其 benchmarks/generate.py 及其词典常量——不可读，防留出集反推）** |
| **_Depends:**（依赖） | TASK-007（已通过，`234fe81`）；rapidfuzz 已在 pyproject 依赖里 |
| **_Commit:**（对应提交） | `30e32eb`（脑验收通过后提交） |

## 1. 目标（一句话）

`src/zhclean/tools/dedupe.py` 实现两级去重：**hash 精确去重** + **rapidfuzz 语义相似去重**（阈值可配），并且**先规范化后去重**（脏写法经 `zhclean.normalize` 归一到规范值再比）。**本单只做 dedupe 工具本体，不做评测接入（评测是下一单）。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/tools/dedupe.py`（dedupe 工具实现）
- `tests/test_dedupe.py`（dedupe 单测）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/**`、`benchmarks/**`、`tools/normalize.py`、`pyproject.toml`）

## 2.5 接口契约（脑定，照此实现）

- 输入：`list[dict]`，每行至少含 `id`、`field`、`value`（与 benchmarks 数据行同构）。
- `dedupe_exact(rows) -> list[list[dict]]`：**先规范化后去重**——`zhclean.normalize(value, field)` 后的规范值相同即合并（同 id 多行当然同组）。
- `dedupe_fuzzy(rows, threshold: float) -> list[list[dict]]`：精确键外，再用 `rapidfuzz.fuzz.ratio`（或 `token_sort_ratio`）在**规范化值**之间做相似度；`ratio >= threshold` 且不在同一组 → 合并（union-find 或等价）。`threshold` 默认 `0.85`，取值 [0,1]。
- 语义：`dedupe(rows, threshold)` = 精确 + 语义两级；返回**组列表**（组内行保持输入顺序，组间按首行顺序）。
- **确定性**：同输入同输出（rapidfuzz 无随机源；并查集按输入序合并）。
- 模块头写 F/R/A/S 四行（对齐 rules 模块风格）。
- `python -m zhclean.tools.dedupe --demo`：内置自检（`_demo()`，≥6 条断言覆盖：精确合并、阈值内合并、阈值外不合、规范化后合并（「王 小明」与「王小明」同组）、空输入、确定性）——对齐 `rules/common.py` 的 `_demo` 先例。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 229 + 新增 `tests/test_dedupe.py` ≥12 用例：精确去重、语义阈值内/外、**规范化后去重**（脏写法归一合并）、阈值边界 [0,1] 校验、空输入、组内保序、确定性（两次调用结果一致）、`dedupe` 综合入口） |
| 2 | demo 自检 | `uv run --project . python -m zhclean.tools.dedupe` | 输出 `dedupe._demo: OK`，exit 0 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/**`、`tools/normalize.py`、`benchmarks/**`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-008）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 `benchmarks/generate.py` 词典常量

## 5. 回滚方式

未提交前：删除本单新增文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀；Windows 终端中文输出加 `PYTHONIOENCODING=utf-8`。
- dedupe 评测口径（下一单用）：同 id 的 clean + 5 条 dirty = 一个「应合并组」，recall = 应合并对被正确合并的比例；≥95% 是目标不是承诺。
- 手脑方案：干完写 `.handoff\outbox\RESULT-008.md`（判据/命令/输出/证据 + 第 7 节「下次接着做什么」），然后**停下**；**不动 TASK 状态字段**（状态归脑）。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。两条判据均经脑亲跑：①`uv run --project . pytest tests/ -q` → 261 passed；②`uv run --project . python -m zhclean.tools.dedupe` → `dedupe._demo: OK` exit 0。
- 边界检查：2 个改动文件 ⊆ `_Boundary:_`（零越界）。
- **结构化代码审查**（2/2 覆盖 100%）：critical/high/medium/low 全 0，零发现。
- 两个契约点裁决（脑定，均采纳手口径）：①只在同一 field 内比较 ✓；②不按 id 强制合并 ✓（id 是评测金标准，实现用 id 合并=评测作弊；不需要 merge_by_id 参数）。
- 采纳手建议：下一单评测同时算 precision；阈值只在 train 上选、heldout 只跑一次（已写进 TASK-009）。
- `_Status: 已完成`；`_Commit: 30e32eb`。

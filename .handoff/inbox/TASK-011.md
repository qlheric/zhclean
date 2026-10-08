# TASK-011　dedupe recall 攻坚：按字段相似度 + 按字段阈值（precision 守卫）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `src/zhclean/tools/dedupe.py`、`tests/test_dedupe.py`、`benchmarks/evaluate_dedupe.py`（加 `--adaptive` 透传）、`tests/test_evaluate_dedupe.py`、`benchmarks/results/**`（评测产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `benchmarks/clean|dirty/*.jsonl` 的 **train 部分**（可，用于实验选配置）、`src/zhclean/**`、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ 特别禁止：读 `benchmarks/generate.py` 词典常量；heldout 只在定版时跑一次** |
| **_Depends:**（依赖） | TASK-010（已通过，`c40fc9b`）；TASK-009 评测管线（`5229d99`） |
| **_Commit:**（对应提交） | `8ef8adc`（脑验收通过后提交） |

## 1. 目标（一句话）

dedupe heldout recall 从 **85.42%** 攻坚提升（目标 ≥95%，如实冲）：给 dedupe 加**按字段相似度函数 + 按字段阈值**的自适应配置，person 短串与 company 简称的漏并是主战场；**precision 必须同时守卫**（目标 ≥95%）。实验与选配置**只在 train 上做**，heldout 只在定版后跑一次。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/tools/dedupe.py`（加自适应配置：scorers + per-field thresholds）
- `tests/test_dedupe.py`（新机制的用例）
- `benchmarks/evaluate_dedupe.py`（加 `--adaptive` 标志透传配置）
- `tests/test_evaluate_dedupe.py`（--adaptive 路径的用例）
- `benchmarks/results/**`（评测产物，不入库）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/**`、`tools/{normalize,audit}.py`、数据文件、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

- `dedupe_fuzzy(rows, threshold=DEFAULT_THRESHOLD, field_overrides=None)`：
  - `field_overrides: dict[str, {"scorer": callable, "threshold": float}] | None`——某字段不覆盖则用全局 `threshold` + `fuzz.ratio`。
  - scorer 签名 `(a: str, b: str) -> float`（返回 [0,1] 相似度，内部与 threshold 比 ≥）。
  - **向后兼容**：不传 field_overrides 时行为与现在逐字相同（现有 32 用例不许改）。
- `dedupe_adaptive(rows, threshold=DEFAULT_THRESHOLD)`：内置推荐配置（`DEFAULT_ADAPTIVE` dict），**配置依据必须是 train 上的实验**，实验过程（各候选配置的 train P/R/F1 表）必须写进回执 §2 与代码注释。
- 候选方向（手在 train 上实验定夺，不限于）：
  - person：`fuzz.partial_ratio` 或 `Levenshtein.normalized_similarity`（短串缩写「范童/范童言」、错字「范同言/范童言」）；阈值单独选（可能显著低于 0.85）。
  - company：`fuzz.partial_ratio` 抓「简称 ⊂ 全称」（「XX有限公司」vs「XX有限责任公司」）。
  - **误并风险**（RESULT-009 §6-2）：person 编辑距离 ≤1 误并风险高（同姓+常见字），任何配置都必须在 train 上查 precision，**不得以 recall 换 precision 大掉**。
- evaluate_dedupe：加 `--adaptive` 标志（与现有参数兼容；选择/评测时把 DEFAULT_ADAPTIVE 传给 dedupe）。
- **heldout 纪律**：开发实验只用 `--split train`；heldout 只在定版后跑一次（本轮最后一次判据 2 跑）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 315 + 新增用例：field_overrides 生效、向后兼容（不传时行为不变）、person 缩写/错字对在自适应下合并、company 简称⊂全称合并、**误并对在自适应下仍被拒**（precision 守卫用例）、--adaptive 透传） |
| 2 | heldout 定版实测 | `uv run --project . python -m benchmarks.evaluate_dedupe --split heldout --threshold 0.85 --adaptive` | exit 0；**recall ≥ 90% 且 precision ≥ 90%**（目标 95/95 如实冲）；summary 落盘含 adaptive 标志；**真实数脑验收时如实汇报** |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/**`、`tools/{normalize,audit}.py`、`benchmarks/generate.py`、数据文件、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-011）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 generate.py 词典常量；不从 heldout 反推

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀；中文输出加 `PYTHONIOENCODING=utf-8`。
- 基线数字（TASK-009 实绩）：heldout recall 85.42% / precision 100%（R85.42 是 adaptive 前的对照）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-011.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。两条判据均经脑亲跑：①`uv run --project . pytest tests/ -q` → 364 passed；②heldout 定版 **R100.00 / P100.00**（与回执逐行一致）；train 复核 **R99.90 / P99.25**（脑亲跑一致）。
- 边界检查：4 个改动文件 ⊆ `_Boundary:_`（零越界）。
- **结构化代码审查**（4/4 覆盖 100%）：critical/high/medium/low 全 0，零发现；向后兼容路径保留原剪枝、有逐组对照测试。
- **拍板：接受 `link` 键**（all|best，缺省 all）——precision 达标的必要守卫（不加它 person P 最好 94.17%），契约升级记 findings。
- 已知局限记账：hub 桥接（train 72 误并对全为此型）测试锁定现状；**100/100 不作泛化承诺，更可信数字是 train 99.90/99.25**。
- `_Status: 已完成`；`_Commit: 8ef8adc`。

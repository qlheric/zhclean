# TASK-003　normalize(人名) 最小闭环：规则打底 + 置信度 + 评测接入

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH（本会话） |
| 日期 | 2026-10-07 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `src/zhclean/__init__.py`、`src/zhclean/rules/__init__.py`、`src/zhclean/rules/person.py`、`src/zhclean/tools/normalize.py`、`benchmarks/evaluate.py`（**仅**在 IMPLS 加 `"rules"` 一项）、`tests/test_normalize.py`、`benchmarks/results/**`（rules 评测产物） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `python` / `uv run` / `pytest` 命令；读 `benchmarks/**`、`task_plan.md`、`findings.md`。**禁止：联网、装包/改依赖、git commit、调用其他 agent、动范围外任何文件** |
| **_Depends:**（依赖） | TASK-002（已通过，`aab345a`） |
| **_Commit:**（对应提交） | `e64f6ac`（脑验收通过后提交） |

## 1. 目标（一句话）

打通**人名清洗最小闭环**：`rules/person.py` 规则打底 → `tools/normalize.py` 分发接口（含置信度）→ 评测接入（`--impl rules`）→ heldout 上跑出人名的**真实规范化率**并落盘报告。**本单只做人名，电话/地址/公司名后续 TASK 逐个补。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/rules/person.py`（人名规则词典与清洗函数）
- `src/zhclean/rules/__init__.py`（规则注册表：field → handler）
- `src/zhclean/tools/normalize.py`（normalize 主接口 + 置信度接口 + 字段分发）
- `src/zhclean/__init__.py`（导出 `normalize` / `normalize_with_confidence`）
- `benchmarks/evaluate.py`（**仅** IMPLS 加一行 `"rules": lambda row: zhclean.normalize(row["field"], row["value"])`）
- `tests/test_normalize.py`（人名规则单测）
- `benchmarks/results/**`（rules 评测产物）
- 除此之外**一律不许动**（尤其 `src/zhclean/loop.py`、`cli.py`、`llm.py`、`tools/dedupe.py`、`tools/audit.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`）

## 2.5 接口契约（脑定，照此实现）

- `zhclean.normalize(value: str, field: str) -> str`：主接口（评测接入点）。**未知 field 或规则无法处理时返回原值，不猜**。
- `zhclean.normalize_with_confidence(value: str, field: str) -> tuple[str, float]`：返回（规范值, 置信度 0~1）。规则命中给高置信（建议 0.9），原样返回/未命中给低置信（建议 0.1）。本单只做简单版（loop/HITL 后续任务用）。
- `rules/__init__.py`：注册表（如 `DISPATCH: dict[str, Callable] = {"person": normalize_person, ...}`），未注册 field 恒等处理。
- 人名规则打底口径（五类扰动的处置，脑定）：
  - `space`：去所有空白（全角/半角/全角空格）→ 应全对
  - `sep`：去分隔符 `- · | ／ ，` 等 → 应全对
  - `noise`：去「姓名：」类前缀、「先生/女士」类后缀 → 应全对
  - `typo`：**通用同音/形近字表**（名字用字 → 错字，从常见错别字知识整理，**不是从测试集反推**）→ 能对多少对多少，如实报
  - `abbrev`：缺字无法可靠恢复 → **低置信返回原值，允许错**（这类将来走 LLM/HITL）
- **铁律：规则词典不得针对测试扰动模式调参**（留出集纪律；typo 表用通用表）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 15 个 + 新增 `tests/test_normalize.py` 至少覆盖：space/sep/noise 三类扰动的代表性用例「脏值→期望规范值」；abbrev 不猜（低置信）；未知 field 恒等；confidence ∈ [0,1]；IMPLS 里 rules 键存在且可跑） |
| 2 | 评测接入并报真实数 | `python -m benchmarks.evaluate --impl rules` | exit 0；`benchmarks/results/summary-rules-heldout.json` 落盘；**person 行 rate > 0 且 failures 行数 < 800**；stdout 分组表正常 |

> 注：**≥95% 是目标不是承诺**，不是本单判据——真实数字脑验收时如实汇报并记入 findings。typo/abbrev 达不到高数是预期的。

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/loop.py`、`cli.py`、`llm.py`、`tools/dedupe.py`、`tools/audit.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-003）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`（只影响本单边界内文件）。

## 6. 备注

- 命名已脑定：评测注入名 `--impl rules`（RESULT-002 §5 提请，§8 拍板）。
- 评测口径见 `findings.md` §5：规范化率 = normalize(value) == truth 逐字符相等；失败案例公开（含真值，脱敏开关发布前再加）。
- 建议实现顺序：先写 test_normalize.py 的代表性用例 → person.py 规则 → normalize 接口 → 接入 evaluate → 跑判据 2 看真实数。
- 手脑方案：干完写 `.handoff\outbox\RESULT-003.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。回执申报清单外新文件并贴 §1.5 基线输出。

## 7. 验收结论（2026-10-07 · 脑）

- **已通过**。两条判据均经脑亲跑：①`uv run --project . pytest tests/ -q` → 58 passed；②`uv run --project . python -m benchmarks.evaluate --impl rules` → exit 0、person 72.00%（144/200）、failures 656 < 800。
- 边界检查：8 个改动文件 ⊆ `_Boundary:_`（零越界；RESULT-003 属交接机制豁免）。
- **结构化代码审查**（6/6 覆盖 100%）：critical 0 / high 0 / medium 1 / low 3，均不阻塞；数字声称（47/31/34、16 条归因、姓氏零缺失）全部经脑侧脚本机械核验对上。
- 三个拍板点裁决（详见 RESULT-003 §8）：①import 不算越界（必要前提+已申报）；②接口以 §2.5 为准，docstring 过时注释由 TASK-004 边界内修；③判据加 uv run 前缀合规（本机裸 python 3.14.7 无 zhclean，已亲验）——后续判据统一 `uv run --project . python ...`。
- 真实数入账：**person heldout 72.00%**（space/sep/noise 100%、typo 60%、abbrev 0% 属预期）。≥95% 是目标不是承诺，如实记录（findings）。
- `_Status: 已完成`；`_Commit: e64f6ac`。

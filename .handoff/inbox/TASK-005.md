# TASK-005　normalize(公司名) 规则：结构清洗 + 组织形式缩写补全 + 错字修复

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH（本会话） |
| 日期 | 2026-10-07 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `src/zhclean/rules/company.py`、`src/zhclean/rules/__init__.py`、`tests/test_company.py`、`benchmarks/results/**`（评测产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `uv run` / `pytest` 命令；读 `benchmarks/**`、`src/zhclean/rules/person.py`、`phone.py`（参考实现风格）、`task_plan.md`、`findings.md`。**禁止：联网、装包/改依赖、git commit、调用其他 agent、动范围外任何文件** |
| **_Depends:**（依赖） | TASK-004（已通过，`e44d3b0`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

公司名规则打底：`rules/company.py` 结构清洗（空白/分隔符/前后缀噪声）+ 组织形式缩写补全（「股份公司」→「股份有限公司」等）+ 通用错字修复（公/司/有/限等必现字），注册进 `DISPATCH`，heldout 上跑出**公司名的真实规范化率**。**本单只做 company；address 是下一单。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/rules/company.py`（公司名规则词典与清洗函数）
- `src/zhclean/rules/__init__.py`（DISPATCH 注册 `"company"`）
- `tests/test_company.py`（公司名规则单测）
- `benchmarks/results/**`（评测产物，已 .gitignore 不入库）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/person.py`、`phone.py`、`tools/normalize.py`、`loop.py`、`cli.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`）

## 2.5 接口契约（脑定，照此实现）

- `normalize_company(value: str) -> tuple[str, float]`，置信度沿用 0.9 结构 / 0.7 推断 / 0.1 无证据。
- 处置口径（五类扰动）：
  - `space`：去所有空白（半角/全角）→ 应全对
  - `sep`：去分隔符（城市/字号/行业/后缀之间）→ 应全对
  - `noise`：去「单位：」「公司：」类前缀、「（总部）」类尾注、尾随标点 → 应全对
  - `abbrev`：**只补可可靠推断的组织形式缩写**——「股份公司」→「股份有限公司」、「有限公司」不变（已是全称）等；**「去城市」「去组织形式」类不可靠恢复一律不猜、低置信原样**（对齐 person/abbrev 口径）
  - `typo`：通用错字修复（公司名必现字「公/司/有/限/集/团」等的形近/同音错字，通用知识整理，**不是从测试集反推**）
- 公司名**没有**电话那样的客观校验闸门 ⇒ **沿用 person 的「结构层命中即返回、不叠加推断层」**（避免两层推断误伤），模块头写清与 phone 的差异。
- **惯例（TASK-004 验收确立）**：测试里必须带**回归护栏**——注册 company 后，person/phone 的行为不变（各抽 ≥2 条代表用例断言）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 104 + 新增 `tests/test_company.py`：space/sep/noise 代表用例、组织形式缩写补全、不可靠 abbrev 不猜、typo 通用表、置信度 ∈ [0,1]、注册表、**person/phone 回归护栏**） |
| 2 | 评测报真实数 | `uv run --project . python -m benchmarks.evaluate --impl rules` | exit 0；**company 行 rate > 0 且 failures 行数 < 800**；真实数脑验收时如实汇报 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/person.py`、`phone.py`、`tools/normalize.py`、`loop.py`、`cli.py`、`llm.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-005）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`（只影响本单边界内文件）。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 先看脏集样本再定口径：`uv run --project . python -c "import json;[print(json.loads(l)) for _,l in zip(range(5),open('benchmarks/dirty/company.jsonl',encoding='utf-8'))]"`（如需）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-005.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。回执申报清单外新文件并贴 §1.5 基线输出。

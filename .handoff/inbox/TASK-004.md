# TASK-004　normalize(电话) 规则：结构清洗 + 数字形近修复

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH（本会话） |
| 日期 | 2026-10-07 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `src/zhclean/rules/phone.py`、`src/zhclean/rules/__init__.py`、`tests/test_phone.py`、`benchmarks/evaluate.py`（**仅**修正第 12/13 行两处过时注释，见 §2.5）、`benchmarks/results/**`（评测产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `uv run` / `pytest` 命令；读 `benchmarks/**`、`src/zhclean/rules/person.py`（参考实现风格）、`task_plan.md`、`findings.md`。**禁止：联网、装包/改依赖、git commit、调用其他 agent、动范围外任何文件** |
| **_Depends:**（依赖） | TASK-003（已通过，`e64f6ac`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

电话规则打底：`rules/phone.py` 实现手机号结构清洗（国家码前缀/空白/分隔符/前后缀噪声/数字形近修复），注册进 `DISPATCH`，`--impl rules` 评测在 heldout 上跑出**电话的真实规范化率**。**本单只做电话，address/company 后续 TASK。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/rules/phone.py`（电话规则词典与清洗函数）
- `src/zhclean/rules/__init__.py`（DISPATCH 注册 `"phone"`）
- `tests/test_phone.py`（电话规则单测）
- `benchmarks/evaluate.py`（**仅**修正两处过时注释：第 12 行示例改成 `zhclean.normalize(row["value"], row["field"])`、第 13 行「本单不 import src/zhclean」删除——均来自 TASK-003 遗留，见 RESULT-003 §8 裁决 2）
- `benchmarks/results/**`（评测产物；**注：results/ 已入 .gitignore，产物不入库**）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/person.py`、`loop.py`、`cli.py`、`llm.py`、`tools/normalize.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`）

## 2.5 接口契约（脑定，照此实现）

- `normalize_phone(value: str) -> tuple[str, float]`，风格对齐 person（三层：结构清洗无损 → 数字形近修复推断 → 无证据原样返回）。
- 置信度阶梯：结构命中 0.9 / 形近修复 0.7 / 无证据 0.1（沿用 person 档位）。
- 处置口径（对应五类扰动）：
  - `space`：去所有空白（半角/全角）→ 应全对
  - `sep`：去 `-`、空格分组（3-4-4 等任意分隔）→ 应全对
  - `abbrev`：剥离国家码前缀 `+86` / `86` / `0086` → 应全对
  - `noise`：去「电话：」「联系方式：」类前缀、「（微信同号）」类后缀 → 应全对
  - `typo`：数字形近修复（`O→0 l→1 Z→2 E→3 S→5 B→8`，通用 OCR 形近知识）→ 能修多少修多少，如实报
- 修复后**必须仍是 11 位、1[3-9] 开头**才返回修复值，否则原样低置信（不猜）。
- **铁律**：规则不得针对测试扰动模式调参（形近表是通用 OCR 知识，不是从测试集反推）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 58 + 新增 `tests/test_phone.py` 至少覆盖：space/sep/abbrev(86 前缀)/noise 代表用例「脏值→期望规范值」、数字形近修复、修坏不返回（位数/开头校验）、置信度 ∈ [0,1]、phone 已注册且 person 行为不受影响） |
| 2 | 评测报真实数 | `uv run --project . python -m benchmarks.evaluate --impl rules` | exit 0；`benchmarks/results/summary-rules-heldout.json` 更新；**phone 行 rate > 0 且 failures 行数 < 800**；真实数脑验收时如实汇报 |

> 判据命令一律带 `uv run --project .` 前缀（本机裸 python 3.14.7 装不到 zhclean，TASK-003 已实测并裁定）。

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/person.py`、`tools/normalize.py`、`loop.py`、`cli.py`、`llm.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-004）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`（只影响本单边界内文件）。

## 6. 备注

- person 遗留 medium（typo 表个别条目收录标准自检）由脑记账，**本单不处理**（零误伤已验，不打断节奏）。
- results/ 已 .gitignore：判据 2 后 `git status` 不应出现 results 产物（被忽略）。
- 参考 `src/zhclean/rules/person.py` 的实现结构与置信度档位，保持风格一致。
- 手脑方案：干完写 `.handoff\outbox\RESULT-004.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。回执申报清单外新文件并贴 §1.5 基线输出。

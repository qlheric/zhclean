# TASK-007　维护单：抽 rules/common.py + 方位构词位置约束（脑裁决）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH（本会话） |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `src/zhclean/rules/common.py`（新建）、`src/zhclean/rules/{person,phone,company,address,__init__}.py`、`tests/test_address.py`（可加约束用例）、`benchmarks/results/**`（评测产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `uv run` / `pytest` 命令；读 `task_plan.md`、`findings.md`、train 失败样本。**禁止：联网、装包/改依赖、git commit、调用其他 agent、动范围外任何文件。⚡ 特别禁止：读 `benchmarks/generate.py` 词典常量；禁止从 heldout 反推** |
| **_Depends:**（依赖） | TASK-006（已通过，`ddedddc`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

**重构不改行为**：①抽 `rules/common.py`（`strip_noise` / `strip_ws_sep` / 滑窗+单字错字修复通用实现 + `CONF_*` 常量 + 结构字守卫表），person/phone/company/address 四模块改为 import 公共件、只留各自词典与特有守卫；②按脑裁决给 `DISTRICT_COMPONENT_WORDS` 命中加**位置约束**（词后必须紧跟「区」或「城」）。重构后四字段评测数字**必须与重构前完全一致**（address 90.5%、总盘 85.88%、failures 113），唯一的允许变化来自约束②（若有影响须如实报差异并逐条归因）。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/rules/common.py`（新建：公共清洗/修复/常量）
- `src/zhclean/rules/person.py`、`phone.py`、`company.py`、`address.py`（改 import + 删重复实现 + address 加约束②）
- `src/zhclean/rules/__init__.py`（如公共常量出口调整）
- `tests/test_address.py`（新增约束用例）
- `benchmarks/results/**`（评测产物）
- 除此之外**一律不许动**（尤其 `tools/normalize.py`、`loop.py`、`cli.py`、`benchmarks/generate.py`、数据文件、`pyproject.toml`）

## 2.5 契约（脑定）

- `common.py` 导出：`CONF_STRUCTURAL / CONF_INFER / CONF_NONE`、`strip_noise(s) -> (str, bool)`、`strip_ws_sep(s) -> (str, bool)`、`repair_typos_by_known_words(s, typo_table, known_words, single_char_ok, guards) -> (str, bool)`——滑窗（≥2 字，修完恰等于 known_words）+ 单字轮（含三条守卫：地名开头不动 / 号室前须数字 / 结构字后须数字）。
- 各字段只留：自己的词典（typo 表、判据集合、守卫名单）+ 特有逻辑（phone 的校验闸门与两段剥离、company 的缩写补全、address 的补全层与一对多消歧）。
- **约束②**：`DISTRICT_COMPONENT_WORDS` 的 15 词在滑窗判据中命中时，要求**窗口后一位是「区」或「城」**（「城东区」可修，「城东雅苑」不修）；address 的单字轮对该集合的守卫同步检查此约束。
- **重构保行为**：不允许顺手改任何词典条目或档位（那些是另一类 TASK 的事）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 225 全保持 + 新增约束用例：`城东雅苑` 型不误伤 + `城茜区→城西区` 型仍修 + 四字段重构后代表用例仍过） |
| 2 | 重构零行为漂移 | `uv run --project . python -m benchmarks.evaluate --impl rules` | exit 0；**address rate ≥ 90.0% 且 failures ≤ 113**；若约束②影响了 heldout 数字，回执逐条列出受影响样本并归因 |

## 4. 禁区（碰了即作废）

- 不许改：`tools/normalize.py`、`loop.py`、`cli.py`、`llm.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-007）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 generate.py 词典常量、不从 heldout 反推

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 这是 TASK-005 §6-2 / RESULT-006 §6-1 建议、脑裁决后的维护单——**目标是去重与口径收敛，不是加功能**。
- 重构顺序建议：先写 common.py → 逐个字段切 import → 每切一个跑一次 pytest 保绿 → 最后加约束② + 用例 → 跑判据 2 对比数字。
- 手脑方案：干完写 `.handoff\outbox\RESULT-007.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

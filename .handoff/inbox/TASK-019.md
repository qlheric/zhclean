# TASK-019　M2 规则：amount/date 规范化 + 评测接入（train 实测报数）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `src/zhclean/rules/amount.py`、`src/zhclean/rules/date.py`、`src/zhclean/rules/__init__.py`、`src/zhclean/rules/common.py`（如需公共机制）、`benchmarks/evaluate.py`（**仅 FIELDS 扩至 6 类**）、`tests/test_amount.py`、`tests/test_date.py`（或合并一个测试文件）、`benchmarks/results/**`（评测产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `benchmarks/clean|dirty/*.jsonl` 的 **train 部分**、`src/zhclean/rules/{person,phone,company,address}.py`（参考实现风格）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ 特别禁止：读 `benchmarks/generate.py` 词典常量；heldout 只在定版后跑一次** |
| **_Depends:**（依赖） | TASK-018（已通过，`714997a`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

`rules/amount.py` 与 `rules/date.py` 实现金额/日期规范化规则（结构清洗 + 数字形近修复 + 校验闸门），注册进 `DISPATCH`，`benchmarks/evaluate.py` 的 FIELDS 扩至 6 类，在 train 上跑出**真实规范化率**（heldout 只在定版后跑一次）。**本单只做 amount/date，身份证/邮箱后续。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/rules/amount.py`、`src/zhclean/rules/date.py`（新建规则）
- `src/zhclean/rules/__init__.py`（DISPATCH 注册 amount/date）
- `src/zhclean/rules/common.py`（**仅当**需要新的公共机制时；不得改现有行为）
- `benchmarks/evaluate.py`（**仅 FIELDS 常量扩至 6 类**）
- `tests/test_amount.py`、`tests/test_date.py`（单测）
- `benchmarks/results/**`（评测产物，不入库）
- 除此之外**一律不许动**（尤其 `src/zhclean/tools/**`、`loop.py`、`benchmarks/generate.py`、数据文件、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

**amount**（干净值形态 = `<数值>元`，无空格——TASK-018 §5-1 已裁定）：
- `space`：去所有空白 → 应全对
- `noise`：去「金额：/金额:/费用：」前缀、「（含税）/（未税）」后缀、尾随标点 → 应全对
- `sep`：千分位归一——逗号（半角/全角/乱插位置）一律去掉 → 应全对
- `abbrev`：**万元展开**（`1.28万元` → `12800元`；数值 ×10000 保留 4 位小数去尾零）→ 应全对
- `typo`：数字形近修复（`DIGIT_TYPOS` 反向：O→0 l→1 Z→2 E→3 A→4 S→5 G→6 T→7 B→8 q→9），**修完必须过校验闸门**（形态 = `整数或小数 + 元`，无多余字符）→ 能修多少修多少
- 校验闸门（对齐 phone 思路）：输出必须匹配 `^\d+(\.\d+)?元$` 才采纳，否则原样低置信。置信度四档沿用（0.95 已规范 / 0.9 结构 / 0.7 推断 / 0.1 无证据）。

**date**（干净值形态 = `YYYY-MM-DD`）：
- `space`：去所有空白 → 应全对
- `noise`：去「日期：/日期:」前缀、「（录入日期）/（生效日）」后缀、尾随标点 → 应全对
- `sep`：`/`、`.`、`／` 统一为 `-` → 应全对
- `abbrev`：**只补缺零**（`2026-1-5` → `2026-01-05`）；**缺年（1-5）、年月（2026-10）不可恢复 → 原样低置信**（对齐「不猜」口径；abbrev 天花板 = 缺零型占比，别预设拿分）
- `typo`：数字形近修复，**修完必须过校验闸门**（形态 + 年 1970–2026、月 01–12、日 01–31）
- 已规范值（形态合法）→ 0.95（沿用 CONF_CLEAN 语义）。

**惯例**：测试带六字段回归护栏（至少 person/phone/company/address 各 1 条代表用例不受影响）；模块头写 F/R/A/S + 与 phone（有闸门）和 person（无闸门）的差异说明。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 468 + 新增 amount/date 用例：space/sep/noise/abbrev(万元展开、缺零)代表用例、不可恢复 abbrev 不猜（缺年/年月）、typo 形近 + 闸门、已规范→0.95、置信度 ∈ [0,1]、注册表、**六字段回归护栏**） |
| 2 | train 实测报数 | `uv run --project . python -m benchmarks.evaluate --impl rules --split train` | exit 0；summary 含 amount/date 两行；**真实数脑验收时如实汇报**（heldout 不跑——留给定版后的 TASK 单独跑） |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/tools/**`、`loop.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-019）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 评测不跑**
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 generate.py 词典常量、不从 heldout 反推

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 建议实现顺序：先看 train 脏集样本（可读数据文件）→ 写测试代表用例 → 规则 → 注册 + evaluate FIELDS → 跑判据 2 看真实数。
- 大写数字轴（壹/贰/叁）已裁定单开一单，本单不做。
- 手脑方案：干完写 `.handoff\outbox\RESULT-019.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

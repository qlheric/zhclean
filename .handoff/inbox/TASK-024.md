# TASK-024　M2 第三批规则：idcard/email 规范化（闸门校验 + 15→18 展开）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `src/zhclean/rules/idcard.py`、`src/zhclean/rules/email.py`、`src/zhclean/rules/__init__.py`（DISPATCH 注册两字段）、`src/zhclean/rules/common.py`（如需公共机制）、`tests/test_idcard.py`、`tests/test_email.py` |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `benchmarks/clean|dirty/{idcard,email}.jsonl` 的 **train 部分**、`src/zhclean/rules/{phone,date}.py`（参考有闸门规则）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ 特别禁止：读 benchmarks/generate.py 词典常量；heldout 不跑（定版在 TASK-025）** |
| **_Depends:**（依赖） | TASK-023（已通过，`597b8b8`；RESULT-023 §5-a 生日 1970–1999 已裁决） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

`rules/idcard.py` 与 `rules/email.py` 实现身份证/邮箱规范化（结构清洗 + 形近修复 + **校验闸门** + 15→18 展开），注册 DISPATCH。**本单只写规则与单测，不做评测接入（TASK-025）。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/rules/idcard.py`、`src/zhclean/rules/email.py`（新建）
- `src/zhclean/rules/__init__.py`（DISPATCH 注册）
- `src/zhclean/rules/common.py`（仅当需要新公共机制；不改现有行为）
- `tests/test_idcard.py`、`tests/test_email.py`（新建）
- 除此之外**一律不许动**（尤其 `tools/**`、`loop.py`、`benchmarks/**`、数据文件、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

**idcard**（干净值 = 18 位 GB 11643：11 开头地区 + 8 位生日 1970–1999 + 3 位顺序 + 校验码）：
- 闸门 `_valid18(s)`：18 位、前 17 全数字、**校验码按 GB 11643 重算必须匹配**（权重表与 `10X98765432` 查表，独立实现不抄生成器）。
- `space`：去所有空白 → 应全对
- `noise`：去「身份证号：/身份证号:」前缀、「（复印件）/（本人）」后缀、尾随标点 → 应全对
- `sep`：生日段分隔符（`1104121976-05-13…`）→ 去 `-` → 应全对
- `typo`：数字形近修复（`IDCARD_TYPOS` 反向），**修完必须过闸门**（校验码不匹配即不采纳）——形近错位可能在生日/顺序/地区，只要过闸门即采纳
- `abbrev`：**15 位老证 → 补「19」+ 重算校验码 → 18 位**（生日 1970–1999 已保证可逆；补完过闸门才采纳，置信度 0.7 推断层）
- 已规范（过闸门）→ 0.95；结构层（space/noise/sep 命中且过闸门）→ 0.9

**email**（干净值 = `user@domain`，user 字母开头+含数字 3–12 位、domain 含点）：
- 闸门 `^\S+@\S+\.\S+$`（宽松形态）+ domain 含点 + 无空白。
- `space`：去所有空白（@ 前后）→ 应全对
- `noise`：去「邮箱：/Email:/E-mail:」前缀（大小写不敏感）、尾随标点 → 应全对
- `typo`：形近还原（`o↔0 l↔1 z↔2 s↔5 g↔6 b↔8` 双向）——**只修 user 段与 domain 的字母位，@ 与点不动**；修完过闸门才采纳
- `sep`：user 段多余的下划线/点**去不掉**（无法区分合法 `a.b` 与多余 `a_b`）——**不猜，原样低置信**（这是 email 的已知天花板，别预设拿分）
- `abbrev`（`.com→.co`、`@gmail.com→@gmail`）：**不可恢复，不猜**——原样低置信
- 已规范（过闸门）→ 0.95

**惯例**：模块头 F/R/A/S + 与 phone（有闸门）的差异说明；测试带八字段回归护栏（六老字段各 1 条代表用例不受影响）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 565 + 新增：idcard 五类代表用例、**15→18 展开 + 校验码重算**、typo 修复过闸门、坏校验码不采纳、0.95 档；email 去空白/前缀、typo 双向、abbrev 与 sep 不猜、闸门、**八字段回归护栏**） |
| 2 | 规则自测（train 数据回环） | 手写临时脚本读 train 行跑 normalize（**不跑评测管线、不跑 heldout**） | 回执贴 idcard/email 的 train 失败数与代表样例（**如实报**，用于 TASK-025 预期校准） |

## 4. 禁区（碰了即作废）

- 不许改：`tools/**`、`loop.py`、`benchmarks/**`（含 evaluate 与数据）、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-024）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 评测不跑**
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 generate.py 词典常量（形近表独立定义，与生成器无关）

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 规则是 TASK-024、评测接入 + heldout 重定版是 TASK-025（老六类逐位复现 M2 定版是硬判据）、文档是 TASK-026。
- email 的 sep/abbrev 按「不猜」是**正确口径**——train 回环数字会因此有天花板，如实报即可。
- 手脑方案：干完写 `.handoff\outbox\RESULT-024.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

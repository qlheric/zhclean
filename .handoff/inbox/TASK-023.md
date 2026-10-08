# TASK-023　M2 第三批字段：generate.py 扩展 idcard/email（老六类逐字节不变）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-09 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `benchmarks/generate.py`（扩展 idcard/email 生成）、`benchmarks/clean|dirty/{idcard,email}.jsonl`（新产物）、`tests/test_benchmark.py`（扩展用例） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `uv run` / `pytest` 命令；读 `benchmarks/generate.py`（**本单允许：扩展生成器本身**）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ 本单写生成器、不写规则；不读词典调规则（规则是后续 TASK）** |
| **_Depends:**（依赖） | TASK-022（已通过，`16d02f4`）；沿用 TASK-001 schema 契约（`32311d4`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

`benchmarks/generate.py` 扩展第三批两个字段：**idcard（身份证号）与 email（邮箱）**——干净集 + 五类扰动 + train/heldout 划分，**老六类在 seed 42 下产物逐字节不变**（每字段独立 RNG 流，追加新字段不扰动旧流）。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `benchmarks/generate.py`（扩展）
- `benchmarks/clean/{idcard,email}.jsonl`、`benchmarks/dirty/{idcard,email}.jsonl`（生成产物）
- `tests/test_benchmark.py`（扩展新字段不变式）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`benchmarks/evaluate*.py`、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

- schema 对齐 TASK-001/018：clean 三字段、dirty 六字段、每类 200 干净值 × 5 扰动 = 1000 脏行、id = `<field>-NNNN`、seed 洗牌前 20% heldout。
- **idcard 干净值**：18 位身份证号（GB 11643 形态）——6 位地区码（合成，11 开头的合法结构即可）+ 8 位生日（同 date 范围）+ 3 位顺序码 + **1 位校验码按 GB 11643 真实算法计算**（让规则侧的格式校验闸门有的放矢；不做真实性查询——地区码与生日是合成组合）。
  - 五类扰动映射：space（段间/数字间空格）、typo（数字形近字母）、abbrev（**15 位老证 → 18 位展开**：19xx 年补「19」+ 校验码重算——干净值 = 18 位，abbrev 扰动把 18 位改写为 15 位老证形态）、sep（生日段加分隔 `19900315` → `1990-03-15`）、noise（「身份证号：」前缀/「（复印件）」后缀）。
- **email 干净值**：`<user>@<domain>`——user = 字母数字混合（3–12 位）、domain = 常见域名（com/cn/net/org/edu 等固定小集合）。
  - 五类扰动映射：space（@ 前后空格）、typo（形近替换如 0/O、1/l，**至少 1 处**）、abbrev（`.com` → `.co`、`@gmail.com` → `@gmail`，不可恢复部分靠不猜）、sep（加多余点/下划线）、noise（「邮箱：」前缀）。
- **确定性**：同 seed 两次运行逐字节一致；老六类 seed 42 产物逐字节不变（判据 2 卡死）。
- CLI 不变：`python -m benchmarks.generate --seed 42`；stdout 汇总表含 8 类。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 564 + 新增 test_benchmark 用例：idcard/email 各 200 干净值、每 id 5 脏变体 truth 一致、split 比例≈0.2、**idcard 校验码按 GB 11643 算法可验证**、同 seed 两次逐字节一致、heldout 覆盖全部扰动类型） |
| 2 | 老六类逐字节不变 | `python -m benchmarks.generate --seed 42` 后 `git diff --exit-code -- benchmarks/clean benchmarks/dirty` | 老六类 12 个 jsonl **零 diff**；新出现 idcard/email 4 个 jsonl；exit 0 |
| 3 | 新字段可读核验 | 抽查 clean 2 行 / dirty 2 行 | schema 正确、truth 与干净值对应、idcard 校验码合法 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`benchmarks/evaluate*.py`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-023）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；本单不写规则

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 流程照 M2 前两批：benchmark 先行 → 规则（TASK-024）→ 评测接入 + 定版（TASK-025）→ 文档（TASK-026）。
- 身份证只做**格式级**校验（位数/生日/校验码），不做真实性查询——生成器据此设计：结构合法但组合合成。
- 手脑方案：干完写 `.handoff\outbox\RESULT-023.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

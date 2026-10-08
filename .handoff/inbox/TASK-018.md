# TASK-018　M2 第一单：generate.py 扩展 amount/date 两字段（老四类逐字节不变）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `benchmarks/generate.py`（扩展 amount/date 字段生成）、`benchmarks/clean|dirty/{amount,date}.jsonl`（新产物）、`tests/test_benchmark.py`（扩展用例） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `uv run` / `pytest` 命令；读 `benchmarks/generate.py`（**本单允许：目的是扩展生成器本身**）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件。⚡ 留出集纪律不变：本单写生成器、不写规则；禁止拿任何词典常量调规则（M2 规则是后续 TASK）** |
| **_Depends:**（依赖） | TASK-017（已通过，`1e3213b`）；沿用 TASK-001 的 schema 契约（`32311d4`） |
| **_Commit:**（对应提交） | `714997a`（脑验收通过后提交） |

## 1. 目标（一句话）

`benchmarks/generate.py` 扩展两个 M2 字段：**amount（金额）与 date（日期）**——干净集 + 五类扰动 + train/heldout 划分（同 seed 洗牌前 20% heldout），**老四类（person/address/phone/company）在 seed 42 下的产物必须逐字节不变**（RNG 流按 `random.Random(f"{seed}:{field}")` 隔离，加新字段不扰动旧流）。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `benchmarks/generate.py`（扩展）
- `benchmarks/clean/{amount,date}.jsonl`、`benchmarks/dirty/{amount,date}.jsonl`（生成产物）
- `tests/test_benchmark.py`（扩展新字段不变式）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`benchmarks/evaluate*.py`、`pyproject.toml`）

## 2.5 契约（脑定，照此实现）

- schema 对齐 TASK-001：clean 行 `{"id","field","value"}`、dirty 行 `{"id","field","value","truth","perturbation","split"}`；每类 200 干净值（`--per-field` 可改）→ 每条 5 类扰动各 1 = 1000 脏行；`id` = `<field>-NNNN`。
- **amount 干净值**：数值 + 单位（「元」基准），如 `12800.5 元`；内置生成规则（大小写数字、小数、千分位）。
  - 五类扰动映射：space（数字间插空格）、typo（数字形近/大写数字错字「壹→壱」类）、abbrev（单位缩写「万」→ 数值）、sep（千分位分隔符乱）、noise（「金额：」前缀/「（含税）」后缀）。
- **date 干净值**：ISO 日期 `YYYY-MM-DD`（合理范围 1970–2026）。
  - 五类扰动映射：space、typo（数字形近）、abbrev（缺零「2026-1-5」或缺年「1-5」或年月「2026-10」）、sep（`2026/10/06`、`2026.10.06`）、noise（「日期：」前缀）。
- **确定性**：同 seed 两次运行全库逐字节一致；老四类 seed 42 产物逐字节不变（判据 2 卡死）。
- CLI 不变：`python -m benchmarks.generate --seed 42 [--per-field 200 --split-ratio 0.2]`；stdout 汇总表含 6 类。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 467 + 新增 test_benchmark 用例：amount/date 各 200 干净值、每 id 5 脏变体且 truth 一致、split 比例≈0.2 且无重叠、五类扰动各字段覆盖、同 seed 两次逐字节一致、heldout 覆盖全部扰动类型） |
| 2 | 老四类逐字节不变 | `python -m benchmarks.generate --seed 42` 后，`git diff --exit-code -- benchmarks/clean benchmarks/dirty`（对已入库的老四类文件） | 老四类 8 个 jsonl **零 diff**；新出现 amount/date 4 个 jsonl；exit 0 |
| 3 | 新字段可读核验 | 抽查 `benchmarks/clean/amount.jsonl` 与 `dirty/date.jsonl` 各 2 行 | schema 六字段/三字段正确、truth 与干净值对应 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`benchmarks/evaluate*.py`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-018）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；本单不写规则、不用任何词典调规则

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 本单是 M2 起步：先有可核评测集，再写 amount/date 规则（TASK-019），最后评测接入（TASK-020）——照 M1 的「benchmark 先行」纪律。
- 手脑方案：干完写 `.handoff\outbox\RESULT-018.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。三条判据均经脑亲跑：①468 passed；②老四类 `git diff --exit-code` = 0（逐字节不变）+ amount/date 4 个新 jsonl；③抽查 schema/truth 正确（2400 行全量核验实据在回执 §3.7）。
- 边界零越界。三个拍板点裁决：①金额干净值无空格（采纳手实现，契约示例改口）；②abbrev 方向元→万元（采纳，TASK-019 规则做万元展开）；③大写数字轴单开一单（不阻塞）。
- §5-4 CRLF warning：脑侧已在 .gitattributes 补 `*.jsonl text eol=lf`。
- **里程碑：M2 评测集就位（六类字段）。**
- `_Status: 已完成`；`_Commit: 714997a`。

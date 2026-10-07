# TASK-006　normalize(地址) 规则：四类收尾，最考验规则设计的一类

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH（本会话） |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `src/zhclean/rules/address.py`、`src/zhclean/rules/__init__.py`、`tests/test_address.py`、`benchmarks/results/**`（评测产物，不入库） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `uv run` / `pytest` 命令；读 `benchmarks/dirty/*.jsonl` 的 **train 失败样本**（可）、`src/zhclean/rules/{person,phone,company}.py`（参考实现风格）、`task_plan.md`、`findings.md`。**禁止：联网、装包/改依赖、git commit、调用其他 agent、动范围外任何文件。⚡ 特别禁止：读 `benchmarks/generate.py` 的词典常量（留出集纪律，2026-10-08 固化——靠机制不靠自觉）；禁止从 heldout 反推** |
| **_Depends:**（依赖） | TASK-005（已通过，`01f03d5`） |
| **_Commit:**（对应提交） | `ddedddc`（脑验收通过后提交） |

## 1. 目标（一句话）

地址规则打底：省/市/区/路/门牌结构清洗 + 可无歧义恢复的行政区划补全 + 通用错字修复（已知词组闸门），注册进 `DISPATCH`，heldout 上跑出**地址的真实规范化率**——四类 normalize 就此收齐。**本单只做 address。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/rules/address.py`（地址规则词典与清洗函数）
- `src/zhclean/rules/__init__.py`（DISPATCH 注册 `"address"`）
- `tests/test_address.py`（地址规则单测）
- `benchmarks/results/**`（评测产物，已 .gitignore 不入库）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/{person,phone,company}.py`、`tools/normalize.py`、`loop.py`、`cli.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`）

## 2.5 接口契约（脑定，照此实现）

- `normalize_address(value: str) -> tuple[str, float]`，置信度沿用 0.9 结构 / 0.7 推断 / 0.1 无证据。
- 处置口径（五类扰动）：
  - `space` / `sep` / `noise`：结构清洗（空白/分隔符/「地址：」类前缀/「（收货地址）」类尾注/尾随标点）→ 应全对（同 person/phone/company 机制）
  - `abbrev`：**先看脏集样本数天花板，别预设拿分**（company 的教训：无歧义可恢复型占比才是上限）。候选有三类：去省段（不可恢复）、去「省」（「广东省」→「广东」，**若可无歧义补回则补**，判据 = 省名闭集词典）、去「省」「市」（「广东省深圳市」→「广东深圳」，需省市两级词典，**歧义时宁可不猜**）。**不猜不可靠恢复，对齐 person/company 口径。**
  - `typo`：行政区划/道路必现字（市/区/路/号等）的通用错字修复，**沿用 company 的已知词组闸门机制**（判据集合 = 行政区划闭集 ∪ 道路词闭集「路/街/巷/道/号/栋/单元/室/层」等；品牌/小区名是开集，不进判据集合）
- **行政区划词典内置**（34 省级单位 + 常见地级市，通用知识整理；真实区县对应关系缺数据源属已知限制，见 findings——「上海市西城区」式组合是生成器合成，规则不负责纠错真实地理，只负责格式还原）。
- **惯例**：测试带 person/phone/company **三字段回归护栏**。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 154 + 新增 `tests/test_address.py`：space/sep/noise 代表用例、可补的 abbrev、不可靠 abbrev 不猜、typo 通用表 + 闸门、置信度 ∈ [0,1]、注册表、**person/phone/company 三回归护栏**） |
| 2 | 评测报真实数（相对基线收紧） | `uv run --project . python -m benchmarks.evaluate --impl rules` | exit 0；**address 行 rate > 0 且 failures 总行数 < 294（TASK-005 实绩）**——address 的 space/sep/noise 结构清洗至少应拿分，全 0 说明实现有问题 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/{person,phone,company}.py`、`tools/normalize.py`、`loop.py`、`cli.py`、`llm.py`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-006）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**
- **不许读 `benchmarks/generate.py` 的词典常量来设计规则**（防留出集反推）；不许从 heldout 反推。查缺漏只看 train 失败样本。

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`（只影响本单边界内文件）。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 建议实现顺序：先看 train 脏集样本定 abbrev 口径（数「无歧义可恢复」占比）→ 写 test_address.py 代表用例 → 规则实现 → 注册 → 跑判据 2 看真实数。
- address 完成后，脑会派维护单（合并三张错字表 + 闸门机制到 `rules/common.py`），本单不用管。
- 手脑方案：干完写 `.handoff\outbox\RESULT-006.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。回执申报清单外新文件并贴 §1.5 基线输出。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。两条判据均经脑亲跑：①`uv run --project . pytest tests/ -q` → 225 passed；②`uv run --project . python -m benchmarks.evaluate --impl rules` → exit 0、**address 90.50%**（181/200；space/sep/noise/typo 全 100%、abbrev 52.5%）、failures 113 < 294。
- 边界检查：手侧 3 个改动文件 ⊆ `_Boundary:_`（零越界）。
- **结构化代码审查**（3/3 覆盖 100%）：critical/high/medium 0、low 2，不阻塞；**数字声称全部机械核验对上**（909/83/8、8 条改坏逐条归因、干净值零误伤、abbrev 天花板 21/23、train/heldout 差 0.5pp）。
- 拍板点裁决：**保留 15 个方位构词 + TASK-007 加「后跟区/城」位置约束**（两全：保留真实场景修复力 + 关掉小区名误伤面）。8 条改坏属「真实区县数据源缺失」已知限制，M2 引入区县表时再消歧。
- **里程碑**：四类 normalize 收齐——person 72% / phone 100% / company 81% / address 90.5%，总盘 85.88%（687/800）。
- `_Status: 已完成`；`_Commit: ddedddc`。

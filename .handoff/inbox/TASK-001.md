# TASK-001　benchmark 先行：干净集 + 扰动生成器 + 留出集划分

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH（本会话） |
| 日期 | 2026-10-07 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `benchmarks/generate.py`、`benchmarks/__init__.py`、`benchmarks/clean/**`、`benchmarks/dirty/**`、`tests/test_benchmark.py` |
| **_Capability:**（只许用） | 写 Python 代码（stdlib only）；跑 `python` / `uv run` / `pytest` 命令；读 `src/zhclean/**`、`task_plan.md`、`findings.md` 作上下文。**禁止：联网、装包/改依赖、git commit、调用其他 agent、动范围外任何文件** |
| **_Depends:**（依赖） | 无（基线提交 `cdb02dd`，pytest 已由脑预装进 dev 依赖） |
| **_Commit:**（对应提交） | `32311d4`（脑验收通过后提交） |

## 1. 目标（一句话）

`benchmarks/generate.py` 程序化生成 4 类（人名/地址/电话/公司名）干净集与脏集：每条脏值标注 ground truth（扰动前原值）与扰动类型，train/heldout 按 id 确定性划分（8:2），同 seed 输出逐字节一致；配套不变式测试全绿。**本单只做数据与生成器，不写任何清洗逻辑。**

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `benchmarks/generate.py`（生成器，**stdlib only**，不新增依赖）
- `benchmarks/__init__.py`（使 `python -m benchmarks.generate` 可用；`python benchmarks/generate.py` 直接跑也必须可用）
- `benchmarks/clean/{person,address,phone,company}.jsonl`（生成产物）
- `benchmarks/dirty/{person,address,phone,company}.jsonl`（生成产物）
- `tests/test_benchmark.py`（不变式测试）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`pyproject.toml`、`benchmarks/results/**`）

## 2.5 数据契约（schema，照此实现，后续任务都靠它）

- clean 行：`{"id": "person-0001", "field": "person", "value": "王小明"}`
- dirty 行：`{"id": "person-0001", "field": "person", "value": "王 小明", "truth": "王小明", "perturbation": "space", "split": "train"}`
- 每类 200 条干净值（`--per-field` 可改，默认 200）；每条干净值生成 **≥3 条脏变体**，扰动模板五类都要覆盖：`space`（加空格）、`typo`（常见错别字）、`abbrev`（简称/后缀变异）、`sep`（分隔符乱）、`noise`（重复/冗余噪声）
- train:heldout = 8:2（`--split-ratio` 默认 0.2）；**划分口径（2026-10-07 验收定稿）＝ seed 洗牌后前 split-ratio（20%）为 heldout、其余为 train**（实现以此为准）
- 确定性：同 seed 两次运行产物**逐字节一致**；输出 utf-8 + LF + jsonl（`ensure_ascii=False`）
- 词典**内置**（不联网）：常见姓氏 ≥50（含复姓）、名字用字、地级行政区划 ≥100、公司后缀/行业词、手机号段规则。**干净值必须看起来真实**（如「杭州云栖科技有限公司」「王小明」），禁纯随机字符拼接
- CLI：`python -m benchmarks.generate --seed 42`（`--seed` 默认 42 / `--per-field` 默认 200 / `--split-ratio` 默认 0.2）；成功 exit 0，stdout 打印每类每 split 行数汇总

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令，脑已亲跑①） | 期望结果 |
|---|---|---|---|
| 1 | 不变式测试全绿 | `uv run --project . pytest tests/ -q` | 全部通过，至少覆盖 7 条不变式：四类各 200 条干净值；每干净值 ≥3 条脏变体且 truth 一致；train/heldout 无 id 重叠且比例≈0.2；同 seed 两次产物逐字节一致；五类扰动每类每字段至少出现一次；脏值≠干净值；heldout 覆盖全部扰动类型 |
| 2 | 生成器可跑且只落 8 个产物 | 连跑两次 `python -m benchmarks.generate --seed 42`，再 `git status --porcelain benchmarks/` | 两次均 exit 0；**除 `_Boundary:_` 内代码文件（generate.py/__init__.py）外**，只多出 8 个新 jsonl（clean×4 + dirty×4），无其他文件变化 |

> ① 判据 1 的命令已由脑在派单前亲跑（2026-10-07：pytest 9.1.1 经 dev 依赖预装，当前 1 passed），环境前提成立。

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除你写 RESULT-001）
- 不许跑：`rm -rf`、任何写 `src/` 的操作、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**（不查资料、不取数据、不装包）

## 5. 回滚方式

未提交前：删除本单新增文件即回原状。若脑已提交：`git revert <该提交sha>`（只影响 benchmarks/ 与 tests/test_benchmark.py）。

## 6. 备注

- 命门口径见 `task_plan.md`：benchmark 先行、ground truth = 扰动前原值、留出集防过拟合（后续规则库不得针对测试扰动模式调参）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-001.md`（**判据/命令/输出/证据**四项必填 + 第 7 节「下次接着做什么」），然后**停下**；**不动 TASK 状态字段**（状态归脑）。
- 回执里必须申报清单外的任何新文件（含缓存），并贴出 §1.5 基线命令的输出。
- 参考：`findings.md` §5（评测口径）。S1 的 `eval/` 结构可参考思路，但本单照本卡契约实现，不照搬。

## 7. 验收结论（2026-10-07 · 脑）

- **已通过**。两条判据均经脑亲跑：①`uv run --project . pytest tests/ -q` → 8 passed；②生成器连跑两次 exit 0、产物 8 个 jsonl、输出与回执逐行一致。
- 边界检查：改动文件 ⊆ `_Boundary:_`（零越界；RESULT-001 属交接机制豁免）。
- 两个拍板点（脑定）：①划分口径 = 前 20% heldout（已定稿回写 §2.5，不重做）；②判据 2 措辞已按手建议修正（§3）。
- 手申报处置：__pycache__ 由 .gitignore 忽略（无需清理）；仓库外 3 个临时目录已由脑清理；合成数据真实性问题（区划组合/生僻名字组合/号段）记 findings.md §5，不阻塞（后续地址规则开发时留意）。
- `_Status: 已完成`；`_Commit: 32311d4`。

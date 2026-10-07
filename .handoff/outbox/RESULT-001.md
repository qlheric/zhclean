# RESULT-001　对应 TASK-001

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-07 |
| 结论 | 完成（两条判据均亲跑通过；未 commit，按禁区留给脑） |

## 0. §1.5 基线（开工前第一件事）

shell：Git Bash；工作目录 = 项目根；HEAD = `6365c38`。

```
$ git status --porcelain -uall
```
（输出为空——基线工作区干净）

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `benchmarks/generate.py` | 原为 7 行 F/R/A/S 文档头空壳 → 完整生成器（内置词典 + 4 类干净值生成 + 5 类扰动 + 确定性划分 + CLI）；保留原 F/R/A/S 头 | +409 / −1 |
| `benchmarks/__init__.py` | 新建，一行 docstring，使 `python -m benchmarks.generate` 可用 | 1 |
| `tests/test_benchmark.py` | 新建，7 个不变式测试 | 162 |
| `benchmarks/clean/{person,address,phone,company}.jsonl` | 生成产物，各 200 行 | 4×200 |
| `benchmarks/dirty/{person,address,phone,company}.jsonl` | 生成产物，各 1000 行（200×5 扰动） | 4×1000 |

范围外的业务文件一个都没碰（`src/`、`pyproject.toml`、`benchmarks/results/` 都没动，见 §3 的 `git status`）。

## 2. 关键 diff 摘要

**确定性**：每个字段用独立的 `random.Random(f"{seed}:{field}")` 流；五类扰动按固定顺序输出；写盘统一 `encoding="utf-8", newline="\n"`，加上 `json.dumps(..., ensure_ascii=False)`。

```python
rng = random.Random(f"{seed}:{field}")  # 每字段独立流：字段间互不影响顺序
...
shuffled = [r["id"] for r in clean_rows]
rng.shuffle(shuffled)
n_heldout = round(per_field * split_ratio)
heldout = set(shuffled[:n_heldout])
```

**划分口径（与简报措辞的差异，请脑确认）**：简报写的是「seed 洗牌后**前 80% 为 train**」，我实现的是「洗牌后**前 split-ratio(20%) 为 heldout**，其余为 train」。两种写法都是确定性的 8:2，集合不一样，但不变式都满足。如需严格按「前 80% 为 train」，改一行切片即可；**本单我没有擅自改**，交给脑拍板。

**防泄漏**：同一个 clean id 的 5 条脏变体与它的干净值属于同一个 split（测试 3 有断言）。

**每个字段的五类扰动都必然可造**（错别字表保证命中）：

| 扰动 | person | address | phone | company |
|---|---|---|---|---|
| space | 中间插半角/全角空格 | 同左 | 同左 | 同左 |
| typo | 名字用字 → 同音/形近字（名字用字池 = 错别字表的键） | 市/区/路/号等必现字 → 错字 | 数字 → 形近字母 0→O 1→l 8→B… | 公/司/有/限等必现字 → 错字 |
| abbrev | 省掉名里一个字 | 去省级段 / 去「省」/ 去「省」「市」 | 补国家码 86 / +86 / 086 | 股份有限公司→股份公司、有限责任公司→有限公司、去城市、去组织形式 |
| sep | 姓/名之间插 `- · \| ／ ，` | 行政层级之间插 | 3-4-4 之间插 | 城市/字号/行业/后缀之间插 |
| noise | 「姓名：」前缀 / 先生·女士 后缀 | 「地址：」/（收货地址）/ 尾随句号 | 「电话：」/（微信同号） | 「单位：」/（总部） |

**词典规模（亲测）**：单姓 120 + 复姓 12 = 132；名字用字 81；地级行政区 179（覆盖 34 个省级单位）；区县 24；路名 30；手机号段 52；公司字号 70、行业词 24、组织形式 4。

**过程中自查修掉的 3 个问题**（都在本单范围内）：
1. 复姓误用 `list("欧阳上官…")` 被拆成了单字 → 改成显式列表。
2. clean 行带了契约外的 `split` 字段 → 删掉，clean 行严格只有 `id/field/value`。
3. 地址曾派生出「石嘴山市石嘴山西区」这样重复城市名的区名（seed 42 下 80/200）→ 去掉「城市+方位区」的派生，改用通用区名池；修复后重复 0。

## 3. 我亲跑过的自测（真实输出）

shell：Git Bash，工作目录 = 项目根。终端是 GBK 代码页，所以 `out=` 那一行里的中文路径显示成了乱码，这是终端显示问题，不影响产物（产物经测试 4 验证为 UTF-8）。

**判据 2：连跑两次生成器**

```
$ python -m benchmarks.generate --seed 42; echo "exit=$?"
seed=42 per_field=200 split_ratio=0.2
out=G:\Agentwork_mvp\s2-���������ݾ�����-zhclean\benchmarks
field    split      clean  dirty
person   train        160    800
person   heldout       40    200
address  train        160    800
address  heldout       40    200
phone    train        160    800
phone    heldout       40    200
company  train        160    800
company  heldout       40    200
exit=0
```

第二次运行（同一条命令）输出与上面逐行相同，同样 `exit=0`。

```
$ git status --porcelain benchmarks/
 M benchmarks/generate.py
?? benchmarks/__init__.py
?? benchmarks/clean/address.jsonl
?? benchmarks/clean/company.jsonl
?? benchmarks/clean/person.jsonl
?? benchmarks/clean/phone.jsonl
?? benchmarks/dirty/address.jsonl
?? benchmarks/dirty/company.jsonl
?? benchmarks/dirty/person.jsonl
?? benchmarks/dirty/phone.jsonl
```

**判据 1：不变式测试**

```
$ uv run --project . pytest tests/ -q
........                                                                 [100%]
8 passed in 1.03s
```
（8 个 = 原有 `test_package` 1 个 + 本单新增 7 个）

**脚本直跑入口**（简报要求 `python benchmarks/generate.py` 也必须可用）

```
$ python benchmarks/generate.py --seed 42; echo "exit=$?"
```
输出与上面判据 2 的相同（9 行汇总），`exit=0`。

**全仓状态（收工时）**

```
$ git status --porcelain -uall
 M benchmarks/generate.py
?? benchmarks/__init__.py
?? benchmarks/clean/address.jsonl
?? benchmarks/clean/company.jsonl
?? benchmarks/clean/person.jsonl
?? benchmarks/clean/phone.jsonl
?? benchmarks/dirty/address.jsonl
?? benchmarks/dirty/company.jsonl
?? benchmarks/dirty/person.jsonl
?? benchmarks/dirty/phone.jsonl
?? tests/test_benchmark.py
```
（`.handoff/outbox/RESULT-001.md` 是在这次 status 之后才写的，所以不在上面）

**产物抽样**

```
$ head -1 benchmarks/clean/company.jsonl
{"id": "company-0001", "field": "company", "value": "嘉兴数联贸易集团有限公司"}
$ head -5 benchmarks/dirty/person.jsonl
{"id": "person-0001", "field": "person", "value": "范 童言", "truth": "范童言", "perturbation": "space", "split": "heldout"}
{"id": "person-0001", "field": "person", "value": "范同言", "truth": "范童言", "perturbation": "typo", "split": "heldout"}
{"id": "person-0001", "field": "person", "value": "范童", "truth": "范童言", "perturbation": "abbrev", "split": "heldout"}
{"id": "person-0001", "field": "person", "value": "范|童言", "truth": "范童言", "perturbation": "sep", "split": "heldout"}
{"id": "person-0001", "field": "person", "value": "范童言女士", "truth": "范童言", "perturbation": "noise", "split": "heldout"}
```

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | 不变式测试全绿，≥7 条不变式 | ✅ 8 passed（新增 7 个） | §3「判据 1」；测试与简报 7 条的对应见下表 |
| 2 | 连跑两次 exit 0，`git status --porcelain benchmarks/` 只出 8 个新 jsonl | ✅ 两次 exit 0；新增 jsonl 正好 8 个。**另外还列出了** `M benchmarks/generate.py` 和 `?? benchmarks/__init__.py`，两者都是本单 `_Boundary:_` 里的文件，不是生成器的产物 | §3「判据 2」 |

简报列的 7 条不变式和测试函数的对应关系：

| 简报不变式 | 测试函数 |
|---|---|
| 四类各 200 条干净值 | `test_clean_counts_and_uniqueness`（另外断言 id/value 唯一，clean 行只有三个字段） |
| 每干净值 ≥3 脏变体且 truth 一致 | `test_dirty_variants_truth_and_coverage` |
| train/heldout 无 id 重叠且比例≈0.2 | `test_split_no_overlap_and_ratio`（另外断言同 id 的脏变体不跨 split） |
| 同 seed 逐字节一致 | `test_same_seed_byte_identical`（另外断言没有 CRLF、没有 `\u` 转义） |
| 五类扰动每类每字段至少一次 | `test_all_perturbations_present`（按 train、heldout 分别断言） |
| 脏值 ≠ 干净值 | 包含在 `test_dirty_variants_truth_and_coverage` 里 |
| heldout 覆盖全部扰动类型 | 包含在 `test_all_perturbations_present` 里 |
| （额外）seed 确实生效 | `test_different_seed_differs` |
| （额外）仓库产物没过期 | `test_repo_artifacts_fresh`：仓库里的 jsonl 必须等于当前生成器 seed 42 的输出 |

## 5. 遗留 / 不确定 / 需要拍板

- **【需拍板】划分口径**：见 §2。现在是「前 20% 为 heldout」，简报原文是「前 80% 为 train」。
- **【需拍板】判据 2 的措辞**：「status 只出现 8 个新 jsonl」在字面上和必然出现的 `M generate.py` / `?? __init__.py` 冲突。建议下一单把判据写成「除 `_Boundary:_` 里的代码文件外，只多出 8 个 jsonl」。
- **【申报·清单外新文件，都是解释器缓存，已被 .gitignore 忽略】**由 `python` / `pytest` 自动产生：
  - `benchmarks/__pycache__/__init__.cpython-312.pyc`、`__init__.cpython-314.pyc`、`generate.cpython-312.pyc`、`generate.cpython-314.pyc`（312 来自 uv 的 .venv，314 来自 PATH 上的 python）
  - `tests/__pycache__/test_benchmark.cpython-312-pytest-9.1.1.pyc`
  - （`tests/__pycache__/test_package…pyc` 是开工前就有的，不是本单产生的）
- **【申报·仓库外临时文件】**我自测确定性时用 `tempfile.mkdtemp()` 在 `C:\Users\38628\AppData\Local\Temp\` 下建了 3 个目录：`tmp7yex_n6n`、`tmpt9mi_j43`、`tmpz7ht6nmd`。它们在仓库外，没有清理（`rm -rf` 在禁区里）。另外，pytest 的 `tmp_path` 也会在系统临时目录里留下目录，由 pytest 自己轮转。
- **【已知局限·真实性】**
  1. 区名池是通用名，会出现「上海市西城区」这种现实里不存在的组合，但格式是真实的。
  2. 部分名字用字组合比较少见（如「聂玲哲」）。
  3. 手机号段只保证形状真实，不校验现在是否还在用。

  这几点不影响 ground truth 的正确性。如果要求更真实，需要引入官方行政区划和区县的对应表，这需要数据源，属于 task_plan Key Question 2。
- **【测试耗时】**`test_repo_artifacts_fresh` 等测试会以子进程方式重新生成数据，全套约 1 秒，可以接受。

## 6. 建议下一步

- 脑拍板划分口径以后，再入库 8 个 jsonl 加上代码（产物被 `test_repo_artifacts_fresh` 守着，生成器一改、产物没重生成，测试就会报红）。
- 下一单（评测脚本）：读 `benchmarks/dirty/*.jsonl` 中 `split=="heldout"` 的行，按「normalize(value) == truth」计算规范化率，按 `perturbation` 分组出数，失败案例落到 `benchmarks/results/`。
- 后续 dedupe recall 的口径可以直接复用：同一个 `id` 的 clean 加 5 条 dirty 就是「应合并组」。

## 7. 下次接着做什么（写给下一轮的我）

- 做到哪了：TASK-001 已交付。生成器在 `benchmarks/generate.py`，产物在 `benchmarks/{clean,dirty}/*.jsonl`，不变式测试在 `tests/test_benchmark.py`。本地 8 passed，未提交。
- 下一步第一件事：读 `.handoff/inbox/` 里最新的 TASK，看脑对「划分口径」的拍板。如果要改成「前 80% 为 train」，只改 `build()` 里 `heldout = set(shuffled[:n_heldout])` 那一行，然后**重跑生成器**（否则 `test_repo_artifacts_fresh` 会红）。
- 要绕开的坑：
  1. 终端是 GBK，打印中文要加 `PYTHONIOENCODING=utf-8`，否则显示乱码（产物本身没问题）。
  2. `rm -rf` 是禁区，权限会拦；临时目录用 `tempfile`。
  3. auto 模式的权限分类器偶尔超时，重试即可。

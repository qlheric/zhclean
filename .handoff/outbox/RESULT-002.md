# RESULT-002　对应 TASK-002

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-07 |
| 结论 | 完成（两条判据均亲跑通过；未 commit，按禁区留给脑） |

## 0. §1.5 基线（开工前第一件事）

shell：Git Bash；工作目录 = 项目根；HEAD = `cc18178`。

```
$ git status --porcelain -uall
```
（输出为空——基线工作区干净）

`_Depends:_` 核对：TASK-001 已由脑验收通过并入库（`32311d4`），划分口径定稿为「洗牌后前 20% 为 heldout」（回写进 TASK-001 §2.5）。本单按此口径评 heldout。

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `benchmarks/evaluate.py` | 新建，评测管线：读脏集 → 跑 normalize → 按 field × perturbation 出数 → 落 summary/failures | 146 |
| `tests/test_evaluate.py` | 新建，8 个管线不变式测试 | 139 |
| `benchmarks/results/summary-stub-heldout.json` | 生成产物（2.7 KB） | — |
| `benchmarks/results/failures-stub-heldout.jsonl` | 生成产物，800 行失败（158 KB） | — |
| `benchmarks/results/summary-perfect-heldout.json` | 生成产物（2.8 KB） | — |
| `benchmarks/results/failures-perfect-heldout.jsonl` | 生成产物，0 字节（perfect 无失败） | — |

范围外一个文件都没碰：`src/zhclean/**`、`benchmarks/generate.py`、`benchmarks/clean|dirty/*.jsonl`、`pyproject.toml` 全部未改动（见 §3 收工 `git status`）。本单**没有 import `src/zhclean`**，规则接入留到后续 TASK。

## 2. 关键 diff 摘要

**normalize 注入点**（一行换一项即可接真实规则）：

```python
IMPLS: dict[str, Callable[[dict], str]] = {
    "stub": lambda row: row["value"],      # 恒原值 → 能红
    "perfect": lambda row: row["truth"],   # 直回真值 → 能绿（只验管线）
}
```

**口径**：`normalize(value) == truth` 逐字符相等，无空白宽容；默认 `--split heldout`。

**可复现**：summary 用 `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)`；failures 按输入顺序（FIELDS 固定序 × 文件行序）；写盘统一 utf-8 + LF。

**分组**：`by_field` / `by_perturbation` / `by_field_perturbation` 三张表都由同一份 `(field, perturbation)` 计数汇总而来，不存在三处各算一遍的漂移风险。

**产物命名**：`summary-<impl>-<split>.json` / `failures-<impl>-<split>.jsonl`。

## 3. 我亲跑过的自测（真实输出）

shell：Git Bash，工作目录 = 项目根。

**判据 1：测试全绿**

```
$ uv run --project . pytest tests/ -q
...............                                                          [100%]
15 passed in 1.92s
```
（15 个 = TASK-001 的 9 个 + 本单新增 8 个）

**判据 2：能红能绿**

```
$ python -m benchmarks.evaluate --impl stub; echo "exit=$?"
impl=stub split=heldout rows=800 failures=800
total 0/800 = 0.00%
field       abbrev    noise      sep    space     typo      all
person       0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
address      0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
phone        0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
company      0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
all          0.00%    0.00%    0.00%    0.00%    0.00%    0.00%
summary  -> summary-stub-heldout.json
failures -> failures-stub-heldout.jsonl
exit=0
```

```
$ python -m benchmarks.evaluate --impl perfect; echo "exit=$?"
impl=perfect split=heldout rows=800 failures=0
total 800/800 = 100.00%
field       abbrev    noise      sep    space     typo      all
person     100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
address    100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company    100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
all        100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
summary  -> summary-perfect-heldout.json
failures -> failures-perfect-heldout.jsonl
exit=0
```

**产物落盘**

```
$ git status --porcelain benchmarks/results/
?? benchmarks/results/failures-perfect-heldout.jsonl
?? benchmarks/results/failures-stub-heldout.jsonl
?? benchmarks/results/summary-perfect-heldout.json
?? benchmarks/results/summary-stub-heldout.json

$ ls -la benchmarks/results/
-rw-r--r-- 1 38628 197609      2 Oct  7 18:05 .gitkeep
-rw-r--r-- 1 38628 197609      0 Oct  7 21:51 failures-perfect-heldout.jsonl
-rw-r--r-- 1 38628 197609 158675 Oct  7 21:51 failures-stub-heldout.jsonl
-rw-r--r-- 1 38628 197609 2820 Oct  7 21:51 summary-perfect-heldout.json
-rw-r--r-- 1 38628 197609 2777 Oct  7 21:51 summary-stub-heldout.json
```
（4 个文件全是本单产物 + 原有 `.gitkeep`，没有多余文件）

**summary 内容核对**（stub）

```
$ python -c "import json;d=json.load(open('benchmarks/results/summary-stub-heldout.json',encoding='utf-8'));print(sorted(d));print(d['impl'],d['split'],d['total'])"
['by_field', 'by_field_perturbation', 'by_perturbation', 'impl', 'split', 'total']
stub heldout {'correct': 0, 'rate': 0.0, 'total': 800}
```

**failures 首行**

```
$ head -1 benchmarks/results/failures-stub-heldout.jsonl
{"id": "person-0001", "field": "person", "value": "范 童言", "normalized": "范 童言", "truth": "范童言", "perturbation": "space"}
```

**可复现（两次运行，临时目录）**

```
$ python -c "<跑两遍到两个 tmp 目录，比对 sha256>"
summary-stub-heldout.json          run1=413336205e0265f6 run2=413336205e0265f6 same=True
failures-stub-heldout.jsonl        run1=23c5a193d05bbaa2 run2=23c5a193d05bbaa2 same=True
summary-perfect-heldout.json       run1=d64e354da2a324a6 run2=d64e354da2a324a6 same=True
failures-perfect-heldout.jsonl     run1=e3b0c44298fc1c14 run2=e3b0c44298fc1c14 same=True
repo: {'summary-stub-heldout.json': '413336205e0265f6', 'failures-stub-heldout.jsonl': '23c5a193d05bbaa2', 'summary-perfect-heldout.json': 'd64e354da2a324a6', 'failures-perfect-heldout.jsonl': 'e3b0c44298fc1c14'}
```
（run1/run2 摘要一致；仓库内 4 个产物的 sha 与之一致 ⇒ 落盘产物就是当前管线的输出）

**收工全仓状态**

```
$ git status --porcelain -uall
?? benchmarks/evaluate.py
?? benchmarks/results/failures-perfect-heldout.jsonl
?? benchmarks/results/failures-stub-heldout.jsonl
?? benchmarks/results/summary-perfect-heldout.json
?? benchmarks/results/summary-stub-heldout.json
?? tests/test_evaluate.py
```
（`.handoff/outbox/RESULT-002.md` 是在这次 status 之后才写的，所以不在上面）

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | 评测管线测试全绿，`tests/test_evaluate.py` 至少断言 4 件事 | ✅ 15 passed（新增 8 个，覆盖全部 4 件 + 更多） | §3「判据 1」；对应关系见下表 |
| 2 | stub / perfect 两次 exit 0，summary+failures 齐，stub `rate == 0`、perfect `rate == 1.0`，results 只多本单产物 | ✅ 两次 exit 0；4 个产物齐；stub `{'correct': 0, 'rate': 0.0, 'total': 800}`；perfect `800/800 = 100.00%`；results 只有 4 个新文件 | §3「判据 2」 |

简报要求的 4 项断言 → 测试函数：

| 简报要求 | 测试函数 |
|---|---|
| stub → 规范化率 0% 且失败案例数 = heldout 行数 | `test_stub_is_red`（另断言失败行六个字段、`normalized == value != truth`） |
| perfect → 100% 且失败案例 0 条 | `test_perfect_is_green`（另断言 failures 文件存在且 0 字节） |
| by_field / by_perturbation 分组数字与手算一致 | `test_grouping_matches_hand_count`（手造 6 行 + 只修空格的注入实现，逐格手算）+ `test_grouping_shape_on_real_heldout`（真实 heldout 上每类 200/每扰动 160） |
| results 产物可复现（两次运行逐字节一致） | `test_results_byte_identical[stub]` / `[perfect]`（另断言无 CRLF、无 `\u` 转义） |
| （额外）默认只评 heldout，train/all 行数正确 | `test_split_filter`（heldout 800 / train 3200 / all 4000；heldout ∩ train = ∅） |

## 5. 遗留 / 不确定 / 需要拍板

- **【需拍板】real 注入项命名**：真实规则接入时的 `--impl` 名字我先没占（本单只有 `stub` / `perfect`）。建议下一单定为 `--impl rules`，在 `IMPLS` 里加一行 `lambda row: ...`。
- **【口径提醒】** `failures-*.jsonl` 里带 `value`（脏值）与 `truth`（真值），属于评测内部数据，但**公开失败案例时是有意公开**（task_plan 口径「失败案例公开」）。若将来要脱敏（人名/电话是真值语义），需要在写盘时加一个 `--redact` 开关，本单没做。
- **【申报·清单外新文件，都被 .gitignore 忽略】**解释器缓存：
  - `benchmarks/__pycache__/evaluate.cpython-312.pyc`、`evaluate.cpython-314.pyc`（本单新增；312 来自 uv 的 .venv，314 来自 PATH 上的 python）
  - `benchmarks/__pycache__/__init__.*.pyc`、`generate.*.pyc`（TASK-001 就有）
  - `tests/__pycache__/test_evaluate.cpython-312-pytest-9.1.1.pyc`（本单新增）
  - `tests/__pycache__/test_benchmark.*.pyc`、`test_package.*.pyc`（先前就有）
- **【申报·仓库外临时文件】** 自测可复现性时用 `tempfile.mkdtemp()` 建了 2 个目录（仓库外、未清理，`rm -rf` 是禁区）；pytest 自己也会在系统临时目录留目录。
- **【已知局限】**
  1. `failures-stub-heldout.jsonl` 158 KB / 800 行，全量公开够用；若后续要按扰动类型拆文件，本单没做（YAGNI）。
  2. 分母口径：`by_field` 每类 200 = 40 个 heldout id × 5 扰动；`by_perturbation` 每类 160 = 40 id × 4 类。与 TASK-001 的 40/类 heldout 完全对齐。
  3. 空格类的 `rate` 在真实规则下**不应**是 100%——`person-0001` 的 `"范 童言"` 去掉空格后等于 truth，但 `noise` 类的 `"姓名：范童言"` 需要去前缀才算对。这是评测口径本身，不是 bug。

## 6. 建议下一步

- 脑验收后入库本单 6 个文件（2 个代码 + 4 个产物）。
- 下一单（评测对象）：`src/zhclean` 里实现四类 normalize 的规则打底版，接入 `--impl rules`，跑 heldout 报**真实数**（task_plan 口径：≥95% 是目标不是承诺）。
- 规则版接入后，`benchmarks/results/` 会新增 `summary-rules-heldout.json`，可以用同一条 `pytest tests/` 做回归。

## 7. 下次接着做什么（写给下一轮的我）

- 做到哪了：TASK-002 已交付。评测管线在 `benchmarks/evaluate.py`，产物在 `benchmarks/results/`，管线测试在 `tests/test_evaluate.py`。本地 15 passed，未提交。
- 下一步第一件事：读 `.handoff/inbox/` 里最新的 TASK。若是「接真实规则」，第一件事是在 `benchmarks/evaluate.py` 的 `IMPLS` 字典里加 `"rules": lambda row: <调 src/zhclean 的入口>`（注意本单刻意没 import，加了就不在 TASK-002 边界内了，按新单走）。
- 要绕开的坑：
  1. 终端 GBK，看中文用 `PYTHONIOENCODING=utf-8`。
  2. `rm -rf` 是禁区，临时目录用 `tempfile`。
  3. `tests/test_evaluate.py` 里 `sys.path.insert(0, ROOT)` 是为了让 `import benchmarks` 不依赖 pytest 启动方式；别再删。
  4. `--out` 是相对路径时相对**当前工作目录**解析，自测请用绝对路径或临时目录，别把产物写到仓库外还不自知。

## 8. 脑侧结构化代码审查（2026-10-07，structured-code-review 口径）

范围: workspace（基线 cc18178）｜可审文件: 2 ｜已审: 2 ｜跳过: 0 ｜覆盖率: 2/2
排除项及理由: benchmarks/results/ 4 个产物（生成物，已按判据抽查内容与回执一致）；RESULT-002.md（交接件非代码）。

按严重度: critical 0, high 0, medium 1, low 2

| path | severity | category | content |
|---|---|---|---|
| benchmarks/evaluate.py | medium | maintainability | `load_dirty` 缺 dirty 文件时裸 traceback（无 FileNotFoundError 处理）。内部管线、输入由同仓生成器保证，风险低，可后续加友好报错 |
| benchmarks/evaluate.py | low | maintainability | `--out`/`--dirty-dir` 相对路径按 cwd 解析（手已在 §7 自提醒）；后续可改按仓库根解析或文档标注 |
| benchmarks/evaluate.py | low | maintainability | `FIELDS` 常量与 generate.py 重复定义两处；字段扩展时需同步两处（当前 4 类固定，可接受） |

审查结论：**无 critical/high，无阻塞问题**。测试断言有效（手造数据逐格手算 + 真实数据形状 + 能红能绿 + 逐字节可复现），管线设计干净（subprocess 走真实 CLI、tmp_path 不污染仓库）。两处拍板点脑已定：①真实规则注入名定 `--impl rules`；②失败案例含真值属「失败案例公开」口径有意为之，脱敏开关留发布前（记 findings）。

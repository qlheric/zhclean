# RESULT-008　对应 TASK-008

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | **完成**（判据 1 / 2 全过；改动文件 2 个，全在 `_Boundary:_` 内） |

## 0. 开工基线（TASK-008 §1.5）

```
$ git status --porcelain -uall
（空输出）
$ git rev-parse --short HEAD
6974165
```

基线洁净（HEAD = `6974165`）。完工后：

```
$ git status --porcelain -uall
 M src/zhclean/tools/dedupe.py
?? tests/test_dedupe.py
```

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/tools/dedupe.py` | 原为仅含 F/R/A/S 模块头的空壳 → 实现 `dedupe_exact` / `dedupe_fuzzy` / `dedupe` + `_UnionFind` + 阈值校验 + `_demo()` + `__main__` 入口；模块头 F/R/A/S 四行保留并补充 | +186 / −4（共 189 行） |
| `tests/test_dedupe.py` | **新建**。21 个测试函数，参数化展开后 **32 个用例** | +147 |

## 2. 关键 diff 摘要

```python
DEFAULT_THRESHOLD = 0.85

def _keys(rows):                       # 精确键 = (field, 规范值)
    return [(r["field"], normalize(r["value"], r["field"])) for r in rows]

def dedupe_exact(rows) -> list[list[dict]]: ...
def dedupe_fuzzy(rows, threshold=DEFAULT_THRESHOLD) -> list[list[dict]]:
    threshold = _check_threshold(threshold)       # [0,1]，拒 NaN / bool / 字符串
    ...                                            # 先跑精确级
    cutoff = threshold * 100                       # rapidfuzz 分数 0~100
    for items in by_field.values():                # 只在同一 field 内、不同规范值之间比
        ... if fuzz.ratio(va, vb, score_cutoff=cutoff) >= cutoff: uf.union(ia, ib)
def dedupe(rows, threshold=DEFAULT_THRESHOLD):     # 综合入口 = dedupe_fuzzy
    return dedupe_fuzzy(rows, threshold)
```

要点：
- **先规范化后去重**：所有比较都基于 `zhclean.tools.normalize.normalize(value, field)` 的结果；入参行对象原样放进组里，不改写 `value`。
- **确定性**：并查集合并时**小下标做根**，收组时按输入序遍历 ⇒ 组内保输入序、组间按首行序；rapidfuzz 无随机源。
- **相似度函数选 `fuzz.ratio`**（契约允许 ratio 或 token_sort_ratio）：中文值没有空格分词，token_sort 对它等于 ratio，故不引入额外语义。
- **阈值标度**：契约阈值是 [0,1]，rapidfuzz 返回 0~100，内部乘 100 比较；传 `85` 会被当作越界拒掉（有用例）。

## 3. 我亲跑过的自测（真实输出）

> 以下命令均在项目根、Windows bash 下原样跑。

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 27%]
........................................................................ [ 55%]
........................................................................ [ 82%]
.............................................                            [100%]
261 passed in 2.57s
```
（exit 0。261 = 原 229 + 新增 32。）

```
$ uv run --project . python -m zhclean.tools.dedupe
dedupe._demo: OK
```
（exit 0。）

```
$ uv run --project . python -m zhclean.tools.dedupe --demo
dedupe._demo: OK
```
（exit 0。TASK §2.5 写带 `--demo`、§3 判据写无参，两种都支持。）

```
$ PYTHONIOENCODING=utf-8 uv run --project . pytest tests/test_dedupe.py -q
................................                                         [100%]
32 passed in 0.07s
```

`_demo()` 共 7 组断言：精确合并、规范化后合并（「王 小明」与「王小明」同组）、阈值内合并（0.85）、阈值外不合（0.95）、空输入、确定性（两次结果相同且等于期望）、阈值越界被拒（-0.1 / 1.1 / NaN）。

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | `pytest tests/ -q` 全绿（原 229 + ≥12 新用例） | **通过**：`261 passed`（229 + 32） | §3 第 1 段 |
| 1a | ↳ 精确去重 | 通过 | `test_exact_merges_identical_values` / `test_exact_keeps_distinct_values_apart` |
| 1b | ↳ 语义阈值内 / 外 | 通过 | `test_fuzzy_merges_within_threshold` / `test_fuzzy_keeps_apart_outside_threshold`（前提校验 `test_fixture_pair_score_is_between_thresholds`） |
| 1c | ↳ 规范化后去重 | 通过 | `test_exact_merges_after_normalize`（3 种脏写法）/ `test_exact_phone_normalized_forms_merge` |
| 1d | ↳ 阈值边界 [0,1] 校验 | 通过 | `test_threshold_out_of_range_rejected`（5）/ `test_threshold_wrong_type_rejected`（3）/ `test_threshold_boundaries_accepted`（5）/ `test_threshold_one_equals_exact` / `test_threshold_zero_merges_whole_field` |
| 1e | ↳ 空输入 | 通过 | `test_empty_input` |
| 1f | ↳ 组内保序 | 通过 | `test_order_within_and_between_groups` |
| 1g | ↳ 确定性 | 通过 | `test_deterministic_across_calls` |
| 1h | ↳ `dedupe` 综合入口 | 通过 | `test_dedupe_is_exact_plus_fuzzy` / `test_default_threshold` |
| 2 | demo 自检输出 `dedupe._demo: OK`，exit 0 | **通过** | §3 第 2、3 段 |
| 3 | 边界：改动 ⊆ `_Boundary:_` | **通过**（见下表） | §0 完工后 status |

| 实际改动 | `_Boundary:_` 是否声明 | 判定 |
|---|---|---|
| `src/zhclean/tools/dedupe.py` | ✔ | 在界内 |
| `tests/test_dedupe.py`（新建） | ✔ | 在界内 |
| （无其他） | — | **无越界** |

## 5. 遗留 / 不确定 / 需要拍板

- **5-1 申报工具副产品**：跑 pytest / `-m` 产生或刷新了 `src/zhclean/tools/__pycache__/dedupe.cpython-312.pyc`、`tests/__pycache__/test_dedupe.cpython-312-pytest-9.1.1.pyc` 等缓存（均被 `.gitignore` 忽略，豁免清单第 1 条）。另 `src/zhclean.egg-info/` 为既有 uv 构建产物（被忽略），本单未主动生成。**无清单外新文件。**
- **5-2 两条口径是我在契约空白处定的，请脑拍板**：
  1. **只在同一 `field` 内比较**：契约没说跨字段是否比较。我判「不比」——person 的「华为」和 company 的「华为」不是重复。有用例 `test_same_value_different_field_not_merged` 锁住。
  2. **不按 `id` 强制合并**：契约 §2.5 写「同 id 多行当然同组」。我的理解是「同 id 的行规范化后相同，**自然**同组」，而**没有**把 id 当合并键。理由：TASK §6 说下一单 recall 口径以 id 为金标准，若实现里用 id 合并，recall 会被直接抬成 100%，评测失去意义。**若脑本意是「id 也是合并键」，改法是在 `_union_exact` 里多加一轮按 `id` union，约 4 行。**
- **5-3 未读的文件**：遵禁区，**未读** `benchmarks/generate.py`；也没读 `task_plan.md` / `findings.md`（本单用不到）。测试样例全部手写。
- **5-4 复杂度**：语义级是每 field 内 O(u²)（u = 不同规范值个数），有 `score_cutoff` 剪枝 + 同组跳过。heldout 800 行量级无压力；若后续上万行，可换 `rapidfuzz.process.cdist` 批量算。**本单未做**（无判据要求、收益未证实）。
- **5-5 非字符串 value**：normalize 对非字符串原样返回；可 hash 的照常参与精确合并，**不参与语义比较**；不可 hash 的（如 list）自成一组不报错。无判据要求，未写专门用例。

## 6. 建议下一步

- **6-1（下一单：评测接入）**：按 TASK §6 口径「同 id 的 clean + 5 条 dirty = 一个应合并组」算 pair recall。建议同时算 **precision**（不同 id 被误并的对数）——阈值 0.85 下 address 这类长串误并风险最高（同一街道不同门牌号 ratio 很容易 > 0.9），只看 recall 会鼓励把阈值调低。
- **6-2**：阈值的「不得用测试集调参」（模块头 S 行）建议在评测单里落成机制：阈值只在 dev split 上选，heldout 只跑一次。
- **6-3**：若脑在 5-2-2 拍「id 也合并」，建议做成显式参数（如 `merge_by_id: bool = False`），评测时关掉。

## 7. 下次接着做什么（写给下一轮的你）

- **做到哪了**：TASK-008 做完 —— `src/zhclean/tools/dedupe.py`（`dedupe_exact` / `dedupe_fuzzy` / `dedupe` + `_demo`）、`tests/test_dedupe.py`（32 用例）；全量 261 绿、demo OK。**未提交、未动 TASK 状态字段**。
- **下一步第一件事**：等脑验收（核 `git status` 两文件 → 置 TASK-008 `_Status:_` / `_Commit:_` → commit）；然后读 `.handoff/inbox/` 编号最大的 TASK（预期 TASK-009：dedupe 评测接入）。若被打回，先看本回执 §5-2 两条口径是不是打回原因。
- **要绕开的坑**：
  1. **阈值是 [0,1]，rapidfuzz 分数是 0~100**：评测接入时别把 `85` 直接传进 `dedupe`（会 ValueError）。
  2. **`dedupe` 不看 id**（§5-2-2）：评测拿 id 当金标准是对的，但别在 dedupe 里“顺手”用 id 合并。
  3. **地址长串误并**：相似地址（只差门牌号）在 0.85 下会合并，评测时注意看 precision，别只追 recall。
  4. 评测单仍然**不许读 `benchmarks/generate.py` 的词典常量**；跑命令一律 `uv run --project .` 前缀，中文输出加 `PYTHONIOENCODING=utf-8`。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 6974165）｜可审文件: 2 ｜已审: 2 ｜跳过: 0 ｜覆盖率: 2/2
（dedupe.py 189 行全文 + test_dedupe.py 32 用例）
按严重度: critical 0, high 0, medium 0, low 0

审查结论：**通过，零发现**。实现质量高：并查集小下标做根 + 迭代路径压缩（确定性、无递归风险）；`_check_threshold` 拒绝 bool/NaN/非数字/越界；`score_cutoff` 剪枝用法正确；不可 hash 值兜底；组内保序、组间首行序。测试 32 用例覆盖判据全部列举项 + 契约空白的两条口径（跨字段不并、id 不作合并键）都有用例锁住。

**两个契约点裁决（脑定，全部采纳手的口径）**：
1. **只在同一 field 内比较** ✓——不同字段值相同不算重复，数据模型正确。
2. **不按 id 强制合并** ✓——论证成立：id 是下一单评测的金标准，实现里用 id 合并等于评测作弊（recall 白送 100%）；「同 id 自然同组」已由 normalize 保证。**不需要** merge_by_id 参数。

另采纳手的两条建议并写进下一单：①评测同时算 **precision**（防只看 recall 鼓励调低阈值；地址长串误并风险手已预告）；②**阈值只在 train 上选、heldout 只跑一次**（防阈值调参污染留出集）。

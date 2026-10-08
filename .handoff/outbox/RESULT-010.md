# RESULT-010　对应 TASK-010

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | **完成**（判据 1 / 2 全过；改动文件 2 个，全在 `_Boundary:_` 内） |

## 0. 开工基线（TASK-010 §1.5）

```
$ git status --porcelain -uall
（空输出）
$ git rev-parse --short HEAD
af74fa1
```

完工后：

```
$ git status --porcelain -uall
 M src/zhclean/tools/audit.py
?? tests/test_audit.py
```

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/tools/audit.py` | 原为仅含 F/R/A/S 模块头的空壳 → 实现 `audit` / `apply` / `rollback` / `format_report` + `_demo()` + `__main__` 入口；模块头 F/R/A/S 保留并补充 | +218 / −3（共 222 行） |
| `tests/test_audit.py` | **新建**。25 个测试函数，参数化后 **30 用例** | 197 |

## 2. 关键 diff 摘要

```python
DEFAULT_MAX_CHANGES = 1000
_BANDS = (("0.9", CONF_STRUCTURAL, "structural"),
          ("0.7", CONF_INFER, "infer"),
          ("0.1", CONF_NONE, "none"))      # 其余 → "other"；档位常量取自 rules/common.py，不另写数字

def audit(rows, dry_run=True, max_changes=DEFAULT_MAX_CHANGES) -> dict
    # total/changed/unchanged/by_field/by_confidence/changes/truncated/dry_run
    # dry_run=False 时额外带 cleaned_rows + backup（= apply 结果），计数部分与 dry_run=True 完全相同
def apply(rows) -> (cleaned_rows, backup)
    # changed 行：value=规范值、_before=原值；unchanged 行原样（深拷贝）；入参不改
def _checksum(original, cleaned) -> str
    # sha256(json.dumps({"rows": 原行, "cleaned": 清洗后行}, sort_keys, 紧凑, ensure_ascii=False))
def rollback(cleaned_rows, backup) -> list[dict]
    # 结构不对 / checksum 对不上 → ValueError；通过则返回 backup["rows"] 的深拷贝
def format_report(report) -> str
```

要点：
- **「为什么」的落点**：`changes` 每条在契约五字段（id/field/before/after/confidence）外多一个 `reason`（structural / infer / none / other），由置信度档位推出。
- **checksum 同时绑定原行和清洗后行**：只哈希原行的话，「拿另一份自洽的备份」也能过校验，起不到契约里「防拿错备份」的作用。现在拿错备份、改过备份、改过清洗结果，三种情况都会被拒（各有用例）。
- **所有函数都不改入参、不写文件**：dry-run 的「不落盘」在函数层天然成立。落盘是 cli.py 的事（下一阶段 TASK）。

## 3. 我亲跑过的自测（真实输出）

> 项目根、Windows bash，命令原样可复制。

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 22%]
........................................................................ [ 45%]
........................................................................ [ 68%]
........................................................................ [ 91%]
...........................                                              [100%]
315 passed in 3.47s
```
（exit 0。315 = 原 285 + 新增 30。）

```
$ uv run --project . python -m zhclean.tools.audit
audit._demo: OK
```
（exit 0。）

```
$ uv run --project . python -m zhclean.tools.audit --demo
audit._demo: OK
```
（exit 0。TASK §2.5 写带 `--demo`、§3 判据写无参，两种都支持。）

`_demo()` 共 7 组断言：报告计数、dry-run 不改数据、apply 替换 + `_before`、rollback 恢复、checksum 拒绝（改过的清洗结果 / 别的备份）、空输入、确定性。

测试样例用到的三档置信度来自亲跑，不是猜的：

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -c "
import zhclean
for v,f in [('王 小明','person'),('王小明','person'),('138-1234-5678','phone'),('范同言','person'),('范童','person'),('13812345678','phone')]: print(repr(v),f,zhclean.normalize_with_confidence(v,f))"
'王 小明' person ('王小明', 0.9)
'王小明' person ('王小明', 0.1)
'138-1234-5678' phone ('13812345678', 0.9)
'范同言' person ('范童言', 0.7)
'范童' person ('范童', 0.1)
'13812345678' phone ('13812345678', 0.1)
```

人读报告样张：

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -c "
from zhclean.tools.audit import audit, format_report
rows=[{'id':1,'field':'person','value':'王 小明'},{'id':2,'field':'person','value':'范同言'},{'id':3,'field':'phone','value':'13812345678'}]
print(format_report(audit(rows)))"
清洗报告（dry-run 预览，未应用）
总行数 3　改动 2（66.67%）　未改 1
按字段：
  person    总     2  改     2  未改     0
  phone     总     1  改     0  未改     1
按置信度：
  0.9        1
  0.7        1
  0.1        1
  other      0
改动明细：列出 2 条
```

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | `pytest tests/ -q` 全绿（285 + ≥12） | **通过**：`315 passed`（+30） | §3 第 1 段 |
| 1a | ↳ 报告计数（changed/unchanged/by_field） | 通过 | `test_report_totals` / `test_report_by_field` / `test_report_by_confidence` / `test_changes_detail_only_changed_rows` / `test_non_string_value_counts_as_other_unchanged` |
| 1b | ↳ dry-run 不落盘不改数据 | 通过 | `test_dry_run_does_not_mutate_input` / `test_dry_run_writes_no_files`（chdir 到 tmp_path 后目录仍空）/ `test_non_dry_run_carries_apply_result_with_same_counts` |
| 1c | ↳ apply 替换 + `_before` 留存 | 通过 | `test_apply_replaces_and_keeps_before` / `test_apply_leaves_unchanged_rows_untouched` / `test_apply_does_not_mutate_input_and_backup_is_independent` / `test_backup_shape` |
| 1d | ↳ rollback 恢复原值 | 通过 | `test_rollback_restores_original` |
| 1e | ↳ **checksum 不匹配拒绝回滚** | 通过 | `test_rollback_rejects_tampered_cleaned_rows` / `test_rollback_rejects_tampered_backup` / `test_rollback_rejects_backup_from_another_apply` / `test_rollback_rejects_malformed_backup`（4） |
| 1f | ↳ max_changes 截断 | 通过 | `test_max_changes_truncates` / `test_max_changes_exact_fit_not_truncated` / `test_max_changes_default_and_zero` / `test_max_changes_invalid_rejected`（4） |
| 1g | ↳ 空输入 | 通过 | `test_empty_input` |
| 1h | ↳ 确定性 | 通过 | `test_deterministic`（报告与 apply 含 checksum 逐字相同） |
| 1i | ↳ （附加）format_report | 通过 | `test_format_report_contents` |
| 2 | demo 输出 `audit._demo: OK`，exit 0 | **通过** | §3 第 2、3 段 |
| 3 | 边界：改动 ⊆ `_Boundary:_` | **通过** | 下表 |

| 实际改动 | `_Boundary:_` 是否声明 | 判定 |
|---|---|---|
| `src/zhclean/tools/audit.py` | ✔ | 在界内 |
| `tests/test_audit.py`（新建） | ✔ | 在界内 |
| （无其他） | — | **无越界** |

## 5. 遗留 / 不确定 / 需要拍板

- **5-1 申报工具副产品**：`src/zhclean/tools/__pycache__/audit.cpython-312.pyc`、`tests/__pycache__/test_audit.cpython-312-pytest-9.1.1.pyc`（被 `.gitignore` 忽略，豁免清单第 1 条）。本单没跑评测，`benchmarks/results/` 未被触碰。**无清单外新文件。**
- **5-2 契约空白处我定的四条口径，请脑拍板**：
  1. **`dry_run=False` 的含义**：契约只定了 dry-run。我让 `dry_run=False` 时报告额外带 `cleaned_rows` 与 `backup`（等于调用 `apply`），**仍不写文件、不改入参**；计数部分两种模式逐字相同（有用例锁住）。
  2. **checksum 的覆盖面**：契约写 `{"rows": 原行列表, "checksum": sha256}`，没说哈希什么。我哈希的是「原行 + 清洗后行」的规范 JSON，理由见 §2 要点 2。若脑本意只哈希原行，改一行即可，但「拿错备份」就只能靠长度对不上来防了。
  3. **`changes` 多一个 `reason` 字段**，对应目标里的「为什么」。只增不减，契约五字段都在。
  4. **非字符串 value**：normalize 原样返回、置信度 0.0 ⇒ 计 unchanged、档位 `other`。
- **5-3 `_before` 键冲突**：若输入行本来就带 `_before` 键且该行被改，`apply` 会覆盖它。原值仍完整保存在 `backup["rows"]` 里，rollback 能恢复，数据不丢。没做专门处理，已写进 `apply` 的 docstring。
- **5-4 未读的文件**：遵禁区，**未读** `benchmarks/generate.py`。没读 `task_plan.md` / `findings.md`（本单用不到）。只读了 `tools/normalize.py` 和 `rules/__init__.py` 里的 `CONF_*` 导入，确认档位常量的出处。

## 6. 建议下一步

- **6-1（下一阶段 cli.py 串接）**：`zhclean audit` 子命令建议默认 dry-run，只打印 `format_report`。`--apply` 时把 `cleaned_rows` 写到输出文件，`backup` 写到旁边的 `*.backup.json`；`zhclean rollback <cleaned> <backup>` 走 `rollback()`。落盘只在 cli 层发生，audit 本体保持纯函数。
- **6-2**：`by_confidence` 键用字符串 `"0.9"/"0.7"/"0.1"/"other"`（JSON 友好）。cli 若输出 JSON 报告直接 `json.dumps` 即可，无需转换。
- **6-3**：TASK-007 审查留的 low 级建议（common 默认守卫表与字段自传表重复）仍未处理，属另一单。

## 7. 下次接着做什么（写给下一轮的你）

- **做到哪了**：TASK-010 做完。`src/zhclean/tools/audit.py` 实现了 `audit` / `apply` / `rollback` / `format_report` / `_demo`，新建 `tests/test_audit.py`（30 用例）。全量 315 绿，demo OK。M1 三工具（normalize / dedupe / audit）本体到此齐了。**未提交、未动 TASK 状态字段。**
- **下一步第一件事**：等脑验收。之后读 `.handoff/inbox/` 编号最大的 TASK，预期是 cli.py 串接三命令。若是，先读本回执 §6-1 的落盘分层建议。若被打回，先看 §5-2 四条口径是不是打回原因。
- **要绕开的坑**：
  1. **audit 本体不写文件**：dry-run 的「不落盘」靠这个保证。cli 串接时别把文件 IO 塞回 `audit.py`。
  2. **checksum 绑定了清洗后行**：调用方在 apply 之后、rollback 之前**不能改 cleaned_rows**，否则回滚会被拒。这是设计如此，不是 bug。
  3. 置信度档位常量从 `rules/common.py` 取（`CONF_STRUCTURAL/INFER/NONE`）。`CONF_TYPO` 已不存在（见 RESULT-007 §7）。
  4. 跑中文输出命令带 `PYTHONIOENCODING=utf-8`。判据命令一律 `uv run --project .` 前缀。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 af74fa1）｜可审文件: 2 ｜已审: 2 ｜跳过: 0 ｜覆盖率: 2/2
（audit.py 222 行全文 + test_audit.py 30 用例）
按严重度: critical 0, high 0, medium 0, low 1

| path | severity | category | content |
|---|---|---|---|
| src/zhclean/tools/audit.py | low | performance | `audit(dry_run=False)` 时 normalize 跑两遍（audit 循环一遍 + apply 一遍）；当前规模无碍，cli 串接大批量时可优化为单遍复用 |

审查结论：**通过**。纯函数分层正确（「不落盘」在函数层天然成立，文件 IO 留给 cli）；checksum 双绑定（原行+清洗后行）防住「拿错备份/改备份/改清洗结果」三种情况，论证到位；`_band` 用 isclose 防浮点、非数字归 other；`_before` 键冲突已申报且原值不丢（backup 里完整）。

**§5-2 四处口径裁决（脑定，全采纳）**：①dry_run=False 附 cleaned_rows+backup 但不写文件 ✓（纯函数分层）；②checksum 双绑定 ✓；③reason 字段 ✓（正是报告「为什么」的落点）；④非字符串计 unchanged + other ✓。

**里程碑**：M1 三工具（normalize / dedupe / audit）本体齐了。下一步 TASK-011（recall 攻坚）→ TASK-012（cli 串接）。

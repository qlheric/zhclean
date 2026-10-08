# RESULT-021　对应 TASK-021（**M2 定版单**）

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-09 |
| 结论 | **完成**（判据 1/2/3/4 全过；amount train = **100.00%**；**heldout 首次定版已跑并锁定**；老四类逐位复现 M1 定版） |

## 1. 改了哪些文件

| 文件 | 改了什么 | 行数 |
|---|---|---|
| `benchmarks/generate.py` | `gen_amount`：小数末位改取 `rng.randint(1, 9)`（杜绝尾随零）；其余不动 | +5 −1 |
| `benchmarks/clean/amount.jsonl` | 重生成（200 行） | 整文件 |
| `benchmarks/dirty/amount.jsonl` | 重生成（1000 行） | 整文件 |
| `tests/test_benchmark.py` | **未改**（原 `re.fullmatch(r"\d+(\.\d+)?元", ...)` 不变式对新值仍成立，无需同步） | 0 |

`git status --porcelain -uall` 共 3 项（全为 `M`），**逐条落在 `_Boundary:_` 内，零越界**；`src/zhclean/rules/**` **零改动**（规则层本单冻结）。

## 2. 关键 diff 摘要

```diff
     干净值**一律纯数字、不带千分位**（TASK-020 §2.5-A）：千分位只作为 `sep` 扰动出现，
     与规则侧闸门 `^\d+(\.\d+)?元$` 自洽 —— 否则两种干净形态会把单值 normalize 锁死。
+    **小数末位取 1–9**（TASK-021）：尾随零（`88982.0`）是冗余写法，万元记法经 float 后
+    必然丢失该位 ⇒ truth 与规范值逐字符不等。排除末位零后 amount 可无损回环。
     """
     intpart = rng.randint(1, 9_999_999)
     numeral = str(intpart)
     ndigits = rng.choice([0, 0, 1, 2])  # 多数整数，少数带小数
     if ndigits:
-        numeral += "." + "".join(str(rng.randint(0, 9)) for _ in range(ndigits))
+        digits = [str(rng.randint(0, 9)) for _ in range(ndigits - 1)]
+        digits.append(str(rng.randint(1, 9)))  # 末位 1–9：杜绝尾随零
+        numeral += "." + "".join(digits)
     return numeral + "元", [numeral, "元"]
```

> `ndigits` 恒为 1 或 2 ⇒ `ndigits - 1` ∈ {0, 1}，逻辑安全（`ndigits ≥ 1` 时才有小数）。

## 3. 我亲跑过的自测（真实输出）

### 3.1 §1.5 基线

```
$ git status --porcelain -uall
```

（**无输出** = 工作区干净；HEAD = `48fbb19`，TASK-020 已于 `4eff077` 通过、`1e56294` 派单。）

### 3.2 改生成器后先验老五类逐字节不变（写到**仓库外**再比，**未直接覆盖仓库**）

```
$ mkdir -p "C:/Users/38628/AppData/Local/Temp/zhclean_gen021"
$ uv run --project . python -m benchmarks.generate --seed 42 --per-field 200 --split-ratio 0.2 --out "C:/Users/38628/AppData/Local/Temp/zhclean_gen021" >/dev/null
$ for f in clean/person clean/address clean/phone clean/company clean/date dirty/person dirty/address dirty/phone dirty/company dirty/date; do if cmp -s "benchmarks/$f.jsonl" "C:/Users/38628/AppData/Local/Temp/zhclean_gen021/$f.jsonl"; then echo "SAME  $f"; else echo "DIFF  $f"; fi; done
SAME  clean/person
SAME  clean/address
SAME  clean/phone
SAME  clean/company
SAME  clean/date
SAME  dirty/person
SAME  dirty/address
SAME  dirty/phone
SAME  dirty/company
SAME  dirty/date
```

> 老五类 **10/10 逐字节相同**；amount 两文件 `DIFF`（预期）。确认无误后才 `cp` 回填。

### 3.3 回填前先核 train 回环（**只用 train 行**，守 heldout 纪律）

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json, re
import zhclean
T="C:/Users/38628/AppData/Local/Temp/zhclean_gen021"
dirty=[json.loads(l) for l in open(f"{T}/dirty/amount.jsonl",encoding="utf-8") if l.strip()]
tr=[r for r in dirty if r["split"]=="train"]
print("train 行数:", len(tr))
bad=[r for r in tr if zhclean.normalize(r["value"],"amount")!=r["truth"]]
print("train 失败数:", len(bad))
for r in bad[:5]: print("  [%s] %r -> %r (truth %r)" % (r["perturbation"], r["value"], zhclean.normalize(r["value"],"amount"), r["truth"]))
clean=[json.loads(l) for l in open(f"{T}/clean/amount.jsonl",encoding="utf-8") if l.strip()]
print("clean 条数:", len(clean), "| 尾随零条数:", sum(r["value"][:-1].endswith("0") and "." in r["value"][:-1] for r in clean))
print("样例:", [r["value"] for r in clean[:6]])
'
train 行数: 800
train 失败数: 0
clean 条数: 200 | 尾随零条数: 0
样例: ['3210394.28元', '571680元', '9103533.5元', '285351元', '8400518元', '5021890.25元']
```

### 3.4 判据 2 —— 老五类零漂移

```
$ git diff --name-only -- benchmarks/clean benchmarks/dirty
benchmarks/clean/amount.jsonl
benchmarks/dirty/amount.jsonl
```

**只有 amount 两个文件**；person/address/phone/company/date 十个文件零 diff（与 §3.2 的 `cmp` 互为印证）。

### 3.5 判据 1 —— 全量测试

```
$ uv run --project . pytest tests/ -q --tb=short
........................................................................ [ 12%]
........................................................................ [ 25%]
........................................................................ [ 38%]
........................................................................ [ 51%]
........................................................................ [ 63%]
........................................................................ [ 76%]
........................................................................ [ 89%]
............................................................             [100%]
564 passed in 5.70s
```

**564 passed / 0 failed**。

### 3.6 判据 3 —— train 复跑（amount 修复生效）

```
$ uv run --project . python -m benchmarks.evaluate --impl rules --split train
impl=rules split=train rows=4800 failures=557
total 4243/4800 = 88.40%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.62%   72.12%
address     55.62%  100.00%  100.00%  100.00%   99.38%   91.00%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      7.50%  100.00%  100.00%  100.00%  100.00%   81.50%
amount     100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
date        28.75%  100.00%  100.00%  100.00%  100.00%   85.75%
all         48.65%  100.00%  100.00%  100.00%   93.33%   88.40%
```

**amount = 100.00%**（≫ 判据线 99.5%；TASK-020 的 8 行残差已清零）；**date 85.75% 与老四类逐位不变**；总分 88.23% → 88.40%。

### 3.7 判据 4 —— **heldout 首次定版跑（本单唯一一次）**

```
$ uv run --project . python -m benchmarks.evaluate --impl rules
impl=rules split=heldout rows=1200 failures=145
total 1055/1200 = 87.92%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.00%   72.00%
address     52.50%  100.00%  100.00%  100.00%  100.00%   90.50%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      5.00%  100.00%  100.00%  100.00%  100.00%   81.00%
amount     100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
date        20.00%  100.00%  100.00%  100.00%  100.00%   84.00%
all         46.25%  100.00%  100.00%  100.00%   93.33%   87.92%
summary  -> summary-rules-heldout.json
failures -> failures-rules-heldout.jsonl
```

落盘核对：

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json
s=json.load(open("benchmarks/results/summary-rules-heldout.json",encoding="utf-8"))
print("impl=%s split=%s" % (s["impl"], s["split"]))
print("total:", s["total"])
for f,v in s["by_field"].items(): print("  %-8s %s" % (f, v))
'
impl=rules split=heldout
total: {'correct': 1055, 'rate': 0.879167, 'total': 1200}
  address  {'correct': 181, 'rate': 0.905, 'total': 200}
  amount   {'correct': 200, 'rate': 1.0, 'total': 200}
  company  {'correct': 162, 'rate': 0.81, 'total': 200}
  date     {'correct': 168, 'rate': 0.84, 'total': 200}
  person   {'correct': 144, 'rate': 0.72, 'total': 200}
  phone    {'correct': 200, 'rate': 1.0, 'total': 200}
```

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | `pytest tests/ -q` 全绿（564 / 0） | **过**：564 passed / 0 failed | §3.5 |
| 2 | `git diff --name-only -- benchmarks/clean benchmarks/dirty` 仅 amount 两文件 | **过**：仅 2 个 amount 文件 | §3.4（+ §3.2 cmp 10/10） |
| 3 | train 复跑：exit 0；amount ≥ 99.5%；date 与老四类逐位不变 | **过**：exit 0；amount **100.00%**；date 85.75% 不变；老四类逐位不变 | §3.6 |
| 4 | heldout 定版跑：exit 0；summary 落盘；六类如实报 | **过**：exit 0；`summary-rules-heldout.json` 已落盘 | §3.7 |

## 5. M2 定版数字（锁定）

| 字段 | train | **heldout（定版）** | 对照 M1 定版 |
|---|---|---|---|
| person | 72.12% | **72.00%** | 72.00 ✅ 逐位复现 |
| address | 91.00% | **90.50%** | 90.50 ✅ 逐位复现 |
| phone | 100.00% | **100.00%** | 100.00 ✅ 逐位复现 |
| company | 81.50% | **81.00%** | 81.00 ✅ 逐位复现 |
| amount | 100.00% | **100.00%** | M2 首次定版 |
| date | 85.75% | **84.00%** | M2 首次定版 |
| **总** | 88.40% | **87.92%**（1055/1200） | — |

老四类**四行逐位复现 M1 定版** ⇒ 新增 amount/date + 生成器口径修正**对老字段零影响**。

## 6. 遗留 / 不确定 / 需要拍板

### a（工具副产品申报，豁免清单第 1 条）

- 仓库外临时目录 `C:/Users/38628/AppData/Local/Temp/zhclean_gen021/`：§3.2/§3.3 的「先比再回填」产物，**非业务文件、不在仓库内**。
- `benchmarks/results/summary-rules-heldout.json`、`failures-rules-heldout.jsonl`：判据 4 定版产物，在 `_Boundary:_` 内（已被 `.gitignore` 忽略、不入库）。
- `benchmarks/results/` 下另有既存产物（`dedupe-*`、`sample.*`、`summary-stub/perfect-*` 等），**非本单产生**，仅列及以免误认。
- `__pycache__/`、`.pytest_cache/`：解释器/工具自动产生，已忽略。
- **仓库内无清单外新文件**（`git status -uall` 仅 3 项 `M`）。

### b（如实提示，非缺陷）heldout 的 abbrev 列仍低（person 0.00 / company 5.00 / date 20.00）

- person/company 的 abbrev 是**老账**（M1 起就低），非 M2 引入。
- date abbrev 20.00%（heldout 40 行里 8 行可回收）——heldout 的 abbrev 采样与 train（28.75%）不同属正常，**均未超出「缺年/年月不可恢复」的口径**。
- amount abbrev **100.00%**（heldout）⇒ TASK-021 的尾零修复在留出集上同样成立。

### c（口径提示）M2 定版数字已锁定，后续任何规则/数据改动都会使本表作废

- 本表（§5）为 M2 定版基线；若再动 `src/zhclean/rules/**` 或任一数据文件，**须重跑 heldout 并更新定版表**（属新 TASK）。

## 7. 建议下一步

1. **TASK-022（脑已在 TASK-021 §6 预告）**：更新 README / `findings.md` 台账 —— 把 §5 的 M2 定版表落进文档，并写 failures 说明。
2. 定版数字以 heldout 为准（train 只作调参参照）：**总 87.92%，六类 72.00 / 90.50 / 100.00 / 81.00 / 100.00 / 84.00**。
3. 老账（person/company abbrev、person typo 60%）若要提分，应**单开规则单**，且须重跑 heldout 更新定版表。

## 8. 下次接着做什么（写给「下一轮的你」）

- **做到哪了**：TASK-021（M2 定版单）完成。改动仅 3 个文件：`benchmarks/generate.py`（`gen_amount` 小数末位 1–9）、重生成 amount 两文件。**amount train 100.00%**；**heldout 已首跑定版**（总 87.92%，六类见 §5）。回执即本文件。
- **下一步第一件事**：等脑验收；随后按预告做 **TASK-022**（README/findings 台账写入 §5 定版表 + failures 文档）。
- **要绕开的坑**：
  1. **heldout 已定版，不要再跑**（除脑派「重定版」单）；本单 §3.7 是唯一一次。
  2. **重生成数据仍要先出仓库外再 `cmp` 回填**（`mkdir -p <全新名字>`，禁止 `rm -rf`）。
  3. **`src/zhclean/rules/**` 本单冻结**；任何规则改动 = 定版表作废，须重跑 heldout。
  4. `ndigits` 只有 1/2，`ndigits - 1` 不会为负；若将来放开小数位，注意此式仍成立。

## 9. 脑侧验收（2026-10-09）

**判据亲跑（四全过）**：①564 passed 零失败 ✓；②重生成后只有 amount 两文件有 diff（老五类 10/10 cmp 相同互为印证）✓；③train：**amount 100.00%**（8 行残差清零）、date 85.75% 与老四类逐位不变、总盘 88.40% ✓；④**heldout 首次定版跑**：exit 0、summary 落盘、总 87.92%（1055/1200）——person 72.00 / address 90.50 / phone 100.00 / company 81.00 / amount 100.00 / date 84.00，**老四类逐位复现 M1 定版**（M2 改动对老字段零影响）✓。边界零越界（3 手侧文件，规则层冻结）。

**§6 处置（脑定）**：a（副产品申报）符合豁免清单，仓库内无清单外文件；b（heldout abbrev 列低）如实记录——date 20.00% 未超「缺年/年月不可恢复」口径，person/company 是老账；c（定版数字锁定）成立——后续任何规则/数据改动须重跑 heldout 重定版（新 TASK）。

审查结论：**通过**。「先出仓库外再 cmp 回填」的流程与 train 回环预检（§3.3）是定版单的正确姿势；尾零修复只动了生成器一处、规则零改动。

**里程碑：M2 定版完成——heldout 六类总盘 87.92%；amount 双 100%（train + heldout）；date 84.00%（顶口径天花板）；老四类逐位复现。数字已锁定，下一步 TASK-022 落文档。**

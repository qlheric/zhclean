# RESULT-020　对应 TASK-020

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-09 |
| 结论 | **完成**（A / B / C 三项全修；判据 1/2/3 全过；amount 40.88% → **99.00%**；老五类零漂移） |

## 1. 改了哪些文件

| 文件 | 改了什么 | 行数 |
|---|---|---|
| `benchmarks/generate.py` | **A**：`gen_amount` 删掉 `if rng.random() < 0.5: numeral = _group(numeral)` 千分位分支（干净值一律纯数字）；**B**：`_wan` 由 `f"{n/10000:.4f}".rstrip("0").rstrip(".")` 改为 `f"{n/10000:.10g}"` | +9 −4 |
| `benchmarks/clean/amount.jsonl` | 重生成（200 行） | 整文件 |
| `benchmarks/dirty/amount.jsonl` | 重生成（1000 行） | 整文件 |
| `tests/test_evaluate.py` | **C**：`FIELDS = ev.FIELDS`、`N_FIELDS = len(FIELDS)`，4 处硬编码 `×4` 全部改为 `×N_FIELDS`（根治） | +5 −3 |
| `tests/test_benchmark.py` | 同步 amount 不变式：从「可能带千分位 / 去掉逗号后能 parse」收紧为 `re.fullmatch(r"\d+(\.\d+)?元", ...)` | +2 −3 |

`git status --porcelain -uall` 共 5 项（全为 `M`），**逐条落在 `_Boundary:_` 内，零越界**；`src/zhclean/rules/**` 未被触碰。

## 2. 关键 diff 摘要

**A — `gen_amount`（删千分位分支）**

```diff
 def gen_amount(rng: random.Random) -> tuple[str, list[str]]:
-    """生成金额：数值 + 「元」；形态含整数 / 小数(1–2 位) / 千分位。返回 (值, 结构段)。"""
+    """生成金额：数值 + 「元」；形态含整数 / 小数(1–2 位)。返回 (值, 结构段)。
+
+    干净值**一律纯数字、不带千分位**（TASK-020 §2.5-A）：千分位只作为 `sep` 扰动出现，
+    与规则侧闸门 `^\d+(\.\d+)?元$` 自洽 —— 否则两种干净形态会把单值 normalize 锁死。
+    """
     intpart = rng.randint(1, 9_999_999)
     numeral = str(intpart)
     ndigits = rng.choice([0, 0, 1, 2])  # 多数整数，少数带小数
     if ndigits:
         numeral += "." + "".join(str(rng.randint(0, 9)) for _ in range(ndigits))
-    if rng.random() < 0.5:
-        numeral = _group(numeral)       # 一半带千分位（干净值基准形态之一）
     return numeral + "元", [numeral, "元"]
```

> `_group()` 本身**保留**（`perturb_amount` 的 `sep` 候选仍在用）；本单只去掉干净值的使用。

**B — `_wan`（去截断）**

```diff
-    n = float(numeral.replace(",", ""))
-    return f"{n / 10000:.4f}".rstrip("0").rstrip(".") + "万元"
+    n = float(numeral.replace(",", ""))
+    return f"{n / 10000:.10g}" + "万元"
```

（`%g` 自带去尾零；数值 ≥ 1 元 ⇒ 结果 ≥ 0.0001，不会落进科学计数法。规则侧 `_expand_wan` 未动。）

**C — `tests/test_evaluate.py`（字段数派生）**

```diff
-FIELDS = ("person", "address", "phone", "company")
+# 字段集从评测管线**派生**（TASK-020 §2.5-C）：以后 evaluate.FIELDS 增字段，本文件自动适配，
+# 不再因硬编码的 4 被打红。
+FIELDS = ev.FIELDS
+N_FIELDS = len(FIELDS)
 PERTURBATIONS = ("abbrev", "noise", "sep", "space", "typo")
-HELDOUT_ROWS = 40 * 5 * 4  # 每类 40 个 heldout id × 5 扰动 × 4 类
+HELDOUT_ROWS = 40 * 5 * N_FIELDS
...
-    assert all(v["total"] == 40 * 4 for v in s["by_perturbation"].values())
+    assert all(v["total"] == 40 * N_FIELDS for v in s["by_perturbation"].values())
...
-    assert _summary(tmp_path, "stub", "train")["total"]["total"] == 160 * 5 * 4
-    assert _summary(tmp_path, "stub", "all")["total"]["total"] == 200 * 5 * 4
+    assert _summary(tmp_path, "stub", "train")["total"]["total"] == 160 * 5 * N_FIELDS
+    assert _summary(tmp_path, "stub", "all")["total"]["total"] == 200 * 5 * N_FIELDS
```

**`tests/test_benchmark.py`（amount 不变式收紧）**

```diff
-    # amount：干净值 = 数值 + 「元」（可能带千分位 / 小数），去掉分隔符后须能解析为数字
+    # amount：干净值 = 纯数字 + 「元」（TASK-020 起**不带千分位**，千分位只留在 sep 扰动里）
     for r in data["amount"]["clean"]:
-        assert r["value"].endswith("元"), f"amount 干净值不以「元」结尾：{r['value']!r}"
-        float(r["value"][:-1].replace(",", ""))  # 解析失败会抛 ValueError
+        assert re.fullmatch(r"\d+(\.\d+)?元", r["value"]), \
+            f"amount 干净值非「纯数字+元」：{r['value']!r}"
```

## 3. 我亲跑过的自测（真实输出）

### 3.1 §1.5 基线（完工后工作区状态）

```
$ git status --porcelain -uall
 M benchmarks/clean/amount.jsonl
 M benchmarks/dirty/amount.jsonl
 M benchmarks/generate.py
 M tests/test_benchmark.py
 M tests/test_evaluate.py
```

> 开工时工作区**干净**（TASK-019 已于 `938dd6a` 入库，HEAD = `24ad799`）。
> 以上 5 项即本单全部改动，与 §1 一致、与 `_Boundary:_` 逐条比对无越界。

### 3.2 生成器改后，先验老五类逐字节不变（写到**仓库外**临时目录再比）

```
$ mkdir -p "C:/Users/38628/AppData/Local/Temp/zhclean_gen020"
$ uv run --project . python -m benchmarks.generate --seed 42 --per-field 200 --split-ratio 0.2 --out "C:/Users/38628/AppData/Local/Temp/zhclean_gen020"
seed=42 per_field=200 split_ratio=0.2
out=C:\Users\38628\AppData\Local\Temp\zhclean_gen020
field    split      clean  dirty
person   train        160    800
person   heldout       40    200
address  train        160    800
address  heldout       40    200
phone    train        160    800
phone    heldout       40    200
company  train        160    800
company  heldout       40    200
amount   train        160    800
amount   heldout       40    200
date     train        160    800
date     heldout       40    200
$ for f in clean/person clean/address clean/phone clean/company clean/date dirty/person dirty/address dirty/phone dirty/company dirty/date; do if cmp -s "benchmarks/$f.jsonl" "C:/Users/38628/AppData/Local/Temp/zhclean_gen020/$f.jsonl"; then echo "SAME  $f"; else echo "DIFF  $f"; fi; done
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

> 老五类 **10/10 逐字节相同**（`cmp` 无输出即相同，上面打印的是判定结果行）；
> amount 两文件 `DIFF`（预期）。确认无误后才 `cp` 回填仓库。

### 3.3 判据 1 —— 全量测试（**4 红已消除**）

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
564 passed in 5.92s
```

**全绿 0 失败**：TASK-019 挂账的 4 红（`test_evaluate.py` 硬编码 4 字段）随 C 的派生改造消失；
总数 564 = TASK-019 的 560 + 本单无新增用例（C 为改造、非新增）。

### 3.4 判据 2 —— train 实测（amount 修复生效 + 零回归）

```
$ uv run --project . python -m benchmarks.evaluate --impl rules --split train
impl=rules split=train rows=4800 failures=565
total 4235/4800 = 88.23%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.62%   72.12%
address     55.62%  100.00%  100.00%  100.00%   99.38%   91.00%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      7.50%  100.00%  100.00%  100.00%  100.00%   81.50%
amount      95.00%  100.00%  100.00%  100.00%  100.00%   99.00%
date        28.75%  100.00%  100.00%  100.00%  100.00%   85.75%
all         47.81%  100.00%  100.00%  100.00%   93.33%   88.23%
summary  -> summary-rules-train.json
failures -> failures-rules-train.jsonl
```

- **amount 40.88% → 99.00%**（≫ 判据线 85%）；四列 space/noise/sep/typo 全部 **100.00%**。
- **date = 85.75% 不变**；**老四类逐位不变**（person 72.12 / address 91.00 / phone 100.00 / company 81.50）⇒ **零回归**。
- 总分 78.54% → **88.23%**（+9.69 点）。
- 实际比 §3.4 的预测 89.75% 更高，原因见 §5-a。

### 3.5 判据 3 —— 老五类数据零漂移

```
$ git diff --stat -- benchmarks/clean benchmarks/dirty
 benchmarks/clean/amount.jsonl |  398 ++++----
 benchmarks/dirty/amount.jsonl | 2000 ++++++++++++++++++++---------------------
 2 files changed, 1199 insertions(+), 1199 deletions(-)
```

**只有 amount 两个文件有差异**；person/address/phone/company/date 十个文件**零 diff**（与 3.2 的 `cmp` 结果互为印证）。

### 3.6 amount 残差定位（8 例，供 §5）

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json
rows=[json.loads(l) for l in open("benchmarks/results/failures-rules-train.jsonl",encoding="utf-8") if l.strip()]
am=[r for r in rows if r["field"]=="amount"]
print("amount train 失败数:", len(am))
for r in am:
    print("  [%s] %r -> %r (truth %r)" % (r["perturbation"], r["value"], r["normalized"], r["truth"]))
'
amount train 失败数: 8
  [abbrev] '204.44818万元' -> '2044481.8元' (truth '2044481.80元')
  [abbrev] '904.69685万元' -> '9046968.5元' (truth '9046968.50元')
  [abbrev] '610.7249万元' -> '6107249元' (truth '6107249.0元')
  [abbrev] '715.61536万元' -> '7156153.6元' (truth '7156153.60元')
  [abbrev] '592.6444万元' -> '5926444元' (truth '5926444.0元')
  [abbrev] '8.8982万元' -> '88982元' (truth '88982.0元')
  [abbrev] '139.6896万元' -> '1396896元' (truth '1396896.0元')
  [abbrev] '550.66685万元' -> '5506668.5元' (truth '5506668.50元')
```

8 例**全是同一类**：干净值带**冗余尾随零**（`X.80` / `X.0`），abbrev 转万元再还原后尾随零丢失（数值相同）。规则侧已冻结 ⇒ 本单无法消除。

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | `pytest tests/ -q` **全绿 0 失败**（4 红消除） | **过**：564 passed / 0 failed | §3.3 |
| 2 | `evaluate --impl rules --split train`：exit 0；amount ≥ 85%；date 85.75% 不变；老四类逐位不变 | **过**：exit 0；amount **99.00%**；date **85.75%**；老四类逐位不变 | §3.4 |
| 3 | 重生成后仅 amount 两文件有差异，其余零 diff | **过**：`git diff --stat` 仅 2 个 amount 文件 | §3.5（+ §3.2 的 cmp 10/10） |

## 5. 遗留 / 不确定 / 需要拍板

### a（口径说明，非缺陷）实测 99.00% 高于 TASK 预测的 89.75%

- TASK §3.4 的 89.75% 是**在旧数据上**算的：当时真值仍带千分位，用的是「把真值逗号去掉再比」的近似，
  且旧 `_wan` 的 `.4f` 截断还在扣分。A + B 落地后这两个扣分源头都没了，故实测更高。
- 结论：**预测与实际不矛盾**，是修复面比预测时假设的更干净。

### b（TASK-018 遗留，**本单无法修**）干净值带冗余尾随零 ⇒ abbrev 有 8/800 残差

- 现象见 §3.6：全部是 `X.80元` → `X.8元`、`X.0元` → `X元`，**数值相同、仅丢冗余尾随零**。
- 根因在**生成器**：`gen_amount` 允许小数末位为 0（`numeral += "." + 随机位`），产生 `2044481.80` 这种非规范写法；
  经 `_wan` 走 float 后该冗余位必然丢失。
- **修法（需新 TASK，属改生成器口径）**：`gen_amount` 生成小数后加一行
  `numeral = numeral.rstrip("0").rstrip(".") if "." in numeral else numeral`（或直接禁止小数末位为 0）。
- **本单为何没做**：TASK §2.5-A 把生成器改动**明确限定为「gen_amount 去千分位分支 + `_wan` 去截断」**，
  尾随零归一不在其列。按手脑契约 v1 §4「有更好的做法，写进回执的建议下一步，不要当场自己改」，此处只报不做。
- 影响：amount train 上限 99.00%（残 1.00%）。**不影响判据 2（99% ≫ 85%）**。

### c（工具副产品申报，豁免清单第 1 条）

- 仓库外临时目录 `C:/Users/38628/AppData/Local/Temp/zhclean_gen020/`：§3.2 用来做「先比再回填」的生成产物，**非业务文件、不在仓库内**。
- `benchmarks/results/summary-rules-train.json`、`failures-rules-train.jsonl`：判据 2 产物，在 `_Boundary:_` 内（已被 `.gitignore` 忽略）。
- `__pycache__/`、`.pytest_cache/`：解释器/工具自动产生，已忽略。
- **仓库内无清单外新文件**（`git status -uall` 仅 5 项 M）。

## 6. 建议下一步

1. **（承接 §5-b）单开一单**：`gen_amount` 小数尾随零归一 ⇒ amount 上限 99.00% → 100%。
   若同时想消掉 `sep` 的「乱插逗号」噪声候选，可一并评估。
2. **可进定版单**：amount/date 现已稳定（amount 99.00%、date 85.75%），且本次是**评测基准口径修正**，
   适合作为定版前最后一次基准变更；**定版单跑一次 heldout**（本单按禁区未跑）。
3. **C 的收益是长期性的**：以后 `evaluate.FIELDS` 再增字段（如身份证/邮箱），`test_evaluate.py` 自动适配，不会再出现 TASK-019 那种「改 FIELDS 必红范围外测试」的冲突。
4. person 的 abbrev（0.00%）与 company 的 abbrev（7.50%）仍是老账，非本单范围。

## 7. 下次接着做什么（写给「下一轮的你」）

- **做到哪了**：TASK-020 三项全修完并自测通过（判据 1/2/3 全过）。改动：`benchmarks/generate.py`（`gen_amount` 去千分位分支、`_wan` 改 `:.10g`）、重生成 amount 两文件、`tests/test_evaluate.py`（字段数从 `ev.FIELDS` 派生）、`tests/test_benchmark.py`（amount 不变式收紧）。amount train **40.88% → 99.00%**，date 与老四类零漂移。回执即本文件。
- **下一步第一件事**：等脑验收；随后按 §6 决定是否开「小数尾随零归一」一单，或直接进**定版单跑 heldout**。
- **要绕开的坑**：
  1. **重生成数据别直接覆盖仓库**：先生成到**仓库外**临时目录、`cmp` 老字段确认逐字节不变，再 `cp` 回填（本单流程，见 §3.2）。
  2. **`rm -rf` 是禁区**；临时目录用 `mkdir -p <全新名字>`（建在仓库外）。
  3. **规则侧 `src/zhclean/rules/**` 本单是禁区** —— amount 分数不够先怀疑**生成器/数据**，别去改规则。
  4. **改 `evaluate.py` 的 FIELDS 前先看 `test_evaluate.py` 是否已派生**（本单已改成派生，以后安全）。
  5. heldout **仍未跑**（截至本单结束），定版单再跑。

## 8. 脑侧验收（2026-10-09）

**判据亲跑**：①564 passed **零失败**（4 红消除，C 根治生效）✓；②train 六类总盘 88.23%——**amount 40.88% → 99.00%**（abbrev 95.00% / 其余四列 100%）、date 85.75% 不变、老四类逐位零回归 ✓；③重生成后**只有 amount 两个文件有 diff**，person/address/phone/company/date 五个干净/脏集零漂移 ✓。边界零越界（5 手侧文件，未碰 rules）。

**§6 裁决（脑定）**：amount 剩余 1%（train 8 行，全在 abbrev）= 「小数尾随零」口径问题——truth「88982.0元」vs 规范「88982元」逐字符不等（干净集生成的 .0 尾零）。**采纳修 a（生成器去尾零，而非改规则保留尾零）**：`gen_amount` 小数末位排除 0 → 重生成 amount → 预期 amount train 100%。与 **heldout 定版首跑**合成 TASK-021（amount/date 首次定版；老四类应复现 M1 定版数）。

审查结论：**通过**。C 的派生改造根治了「改 FIELDS 必红范围外测试」一类冲突；A/B 改动极小且全部指向生成器侧，规则零改动——「数据问题别怪规则」的分层判断正确。

**里程碑：M2 六类 train 实测——amount 99.00% / date 85.75%（顶天花板）/ 老四类零回归；总盘 88.23%。**

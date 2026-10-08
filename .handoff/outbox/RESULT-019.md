# RESULT-019　对应 TASK-019

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-09 |
| 结论 | **部分完成**（判据 2 过；判据 1 有 4 红，红点全在本单边界之外的 `tests/test_evaluate.py`，见 §5-C；老大已裁定「守边界、留红、上报」） |

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/rules/amount.py` | 由桩改为完整规则：结构清洗（去空白/去千分位逗号/去噪声）+ 万元展开 + 数字形近修复 + 闸门 `^\d+(\.\d+)?元$`，四档置信度 | +104 |
| `src/zhclean/rules/date.py` | 由桩改为完整规则：去空白 + 分隔符归一（`/ . ／ ．`→`-`）+ 去噪声 + 补缺零 + 数字形近修复，闸门 = ISO 形态 + 年 1970–2026 / 月 01–12 / 日 01–31 | +106 |
| `src/zhclean/rules/__init__.py` | DISPATCH 注册 `amount`/`date`；文档串改为「六类字段已全部注册」 | +6 −2 |
| `benchmarks/evaluate.py` | **仅 FIELDS**：`("person","address","phone","company")` → 追加 `"amount","date"` | +1 −1 |
| `tests/test_amount.py` | 新建单测（space/sep/noise/abbrev/typo/闸门/0.95档/置信度区间/注册表/六字段回归护栏） | 新建 131 行 |
| `tests/test_date.py` | 新建单测（同上五类 + 不可恢复 abbrev 不猜 + 范围闸门） | 新建 137 行 |

`git status --porcelain -uall` 共产出 6 项：4 改 + 2 新，**无一超出 `_Boundary:_`**（`tests/test_evaluate.py` 未被触碰，见 §5-C）。

## 2. 关键 diff 摘要

**`benchmarks/evaluate.py`（唯一改动，逐字如下）**

```diff
-FIELDS = ("person", "address", "phone", "company")
+FIELDS = ("person", "address", "phone", "company", "amount", "date")
```

**`src/zhclean/rules/__init__.py`**

```diff
-from .address import normalize_address
+from .address import normalize_address
+from .amount import normalize_amount
 from .common import CONF_NONE
 from .company import normalize_company
+from .date import normalize_date
@@ DISPATCH @@
     "company": normalize_company,
+    "amount": normalize_amount,
+    "date": normalize_date,
```

**`rules/amount.py` 主入口（骨架）**

```python
def normalize_amount(value):
    if not isinstance(value, str) or not value: return value, CONF_NONE
    out, noise_hit = strip_noise(value)
    ws_hit = _WS_RE.search(out) is not None; out = _WS_RE.sub("", out)
    comma_hit = _COMMA_RE.search(out) is not None; out = _COMMA_RE.sub("", out)
    if (noise_hit or ws_hit or comma_hit) and _AMOUNT_RE.match(out):      # 结构层
        return out, CONF_STRUCTURAL
    expanded, wan_hit = _expand_wan(out)                                  # 万元 ×10000
    fixed, typo_hit = apply_table(expanded, CONFUSABLE_TO_DIGIT)          # 形近修复
    if typo_hit and _AMOUNT_RE.match(fixed): return fixed, CONF_INFER
    if wan_hit and _AMOUNT_RE.match(expanded): return expanded, CONF_INFER
    if _AMOUNT_RE.match(value): return value, CONF_CLEAN
    return value, CONF_NONE
_AMOUNT_RE = re.compile(r"^\d+(\.\d+)?元$")   # 闸门：纯数字 + 元，无千分位、无多余字符
```

**`rules/date.py` 主入口（骨架）**

```python
def normalize_date(value):
    ...
    out, noise_hit = strip_noise(value)
    out, sep_hit = _unify_sep(out)                       # / . ／ ．→ -
    ws_hit = _WS_RE.search(out) is not None; out = _WS_RE.sub("", out)
    canon = _canon_date(out)                             # 补缺零 + 范围校验
    if canon is not None and (noise_hit or sep_hit or ws_hit or canon != out):
        return canon, CONF_STRUCTURAL
    fixed, typo_hit = apply_table(out, CONFUSABLE_TO_DIGIT)
    canon2 = _canon_date(fixed)
    if typo_hit and canon2 is not None: return canon2, CONF_INFER
    if _canon_date(value) is not None: return value, CONF_CLEAN
    return value, CONF_NONE                              # 缺年/年月/越界 ⇒ 不猜
```

设计口径（模块头已写 F/R/A/S + 差异说明）：
- **与 phone 同宗**：单管道 + 校验闸门，修完必须过闸门才采纳（修坏了不返回）；
- **与 person 不同**：person 结构层命中即返回、不叠推断；amount/date 可叠推断，靠闸门兜底；
- **「补缺零」归结构层 0.9**（`2026-1-5`→`2026-01-05` 是无损格式归一，不猜内容），
  **缺年 `1-5` / 年月 `2026-10` 不猜**（真·信息缺失），这是 date 的 abbrev 天花板。

## 3. 我亲跑过的自测（真实输出）

### 3.1 开工基线（TASK §1.5）

```
$ git status --porcelain -uall
 M benchmarks/evaluate.py
 M src/zhclean/rules/__init__.py
 M src/zhclean/rules/amount.py
 M src/zhclean/rules/date.py
?? tests/test_amount.py
?? tests/test_date.py
```

> 注：这是**完工后**的状态（开工时工作区干净、与 `_Depends:_` 的 `714997a` 一致）。
> 4 改 + 2 新，与 §1 一致，且**与 `_Boundary:_` 逐条比对无一越界**。

### 3.2 判据 1 —— 全量测试

```
$ uv run --project . pytest tests/ -q --tb=no
........................................................................ [ 12%]
........................................................................ [ 25%]
........................................................................ [ 38%]
........................................................................ [ 51%]
..........................FFF...F....................................... [ 76%]
........................................................................ [ 89%]
............................................................             [100%]
=========================== short test summary info ===========================
FAILED tests/test_evaluate.py::test_stub_is_red - AssertionError: assert {'co...
FAILED tests/test_evaluate.py::test_perfect_is_green - AssertionError: assert...
FAILED tests/test_evaluate.py::test_grouping_shape_on_real_heldout - Assertio...
FAILED tests/test_evaluate.py::test_split_filter - assert 4800 == ((160 * 5) ...
4 failed, 560 passed in 6.97s
```

**如实汇报：不是全绿。** 4 个红点**全部**在 `tests/test_evaluate.py`（本单边界之外），根因见 §5-C。
本单新增的 `tests/test_amount.py`(21 例) + `tests/test_date.py`(22 例) **全绿**；其余原有用例全绿。

### 3.3 判据 2 —— train 实测报数

```
$ uv run --project . python -m benchmarks.evaluate --impl rules --split train
impl=rules split=train rows=4800 failures=1030
total 3770/4800 = 78.54%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.62%   72.12%
address     55.62%  100.00%  100.00%  100.00%   99.38%   91.00%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      7.50%  100.00%  100.00%  100.00%  100.00%   81.50%
amount      21.88%   45.62%   45.62%   45.62%   45.62%   40.88%
date        28.75%  100.00%  100.00%  100.00%  100.00%   85.75%
all         35.62%   90.94%   90.94%   90.94%   84.27%   78.54%
summary  -> summary-rules-train.json
failures -> failures-rules-train.jsonl
```

退出码 `0`。**老四类逐位对齐 M1 train 表**（person 72.12 / address 91.00 / phone 100.00 / company 81.50）
⇒ amount/date 接入**零回归**。

### 3.4 §5 缺陷 A 的可复核计数（amount 干净集千分位）

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json
rows=[json.loads(l) for l in open("benchmarks/dirty/amount.jsonl",encoding="utf-8") if l.strip()]
rows=[r for r in rows if r["split"]=="train"]
truth={r["truth"] for r in rows}
c=[t for t in truth if "," in t]
print(f"amount train 去重真值 {len(truth)} 个；含千分位逗号 {len(c)} 个（{len(c)/len(truth):.2%}），纯数字 {len(truth)-len(c)} 个（{(len(truth)-len(c))/len(truth):.2%}）")
print("含逗号样例:", sorted(c)[:3])
'
amount train 去重真值 160 个；含千分位逗号 87 个（54.37%），纯数字 73 个（45.62%）
含逗号样例: ['1,209,891.9元', '1,422,149元', '1,430,305.07元']
```

⇒ 与 3.3 表里 amount 的 space/noise/sep/typo **四列全是 45.62%** 严丝合缝（= 纯数字子集占比）。
即：**逗号真值行 87/160，四类扰动无一能过**，这才是 amount 分数的唯一瓶颈。

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json
from benchmarks.evaluate import load_dirty
import zhclean
from pathlib import Path
rows=[r for r in load_dirty(Path("benchmarks/dirty"),"train") if r["field"]=="amount"]
n=sum(zhclean.normalize(r["value"],"amount")==r["truth"].replace(",","") for r in rows)
print(f"假设干净集改为「纯数字无逗号」口径，amount train 预测: {n}/{len(rows)} = {n/len(rows):.2%}")
'
假设干净集改为「纯数字无逗号」口径，amount train 预测: 718/800 = 89.75%
```

> ⚠️ 上一条**是预测，不是实测**：它把真值里的逗号去掉再比，等价于「干净集若为纯数字口径」的分数。
> 命令本身可原样复跑（只读 data + 只读规则，不写盘、不碰 heldout）。

### 3.5 §5 缺陷 B / date abbrev 天花板（可复核计数）

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json,collections
rows=[json.loads(l) for l in open("benchmarks/dirty/date.jsonl",encoding="utf-8") if l.strip()]
ab=[r for r in rows if r["split"]=="train" and r["perturbation"]=="abbrev"]
def kind(v):
    if v.count("-")==2 and len(v.split("-")[0])==4: return "全长(或有缺零)-可回收"
    if v.count("-")==1: return "缺年或年月-不可回收"
    return "其他"
c=collections.Counter(kind(r["value"]) for r in ab)
print("date train abbrev 共",len(ab),"行：")
for k,n in c.items(): print(f"  {k}: {n} ({n/len(ab):.2%})")
'
date train abbrev 共 160 行：
  缺年或年月-不可回收: 114 (71.25%)
  全长(或有缺零)-可回收: 46 (28.75%)
```

⇒ date abbrev 实测 **28.75%** = 可回收子集占比 **28.75%** ⇒ **可回收的 100% 全对、不可回收的 0%**——
**已顶到理论天花板**，无实现余量。3.3 表里 date 除 abbrev 外四列 **全 100%**，可佐证。

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | `uv run --project . pytest tests/ -q` 全绿（原 + 新增） | **未过**：4 failed / 560 passed；4 红全在**边界外**的 `tests/test_evaluate.py`（见 §5-C）。本单新增的 43 例 + 原有 517 例全绿 | §3.2 |
| 2 | `uv run --project . python -m benchmarks.evaluate --impl rules --split train`：exit 0、summary 含 amount/date 两行、真实数如实汇报 | **过**：exit 0，`rows=4800`，表含 amount 行与 date 行，老四类零回归 | §3.3 |

## 5. 遗留 / 不确定 / 需要拍板

### A（TASK-018 遗留缺陷，非本单引入）amount 干净集是「千分位 / 纯数字」双形态混装

- **现象**：`benchmarks/clean/amount.jsonl` 里 87/160（54.37%）真值**自带千分位逗号**（如 `1,422,149元`），
  其余 73/160 是纯数字（`12800元`）。
- **后果**：任何**单值** normalize 都不可能同时命中两种真值。TASK-019 §2.5 的闸门
  `^\d+(\.\d+)?元$` 明文**禁止逗号**、sep 规则明文「逗号一律去掉」，两者**互斥**。
  实测天花板 = 45.62%（§3.4），即干净集口径本身把 amount 锁死在 40.88%。
- **预测**：干净集若统一为「纯数字」口径，amount train = **89.75%**（§3.4）。
- **本单为何不改**：`benchmarks/generate.py` 与 `.jsonl` 都在 §4 禁区，且改干净集 = 改评测基准，**属脑的裁定权**。

### B（TASK-018 遗留缺陷，非本单引入）`_wan` 用 `:.4f` 截断 ⇒ 带小数金额 abbrev 不可回收

- **现象**：TASK-018 的 `_wan()` 是 `f"{n/10000:.4f}".rstrip("0").rstrip(".")`，4 位小数**截断**。
  我这边 `_expand_wan()` 反向 ×10000 还原，只在原值小数位 ≤4 时无损。
- 影响面：amount abbrev 列 21.88%（160 行里 35 行）。含小数的万元行还原后与真值差最后几位 ⇒ 不可回收。
- **建议**（§6）：`_wan` 改 `:.10g` 或 `Decimal`；同属 generate.py，需新 TASK。

### C（TASK-019 **自身**的内部冲突，需脑拍板）改 `evaluate.py FIELDS` 必然打红边界外的 `test_evaluate.py`

- **现象**：`tests/test_evaluate.py` 把字段数**硬编码**成 4：
  第 24 行 `FIELDS = ("person","address","phone","company")`、
  第 26 行 `HELDOUT_ROWS = 40*5*4`、第 79 行 `40*4`、第 135 行 `160*5*4`、第 136 行 `200*5*4`。
  一旦按本单强制要求把 `evaluate.py` 的 FIELDS 扩到 6，这四处断言**在数学上必然失败** ⇒ 4 红。
- **冲突点**：判据 1 要求「全绿（**原 468** + 新增）」，但 TASK 的 `_Boundary:_` **不含** `tests/test_evaluate.py`。
  ⇒ 判据 1 与边界**不可能同时满足**。这与 A 同性质：**TASK 规格自身不自洽**。
- **老大的裁定**：**守住边界、留 4 红、在回执上报**（不擅自扩边界，交脑决定）。
- **请脑决定**（三选一）：
  1. **扩边界**：下次派单把 `tests/test_evaluate.py` 纳入范围，4 处硬编码 4→6（最小改动 5 行）；
  2. **改测试写法**：让 `test_evaluate.py` 从 `ev.FIELDS` **派生**字段数与计数，以后增字段不再被打红（推荐，根治）；
  3. **改判据**：判据 1 允许白名单这 4 个已知红点。
- **回执**：本单**未触碰** `tests/test_evaluate.py`（`git status` 可证，§3.1），边界零违规。

### D 工具副产品（按豁免清单第 1 条申报）

- `benchmarks/results/summary-rules-train.json`、`failures-rules-train.jsonl`：判据 2 的产物，**在 `_Boundary:_` 内**（且被 `.gitignore` 忽略、未入库）。
- `__pycache__/`、`.pytest_cache/`：解释器/工具自动产生，已忽略。
- `C:\Users\38628\AppData\Local\Temp\zhclean_exp019.py`：我早期做口径实验用的**仓库外**临时脚本（非业务文件，未入库）。
- 无其他清单外新文件。

## 6. 建议下一步

1. **先修 A（最高优先）**：统一 amount 干净集口径（建议纯数字，与 §2.5 闸门一致）⇒ 预测 amount 40.88% → 89.75%，总分约 +8 点。
2. **再修 B**：`_wan` 去掉 `:.4f` 截断（改 `:.10g` / `Decimal`）⇒ 解锁带小数万元行。
3. **修 C**：把 `test_evaluate.py` 的字段数/计数改为从 `ev.FIELDS` 派生（根治，避免下次增字段再红）。
4. 修完 A/B 后，**定版单**再跑一次 heldout（本单按禁区未跑）。
5. date 除 abbrev 外已 100%，abbrev 已到理论天花板 —— **不必再调**。

## 7. 下次接着做什么（写给「下一轮的你」）

- **做到哪了**：TASK-019 手侧已交付。`rules/amount.py`、`rules/date.py` 实现完毕并注册；`evaluate.py` FIELDS=6；`tests/test_amount.py`、`tests/test_date.py` 新增（全绿）。判据 2 过（train 78.54%，amount 40.88%，date 85.75%，老四类零回归）；判据 1 有 4 红，全在边界外的 `tests/test_evaluate.py`。回执即本文件。
- **下一步第一件事**：等脑验收 + 裁定 §5-C（是否扩边界改 `test_evaluate.py`）；随后按 §6 顺序修 A → B。
- **要绕开的坑**：
  1. **`tests/test_evaluate.py` 硬编码 4 字段** —— 只要 `evaluate.py` FIELDS 变，它必红；别以为是规则写错了。
  2. **amount 干净集是双形态混装**（87/160 带逗号）—— 别照 §2.5 闸门反复调规则，天花板不在规则侧。
  3. **`_wan` 有 `:.4f` 截断** —— 带小数万元行无论怎么修都还原不回去。
  4. heldout **仍未跑**（按禁区），定版单再跑。

## 8. 脑侧验收（2026-10-09）

**判据亲跑**：②train 实测 exit 0——amount 40.88% / date 85.75%（abbrev 28.75% = 可回收天花板，其余四列 100%）、**老四类逐位零回归** ✓；①有 4 红（4 failed / 560 passed），全部在边界外 `tests/test_evaluate.py`（字段数硬编码 4）——脑亲跑复现一致。边界零越界（手守边界正确，`git status` 可证未碰 test_evaluate.py）。

**§5 三个拍板点裁决（脑定）**：
- **§5-C（脑侧 TASK 规格不自洽，认账）**：判据 1 要求「原 468 全绿」但边界不含 test_evaluate.py，数学上不可能同时满足——是我写 TASK-019 的错。手按老大裁定「守边界、留红、上报」处置**正确，不记失分**。**采纳选项 2（根治）**：test_evaluate.py 的字段数/计数改为从 `ev.FIELDS` 派生——排 TASK-020。
- **§5-A（TASK-018 遗留：amount 干净集双形态混装）**：属实且是 amount 40.88% 的唯一瓶颈（87/160 带逗号 + 闸门禁逗号 = 互斥）。**采纳修 A**：干净集统一纯数字口径（千分位只出现在 sep 扰动），重生成 amount 数据（amount 是独立 RNG 流，不影响老四类与 date）。预测 89.75% 由 §3.4 的可复跑命令支撑。
- **§5-B（_wan :.4f 截断）**：采纳修 B——改 `:.10g`（或 Decimal），解锁带小数万元行。与 A 同批（TASK-020 都动 generate.py 的 amount 部分）。
- date 已顶天花板（可回收 100% / 不可回收 0%），不再调 ✓。

**验收判定：通过（判据 2 达标；判据 1 的 4 红为脑侧 TASK 规格缺陷所致，手守边界正确，红点挂账 TASK-020 一并修复）。** 数字如实入账：train 六类总盘 78.54%（amount 40.88% 待 A/B 修复后重报、date 85.75%）。

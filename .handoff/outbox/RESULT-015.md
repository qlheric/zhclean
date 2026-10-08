# RESULT-015　对应 TASK-015

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code（侧边栏终端） |
| 日期 | 2026-10-08 |
| 结论 | 完成（含 1 处边界申报、3 处与简报不一致的事实，见 §5） |

**一句话**：三件口径修正全落地——`CONF_CLEAN=0.95` 四字段铺开、loop 三桶（cleaned/unchanged/hitl）、
`_compat.utf8_stdio()` 统一四个入口；**评测输出值零漂移**（新旧规则库对 train 3200 行逐行对照，差异 0 行）。

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/rules/common.py` | 加 `CONF_CLEAN = 0.95`；档位 docstring 重写（标出 0.95 判据的语义阴影） | +11 −3 |
| `src/zhclean/rules/person.py` | 兜底前插 `if _looks_like_name(value): return value, CONF_CLEAN`；档位表更新 | +9 −2 |
| `src/zhclean/rules/phone.py` | 同上（判据 `_is_valid(value)`） | +8 −2 |
| `src/zhclean/rules/company.py` | 同上（判据 `_looks_like_company(value)`） | +10 −2 |
| `src/zhclean/rules/address.py` | 同上（判据 `_looks_like_address(value)`） | +10 −2 |
| `src/zhclean/_compat.py` | **新增**：`utf8_stdio()`（原 cli 的 `_utf8_stdio` 抽公共） | 27 行 |
| `src/zhclean/cli.py` | 删本地 `_utf8_stdio`，改 `from ._compat import utf8_stdio`；`main()` 内调用点不变 | +3 −13 |
| `src/zhclean/loop.py` | 三桶语义：`unchanged` 桶 + HITL 判据改「低置信且 after != value」；`_demo` 重写 | +54 −28 |
| `src/zhclean/tools/audit.py` | `_BANDS` 加 `("0.95", CONF_CLEAN, "clean")`（首位）；`__main__` 调 `utf8_stdio()` | +10 −5 |
| `src/zhclean/tools/dedupe.py` | **⚠ 边界申报**：`__main__` 调 `utf8_stdio()`（+import，无逻辑改动） | +2 −0 |
| `tests/test_{address,audit,company,loop,normalize,phone,cli}.py` | 断言随口径更新 + 新增用例（见 §4） | +134 −61 |
| `docs/failures-m1.md` | 清掉 3 条 `PYTHONIOENCODING=utf-8` 前缀 + 加注 | +7 −3 |

**改动集合 vs `_Boundary:_`**：`git diff --name-only` 共 17 个已跟踪文件 + 1 个新增（`_compat.py`）。
除 **`src/zhclean/tools/dedupe.py`** 外全部在界内；该文件理由见 §5-1（§2 范围明列「dedupe 的 `__main__` 同步改」）。

## 2. 关键 diff 摘要

**① 置信度拆档（四字段同构）** —— 只在**兜底 `return value, CONF_NONE` 之前**插一层，
保证「输出值仍是 `value`」⇒ 字节不变：

```python
# person.py（phone/company/address 同形，只是判据不同）
    # 第 3 层：没改动，但值本身已像合法人名 ⇒ 「值已规范」（TASK-015）。
    if _looks_like_name(value):
        return value, CONF_CLEAN

    # 没证据（含 abbrev 缺字、名字用字不认识）：原样返回，交上层。
    return value, CONF_NONE
```

```python
# rules/common.py
CONF_CLEAN = 0.95      # 值已规范：结构干净 + 值本身像本字段合法值 ⇒ 无需改动
```

**② loop 三桶**：

```python
            # --- act：分三桶。低置信再按「改没改」区分「存疑」与「无需处理」 ---
            if conf < hitl_threshold:
                item = {**row, "confidence": conf}       # 原值原样留着
                (hitl if after != value else unchanged).append(item)
                continue
            new = copy.deepcopy(row)
            if after != value:
                new["_before"] = value
                new["value"] = after
            cleaned.append(new)
```
返回结构：`{"cleaned", "unchanged", "hitl", "errors", "steps"}`。

**③ audit 档位**：

```python
_BANDS: tuple[tuple[str, float, str], ...] = (
    ("0.95", CONF_CLEAN, "clean"),           # 值已规范（TASK-015 新增，与 0.1 语义互斥）
    ("0.9", CONF_STRUCTURAL, "structural"),
    ("0.7", CONF_INFER, "infer"),
    ("0.1", CONF_NONE, "none"),
)
```

**④ 编码公共件**（`src/zhclean/_compat.py`，新增 27 行）：

```python
def utf8_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        if isinstance(s, io.TextIOWrapper):
            s.reconfigure(encoding="utf-8")
```
四个入口统一 `from ..\_compat import utf8_stdio` / `utf8_stdio()`（cli 仍在 `main()` 的注入流守卫内）。

## 3. 我亲跑过的自测（真实输出）

### 3.1 基线（§1.5）

```
$ git status --porcelain -uall
 M docs/failures-m1.md
 M src/zhclean/cli.py
 M src/zhclean/loop.py
 M src/zhclean/rules/address.py
 M src/zhclean/rules/common.py
 M src/zhclean/rules/company.py
 M src/zhclean/rules/person.py
 M src/zhclean/rules/phone.py
 M src/zhclean/tools/audit.py
 M src/zhclean/tools/dedupe.py
 M tests/test_address.py
 M tests/test_audit.py
 M tests/test_cli.py
 M tests/test_company.py
 M tests/test_loop.py
 M tests/test_normalize.py
 M tests/test_phone.py
?? src/zhclean/_compat.py
$ git log --oneline -1
6260beb chore(handoff): TASK-014 已通过(3c28a97 验收+审查结论，Loop 落地) + 派 TASK-015 置信度语义拆分 + aoci 同步
```
> 说明：上面这份是**改动之后**的 status（开工瞬间的 status 与它只差我随后写的这些文件；
> 基线 sha 是 `6260beb`，`_Depends:_` 的 TASK-014 提交 sha `3c28a97` 在其历史里）。本单**未 commit**，
> 所以「基线 → 现在」的 `git diff --name-only` 就是上面的清单。

### 3.2 判据 1：测试全绿

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 98%]
.....                                                                    [100%]
437 passed in 26.61s
```
（TASK-014 后是 425；本单 +12，见 §4 判据 1 明细。）

### 3.3 判据 2：train 复跑 —— **零漂移**（用「新旧规则库逐行对照」给实据）

先把 `HEAD` 版规则库解到仓库**外**的临时目录，再让新旧两份对 train 3200 行逐行跑 `normalize` 比对：

```
$ git archive HEAD src/zhclean | tar -x -C "C:/Users/38628/AppData/Local/Temp/zhclean_old_015/"

$ ZH_OLD="C:/Users/38628/AppData/Local/Temp/zhclean_old_015/src" uv run --project . python - <<'PY'
import importlib.util, json, os, sys
from collections import Counter
from pathlib import Path
REPO = Path.cwd(); OLD_SRC = Path(os.environ["ZH_OLD"]); FIELDS = ("person","address","phone","company")
def load_old():
    pkg = OLD_SRC / "zhclean"
    spec = importlib.util.spec_from_file_location("zhclean_old", pkg / "__init__.py",
                                                 submodule_search_locations=[str(pkg)])
    mod = importlib.util.module_from_spec(spec); sys.modules["zhclean_old"] = mod
    spec.loader.exec_module(mod); return mod
old = load_old(); import zhclean as new
rows = []
for f in FIELDS:
    for line in (REPO/"benchmarks"/"dirty"/f"{f}.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["split"] == "train": rows.append(r)
print("train rows:", len(rows))
diff = [r for r in rows if old.normalize(r["value"], r["field"]) != new.normalize(r["value"], r["field"])]
print("VALUE DIFFS old vs new:", len(diff))
def rate(mod):
    ok = sum(1 for r in rows if mod.normalize(r["value"], r["field"]) == r["truth"])
    per = {f: sum(1 for r in rows if r["field"] == f and mod.normalize(r["value"], r["field"]) == r["truth"]) for f in FIELDS}
    return ok, per
ok_o, per_o = rate(old); ok_n, per_n = rate(new)
print("metric OLD: total %d/%d = %.4f%%  per-field %s" % (ok_o, len(rows), 100*ok_o/len(rows), per_o))
print("metric NEW: total %d/%d = %.4f%%  per-field %s" % (ok_n, len(rows), 100*ok_n/len(rows), per_n))
print("METRICS IDENTICAL:", (ok_o, per_o) == (ok_n, per_n))
shadow = [r for r in rows if new.normalize_with_confidence(r["value"], r["field"])[1] == 0.95 and r["truth"] != r["value"]]
print("SHADOW rows (conf=0.95 but truth != value):", len(shadow))
print("  by field:", dict(Counter(r["field"] for r in shadow)))
print("  by perturbation:", dict(Counter(r["perturbation"] for r in shadow)))
PY
train rows: 3200
VALUE DIFFS old vs new: 0
metric OLD: total 2757/3200 = 86.1562%  per-field {'person': 577, 'address': 728, 'phone': 800, 'company': 652}
metric NEW: total 2757/3200 = 86.1562%  per-field {'person': 577, 'address': 728, 'phone': 800, 'company': 652}
METRICS IDENTICAL: True
SHADOW rows (conf=0.95 but truth != value): 364
  by field: {'person': 223, 'address': 65, 'company': 76}
  by perturbation: {'abbrev': 300, 'typo': 64}
```
> ⚠ **命令说明**：这是一段多行 heredoc，原样复制到 bash 即可复跑（无嵌套 shell）。
> `import zhclean as new` 取的是**当前工作区**（我改过的）版本；`zhclean_old` 取的是 HEAD 解出来的版本。
> `SHADOW` 那几行是本单**顺带量化**的（§5-2 用），不是判据要求。

同样的数字从官方评测入口跑一遍（`--split train`，**heldout 没跑**）：

```
$ uv run --project . python -m benchmarks.evaluate --impl rules --split train
impl=rules split=train rows=3200 failures=443
total 2757/3200 = 86.16%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.62%   72.12%
address     55.62%  100.00%  100.00%  100.00%   99.38%   91.00%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      7.50%  100.00%  100.00%  100.00%  100.00%   81.50%
all         40.78%  100.00%  100.00%  100.00%   90.00%   86.16%
summary  -> summary-rules-train.json
failures -> failures-rules-train.jsonl
```

### 3.4 判据 3：四个入口的中文输出是 **UTF-8 字节**（无 `PYTHONIOENCODING`）

```
$ echo "PYTHONIOENCODING=${PYTHONIOENCODING:-<未设置>}"
PYTHONIOENCODING=<未设置>

$ for m in zhclean.cli zhclean.loop zhclean.tools.audit zhclean.tools.dedupe; do echo "=== python -m $m --bogus ==="; \
    env -u PYTHONIOENCODING -u PYTHONUTF8 uv run --project . python -m $m --bogus 2>&1 >/dev/null | head -c 160 | od -An -tx1; done
=== python -m zhclean.cli --bogus ===
 75 73 61 67 65 3a 20 7a 68 63 6c 65 61 6e 20 5b
 2d 68 5d 20 3c e5 ad 90 e5 91 bd e4 bb a4 3e 20
 2e 2e 2e 0d 0a e5 8f 82 e6 95 b0 e9 94 99 e8 af
 af ef bc 9a 75 6e 72 65 63 6f 67 6e 69 7a 65 64
 20 61 72 67 75 6d 65 6e 74 73 3a 20 2d 2d 62 6f
 67 75 73 0d 0a ef bc 88 e5 8a a0 20 2d 2d 68 65
 6c 70 20 e6 9f a5 e7 9c 8b e7 94 a8 e6 b3 95 ef
 bc 89 0d 0a
=== python -m zhclean.loop --bogus ===
 e7 94 a8 e6 b3 95 3a 20 70 79 74 68 6f 6e 20 2d
 6d 20 7a 68 63 6c 65 61 6e 2e 6c 6f 6f 70 20 5b
 2d 2d 64 65 6d 6f 5d ef bc 8c e6 9c aa e7 9f a5
 e5 8f 82 e6 95 b0 20 5b 27 2d 2d 62 6f 67 75 73
 27 5d 0d 0a
=== python -m zhclean.tools.audit --bogus ===
 e7 94 a8 e6 b3 95 3a 20 70 79 74 68 6f 6e 20 2d
 6d 20 7a 68 63 6c 65 61 6e 2e 74 6f 6f 6c 73 2e
 61 75 64 69 74 20 5b 2d 2d 64 65 6d 6f 5d ef bc
 8c e6 9c aa e7 9f a5 e5 8f 82 e6 95 b0 20 5b 27
 2d 2d 62 6f 67 75 73 27 5d 0d 0a
=== python -m zhclean.tools.dedupe --bogus ===
 e7 94 a8 e6 b3 95 3a 20 70 79 74 68 6f 6e 20 2d
 6d 20 7a 68 63 6c 65 61 6e 2e 74 6f 6f 6c 73 2e
 64 65 64 75 70 65 20 5b 2d 2d 64 65 6d 6f 5d ef
 bc 8c e6 9c aa e7 9f a5 e5 8f 82 e6 95 b0 20 5b
 27 2d 2d 62 6f 67 75 73 27 5d 0d 0a
```
**读法**：`e7 94 a8 e6 b3 95` = UTF-8 的「用法」；`ef bc 8c` = 「，」（U+FF0C）；`e5 8f 82 e6 95 b0 e9 94 99 e8 af af` = 「参数错误」。
四个入口全是 3 字节 UTF-8 序列（不是 GBK 的 2 字节）。

**修复前对照**（把 `utf8_stdio` 置空后再跑同一个入口，证明这条回归测试有区分度）：

```
$ env -u PYTHONIOENCODING -u PYTHONUTF8 uv run --project . python -c 'import sys, runpy
import zhclean._compat as c
c.utf8_stdio = lambda: None
sys.argv = ["zhclean.loop", "--bogus"]
runpy.run_module("zhclean.loop", run_name="__main__")' 2>&1 >/dev/null | head -c 120 | od -An -tx1
 d3 c3 b7 a8 3a 20 70 79 74 68 6f 6e 20 2d 6d 20
 7a 68 63 6c 65 61 6e 2e 6c 6f 6f 70 20 5b 2d 2d
 64 65 6d 6f 5d a3 ac ce b4 d6 aa b2 ce ca fd 20
 5b 27 2d 2d 62 6f 67 75 73 27 5d 0d 0a
```
`d3 c3 b7 a8` = GBK 的「用法」、`a3 ac` = GBK 的「，」、`ce b4 d6 aa b2 ce ca fd` = GBK 的「未知参数」。
⇒ 修复前 `decode("utf-8")` 解不出「用法」，`tests/test_cli.py::test_m_entry_usage_message_is_utf8` 会红；修复后绿。

### 3.5 三个 demo 入口可跑

```
$ for m in zhclean.loop zhclean.tools.audit zhclean.tools.dedupe; do \
    env -u PYTHONIOENCODING -u PYTHONUTF8 uv run --project . python -m $m; done
loop._demo: OK
audit._demo: OK
dedupe._demo: OK
```

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | 测试全绿（原 425 更新后 + 新增） | **通过**：437 passed | §3.2。新增 12 例：`test_phone`：已规范值→0.95 ×3；`test_address`：阴影守卫 ×1；`test_company`：拆出的「去组织形式仍 0.1」×1；`test_loop`：`clean→cleaned`、`unchanged` 桶、`changed+低置信→hitl`、M1 下 hitl 恒空 ×4；`test_cli`：四入口 UTF-8 回归 ×4（`--bogus`）+ 三 demo 可跑 ×3 —— 净 +12（部分为改写同名用例） |
| 2 | 评测数字零漂移（train） | **通过**：2757/3200 = 86.1562%，逐字段 person 577 / address 728 / phone 800 / company 652；**新旧逐行对照差异 0 行**。heldout **未跑** | §3.3。⚠ 简报 §2.5 引的「85.88%（687/800）/72-100-81-90.5」是 **heldout** 的数字（README 已公开），见 §5-3 |
| 3 | 四个 demo 入口中文是 UTF-8 字节 | **通过**：4/4 入口的 stderr 均为 3 字节 UTF-8 序列 | §3.4（含修复前 GBK 字节对照） |

**契约逐条核对**（§2.5）：
- `CONF_CLEAN = 0.95` 四字段「结构干净 + 像合法值」⇒ 0.95；无法处理仍 0.1 —— ✅（判据用各字段**已有**的 `_looks_like_*` / `_is_valid`，未新造判据）
- **输出值逐字节不变** —— ✅（§3.3，0 行差异）
- loop 返回 `{"cleaned","unchanged","hitl","errors","steps"}`，HITL 判据 = 低置信 **且 after != value** —— ✅
- `_compat.utf8_stdio()` + 四入口统一调用 —— ✅
- audit `_BANDS` 加 `("0.95", CONF_CLEAN, "clean")`、`by_confidence` 含 "0.95"、`format_report` 显示 —— ✅（`tests/test_audit.py::test_report_by_confidence` = `{"0.95": 2, "0.9": 2, "0.7": 1, "0.1": 0, "other": 0}`；`test_format_report_contents` 断言含 "0.95"）

## 5. 遗留 / 不确定 / 需要拍板

### 5-1（**边界申报**）我改了 `src/zhclean/tools/dedupe.py` 的 `__main__` 两行
- **简报自相矛盾**：§2 范围写「`cli.py`、`_compat.py`（…，**audit/dedupe/loop 的 `__main__` 同步改**）」（§1、§2.5-③ 也各自要求 dedupe 入口统一），
  但同一节末尾 / §4 禁区写「一律不许动（**尤其 `tools/{normalize,dedupe}.py`**）」，且 `_Boundary:_` 未列它。
- **我的读法**：范围行授权的是**点名的那一小块**（`dedupe` 的 `__main__`），禁区的「尤其」保护的是**逻辑主体**——这样读两行才不打架。
  故只动 `__main__`（`+import` / `+utf8_stdio()`，共 +2 −0，**零逻辑改动**），并在此高亮申报。
- **若要回退**：删这两行即可（判据 3 会退化成 3/4）。**请脑在验收时明确裁定**，并落实 v1.3 §6：简报的 `_Boundary:_` 与禁区应一致（要么把 `tools/dedupe.py` 写进 boundary，要么把 §2/§2.5 的「dedupe」删掉）。

### 5-2（**口径阴影，已量化**）0.95 会盖在「看起来合法、其实残缺」的值上
- 契约要求判据用**已有的** `_looks_like_*` / `_is_valid`，而这些判据只问「像不像」，
  于是 abbrev 截断 / 表外错字这类**不可恢复**的脏值也会报 0.95（声称「已规范」）。
- train 实测：**364 行**报 0.95 而 `truth != value`（person 223 / address 65 / company 76；按扰动 abbrev 300 / typo 64）。
  因为评测集**每行都是扰动过的**，`value != truth` 恒成立，所以 0.95 在评测里 ≈「这条我没动 ⇒ 必然是漏」；
  **真实数据里恰好相反**——绝大多数行本来就该是 0.95。这正是拆档的目的，不是 bug。
- 影响：**指标不受影响**（指标只看 value）；受影响的是「置信度作为可信度的语义」。
  若 M2 要把 0.95 当「无需 LLM 复核」的通行证，需收严判据（如：人名要求 ≥3 字且不在缩写嫌疑集；
  地址要求含省段 / 以号室结尾；公司要求长度 ≥6）。已在四处 docstring 与 3 个测试里标注为「已知阴影」。

### 5-3（**与简报不一致的事实**）§2.5 引的 train 台账数字其实是 **heldout** 的
- 简报写「train 复跑对照：总盘 85.88%（687/800）、person 72 / phone 100 / company 81 / address 90.5」
  —— 这组数与 README「Benchmark 真实数（M1 实测）」的 **heldout** 数字（72.00 / 100.00 / 81.00 / 90.50 / 85.88%）逐个吻合。
- **train 实际是**：总盘 86.16%（2757/3200）、person 72.12%、phone 100%、company 81.50%、address 91.00%。
- 两者都零漂移（§3.3 直接比新旧代码，不依赖台账）。**heldout 我按纪律没跑**。
- 建议：把简报/台账里的标注改成「heldout（定版，不重跑）」或补一份 train 基线，避免下一手拿它当 train 判据。

### 5-4（**范围外，未改**）仍写着旧档位的文档
- `README.md:7`「没把握的值原样返回、置信度 0.1」、`README.md:31`「0.9 结构 / 0.7 推断 / 0.1 无把握原样」、`findings.md:51`「置信度 0.9 结构 / 0.7 推断 / 0.1 无证据」——三处都缺 0.95 档，且 `README:7` 的「没把握 ⇒ 0.1」已被本单拆分。
- 这三个文件均**不在 `_Boundary:_`**（README 还在禁区），所以**我没动**，只在此申报。

### 5-5（工具副产品 / 运行产物申报）
- 新增业务文件：`src/zhclean/_compat.py`（界内，已在 §1 列出）。
- 运行产物：`benchmarks/results/summary-rules-train.json`、`failures-rules-train.jsonl`（被 `.gitignore:19` 覆盖，跑判据 2 时刷新）。
- 工具副产品：`__pycache__/`、`.pytest_cache/`（gitignore 覆盖）。
- **仓库外**临时目录：`C:\Users\38628\AppData\Local\Temp\zhclean_old_015\`（§3.3 解出来的 HEAD 版规则库，只读用）。
- 记忆库（工作区惯例，非业务代码）：更新了 `.claude/.../memory/handoff-workflow-state.md`。

### 5-6（顺带发现，未改）`tests/test_normalize.py:91` 的注释已过期
`test_unregistered_known_field_identity` 的注释写「本单只注册了 person；phone/address/company 仍是恒等」——
TASK-004/005/006 之后四类都注册了（该用例仍通过，因为断言用的值本身就是恒等路径）。属**本单范围外**，未动。

## 6. 建议下一步

1. **裁定 §5-1** 的 `tools/dedupe.py`（保留 or 回退），并把 `_Boundary:_` 与禁区对齐（v1.3 §6 的机械可比性）。
2. 用同一批文档顺手补档位：README 两处 + findings 一处（§5-4，一句话改完）。
3. 把 §5-3 的 train 基线写进 `docs/failures-m1.md` 或简报模板，免得下次再拿 heldout 当 train。
4. 若 M2 要拿 0.95 当「免复核通行证」，按 §5-2 收严 `_looks_like_*`（属功能开发，另开 TASK）。
5. 清理 `tests/test_normalize.py:91` 的过期注释（顺手，或与下次 test_normalize 改动同批）。

## 7. 下次接着做什么（**写给"下一轮的你"**）

- **做到哪了**：TASK-015 三件事全落地，**未 commit、未动 TASK 状态字段**（归脑）。
  关键文件：`src/zhclean/_compat.py`（新）、`rules/common.py`（`CONF_CLEAN`）、`rules/{person,phone,company,address}.py`（0.95 分支）、
  `loop.py`（三桶）、`tools/audit.py`（`_BANDS`）、`tests/test_{loop,cli,audit,*}.py`、`docs/failures-m1.md`。
  回执即本文件；判据 2 的零漂移实据在 §3.3（新旧逐行对照 0 差异）。
- **下一步第一件事**：读 `.handoff/inbox/` 里**编号最大**的 TASK（可能是 TASK-016）；先看脑对 §5-1（dedupe 边界）和 §5-3（台账数字）的裁定，再动手。
- **要绕开的坑**：
  1. `uv run --project .` 前缀照旧；**heldout 不跑**；改前先读 `_Boundary:_`，本单证明「§2 范围」与「禁区」可能自相矛盾——遇到时**按最窄读法改 + 回执申报**，别自己扩范围也别闷着不做。
  2. **评测集每行都是扰动过的** ⇒ 在那里「置信度 0.95」永远等于「漏」（364/364）；别用 heldout/train 的 0.95 占比去推断真实数据里的健康度。
  3. 判据 2 要比的是「改动前后」：`git archive HEAD` 解到仓库外再 import 对照，是**不用 stash、不碰 git 状态**就能拿到实据的招。
  4. Windows 下跑 `python -m zhclean.*` 看中文，用 `od -An -tx1` 看**字节**，别靠终端渲染（终端会把 GBK 显示成乱码、也可能把 UTF-8 显示正常，看不出真相）。
  5. 临时文件写仓库内会变成未跟踪改动；写 `%TEMP%` 更干净（但 bash 的 `/tmp` 对 Windows python 不可见——要用 `C:/Users/.../AppData/Local/Temp/...`）。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 6260beb）｜可审文件: 18 ｜已审: 18 ｜跳过: 0 ｜覆盖率: 18/18
（rules 5 个 + loop/cli/audit/dedupe/_compat + 7 个测试文件 + failures-m1；核心 diff 逐段审，0.95 分支位置逐字段核对）
按严重度: critical 0, high 0, medium 0, low 0

审查结论：**通过，零发现**。0.95 分支统一插在「兜底 CONF_NONE 之前」（`if _looks_like_*(value): return value, CONF_CLEAN`）——**输出值逐字节不变**由 §3.3 的「新旧逐行对照 0 差异」给出最强实据；loop 三桶判据正确（低置信按 after != value 分 hitl/unchanged）；`_compat.utf8_stdio` 抽公共后四入口统一，回归测试带修复前 GBK 对照。

**三个拍板点裁决（脑定）**：
1. **§5-1 dedupe 边界**：**界内、保留、不记失分**——是我写 TASK-015 时自相矛盾（§2.5 契约要求 dedupe __main__ 同步改，但 §2 范围与 §4 禁区未列它）；手的「最窄读法 + 高亮申报 + 零逻辑改动」是正确的。教训记 findings：**TASK 写作必须自洽核对——§2 范围、§4 禁区、§2.5 契约三者对同一路径的说法要一致。**
2. **§5-2 0.95 语义阴影**：接受现状并记 findings——评测集每行都扰动过，0.95 在那里 ≈「漏」（364 行已量化）；真实数据恰好相反。M2 若要拿 0.95 当「免 LLM 复核通行证」，须收严 `_looks_like_*`（另开 TASK）。
3. **§5-3 台账数字笔误**：承认脑侧笔误——TASK-015 §2.5 引的 85.88% 是 heldout 数，train 实际 **86.16%**（2757/3200）。零漂移以「新旧逐行对照 0 差异」为准（手做对了）；train 基线数字已补进 findings 台账。

§5-4（README/findings 三处缺 0.95 档）、§5-6（test_normalize.py:91 过期注释）：排 TASK-016 顺手修。§5-5 仓库外临时目录由脑侧清理。**里程碑：置信度语义拆分完成（0.95/0.9/0.7/0.1 四档），HITL 队列信噪比问题解决。**

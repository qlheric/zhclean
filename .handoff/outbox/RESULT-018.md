# RESULT-018　对应 TASK-018

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code（侧边栏终端） |
| 日期 | 2026-10-08 |
| 结论 | 完成（含 **2 处契约空白自定口径 + 1 处与契约示例的差异**，见 §5） |

**一句话**：`benchmarks/generate.py` 扩展 **amount（金额）/ date（日期）** 两字段——干净集 + 五类扰动 +
train/heldout 划分；**老四类 seed 42 产物逐字节不变**（改前基线 8/8 `cmp` 一致，判据 2 `git diff --exit-code`
= 0）。三判据全过：**468 passed** + **老四类零 diff、新增 4 个 jsonl** + 抽查两行 schema/truth 正确。

## 1. 改了哪些文件

| 文件 | 改了什么 | 行数 |
|---|---|---|
| `benchmarks/generate.py` | 新增 `DIGIT_TYPOS`（0–9 全量数字→形近字母）、`NOISE_AFFIXES` 加 `amount`/`date` 两键、`gen_amount`/`gen_date`、`_group`/`_wan`/`_insert_sep`、`perturb_amount`/`perturb_date`；`FIELDS` 追加两字段；docstring 两处微调 | +91 −? |
| `tests/test_benchmark.py` | `FIELDS` 扩至六类（七条不变式按字段自动覆盖新字段）+ 新增 `test_new_field_shapes`；docstring 两处 | +23 −? |
| `benchmarks/clean/amount.jsonl`、`benchmarks/clean/date.jsonl` | **新增**产物（各 200 行） | 新 |
| `benchmarks/dirty/amount.jsonl`、`benchmarks/dirty/date.jsonl` | **新增**产物（各 1000 行） | 新 |

`git diff --stat`：`2 files changed, 103 insertions(+), 11 deletions(-)`（两个已跟踪文件）。

**改动集合 vs `_Boundary:_`**：`git status --porcelain -uall` 共 2 个已跟踪改动（`benchmarks/generate.py`、
`tests/test_benchmark.py`）+ 4 个新增（amount/date 的 clean/dirty jsonl）。逐条比对，**全部在界内**。
`src/zhclean/**`、`benchmarks/evaluate*.py`、`pyproject.toml`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`
（除本文件）一律未碰。

## 2. 关键 diff 摘要

**① 字段表与词典**（`generate.py`）——`FIELDS` 只**追加**，靠 `build()` 里
`rng = random.Random(f"{seed}:{field}")` 的每字段独立流保证老四类不被扰动：

```python
FIELDS = ("person", "address", "phone", "company", "amount", "date")

# 金额 / 日期：0–9 全量数字 → 形近字母（OCR 常见；保证任意数值串都能造 typo）
DIGIT_TYPOS = {"0": "O", "1": "l", "2": "Z", "3": "E", "4": "A",
               "5": "S", "6": "G", "7": "T", "8": "B", "9": "q"}

NOISE_AFFIXES["amount"] = [("金额：", "prefix"), ("金额:", "prefix"), ("费用：", "prefix"),
                           ("（含税）", "suffix"), ("（未税）", "suffix"), ("。", "suffix")]
NOISE_AFFIXES["date"]   = [("日期：", "prefix"), ("日期:", "prefix"), ("（录入日期）", "suffix"),
                           ("（生效日）", "suffix"), ("。", "suffix")]
```

**② 新生成器**：

```python
def gen_amount(rng):
    """生成金额：数值 + 「元」；形态含整数 / 小数(1–2 位) / 千分位。"""
    intpart = rng.randint(1, 9_999_999)
    numeral = str(intpart)
    ndigits = rng.choice([0, 0, 1, 2])            # 多数整数，少数带小数
    if ndigits:
        numeral += "." + "".join(str(rng.randint(0, 9)) for _ in range(ndigits))
    if rng.random() < 0.5:
        numeral = _group(numeral)                 # 一半带千分位
    return numeral + "元", [numeral, "元"]

def gen_date(rng):
    """生成 ISO 日期 YYYY-MM-DD（1970–2026，日取 1–28 避开月长问题）。"""
    y = rng.randint(1970, 2026); m = rng.randint(1, 12); d = rng.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}", [str(y), f"{m:02d}", f"{d:02d}"]
```

**③ 新扰动器**（五类映射，全部保证 `脏值 ≠ 干净值`）：

```python
def perturb_amount(rng, value, parts):
    numeral = parts[0]
    return {
        "space":  _space(rng, value),                                  # 数字间插空格
        "typo":   _typo_at(rng, value, DIGIT_TYPOS),                   # 数字→形近字母
        "abbrev": _choose(rng, [_wan(numeral)], value),                # 元 → 万元（12800元→1.28万元）
        "sep":    _choose(rng, [_group(numeral) + "元",
                                numeral.replace(",", "") + "元",
                                _insert_sep(rng, numeral) + "元"], value),  # 千分位分组/去分组/乱插
        "noise":  _noise(rng, value, NOISE_AFFIXES["amount"]),         # 金额：前缀 / （含税）后缀
    }

def perturb_date(rng, value, parts):
    y, m, d = parts
    return {
        "space":  _space(rng, value),
        "typo":   _typo_at(rng, value, DIGIT_TYPOS),
        "abbrev": _choose(rng, [f"{int(y)}-{int(m)}-{int(d)}",         # 缺零 2026-1-5
                                f"{int(m)}-{int(d)}",                   # 缺年 1-5
                                f"{int(y)}-{int(m)}"], value),          # 年月 2026-10
        "sep":    _choose(rng, [value.replace("-", "/"),
                                value.replace("-", "."),
                                value.replace("-", "／")], value),     # 2026/10/06、2026.10.06
        "noise":  _noise(rng, value, NOISE_AFFIXES["date"]),           # 日期：前缀
    }
```

（`_wan` = 数值/10000 保留 4 位小数去尾零 + 「万元」；`_insert_sep` = 在数字串随机位置插半角/全角逗号；
`_group` = `f"{int(...):,}"` 只作用于整数部分、已带逗号也能用。）

## 3. 我亲跑过的自测（真实输出）

### 3.1 基线（§1.5）

```
$ git status --porcelain -uall
（无输出 —— 工作区干净）

$ git log --oneline -1
feca525 chore(handoff): TASK-017 已通过(1e3213b 验收结论，M1 全部收官) + 派 TASK-018 M2 评测集扩展 + aoci 同步
```

### 3.2 **改代码前**先证明「现有产物确由当前代码 + seed 42 生成」（不然改了分不清是谁的问题）

```
$ mkdir -p "C:/Users/38628/AppData/Local/Temp/zhclean_b018" \
  && uv run --project . python -m benchmarks.generate --seed 42 --out "C:/Users/38628/AppData/Local/Temp/zhclean_b018"
（输出为老四类汇总表，无 amount/date）

$ for k in clean dirty; do for f in person address phone company; do \
    cmp -s "benchmarks/$k/$f.jsonl" "C:/Users/38628/AppData/Local/Temp/zhclean_b018/$k/$f.jsonl" \
      && echo "OK  byte-identical: $k/$f.jsonl" || echo "DIFF: $k/$f.jsonl"; done; done
OK  byte-identical: clean/person.jsonl
OK  byte-identical: clean/address.jsonl
OK  byte-identical: clean/phone.jsonl
OK  byte-identical: clean/company.jsonl
OK  byte-identical: dirty/person.jsonl
OK  byte-identical: dirty/address.jsonl
OK  byte-identical: dirty/phone.jsonl
OK  byte-identical: dirty/company.jsonl
```

### 3.3 **改代码后**：老四类仍逐字节一致（对照 3.2 的基线目录）

```
$ uv run --project . python -m benchmarks.generate --seed 42 --out "C:/Users/38628/AppData/Local/Temp/zhclean_new018"
（汇总表已含 6 类；与 3.2 的基线目录逐字节比对：）
for k in clean dirty; do for f in person address phone company; do \
    cmp -s ".../zhclean_b018/$k/$f.jsonl" ".../zhclean_new018/$k/$f.jsonl" \
      && echo "OK   $k/$f.jsonl" || echo "DIFF $k/$f.jsonl"; done; done
OK   clean/person.jsonl
OK   clean/address.jsonl
OK   clean/phone.jsonl
OK   clean/company.jsonl
OK   dirty/person.jsonl
OK   dirty/address.jsonl
OK   dirty/phone.jsonl
OK   dirty/company.jsonl
```

### 3.4 判据 1：测试全绿

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 15%]
........................................................................ [ 30%]
........................................................................ [ 46%]
........................................................................ [ 61%]
........................................................................ [ 76%]
........................................................................ [ 92%]
....................................                                     [100%]
468 passed in 8.18s
```

> 原 467 + 新增 `test_new_field_shapes` 1 条 = 468。其余七条不变式是**函数内按 `FIELDS` 循环**，
> 不增加用例计数，但已自动覆盖 amount/date（六类的条数/唯一性/五扰动/truth/split/逐字节/防陈旧全测到）。

### 3.5 判据 2：老四类零 diff + 新增 4 个 jsonl

```
$ PYTHONUTF8=1 uv run --project . python -m benchmarks.generate --seed 42
seed=42 per_field=200 split_ratio=0.2
out=G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean\benchmarks
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

$ git diff --exit-code -- benchmarks/clean benchmarks/dirty
warning: in the working copy of 'benchmarks/clean/address.jsonl', LF will be replaced by CRLF the next time Git touches it
（其余 7 条同类 warning，略）
git-diff-exit=0

$ git status --porcelain -uall
 M benchmarks/generate.py
 M tests/test_benchmark.py
?? benchmarks/clean/amount.jsonl
?? benchmarks/clean/date.jsonl
?? benchmarks/dirty/amount.jsonl
?? benchmarks/dirty/date.jsonl
```

> `git diff --exit-code` **退出码 0**：老四类 8 个 jsonl 零 diff；4 个 amount/date 是 untracked（`??`），
> `git diff`（对已跟踪文件）看不到它们，符合预期。
> 那 8 条 `LF will be replaced by CRLF` warning 是 **`.gitattributes` 的 `* text=auto`** 触发的
> （jsonl 没有专门 eol 规则），**改前跑同样的命令也会报同样 8 条**（老四类文件），属**既存现象、非本单引入**；
> 磁盘上的产物是 LF（§3.7 已核 `\r` 不存在）。见 §5-4。

### 3.6 判据 3：抽查两行

```
$ head -2 benchmarks/clean/amount.jsonl
{"id": "amount-0001", "field": "amount", "value": "3210394.27元"}
{"id": "amount-0002", "field": "amount", "value": "741,631.97元"}

$ head -2 benchmarks/dirty/date.jsonl
{"id": "date-0001", "field": "date", "value": "1996-11　-07", "truth": "1996-11-07", "perturbation": "space", "split": "train"}
{"id": "date-0001", "field": "date", "value": "1996-11-0T", "truth": "1996-11-07", "perturbation": "typo", "split": "train"}
```

> clean 行 3 字段 `{id,field,value}`、dirty 行 6 字段 `{id,field,value,truth,perturbation,split}`，
> `truth` = 干净值（`date-0001` 干净值见 `clean/date.jsonl` 第 1 行 = `1996-11-07`）✓。

### 3.7 全量机械核验（两字段 2400 行）

```
$ PYTHONUTF8=1 uv run --project . python -c "…（见下）"
amount clean= 200 dirty= 1000 ids= 200 truth_mismatch= 0 variants_per_id= {5} dirty_eq_truth= 0
   clean has_CR= False
   dirty has_CR= False
date clean= 200 dirty= 1000 ids= 200 truth_mismatch= 0 variants_per_id= {5} dirty_eq_truth= 0
   clean has_CR= False
   dirty has_CR= False
```

> 脚本正文（此处为全文，未截断）：

```python
import json,pathlib
root=pathlib.Path('benchmarks')
for field in ('amount','date'):
    clean={json.loads(l)['id']:json.loads(l)['value'] for l in open(root/'clean'/f'{field}.jsonl',encoding='utf-8')}
    dirty=[json.loads(l) for l in open(root/'dirty'/f'{field}.jsonl',encoding='utf-8')]
    bad=[r for r in dirty if r['truth']!=clean[r['id']]]
    ids=set(r['id'] for r in dirty)
    per=set(len([r for r in dirty if r['id']==i]) for i in ids)
    eq=sum(1 for r in dirty if r['value']==r['truth'])
    print(field, 'clean=',len(clean),'dirty=',len(dirty),'ids=',len(ids),'truth_mismatch=',len(bad),'variants_per_id=',per,'dirty_eq_truth=',eq)
    for sub in ('clean','dirty'):
        raw=(root/sub/f'{field}.jsonl').read_bytes()
        print('  ',sub, 'has_CR=', b'\r' in raw)
```

### 3.8 五类扰动实际取值（目视核对，抽 `amount-0004` / `date-0001`）

```
amount-0004 truth='3633930.88元'
    space   -> '363　3930.88元'（全角空格）
    typo    -> 'E633930.88元'
    abbrev  -> '363.3931万元'
    sep     -> '3633930.8，8元'（全角逗号乱插）
    noise   -> '3633930.88元（含税）'
date-0001 truth='1996-11-07'
    space   -> '1996-11　-07'
    typo    -> '1996-11-0T'
    abbrev  -> '1996-11'（年月）
    sep     -> '1996.11.07'
    noise   -> '1996-11-07。'
```

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | 测试全绿 | **通过**：`468 passed`（原 467 + 1 新用例；七条不变式按字段自动覆盖新字段） | §3.4 |
| 2 | 老四类逐字节不变 | **通过**：`git diff --exit-code` 退出码 **0**（老四类 8 个 jsonl 零 diff）；新增 amount/date 4 个 jsonl | §3.3（改前/改后 cmp 8/8）+ §3.5 |
| 3 | 新字段可读核验 | **通过**：clean 3 字段 / dirty 6 字段 / truth 对应正确；2400 行全量 truth 零不符 | §3.6 + §3.7 |

**契约逐条核对（§2.5）**：
- schema 对齐 TASK-001（clean 3 字段 / dirty 6 字段 / `id=<field>-NNNN`）；**每类 200 干净 → 1000 脏行**（5×200）—— ✅（§3.7：各 field clean=200 dirty=1000）
- amount：干净值 = 数值 + 「元」；五类扰动 = space/typo/abbrev(万)/sep(千分位)/noise(金额前缀·含税后缀) —— ✅（§3.8）
- date：干净值 = ISO `YYYY-MM-DD`（1970–2026）；五类扰动 = space/typo/abbrev(缺零·缺年·年月)/sep(`/`、`.`)/noise(日期前缀) —— ✅
- 确定性：同 seed 两次逐字节一致（`test_same_seed_byte_identical` 覆盖六类）—— ✅；老四类 seed 42 逐字节不变 —— ✅
- CLI 不变：`python -m benchmarks.generate --seed 42 [--per-field 200 --split-ratio 0.2]`；stdout 汇总表含 **6 类** —— ✅（§3.5）

## 5. 遗留 / 不确定 / 需要拍板

### 5-1（**与契约示例的差异，请脑裁定**）amount 干净值**不含空格**
- §2.5 示例写作 `` `12800.5 元` ``（数字与「元」之间有一个空格）。我实现为**无空格**（`12800.5元`）。
- **理由**：M1 四类干净值**全部无空格**（`王小明`/`广东省…`/`13812345678`/`嘉兴…`），且口径是
  「**已规范的值原样返回、置信度 0.95**」——若干净值自带装饰性空格，则**每条金额都"不干净"**，
  0.95 语义会自相矛盾。故取「干净 = 规范形态（无空格）」。
- **若要改回带空格**：`gen_amount` 末行 `return numeral + "元"` → `numeral + " 元"`（1 行），
  且需注意此时 `space` 扰动的「数字间插空格」与干净值的空格要区分（建议 space 只插数字之间）。

### 5-2（**契约空白自定口径**）两处需脑确认
1. **abbrev 方向**：契约写「单位缩写「万」→ 数值」。我实现为 **干净用「元」基准、abbrev 改写成「万元」记法**
   （`12800元 → 1.28万元`），即「万」是脏侧的缩写形态、真值是元的数值。若脑的原意是**干净值即用万元、
   abbrev 展开为元**，则方向相反（改 `gen_amount` + `perturb_amount` 各一处）。
2. **typo 未生成「大写数字」轴**：契约提「大写数字错字「壹→壱」类」。因干净值是**阿拉伯数字**，
   我实现为**数字→形近字母**（`DIGIT_TYPOS`，复用电话的 OCR 思路、补全 0–9）。**没有**生成
   壹/贰/叁（大写中文数字）形态。若要该轴，属**新增干净值形态**（干净集会出现 `壹万贰仟…`），
   影响面较大，建议单开一单（且会牵动 TASK-019 的规则设计）。

### 5-3（**小瑕疵，可优化**）amount 干净值可能出现尾随 `.0`
- 生成时 1 位小数且末位为 0，会产出如 `3950098.0元`。**写法合法但不自然**（等于整数还带 `.0`）。
- 未改：不违反契约，且 `_unique_value` 保证唯一；若要消除，在 `gen_amount` 里对小数位 `rstrip("0").rstrip(".")`（1 行）。

### 5-4（**既存现象，非本单引入**）`git diff` 的 8 条 CRLF warning
- 触发源是 `.gitattributes` 的 `* text=auto`（jsonl 无专门 eol 规则）。**改前**对老四类跑同样命令
  会报**同样 8 条**；磁盘产物是 LF（§3.7 核过 `\r` 不存在），`test_same_seed_byte_identical` 也断言了无 `\r`。
- 建议（属**范围外**、本单未动）：`.gitattributes` 补一行 `*.jsonl text eol=lf` 消除歧义（走 §6 建议，不擅自改）。

### 5-5（其余申报）
- **未跑评测**（判据没要求；本单不写规则、不用词典调规则）⇒ **heldout 纪律不受影响**。
- 工具副产品：`__pycache__/`、`.pytest_cache/`（`.gitignore` 覆盖）。**无清单外新文件**。
- 临时目录 `.../Temp/zhclean_b018`、`.../zhclean_new018` 建在**仓库外**（用 `mkdir -p`，**未跑 `rm -rf`**）。
- 记忆库 `handoff-workflow-state.md` + `MEMORY.md`（工作区惯例，非业务代码，已在 RESULT-016/017/本单申报过）。
- `aoci.*` / `.aoci/` **一行没碰**（那是脑的收尾动作）。

## 6. 建议下一步

1. **TASK-019（M2 规则）**：按本单评测集写 amount/date 规范化规则——目标口径就是：
   - amount：去空格 → 去/正千分位 → 万↔元换算 → 去「金额：」前缀 /「（含税）」后缀，输出 `<数值>元`；
   - date：去空格 → 分隔符统一为 `-` → 补齐缺零/缺年（缺年**不可恢复**，应原样返回、低置信）→ 去「日期：」前缀。
2. 若采纳 §5-1（干净值带空格）或 §5-2（abbrev 方向 / 大写数字轴），**先在本单回执上拍板再进 TASK-019**，
   否则规则会照着错误形态写。
3. 可选：`.gitattributes` 补 `*.jsonl text eol=lf`（消除 §5-4 的 warning）。
4. 可选：`docs/failures-m1.md` 的 M1 数字**不受本单影响**（本单没碰 `src/**`，未重跑 heldout）。

## 7. 下次接着做什么（**写给"下一轮的你"**）

- **做到哪了**：TASK-018 全部落地，**未 commit、未动 TASK 状态字段**（归脑）。关键文件：
  `benchmarks/generate.py`（+amount/date）、`tests/test_benchmark.py`（FIELDS 六类 + 1 新用例）、
  `benchmarks/{clean,dirty}/{amount,date}.jsonl`（新，共 2400 行）。回执即本文件；
  三判据实据在 §3.4（468 passed）、§3.5（git diff exit 0）、§3.6（抽查）。
- **下一步第一件事**：读 `.handoff/inbox/` 里**编号最大**的 TASK（应是你单 TASK-019：M2 amount/date 规则）；
  先看脑对 §5-1/§5-2 的处置（**金额干净值是否带空格、abbrev 方向**——这两个直接决定规则怎么写）。
- **要绕开的坑**：
  1. **`rm -rf` 是禁区**；清/建临时目录用 `mkdir -p <全新名字>`（本单再次确认）。
  2. **改 `generate.py` 后必须验老四类逐字节不变**：先 `mkdir -p <tempA>` 跑改前产物，
     改完再跑 `<tempB>`，`cmp` 8 个文件——**别只看 `git diff`**（untracked 新文件在 `git diff` 里看不见）。
  3. **每字段独立 RNG 是命门**：`random.Random(f"{seed}:{field}")`；新字段只能**追加**到 `FIELDS`、
     词典只能**加键**，别改旧字段的生成器/扰动器/`NOISE_AFFIXES` 旧列表。
  4. **`newline="\n"`** 落盘（`dump()` 已处理）；判「有无 CRLF」看**字节** `b"\r" in raw`。
  5. 一次性证据脚本的中文输出：本机默认 cp936，临时 `PYTHONUTF8=1` 才可读（产品入口自己调 `utf8_stdio()`）。
  6. 判据命令一律 `uv run --project .` 前缀；`git diff` 的 CRLF warning 是既存现象（§5-4），别当成 diff。

## 8. 脑侧验收（2026-10-08）

**判据亲跑**：①468 passed ✓；②老四类 `git diff --exit-code` = 0（逐字节不变）+ amount/date 4 个新 jsonl ✓；③抽查 schema/truth 正确，2400 行全量核验（回执 §3.7 实据）✓。边界零越界（generate.py + test_benchmark.py + 4 产物）。

**三个拍板点裁决（脑定）**：
1. **金额干净值无空格（采纳手的实现）**：理由成立——M1 干净值全无空格 + 「已规范⇒0.95」语义自洽；契约示例改口，TASK-019 按无空格写规则。
2. **abbrev 方向（采纳）**：元基准 → 万元记法（12800元→1.28万元）；TASK-019 规则方向 = 万元展开为元。
3. **大写数字轴（采纳「单开一单」）**：属新增干净值形态，牵动面大，排 TASK-019 之后单独做。

§5-4 CRLF warning：脑侧顺手在 .gitattributes 补 `*.jsonl text eol=lf`（治理件，非手任务）。

审查结论：**通过**。RNG 流隔离证明完整（改前/改后 cmp 8/8 + git diff 0）；七条不变式按字段循环自动覆盖新字段的设计省事且不降覆盖。

**里程碑：M2 评测集就位（六类字段），TASK-019 可开工。**

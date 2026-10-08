# RESULT-023　对应 TASK-023

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-09 |
| 结论 | **完成**（generate.py 扩展 idcard/email 两字段；老六类 seed 42 产物**逐字节不变**；判据 1/2/3 全过。一处契约自相矛盾的解读见 §5-a） |

## 1. 改了哪些文件

| 文件 | 改了什么 | 行数 |
|---|---|---|
| `benchmarks/generate.py` | 加 `gen_idcard`（GB 11643 校验码）+ `gen_email`；加 `perturb_idcard`/`perturb_email` + `_insert_local_sep`；加词典 `EMAIL_LOCAL_CHARS`/`EMAIL_DOMAINS`/`EMAIL_TYPOS`/`IDCARD_TYPOS` + `_ID_WEIGHTS`/`_ID_CHECK_CODES`/`_id_check_digit`；`NOISE_AFFIXES` 补 idcard/email 两条；`FIELDS` 追加两字段（**只追加**）；`GENERATORS`/`PERTURBERS` 各注册两项 | +92 −6 |
| `tests/test_benchmark.py` | `FIELDS` 扩到 8 类；新增 `test_idcard_email_shapes`（独立重算 GB 11643 校验码 + email 形态）；模块 docstring 同步 | +30 −2 |
| `benchmarks/clean/idcard.jsonl`、`benchmarks/clean/email.jsonl`、`benchmarks/dirty/idcard.jsonl`、`benchmarks/dirty/email.jsonl` | **新产物**（各 200 clean / 1000 dirty） | 新增 4 文件 |

`git status --porcelain -uall` 共 **6 项**（2 `M` + 4 `??`），**逐条落在 `_Boundary:_` 内，零越界**；`src/zhclean/**`、`benchmarks/evaluate*.py`、`pyproject.toml` **零改动**。

## 2. 关键 diff 摘要

**字段注册（只追加，不动老字段）**

```diff
-FIELDS = ("person", "address", "phone", "company", "amount", "date")
+FIELDS = ("person", "address", "phone", "company", "amount", "date", "idcard", "email")
 GENERATORS = {..., "date": gen_date,
+              "idcard": gen_idcard, "email": gen_email}
 PERTURBERS = {..., "date": perturb_date,
+              "idcard": perturb_idcard, "email": perturb_email}
```

**idcard 生成器 + GB 11643 校验码**

```python
# GB 11643-1999 校验码：前 17 位加权求和 mod 11 → 查表（'10X98765432'）
_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK_CODES = "10X98765432"

def _id_check_digit(first17: str) -> str:
    total = sum(int(ch) * w for ch, w in zip(first17, _ID_WEIGHTS))
    return _ID_CHECK_CODES[total % 11]

def gen_idcard(rng):
    region = f"11{rng.randint(0, 9999):04d}"        # 11 打头（北京结构）
    y = rng.randint(1970, 1999)                     # ← §5-a：与 abbrev「补19」取交集
    birthday = f"{y:04d}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"
    seq = f"{rng.randint(0, 999):03d}"
    first17 = region + birthday + seq
    check = _id_check_digit(first17)
    return first17 + check, [region, birthday, seq, check]
```

**idcard 五类扰动**（abbrev = 18→15 老证；sep = 只给生日段加分隔）

```python
def perturb_idcard(rng, value, parts):
    region, birthday, seq, check = parts
    return {
        "space": _space(rng, value),                 # 段间 / 数字间空格
        "typo": _typo_at(rng, value, IDCARD_TYPOS),  # 数字→形近字母（校验位 X 不在表内，不受影响）
        "abbrev": region + birthday[2:] + seq,       # 丢掉世纪「19」与校验码 → 15 位
        "sep": region + f"{birthday[:4]}-{birthday[4:6]}-{birthday[6:]}" + seq + check,
        "noise": _noise(rng, value, NOISE_AFFIXES["idcard"]),
    }
```

**email 生成器 + 五类扰动**

```python
EMAIL_DOMAINS = ["gmail.com", "qq.com", "163.com", "126.com", "sina.com", "sohu.com",
                 "foxmail.com", "outlook.com", "hotmail.com", "yahoo.com", "aliyun.com",
                 "139.com", "189.cn", "example.com", "company.net", "school.edu",
                 "test.org", "mail.cn"]          # com/cn/net/org/edu 全在
EMAIL_TYPOS = {"0": "o", "1": "l", "2": "z", "5": "s", "6": "g", "8": "b",
               "o": "0", "l": "1", "z": "2", "s": "5", "g": "6", "b": "8"}   # 双向

def gen_email(rng):
    n = rng.randint(3, 12)
    for _ in range(1000):
        user = "".join(rng.choice(EMAIL_LOCAL_CHARS) for _ in range(n))
        if user[0].isalpha() and any(c.isdigit() for c in user):   # 字母开头 + 含数字
            break
    else:
        raise RuntimeError("造不出「字母开头且含数字」的邮箱用户名")
    domain = rng.choice(EMAIL_DOMAINS)
    return f"{user}@{domain}", [user, domain]

def perturb_email(rng, value, parts):
    user, domain = parts
    head, tld = domain.rsplit(".", 1)
    return {
        "space": user + rng.choice([" @", "@ "]) + domain,   # @ 前后空格
        "typo": _typo_at(rng, value, EMAIL_TYPOS),           # 至少 1 处
        "abbrev": _choose(rng, [f"{user}@{head}.{tld[:-1]}",  # .com → .co
                                f"{user}@{head}"], value),    # @gmail.com → @gmail
        "sep": f"{_insert_local_sep(rng, user)}@{domain}",    # user 里插多余的点/下划线
        "noise": _noise(rng, value, NOISE_AFFIXES["email"]),
    }
```

**测试（独立重算校验码，不复用生成器实现）**

```python
FIELDS = ("person", "address", "phone", "company", "amount", "date", "idcard", "email")

def test_idcard_email_shapes(data):
    for r in data["idcard"]["clean"]:
        v = r["value"]
        assert re.fullmatch(r"11\d{4}\d{8}\d{3}[\dX]", v)
        y, m, d = int(v[6:10]), int(v[10:12]), int(v[12:14])
        assert 1970 <= y <= 1999 and 1 <= m <= 12 and 1 <= d <= 28
        expect = _ID_C[sum(int(c) * w for c, w in zip(v[:17], _ID_W)) % 11]
        assert v[17] == expect                      # ← 按 GB 11643 可验证
    for r in data["email"]["clean"]:
        v = r["value"]
        assert re.fullmatch(r"[a-z][a-z0-9]{2,11}@[a-z0-9]+\.(com|cn|net|org|edu)", v)
        assert any(c.isdigit() for c in v.split("@")[0])
```

## 3. 我亲跑过的自测（真实输出）

### 3.1 §1.5 基线

```
$ git status --porcelain -uall
```

（**无输出** = 工作区干净；HEAD = `5ebdebb`）

### 3.2 生成到仓库外临时目录（不直接覆盖仓库文件）

```
$ uv run --project . python -m benchmarks.generate --seed 42 --out "G:/Agentwork_mvp/_t023_gen"
seed=42 per_field=200 split_ratio=0.2
out=G:\Agentwork_mvp\_t023_gen
field    split      clean  dirty
person   train        160    800
person   heldout       40    200
address  train        160    800
address  heldout       40    200
phone    train        160    800
phone    heldout       40    200
company  train        160    800
company    heldout       40    200
amount   train        160    800
amount   heldout       40    200
date     train        160    800
date     heldout       40    200
idcard   train        160    800
idcard   heldout       40    200
email    train        160    800
email    heldout       40    200
```

### 3.3 老六类逐字节比对（临时目录 vs 仓库）

```
$ for kind in clean dirty; do
    for f in person address phone company amount date; do
      if cmp -s "benchmarks/$kind/$f.jsonl" "G:/Agentwork_mvp/_t023_gen/$kind/$f.jsonl"; then
        echo "SAME  $kind/$f.jsonl"
      else
        echo "DIFF  $kind/$f.jsonl"
      fi
    done
  done
SAME  clean/person.jsonl
SAME  clean/address.jsonl
SAME  clean/phone.jsonl
SAME  clean/company.jsonl
SAME  clean/amount.jsonl
SAME  clean/date.jsonl
SAME  dirty/person.jsonl
SAME  dirty/address.jsonl
SAME  dirty/phone.jsonl
SAME  dirty/company.jsonl
SAME  dirty/amount.jsonl
SAME  dirty/date.jsonl
```

（12/12 SAME ⇒ 确认后才 `cp` 回填 4 个新文件进仓库。）

### 3.4 判据 1 —— 测试全绿

```
$ uv run --project . pytest tests/ -q
........................................................................ [ 12%]
........................................................................ [ 25%]
........................................................................ [ 38%]
........................................................................ [ 50%]
........................................................................ [ 63%]
........................................................................ [ 76%]
........................................................................ [ 89%]
.............................................................            [100%]
565 passed in 6.09s
```

（564 → **565**，新增 `test_idcard_email_shapes` 一条。）

### 3.5 判据 2 —— 老六类零 diff

```
$ git diff --exit-code -- benchmarks/clean benchmarks/dirty; echo "exit=$?"
exit=0
```

（老六类 12 个 jsonl 零改动；idcard/email 4 个是**新增未跟踪**文件，`git diff` 里本就不出现 —— 与判据措辞一致。）

### 3.6 变更清单（边界证明）

```
$ git status --porcelain -uall
 M benchmarks/generate.py
 M tests/test_benchmark.py
?? benchmarks/clean/email.jsonl
?? benchmarks/clean/idcard.jsonl
?? benchmarks/dirty/email.jsonl
?? benchmarks/dirty/idcard.jsonl
```

### 3.7 判据 3 —— 新字段可读核验（抽查 clean 2 行 / dirty 2 行）

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json
def load(p): return [json.loads(l) for l in open(p,encoding="utf-8") if l.strip()]
for f in ("idcard","email"):
    for kind in ("clean","dirty"):
        rows=load(f"benchmarks/{kind}/{f}.jsonl")
        print(f"--- {kind}/{f}.jsonl  共 {len(rows)} 行  前 2 行 ---")
        for r in rows[:2]:
            print("   ", json.dumps(r, ensure_ascii=False))
'
--- clean/idcard.jsonl  共 200 行  前 2 行 ---
    {"id": "idcard-0001", "field": "idcard", "value": "110412197605131500"}
    {"id": "idcard-0002", "field": "idcard", "value": "116047198805081999"}
--- dirty/idcard.jsonl  共 1000 行  前 2 行 ---
    {"id": "idcard-0001", "field": "idcard", "value": "11041219760513 1500", "truth": "110412197605131500", "perturbation": "space", "split": "heldout"}
    {"id": "idcard-0001", "field": "idcard", "value": "11041219760513150O", "truth": "110412197605131500", "perturbation": "typo", "split": "heldout"}
--- clean/email.jsonl  共 200 行  前 2 行 ---
    {"id": "email-0001", "field": "email", "value": "a232zxb3s@139.com"}
    {"id": "email-0002", "field": "email", "value": "um7dy@hotmail.com"}
--- dirty/email.jsonl  共 1000 行  前 2 行 ---
    {"id": "email-0001", "field": "email", "value": "a232zxb3s@ 139.com", "truth": "a232zxb3s@139.com", "perturbation": "space", "split": "train"}
    {"id": "email-0001", "field": "email", "value": "a232zx83s@139.com", "truth": "a232zxb3s@139.com", "perturbation": "typo", "split": "train"}
```

### 3.8 五类扰动样例（idcard-0001 / email-0001）+ 校验码独立复核

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json, re
W=(7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2); C="10X98765432"
def ck(s): return C[sum(int(c)*w for c,w in zip(s[:17],W))%11]
def load(p): return [json.loads(l) for l in open(p,encoding="utf-8") if l.strip()]
clean=load("benchmarks/clean/idcard.jsonl")
bad=[r["value"] for r in clean if not re.fullmatch(r"11\d{16}[\dX]", r["value"]) or len(r["value"])!=18 or ck(r["value"])!=r["value"][17]]
print("idcard 干净 200 条：形态或校验码非法数 =", len(bad))
print("样例校验码：", [(v, ck(v)) for v in [r["value"] for r in clean[:3]]])
d=load("benchmarks/dirty/idcard.jsonl")
byid={r["id"]:r["value"] for r in clean}
print("idcard 脏行 truth 与干净值不符数 =", sum(1 for r in d if r["truth"]!=byid[r["id"]]))
print("idcard 脏行 truth 校验码非法数 =", sum(1 for r in d if ck(r["truth"])!=r["truth"][17]))
print("--- idcard-0001 五类扰动 ---")
for r in d:
    if r["id"]=="idcard-0001": print("  %-7s %s" % (r["perturbation"], r["value"]))
print("--- email-0001 五类扰动 ---")
for r in load("benchmarks/dirty/email.jsonl"):
    if r["id"]=="email-0001": print("  %-7s %s" % (r["perturbation"], r["value"]))
'
idcard 干净 200 条：形态或校验码非法数 = 200
样例校验码： [('110412197605131500', '0'), ('116047198805081999', '9'), ('117395198604076294', '4')]
idcard 脏行 truth 与干净值不符数 = 0
idcard 脏行 truth 校验码非法数 = 0
--- idcard-0001 五类扰动 ---
  space   11041219760513 1500
  typo    11041219760513150O
  abbrev  110412760513150
  sep     1104121976-05-131500
  noise   110412197605131500（本人）
--- email-0001 五类扰动 ---
  space   a232zxb3s@ 139.com
  typo    a232zx83s@139.com
  abbrev  a232zxb3s@139.co
  sep     a232zx_b3s@139.com
  noise   Email:a232zxb3s@139.com
```

⚠️ **上一条命令的输出里 `非法数 = 200` 是那段命令自身的正则写错**（`11\d{16}[\dX]` = **19** 位，实际值 18 位）⇒ 该"非法数"统计**无效**。**样例校验码**与**脏行两行**才是有效证据：样例 ck 与末位逐个相等（`…1500`→`0`、`…1999`→`9`、`…6294`→`4`），脏行 truth 与干净值不符数 = 0、校验码非法数 = 0。

**改对正则后重跑（去掉正则，只按长度/数字/前缀/校验码判）**：

```
$ PYTHONUTF8=1 uv run --project . python -c '
import json
W=(7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2); C="10X98765432"
def ck(s): return C[sum(int(c)*w for c,w in zip(s[:17],W))%11]
def load(p): return [json.loads(l) for l in open(p,encoding="utf-8") if l.strip()]
clean=load("benchmarks/clean/idcard.jsonl")
bad=[r["value"] for r in clean if len(r["value"])!=18 or not r["value"][:17].isdigit()
     or r["value"][17]!=ck(r["value"]) or not r["value"].startswith("11")]
print("idcard 干净 200 条：长度/数字/校验码/前缀 任一非法数 =", len(bad))
'
idcard 干净 200 条：长度/数字/校验码/前缀 任一非法数 = 0
```

（样例 `110412…1500`：地区码 `110412`、生日 `19760513`、顺序 `150`、校验 `0` → 18 位 GB 形态；abbrev 得 15 位 `110412760513150` 正好是「去世纪 + 去校验码」。email abbrev `a232zxb3s@139.co` = `.com→.co` 形态。）

### 3.9 改动统计

```
$ git diff --stat -- benchmarks/generate.py tests/test_benchmark.py
 benchmarks/generate.py  | 98 +++++++++++++++++++++++++++++++++++++++++++++++--
 tests/test_benchmark.py | 32 ++++++++++++++--
 2 files changed, 124 insertions(+), 6 deletions(-)
```

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | `uv run --project . pytest tests/ -q` 全绿（原 564 + 新增用例） | **过**：565 passed / 0 failed（新增 `test_idcard_email_shapes`：idcard 校验码独立重算 + email 形态） | §3.4 |
| 2 | `python -m benchmarks.generate --seed 42` 后老六类 `git diff --exit-code` 零 diff，新出现 4 个 jsonl，exit 0 | **过**：`exit=0`；另以 `cmp` 逐个核老六类 12 文件 **12/12 SAME** 后才回填新产物 | §3.3、§3.5 |
| 3 | 抽查 clean 2 行 / dirty 2 行：schema 正确、truth 与干净值对应、idcard 校验码合法 | **过**：schema 6 字段齐、truth 指向对应干净值（不符数 0）；idcard 全长 200 条校验码**独立重算** 0 非法 | §3.7、§3.8 |

## 5. 遗留 / 不确定 / 需要拍板

### a（**须脑拍板**：§2.5 的一条自相矛盾，按「最窄读法」处理）

- §2.5 对 idcard 生日同时写了两条**互斥**要求：
  1. 「8 位生日（**同 date 范围**）」⇒ date 范围是 `1970–2026`；
  2. abbrev「**19xx 年补「19」**+ 校验码重算」⇒ 只有 19xx 的生日才能靠补「19」无损还原。
- 若生日落到 2000–2026，则 15→18 展开要补的是「20」，与「补 19」不符 ⇒ abbrev 变成**部分不可逆**。
- **我的处理**：按 findings.md 已固化的「手遇矛盾 → 最窄读法 + 回执申报」，取**交集** ⇒ 生日年 `rng.randint(1970, 1999)`（月/日仍同 date：1–12 / 1–28）。这样两条要求**同时成立**，18↔15 缩写无损可逆。
- **若脑本意是全世纪 1970–2026**（abbrev 有意做成「只对 19xx 可逆」的部分不可逆型）：改一行（`1970, 1999` → `1970, 2026`）+ 重生成即可，**老六类仍逐字节不变**。请脑给一句口径。

### b（口径提示：email abbrev 的 `.co` 形态在 2 字符 TLD 上退化）

- 契约写「去 TLD 末位（`.com` → `.co`）」，我按字面对**所有** TLD 统一执行 ⇒ `189.cn` → `189.c`、`school.edu` → `school.ed`、`company.net` → `company.ne`、`test.org` → `test.or`。
- 其中 `189.c` 观感偏怪（虽仍是「去一位」的合法缩写形态，且另一候选 `@189` 形态不受影响）。**实测**：`benchmarks/dirty/email.jsonl` 的 abbrev 里 `.c` 形态共 **6 条**（`189.c` 5 + `mail.c` 1）。
- 未做特殊化是**故意保守**（字面执行、不擅自加分支）；若脑想去掉 `.c` 形态（例如只在 `.com` 上做 `→.co`），属新口径，本单不改。

### c（工具副产品申报，按豁免清单）

- `tests/__pycache__/*.pyc`、`benchmarks/__pycache__/`：pytest 运行产生的解释器缓存（豁免清单内，已申报）。
- 仓库**外**临时目录 `G:\Agentwork_mvp\_t023_gen\`：本单生成用的中间产物，**未入仓库**（§7 建临时目录用 `mkdir -p` 全新名字，非 `rm -rf`）。
- 仓库内无清单外新文件（`git status -uall` 仅 §3.6 的 6 项）。

## 6. 建议下一步

1. **脑验收**：判据 1/2/3 已备齐可核证据；请裁 §5-a 的生日范围口径、知悉 §5-b 的 `.c` 形态。
2. **TASK-024（规则）**：写 `idcard`/`email` 的 normalize——idcard 需 15↔18 展开（补「19」+ **重算校验码**）+ 位数/生日/校验码格式闸门；email 需去空白 / 形近还原（`o↔0`、`l↔1`…）/ 去前缀标签。
3. **TASK-025（评测接入 + 重定版）**：`benchmarks/evaluate.py` 的 `FIELDS` 追加 idcard/email ⇒ **heldout 须重跑、重新定版**；届时**老六类数字必须逐位复现 M2 定版**（72.00 / 90.50 / 100.00 / 81.00 / 100.00 / 84.00、总 87.92%），这是「只加字段不改旧字段」的验收硬判据。
4. **TASK-026（文档）**：README 定版表扩到八类 + `docs/failures-m3.md`。

## 7. 下次接着做什么（**写给「下一轮的你」**）

- **做到哪了**：TASK-023 —— `benchmarks/generate.py` 追加 `idcard`/`email` 两字段（干净值 + 五类扰动 + train/heldout 划分），新增 4 个产物；`tests/test_benchmark.py` 扩到 8 类 + 加 `test_idcard_email_shapes`。**565 passed**；老六类 12 文件 `cmp` 全 SAME、`git diff` exit 0。回执即本文件。
- **下一步第一件事**：等脑验收 + 裁 §5-a（生日范围）；若通过，下一单是 TASK-024 写 idcard/email 的**规则**（别在本单基础上改规则）。
- **要绕开的坑**：
  1. **本单只写生成器，不写规则** —— `src/zhclean/**` 一行未动（规则是 TASK-024）。
  2. **加字段的纪律**：只许**追加**到 `FIELDS`/`GENERATORS`/`PERTURBERS`、只许**加键**到词典；每字段独立 RNG（`random.Random(f"{seed}:{field}")`）是老字段不变的命门。
  3. **改生成器后必须验老字段逐字节不变**：**先生成到仓库外**（`mkdir -p` 全新目录名，非 `rm -rf`）→ 逐个 `cmp`（8 字段时是 14 个非目标文件）→ **确认无误再 `cp` 回填**。别直接覆盖仓库文件再回滚；也别只信 `git diff`（新产物是 untracked，`git diff` 里看不见）。
  4. **贴证据时的正则/命令自己先跑通**：本单踩过两次「自写正则位数数错」（`11\d{16}[\dX]` 是 19 位）导致贴出的「非法数=200」是**假红**。判校验码用 `len(v)==18 and v[17]==ck(v[:17])` 这种**不依赖正则**的写法最稳。
  5. **heldout 纪律**：本单**没跑** heldout（未接评测）；定版留到 TASK-025，跑一次即锁。
  6. 判据命令一律 `uv run --project .` 前缀；一次性证据脚本要 `PYTHONUTF8=1` 中文才不乱码。
  7. **TASK 状态字段不动**（归脑）；不 `git commit`。

## 8. 脑侧验收（2026-10-09）

**判据亲跑（三全过）**：①565 passed 零失败 ✓；②老六类 `git diff --exit-code` = 0（12/12 cmp SAME 互为印证）✓；③抽查 schema 正确、idcard 200 条校验码独立重算 0 非法、truth 与干净值不符数 0 ✓。边界零越界（6 手侧文件，`src/zhclean/**` 零改动）。

**§5 两拍板裁决（脑定）**：
- **§5-a 生日范围**：**采纳手的交集方案（1970–1999）**——优先保证 18↔15 abbrev 无损可逆；我 TASK-023 §2.5 的两条要求互斥（「同 date 范围 1970–2026」vs「abbrev 补 19」）是脑侧写作缺陷，手按 findings 已固化的「最窄读法 + 申报」处置正确，不记失分。**教训再记一笔：§2.5 内部各条也要交叉自洽（已是第二次同类问题）。**
- **§5-b email `.c` 形态（189.c 共 6 条）**：**接受现状**——字面执行合法、样本小；规则侧对不可恢复缩写按「不猜」原样返回，属 abbrev 天花板的一部分，不做特殊化。

§3.8 手自曝「非法数=200」是自写正则位数数错（19 位正则）造成的假红、随后用不依赖正则的判法重验——**诚实披露与自我纠错，正确**。

审查结论：**通过**。idcard 校验码按 GB 11643 真算法 + 测试独立重算（不复用生成器实现）是干净做法；「先出仓库外再 cmp 回填」纪律延续。

**里程碑：M2 第三批评测集就位（八类字段），TASK-024 规则可开工。**

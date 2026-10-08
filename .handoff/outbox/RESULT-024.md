# RESULT-024　对应 TASK-024

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-09 |
| 结论 | 完成（**含一处按「最窄读法」对契约的收窄，见 §5-a，需脑拍板**） |

---

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/rules/idcard.py` | **新建**。身份证规范化：GB 11643 校验码闸门 + 结构清洗 + 数字形近修复 + 15→18 补全 | 137（新） |
| `src/zhclean/rules/email.py` | **新建**。邮箱规范化：形态闸门 + 结构清洗 + **只修「位置可判定」的形近字** | 176（新） |
| `src/zhclean/rules/__init__.py` | 注册 `idcard` / `email` 到 `DISPATCH`；模块头「六类」→「八类」 | +5 −1 |
| `tests/test_idcard.py` | **新建**。44 条 | 173（新） |
| `tests/test_email.py` | **新建**。41 条（含八字段回归护栏） | 158（新） |

**`src/zhclean/rules/common.py` 未动**（不需要新公共机制；`strip_noise` / `strip_ws_sep` / `apply_table` / `CONF_*` 已够用）⇒ 实际改动集是本单 `_Boundary:_` 的**真子集**。

**申报的工具副产品（豁免清单外无新增）**：
- `src/zhclean/{,rules/,tools/}__pycache__/`、`tests/__pycache__/` —— 解释器缓存（豁免清单第 1 类，未入库）。
- `G:\Agentwork_mvp\_t024_scratch\`（**仓库外**）—— 我这次写的一次性脚本 `measure.py`（量测强制位覆盖率）与 `train_loop.py`（判据 2 的 train 回环）。按纪律建在仓库外、未 `rm -rf`。

---

## 2. 关键 diff 摘要

**`__init__.py`（唯一被修改的已跟踪文件，完整 diff）**：
```diff
-R: rules/{person,address,phone,company,amount,date}.py（六类字段已全部注册）
+R: rules/{person,address,phone,company,amount,date,idcard,email}.py（八类字段已全部注册）
@@
+from .email import normalize_email
+from .idcard import normalize_idcard
@@
     "date": normalize_date,
+    "idcard": normalize_idcard,
+    "email": normalize_email,
 }
```

**`idcard.py` 闸门（强判据，独立实现不抄生成器）**：
```python
_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK_CODES = "10X98765432"

def _valid18(s: str) -> bool:
    return len(s) == 18 and s[:17].isdigit() and s[17] == _check_digit(s[:17])
```
15→18 补全（补「19」+ **重算**校验码）：
```python
def _expand15(s: str) -> str | None:
    if len(s) != 15 or not s.isdigit():
        return None
    first17 = s[:6] + _CENTURY + s[6:]        # _CENTURY = "19"
    return first17 + _check_digit(first17)
```

**`email.py` 还原层（本单的核心取舍 —— 只修「位置本身可判定」的字符）**：
```python
def _repair_forced(value: str) -> tuple[str, bool]:
    """只修「位置本身可判定」的形近字。`@` 与 `.` 一律不动。"""
    user, sep, dom = value.partition("@")
    if not sep:
        return value, False
    hit = False
    if user and user[0] in DIGIT_TO_ALPHA:      # ③ user 首字符必是字母
        user = DIGIT_TO_ALPHA[user[0]] + user[1:]; hit = True
    new_dom, dom_hit = _repair_domain(dom)      # ① TLD 必字母 ② 域名主体黑白分明
    ...
```
`_repair_heterogeneous`：域名主体混入的「异类」**恰 1 个**才修，≥2 个不猜（分不清错哪个）。

---

## 3. 我亲跑过的自测（真实输出）

### 3.1 §1.5 基线

开工时工作树干净（`git status --porcelain -uall` 无输出）、`HEAD = 049c84f`。
写完本回执后再跑（**最终真实状态**，含回执自身）：

```
$ git status --porcelain -uall
 M src/zhclean/rules/__init__.py
?? .handoff/outbox/RESULT-024.md
?? src/zhclean/rules/email.py
?? src/zhclean/rules/idcard.py
?? tests/test_email.py
?? tests/test_idcard.py
$ git rev-parse --short HEAD
049c84f
```

> 业务改动 5 个路径**逐条 ⊆ `_Boundary:_`**；第 6 行 `.handoff/outbox/RESULT-024.md` 是**交接机制本身**（CLAUDE.md 豁免清单第 3 类，`.handoff/` 未被 gitignore ⇒ 会显示，但不算越界）。`HEAD` 与开工时一致（脑未提交，我未动 git）。

### 3.2 模块自检（`python -m` 直接跑）

```
$ PYTHONUTF8=1 uv run --project . python -m zhclean.rules.idcard
idcard._demo: OK
$ PYTHONUTF8=1 uv run --project . python -m zhclean.rules.email
email._demo: OK
```

### 3.3 判据 1：全量测试

```
$ PYTHONUTF8=1 uv run --project . pytest tests/ -q
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
........................................................................ [ 44%]
........................................................................ [ 55%]
........................................................................ [ 66%]
........................................................................ [ 77%]
........................................................................ [ 88%]
........................................................................ [ 99%]
..                                                                       [100%]
650 passed in 6.71s
```
> 上面是**全长输出**（10 行进度条 + 汇总行），未截断。
拆分与回归（证明「原 565 全绿」未被破坏）：
```
$ PYTHONUTF8=1 uv run --project . pytest tests/test_idcard.py -q
44 passed in 0.03s
$ PYTHONUTF8=1 uv run --project . pytest tests/test_email.py -q
41 passed in 0.03s
$ PYTHONUTF8=1 uv run --project . pytest tests/ -q --ignore=tests/test_idcard.py --ignore=tests/test_email.py
565 passed in 6.27s
```
> 565（原）+ 44 + 41 = **650** ✓

### 3.4 判据 2：train 回环自测（只读 train，不跑评测管线、不跑 heldout）

命令（脚本在仓库外）：`PYTHONUTF8=1 uv run --project . python G:/Agentwork_mvp/_t024_scratch/train_loop.py`
```
==== idcard：train 回环 800/800 = 100.00% ====
  space   160/160
  noise   160/160
  sep     160/160
  abbrev  160/160
  typo    160/160

==== email：train 回环 412/800 = 51.50% ====
  space   160/160
  noise   160/160
  sep       0/160
  abbrev    0/160
  typo     92/160
    [失败/typo] 脏值='a232zx83s@139.com'  真值='a232zxb3s@139.com'  得到='a232zx83s@139.com'
    [失败/typo] 脏值='uizaz8kr4y@outlook.com'  真值='uizazbkr4y@outlook.com'  得到='uizaz8kr4y@outlook.com'
    [失败/abbrev] 脏值='a232zxb3s@139.co'  真值='a232zxb3s@139.com'  得到='a232zxb3s@139.co'
    [失败/abbrev] 脏值='um7dy@hotmail.co'  真值='um7dy@hotmail.com'  得到='um7dy@hotmail.co'
    [失败/sep] 脏值='a232zx_b3s@139.com'  真值='a232zxb3s@139.com'  得到='a232zx_b3s@139.com'
    [失败/sep] 脏值='um7d.y@hotmail.com'  真值='um7dy@hotmail.com'  得到='um7d.y@hotmail.com'
```
> 每个失败类只打 2 条样例（脚本 `len(fails[p]) < 2` 截断）——**此处为截断输出，非全长**（v1.2 第四条）。

### 3.5 「零改坏」核验（失败行是**原样未改**，不是改成了别的值）

```
$ PYTHONUTF8=1 uv run --project . python -c "
import json,sys,collections
sys.path.insert(0,'src'); import zhclean
def load(p): return [json.loads(l) for l in open(p,encoding='utf-8') if l.strip()]
print('字段  总数  改对  原样未改  改成了别的值(改坏)')
for f in ('idcard','email'):
    rows=[r for r in load(f'benchmarks/dirty/{f}.jsonl') if r['split']=='train']
    c=collections.Counter()
    for r in rows:
        g=zhclean.normalize(r['value'],f)
        if g==r['truth']: c['改对']+=1
        elif g==r['value']: c['原样未改']+=1
        else: c['改坏']+=1
    print(f'{f:6s} {len(rows):4d} {c[\"改对\"]:5d} {c[\"原样未改\"]:9d} {c[\"改坏\"]:14d}')
"
字段  总数  改对  原样未改  改成了别的值(改坏)
idcard  800   800         0              0
email   800   412       388              0
```
> **改坏 = 0**。这是本库「宁可漏改，绝不改坏」的实据：所有未修对的 email 行都是**逐字原样返回**。

---

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | 测试全绿（原 565 + 新增） | ✅ **650 passed**（565 原有全绿 + 44 idcard + 41 email） | §3.3 |
| 1a | idcard 五类代表用例 | ✅ space/noise/sep/typo/abbrev 各多例 | `tests/test_idcard.py` |
| 1b | 15→18 展开 + **校验码重算** | ✅ 含交叉验证（第 18 位 == 独立重算的 GB 11643 校验码） | `test_abbrev_expansion_recomputes_check_digit` |
| 1c | typo 修复过闸门 | ✅ l→1 / T→7 / 两处形近一次复核 | `test_confusable_digits_repaired` |
| 1d | 坏校验码不采纳 | ✅ 4 例（校验码错 / 17 位 / 19 位 / 含 A）均原样 0.1 | `test_bad_check_digit_stays_untouched` |
| 1e | 0.95 档 | ✅ 两字段合法值均 `(value, 0.95)` | `test_clean_value_untouched_and_high_confidence` |
| 1f | email 去空白 / 前缀 | ✅ 半角/全角空白；`Email:` / `E-mail:` / `邮箱：`（大小写不敏感） | `test_space_stripped` / `test_noise_stripped` |
| 1g | email typo **双向** | ✅ 数字→字母（`h0tmail`→`hotmail`）、字母→数字（`l26`→`126`） | `test_confusable_repaired_both_directions` |
| 1h | abbrev 与 sep **不猜** | ✅ 5 例原样返回 | `test_abbrev_not_guessed` / `test_sep_not_guessed` |
| 1i | 闸门 | ✅ 空/无 @/无点/无 user/两个 @ 均 0.1 | `test_gate_rejects_non_email` |
| 1j | **八字段回归护栏** | ✅ 老六类各 1 条代表用例不变；`set(DISPATCH)` 恰八类 | `test_old_six_fields_unaffected` / `test_all_eight_fields_registered` |
| 2 | train 回环自测（如实报） | ✅ idcard **100.00%**、email **51.50%**；**零改坏** | §3.4 / §3.5 |

---

## 5. 遗留 / 不确定 / 需要拍板

### 5-a ⚠️ email 还原层我**收窄**了契约的字面写法（**需脑拍板**）

**契约原话**（TASK-024 §2.5）：「typo：形近还原（`o↔0 l↔1 …` 双向）——只修 user 段与 domain 的字母位，`@` 与点不动；**修完过闸门才采纳**」。
契约同时要求：「已规范（过闸门）→ 0.95」。

**问题**：email 的闸门是**宽松形态闸门**（`名字@带点的域名`），**对单字符形近替换没有判别力** —— 干净值 `a232zxb3s@139.com` 与脏值 `a232zxb3s@139.c0m` 同样过闸门。因此：
1. **盲修**（照表逐字替换）会把干净值的 `.com` 改成 `.c0m` 并当作「推断命中 0.7」返回 ⇒ **改坏**，且使契约要求的「已规范 → 0.95」对**任何干净邮箱**都不可达（第 2 层先于第 3 层吞掉它）。
2. 我实测过盲修：train typo 只 **19.4%**（`单点/首个候选 双向`）；`改坏` 风险确凿。

**我按 findings.md 的「最窄读法 + 回执申报」处理**：把还原层收窄为**位置本身可判定**的三条（判据都是契约里已有的形态约束）：

| 判据 | 依据 |
|---|---|
| ① TLD 必是**字母** ⇒ TLD 里的形近数字即错 | 域名常识 |
| ② 域名主体**黑白分明**（全字母 / 全数字）⇒ 混入的**恰 1 个**异类即错 | 实测 train 160/160 干净域名主体皆黑白分明 |
| ③ user **首字符必是字母** ⇒ 首位若是形近数字即错 | 契约「user 字母开头」 |

结果：train typo **92/160 = 57.5%**（①24 + ②64 + ③4，互不重叠），**零改坏**；三条判据都**不会命中任何规范值**（故 §3.5 的 `改坏=0` 是结构性的，不是碰巧）。

**请脑裁定**：
- **(A) 认可本收窄**（推荐）—— 保持现状；
- **(B) 要字面盲修** —— 我改 `_repair_forced` 一处即可，代价是干净邮箱会被改坏（且 0.95 档对 email 名存实亡）；
- **(C) 加更宽的判据**（域名白名单 / TLD 白名单）—— 属**新口径**、有过拟合风险，请脑先定。

### 5-b email 的已知天花板（**契约已明示，属正确口径**，此处只做数字兑现）

- **sep 0/160、abbrev 0/160**：契约明写「不猜 —— 原样低置信」，我**逐字执行**，无异议。
- **user 段内部错字不修**：train 160 条 typo 里有 **68 条**错在 user 段内部（如 `a232zx83s`）。形态闸门与域名证据都管不到 user 段内部（`w0avx` 里的 `0` 可能是真数字）⇒ 无判据 ⇒ **不猜**。这是 email typo 停在 57.5% 的全部原因。

### 5-c sep / abbrev 的**置信度落 0.95**，而非契约写的 0.1

宽松闸门认不出「截断」（`.co` 过闸门）⇒ 它们落进「值已规范 0.95」档。这与 common.py 已记录在案的 **0.95 已知阴影**同源（`RESULT-015 §5-2`：「看起来合法、其实是截断/缺段」的脏值也会落 0.95）。
**要紧的部分是值原样未改**（§3.5 已证）。若脑要求压回 0.1，需给 0.95 加更严判据（如 TLD 白名单）——属新口径，与 5-a(C) 是同一个决定。

### 5-d idcard 无遗留

强闸门（校验码）使「形近修复」与「15→18 补全」都能**先猜后验**，猜错必然过不了闸门 ⇒ 不存在改坏路径，train 100.00%、零改坏。契约里 idcard 部分**逐条照做，无偏离**。

---

## 6. 建议下一步

1. **脑验收本单**；`_Boundary:_` 比对命令（可直接复制）：
   ```bash
   git diff --name-only 049c84f..HEAD && git status --porcelain -uall
   ```
   期望：业务改动集 = `src/zhclean/rules/{__init__.py,idcard.py,email.py}` + `tests/test_{idcard,email}.py`；
   另有 `.handoff/outbox/RESULT-024.md`（豁免清单第 3 类）。**无其它**。
2. **TASK-025（评测接入 + heldout 重定版）前请先裁 §5-a 与 §5-c** —— 它们直接决定 email 的 heldout 预期。
3. **TASK-025 的口径提醒**：新增两类会**拉低总平均**（email 天花板 ≈51.5%、idcard ≈100%）。请脑在派单时明确总分是「**八类平均**」还是「老六类 / 新两类分列」——否则新定版数与 M2 的 87.92% 不可比。
4. 若要提 email typo：优先考虑 5-a(C) 的**域名白名单**（公开常识域名，不是生成器词典），但请脑先裁是否值得为此开工。

---

## 7. 下次接着做什么（写给「下一轮的你」）

- **做到哪了**：TASK-024 手侧完成 —— `src/zhclean/rules/{idcard,email}.py` 新建并注册进 `DISPATCH`（八类齐全），`tests/test_{idcard,email}.py` 85 条；全量 **650 绿**；train 回环 idcard **100%** / email **51.5%**、**零改坏**。回执即本文件。
- **下一步第一件事**：等脑验收。验收通过后由脑派 **TASK-025**（评测接入：把 idcard/email 加进 `benchmarks/evaluate.py` 的字段表 + heldout 重定版）。**别提前动 `benchmarks/**`**（TASK-024 禁区）。
- **要绕开的坑**：
  1. `zhclean.normalize(...)` 返回**字符串**（不是 tuple）—— 我这次写测试时误用 `[0]`，取到首字符，造出 7 条假红。要 `(值, 置信度)` 请用 `normalize_with_confidence`。
  2. **别对 email 做盲修**（理由见 §5-a）：宽松闸门挡不住单字符替换，会改坏干净值。
  3. email 里**不能用** `common.strip_ws_sep`（它会把 `.` `_` 一起删掉），要用只含空白的 `_WS_RE`。
  4. 15 位老证**必须重算**校验码（不能照抄任何一位）；补的世纪位是 `"19"`，依据是生日口径 1970–1999（RESULT-023 §5-a 已裁决）。

## 8. 脑侧验收与结构化代码审查（2026-10-09）

**范围**: workspace（基线 049c84f）｜可审文件: 5 ｜已审: 5 ｜跳过: 0 ｜覆盖率: 5/5
（idcard.py 137 行全文 / email.py 176 行全文 / __init__ 注册 / test_idcard 44 例 / test_email 41 例）
按严重度: critical 0, high 0, medium 0, low 0

**判据亲跑**：①650 passed（565 原全绿 + 44 + 41，拆分验证过）✓；②train 回环（脑复核 §3.5 口径）：idcard 800/800 = 100.00%、email 412/800 = 51.50%，**两字段改坏均为 0**（失败行全部逐字原样返回）✓。边界零越界（5 手侧文件，common.py 未动）。

审查结论：**通过，零发现**。idcard 的强闸门（校验码重算）让「任意位置形近修复」有理论依据（猜错 1/11 概率过闸，模块头论证完整）；email 的「位置可判定才修」三条判据（TLD 必字母 / 主体黑白分明恰 1 异类 / user 首字母）零改坏是结构性保证；`_WS_RE` 拒绝 strip_ws_sep（点/下划线在邮箱有语义）细节正确。

**§5 三裁决（脑定）**：
- **§5-a 采纳 (A) 认可收窄**——手的论证成立：宽松形态闸门对单字符替换无判别力，字面盲修会把干净值 `.com`→`.c0m` 改坏且使 0.95 档失效；契约两条要求互斥是脑侧设计缺陷，收窄为位置判据是正确工程决策，不记失分。**教训记 findings：修复层激进程度必须匹配闸门强度——强闸门可盲修（idcard/phone），弱闸门只修「位置可判定」字符（email）。**
- **§5-c 接受现状**——sep/abbrev 落 0.95 属 0.95 已知阴影（RESULT-015 §5-2）实例，值原样未改是要紧的；压回 0.1 需 TLD 白名单（新口径），不为合成数据场景开工。
- **§6-3 采纳**——TASK-025 总分口径 = 八类平均 + **老六类分列对照 M2 定版**（不混算一个总平均糊弄，新定版数与 87.92% 不可比要写明）。

**里程碑：八类字段规则全部就位（idcard 100% / email 51.5% 顶口径天花板、双零改坏）。**

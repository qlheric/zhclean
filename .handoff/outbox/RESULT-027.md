# RESULT-027　对应 TASK-027

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-09 |
| 结论 | 完成（判据 1/2/3 全过；有 2 处契约空白由我按下述最窄读法定，见 §5） |
| 基线 | HEAD = `497b8c7`（TASK-026 验收提交，本单开工前工作区干净） |

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/tools/table.py` | **新建**：`clean_table()` 整表清洗（CSV 读 → 列映射 → 逐格 `normalize_with_confidence` → 原位替换 + 报告）；`FIELDS` 取自 `rules.DISPATCH`；可选整行去重；`_demo()` 自检 8 组断言 | 227 行（新） |
| `src/zhclean/cli.py` | 加 `table` 子命令（parser + `_cmd_table` + `_columns_arg` + `_write_csv`）；模块头 F/R/A/S 与用法示例同步；**其余四个子命令零改动** | +67 −3 |
| `tests/test_table.py` | **新建**：23 例单测（列映射 自动/显式、未匹配列原样、逐格替换、报告统计、hitl、dedupe 4 例、短行容忍、BOM 路径、确定性、空/仅表头、参数错误、不改进参、demo） | 146 行（新） |
| `tests/test_cli.py` | 加 table 端到端 9 例 + 参数错误 4 例 + `table` 并入两处 `-m` 入口参数化（+2）；`test_help_lists_four_subcommands` 更名 `test_help_lists_all_five_subcommands` 并加 `table` | +97 −14 |
| `docs/examples/sample.csv` | **新建**：8 列 × 3 行样例（列名 = 字段名，另含 `id`/`备注` 两个未映射列；第 1 行全脏、第 2 行全干净、第 3 行另一个人的半脏行） | 4 行（新） |

**申报（清单外新文件，CLAUDE.md 豁免条款要求申报）**
- `.handoff/outbox/RESULT-027.md` —— 本回执，交接机制本身（豁免类 3）。
- **惯例收尾动作**（v1.1 §3 要求申报）：更新了**仓库外**的记忆快照 `C:\Users\38628\.claude\projects\G--Agentwork-mvp-s2----------zhclean\memory\handoff-workflow-state.md` 与同目录 `MEMORY.md`（把 TASK-026 标为已通过、记 TASK-027 交付内容与两处待拍板、补两条坑）。**未触碰任何业务代码**；本单 5 个文件的修改时间未被这几步影响。
- 仓库**外**：`G:\Agentwork_mvp\_t027_scratch\`（`out.csv` / `a.txt` / `b.txt`）—— 临时输出目录，按惯例建在仓库外，不在仓库内。
- `__pycache__/`、`.pytest_cache/`：pytest / 解释器副产品（豁免类 1），`git status --porcelain -uall` 未列出（已被 .gitignore 覆盖）。

**边界自检**：`git status --porcelain -uall` 列出的改动集合 = 上面 5 个文件，与 TASK §2 `_Boundary:_` 声明逐条相同，**无越界、无未申报新文件**。

## 2. 关键 diff 摘要

**2.1 `clean_table` 契约实现（`src/zhclean/tools/table.py`）**

```python
FIELDS: tuple[str, ...] = tuple(DISPATCH)          # 字段名唯一真相源 = 规则库注册表

def clean_table(src, dst=None, columns=None, dedupe=False) -> dict:
    reader = csv.reader(io.StringIO(_read_csv_text(src)))
    table = [row for row in reader if any(cell.strip() for cell in row)]   # 丢全空行
    header = table[0] if table else []
    rows = table[1:]
    col_map = _resolve_columns(header, columns)     # None ⇒ 列名 == 字段名 自动匹配
    unmapped = [h for h in header if h not in col_map]
    cleaned, changed_cells, by_field = _clean_rows(header, rows, col_map)
    ...
    return {"header", "rows", "rows_out", "changed_cells", "report"}
```

逐格清洗（`_clean_rows`）——**原位替换**，行序与列数不变：

```python
field = col_map.get(header[i]) if i < len(header) else None
if field is None:
    continue                                   # 未映射列 / 超长行的多余格：原样保留
after, conf = normalize_with_confidence(cell, field)
if after != cell:  changed_cells += 1; stat["changed"] += 1
else:              stat["unchanged"] += 1
if isinstance(conf, (int, float)) and conf < HITL_THRESHOLD:  stat["hitl"] += 1
new_row[i] = after
```

**2.2 `table` 子命令（`src/zhclean/cli.py`）**

```python
def _cmd_table(args, stdin, stdout, stderr) -> int:      # 清洗在 table.clean_table，本层只读/写/汇总
    text = _read_text(args.input, stdin)
    try:
        result = clean_table(io.StringIO(text), columns=args.columns, dedupe=args.dedupe)
    except ValueError as e:
        raise CliError(f"整表清洗失败：{e}") from None
    _write_csv(result["header"], result["rows"], args.out, stdout)
    print(f"table：共 {rep['rows_in']} 行 × {rep['cols']} 列，改了 {result['changed_cells']} 格"
          f"，输出 {result['rows_out']} 行{dd}", file=_info_stream(args, stdout, stderr))
```
- `--columns` 在 argparse 层就校验（缺 `=`／字段不属八类／列名重复 ⇒ 退出码 2）；列名不在表头 ⇒ 运行期 `CliError` ⇒ 退出码 1。
- `_write_csv` 用 `StringIO` 先渲染再落盘 ⇒ 逐字节确定；空表（连表头都没有）**不写任何字节**，不吐孤零零的换行。

**2.3 整行去重语义（本单唯一一处"按最窄读法改口径"，理由见 §5-2）**

```python
per_row[i][列下标] = 去重组号          # 每格经 dedupe_adaptive 落组
for i in range(n):
    for k in range(i + 1, n):
        common = a.keys() & b.keys()
        if common and all(a[c] == b[c] for c in common):   # 每一列都同组才并
            uf.union(i, k)
```

## 3. 我亲跑过的自测（真实输出）

> 环境：`PYTHONIOENCODING=utf-8`；命令一律 `uv run --project .` 前缀（TASK §6）。
> 下面每段输出与它正上方的命令**严格对应**；只有两处带过滤，均在该处标注：
> （a）pytest 输出用 `| tail -N` 截尾 —— §3.1 两段；（b）§3.6 的确定性 `cmp` 两条把 stderr 丢弃（`2>/dev/null`，因为只比 stdout 字节）。其余为原样粘贴。

**3.1 判据 1 —— 全量测试**（命令带 `| tail -3`，**此处为截尾后的输出**）

```
$ PYTHONIOENCODING=utf-8 uv run --project . pytest tests/ -q 2>&1 | tail -3
........................................................................ [ 94%]
.........................................                                [100%]
689 passed in 6.73s
```

新增用例数（`--collect-only`，非截尾）：

```
$ PYTHONIOENCODING=utf-8 uv run --project . pytest tests/test_table.py -q --collect-only 2>&1 | tail -2
23 tests collected in 0.03s

$ PYTHONIOENCODING=utf-8 uv run --project . pytest tests/test_cli.py -q --collect-only 2>&1 | tail -2
66 tests collected in 0.04s
```
即：本单新建 `tests/test_table.py` 收集 **23** 例；`tests/test_cli.py` 现收集 **66** 例。全量 689 与 TASK-026 回执记录的 650 之差 = 39（其中 23 例出自 `test_table.py`，其余 16 例出自 `test_cli.py` 的新增/参数化）。

**3.2 判据 2 —— demo 自检**

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -m zhclean.tools.table; echo "exit=$?"
table._demo: OK
exit=0
```

**3.3 判据 3 —— cli 端到端（原始样例）**

```
$ PYTHONIOENCODING=utf-8 uv run --project . zhclean table --input docs/examples/sample.csv; echo "exit=$?"
table：共 3 行 × 8 列，改了 8 格，输出 3 行
id,person,phone,company,address,idcard,email,备注
1,范童言,13800138000,嘉兴数联贸易集团有限公司,贵州省贵阳市城关区建设路596号,110412197605131500,sbe1hdy@hotmail.com,未映射列原样保留
2,范童言,13800138000,嘉兴数联贸易集团有限公司,贵州省贵阳市城关区建设路596号,110412197605131500,sbe1hdy@hotmail.com,本行已是干净值
3,孟露峰,13800138000,数联贸易集团有限公司,贵阳市城关区建设路596号,110412197605131500,sbe1hdy@hotmail.com,第三行
exit=0
```

**3.4 「改了 8 格」逐格对账**（防止汇总数字是编的；命令里 `-c` 内联脚本无输出截断，原样粘贴）

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -c "
import csv,io
from pathlib import Path
from zhclean.tools.table import clean_table
p=Path('docs/examples/sample.csv')
raw=[r for r in csv.reader(p.read_text(encoding='utf-8-sig').splitlines())]
res=clean_table(p)
for i,(a,b) in enumerate(zip(raw[1:],res['rows']),1):
    for h,x,y in zip(res['header'],a,b):
        if x!=y: print(f'行{i} {h}: {x!r} -> {y!r}')
print('changed_cells =', res['changed_cells'])
print('by_field =', res['report']['by_field'])
"; echo "exit=$?"
行1 person: '范 童言' -> '范童言'
行1 phone: '+86 138-0013-8000' -> '13800138000'
行1 company: '公司名称：嘉兴 数联贸易集团有限公司' -> '嘉兴数联贸易集团有限公司'
行1 idcard: '11041219760513 1500' -> '110412197605131500'
行1 email: 'sbe1hdy@ hotmail.com' -> 'sbe1hdy@hotmail.com'
行3 phone: '138 0013 8000' -> '13800138000'
行3 idcard: '1104121976-05-131500' -> '110412197605131500'
行3 email: 'sbe1hdy@hotmail.com。' -> 'sbe1hdy@hotmail.com'
changed_cells = 8
by_field = {'person': {'changed': 1, 'unchanged': 2, 'hitl': 0}, 'phone': {'changed': 2, 'unchanged': 1, 'hitl': 0}, 'company': {'changed': 1, 'unchanged': 2, 'hitl': 0}, 'address': {'changed': 0, 'unchanged': 3, 'hitl': 0}, 'idcard': {'changed': 2, 'unchanged': 1, 'hitl': 0}, 'email': {'changed': 2, 'unchanged': 1, 'hitl': 0}}
exit=0
```

**3.5 `--dedupe` + `--out`（输出文件内容也为真实粘贴）**

```
$ PYTHONIOENCODING=utf-8 uv run --project . zhclean table --input docs/examples/sample.csv --dedupe --out "G:/Agentwork_mvp/_t027_scratch/out.csv"; echo "exit=$?"
table：共 3 行 × 8 列，改了 8 格，输出 2 行，去重后去掉 1 行
exit=0
$ cat "G:/Agentwork_mvp/_t027_scratch/out.csv"
id,person,phone,company,address,idcard,email,备注
1,范童言,13800138000,嘉兴数联贸易集团有限公司,贵州省贵阳市城关区建设路596号,110412197605131500,sbe1hdy@hotmail.com,未映射列原样保留
3,孟露峰,13800138000,数联贸易集团有限公司,贵阳市城关区建设路596号,110412197605131500,sbe1hdy@hotmail.com,第三行
```

**3.6 边界情形与退出码（每条命令都是可原样复制的完整命令行）**

```
$ printf '姓名,手机,备注\n范 童言,+86 138-0013-8000,x\n' | PYTHONIOENCODING=utf-8 uv run --project . zhclean table --columns "姓名=person,手机=phone"; echo "exit=$?"
table：共 1 行 × 3 列，改了 2 格，输出 1 行
姓名,手机,备注
范童言,13800138000,x
exit=0

$ PYTHONIOENCODING=utf-8 uv run --project . zhclean table --columns "person" </dev/null; echo "exit=$?"
usage: zhclean table [-h] [--input INPUT] [--columns COLUMNS] [--out OUT]
                     [--dedupe]
参数错误：argument --columns: 列映射须写成 列名=字段，收到 'person'
（加 --help 查看用法）
exit=2

$ PYTHONIOENCODING=utf-8 uv run --project . zhclean table --columns "person=bogus" </dev/null; echo "exit=$?"
usage: zhclean table [-h] [--input INPUT] [--columns COLUMNS] [--out OUT]
                     [--dedupe]
参数错误：argument --columns: 字段须是八类之一 ('person', 'address', 'phone', 'company', 'amount', 'date', 'idcard', 'email')，收到 'bogus'
（加 --help 查看用法）
exit=2

$ PYTHONIOENCODING=utf-8 uv run --project . zhclean table --columns "不存在=person" --input docs/examples/sample.csv; echo "exit=$?"
错误：整表清洗失败：列名 '不存在' 不在表头中（表头：['id', 'person', 'phone', 'company', 'address', 'idcard', 'email', '备注']）
exit=1

$ PYTHONIOENCODING=utf-8 uv run --project . zhclean table --input "no_such.csv"; echo "exit=$?"
错误：输入文件不存在：no_such.csv
exit=1

$ PYTHONIOENCODING=utf-8 uv run --project . zhclean table --input docs/examples/sample.csv > "G:/Agentwork_mvp/_t027_scratch/a.txt" 2>/dev/null
$ PYTHONIOENCODING=utf-8 uv run --project . zhclean table --input docs/examples/sample.csv > "G:/Agentwork_mvp/_t027_scratch/b.txt" 2>/dev/null
$ cmp "G:/Agentwork_mvp/_t027_scratch/a.txt" "G:/Agentwork_mvp/_t027_scratch/b.txt" && echo "cmp: 相同"
cmp: 相同

$ printf '' | PYTHONIOENCODING=utf-8 uv run --project . zhclean table; echo "exit=$?"
table：共 0 行 × 0 列，改了 0 格，输出 0 行
exit=0
```
（说明：上面各条按序执行；`usage:` 两行是 argparse 标准英文骨架，按真实输出粘贴、未截断。确定性两条丢弃 stderr，理由见本节开头。）

**3.7 基线 / 边界（TASK §1.5）**

```
$ git status --porcelain -uall
 M src/zhclean/cli.py
 M tests/test_cli.py
?? docs/examples/sample.csv
?? src/zhclean/tools/table.py
?? tests/test_table.py
$ git rev-parse --short HEAD
497b8c7
```

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | 测试全绿 `uv run --project . pytest tests/ -q` | ✅ 689 passed（TASK-026 回执记 650，本单 +39；其中 `tests/test_table.py` 独立收集 23 例） | §3.1。覆盖了简报点名的全部项：列映射（显式见 §3.6 第一条 / 自动见 §3.3）、未匹配列原样（`备注` 三行保持不变）、逐格替换正确（§3.4 八格对账）、报告统计（§3.4 `by_field`）、dedupe 路径（§3.5 + 单测 4 例）、cli 端到端 tmp 文件往返（`test_table_end_to_end_tmp_file_roundtrip`）、退出码（0/1/2 各一例，§3.6）、确定性（`test_table_determinism` + §3.6 的 `cmp`） |
| 2 | demo 自检 `python -m zhclean.tools.table` | ✅ `table._demo: OK`，exit 0 | §3.2。`_demo()` 断言 8 组（≥6 满足 §2.5） |
| 3 | cli 端到端 `zhclean table --input docs/examples/sample.csv` | ✅ exit 0；汇总「共 3 行 × 8 列，改了 8 格，输出 3 行」；stdout 是合法 CSV（4 行 8 列、列对齐） | §3.3（原样）。`docs/examples/sample.csv` 本身可被 csv 解析且各行等宽，见 `test_table_sample_csv_is_legal` |

## 5. 遗留 / 不确定 / 需要拍板

**5-1 `clean_table` 的 `dst` 参数：接了但不写（按最窄读法）**
契约签名给了 `dst=None`，同一段又写「**纯函数不写文件**（写盘是 cli 层）」。我按「纯函数」优先：`dst` 仅为接口对称保留、传值被忽略，`src` 也只**读**（路径或已打开文本流，utf-8-sig 容 BOM）。已在函数 docstring 写明。**若脑要的是"传 dst 就落盘"，这是改一处 3 行的事，请拍板。**

**5-2 `dedupe=True` 的「整行」判定：我按最窄读法取「每一列都同组」（需脑确认）**
契约只写「对整行做 `dedupe_adaptive` 去重」，没定「任一列同组」还是「每列都同组」。我**先**按「任一列同组」实现，结果在自家样例上就翻了车：`sample.csv` 第 1/3 行是**两个不同的人**（范童言 / 孟露峰），只因手机、身份证、邮箱三列相同被并成一行（`输出 1 行，去掉 2 行`）。这与 `tools/dedupe.py` 自己声明的口径（口径 1：「只在同一 field 内比较」）相冲——把"同行共有一格"当成"同一行"。
改为最窄读法后：**每一列都同 dedupe 组才算重复行**（各列合取，只在共有映射列上比；无共有映射列的行绝不并），`sample.csv --dedupe` 得 `输出 2 行，去掉 1 行`（第 1/2 行并、第 3 行保留，§3.5）。回归守卫写进 `_demo` 5b 与 `test_dedupe_requires_all_columns_to_match`。
**依据**：RESULT-015 §5-1「手遇到矛盾按最窄读法 + 回执申报」。若脑认为该用「任一列同组」（例如"同一手机号必是同一人"的业务假设），**一行改动量，按脑的口径改**——但请注意该读法会误并不同姓名者。

**5-3 基线命令是"写完文件后才跑的"（诚实申报）**
TASK §1.5 要求「开工前第一件事」跑 `git status --porcelain -uall`。我实际是**先把文件写出来了才补跑**，所以 §3.7 贴的是**完工后**的工作区状态，不是开工前快照。开工前基线可由两点推出：HEAD = `497b8c7`（TASK-026 验收提交，此后无任何提交落库）、工作区原有跟踪文件均未被改（当前 `M` 的两个文件正是本单产物）。**若脑要求严格快照，这条算流程瑕疵，不掩盖。**

**5-4 本单范围只到 CSV**
`csv` 是 stdlib，零新依赖；XLSX 需加 `openpyxl`（改 `pyproject.toml`），按 TASK §6 的约定另单。**未做，也未擅自加依赖。**

**5-5 表很大时去重是 O(n²)**
行两两比较（`_dedupe_rows`），已在代码里留 `# ponytail:` 注释标注上限与升级路径（按首列分桶）。当前样例量级无影响，未优化。

## 6. 建议下一步

1. **README 补 `table` 一节**（快速上手 / 字段表 / 与 XLSX 的边界）。README 在 TASK §4 禁区内，本单**未动**；建议脑单开一小单（或授权本单追加），否则发布时"一键清洗整张表"这个卖点在文档里不存在。
2. **XLSX 另单**：加 `openpyxl` 依赖 + `table` 支持 `.xlsx`（列映射与 `clean_table` 复用，只换读写层）。
3. **`--dedupe` 口径拍板**（§5-2）：确认「每列都同组」还是「任一列同组」。
4. **可选**：`table` 增加 `--unmapped {keep,drop,error}`，让"表里出现没映射的列"可显式控制（现在的行为是固定 keep + 报告里列出）。

## 7. 下次接着做什么（写给"下一轮的你"）

- 做到哪了：TASK-027 已交付 —— `src/zhclean/tools/table.py`（整表清洗，CSV，八类逐格规范化 + 可选整行去重）、`src/zhclean/cli.py` 的 `table` 子命令、`tests/test_table.py`（23 例）、`tests/test_cli.py`（新增 16 例）、`docs/examples/sample.csv`。全套 689 绿，demo OK，端到端 OK。**已写 `.handoff/outbox/RESULT-027.md`，停在这里等脑验收。未动 TASK 状态字段，未 git add / commit。**
- 下一步第一件事：等脑验收 TASK-027。若脑打回，最可能的点是 **§5-2 的 dedupe 口径**（改 `_dedupe_rows` 里那个 `all(...)` 合取）或 **§5-1 的 `dst` 是否该落盘**（改 `clean_table` 尾部 3 行）；两处都定位在 `src/zhclean/tools/table.py` 单文件内，改动量都很小。若脑通过，下一单大概率是 README 的 `table` 一节 或 XLSX 支持。
- 要绕开的坑：
  1. **`--dedupe` 别用「任一列同组」**——会把共有一格（共用手机号 / 同一发证地）的**不同人**并成一行，`sample.csv` 上立刻可见（§5-2）。
  2. **写 CSV 测试数据时值里别带逗号**——会被 csv 拆列，我第一版 `test_unmapped_column_kept_verbatim...` 就栽在这（`  12,345.00  ` 拆成两格）；测试失败先怀疑数据，别急着改代码。
  3. `git add -N` 也算 `git add`（TASK §4 禁区）——要数行就用 `wc -l` / `git diff --numstat`，**别碰索引**（TASK-026 已踩过一次）。
  4. 汇总走哪条流看 `--out`：有 `--out` 时汇总走 stdout，无 `--out` 时汇总走 stderr、stdout 是纯 CSV（`_info_stream`）。写新用例断言输出前先想清这条。

## 8. 脑侧验收与结构化代码审查（2026-10-09）

**范围**: workspace（基线 497b8c7）｜可审文件: 5 ｜已审: 5 ｜跳过: 0 ｜覆盖率: 5/5
（table.py 227 行全文 + cli.py table 部分 + test_table 23 例 + test_cli 新增 16 例 + sample.csv）
按严重度: critical 0, high 0, medium 0, low 0

**判据亲跑（三全过）**：①689 passed（650 + 39）；②`table._demo: OK`（8 组断言）；③cli 端到端 exit 0、汇总「8 格」与 §3.4 逐格对账一致、stdout 合法 CSV。边界零越界（5 手侧文件）。

审查结论：**通过，零发现**。字段唯一真相源取自 `DISPATCH`（八类自动同步）；逐格替换 + 未映射列原样 + 短行容忍的边界处理正确；`--columns` 参数错/运行错分层（退出码 2/1）符合既有退出码语义；确定性有 `cmp` 字节级实据。

**§5 三拍板裁决（脑定）**：
1. **§5-1 dst 保留不写：采纳**——「纯函数不写文件、写盘在 cli 层」是本仓一贯分层（audit 同款）；TASK 契约两处自相矛盾是脑侧写作疏漏。
2. **§5-2 dedupe「每一列都同组」：采纳**——手的「先试任一列、翻车后改合取」的实证过程很有说服力（共手机号/身份证会误并不同人）；且与 dedupe.py「同一 field 内比较」的既定口径一致。**跨字段合取是唯一正确语义。**
3. **§5-3 基线命令后跑：接受、不记失分**——如实申报不掩盖；HEAD 与工作区证据可推出基线，无实际影响。

§5-5 O(n²) 上限已注释标注升级路径（首列分桶），当前量级无碍。§6 建议：README 补 table 节排 TASK-028。

**里程碑：整表清洗落地（zhclean table 五子命令齐全）——发布前最后一块功能完成。**

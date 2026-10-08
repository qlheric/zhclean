# RESULT-028　对应 TASK-028

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-09 |
| 结论 | 完成（判据 1/2/3 的可核项全过；**1 处 `_Boundary:_` 与 §2.5 冲突未执行，见 §5-1**） |
| 基线 | HEAD = `263cd01`，工作区干净（`git status --porcelain -uall` 无输出，开工前亲跑） |

## 1. 改了哪些文件

| 文件 | 改了什么 | 行数变化 |
|---|---|---|
| `README.md` | ①新增 **`## 整表清洗（table）`** 一节（7 条要点）；②快速上手加**第 4 条命令**（`table --input docs/examples/sample.csv`）+ 样例说明改成两份样例 + 效果块加 `table：共 3 行 × 8 列…`；③**措辞统一**「老六类」→「M1+M2 六类」（5 处）；④顶部「三件工具」→「四件工具」（+`table`）、首句加「+ 整表清洗」；⑤路线加「整表清洗（CSV 已完成）」一条 | 119 → **141** 行（`git diff --numstat`: +33 −11） |
| `docs/release-checklist.md` | 按现状**重写**：M1 时代（467 passed、M1 数字、三条命令、四个 demo）→ v0.1.0（689 passed、八类定版分列、四条命令、五个 demo）；已核项打 `[x]` 并注明亲跑，未完成项打 `[ ]` 并注明待办（干净机器安装、CI 首跑、git tag、GitHub 建仓）；新增 **F. 文档面** 一节 | 70 → **95** 行（`git diff --numstat`: +65 −40） |

**未改动**（TASK §2 范围外，一个字都没碰）：`src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`、`.handoff/**`（除本回执）。

**申报（清单外新文件）**
- `.handoff/outbox/RESULT-028.md` —— 本回执，交接机制本身（豁免类 3）。
- **惯例收尾动作**（v1.1 §3 要求申报）：更新**仓库外**记忆快照 `C:\Users\38628\.claude\projects\G--Agentwork-mvp-s2----------zhclean\memory\handoff-workflow-state.md` 与同目录 `MEMORY.md`（标 TASK-027 已通过 `edca08f`、记 TASK-028 交付与待拍板项）。**未触碰任何业务代码**。

**边界自检**（`git status --porcelain -uall`，完工后）：
```
 M README.md
 M docs/release-checklist.md
```
= `_Boundary:_` 声明的两个文件，**无越界、无未申报新文件**。

## 2. 关键 diff 摘要

**2.1 README 新增小节**（插在「快速上手」与「Benchmark」之间）

```markdown
## 整表清洗（table）

上面几个工具一次处理一行 jsonl；`table` 一次处理**整张表**——按列名把每列映射到八类字段，逐格规范化，未映射的列一格都不动。

```bash
zhclean table --input docs/examples/sample.csv                   # 列名 == 字段名时自动匹配
zhclean table --input docs/examples/sample.csv --dedupe          # 清洗后整行去重
zhclean table --input docs/examples/sample.csv --out clean.csv   # 写文件（缺省写 stdout）
```
```
七条要点：列映射（自动 / `--columns` 显式）｜未映射列原样保留（`id`/`备注`）｜汇总口径（「改了 X 格」= 逐字符不同）｜`--dedupe` 语义（**每一列都同组**才算重复行，共用手机号的两个人不会并）｜流向与退出码｜暂只支持 CSV（stdlib 零依赖）、XLSX 待支持。

**2.2 快速上手第 4 条**

```bash
# 4. 整表清洗：CSV 逐格规范化（列名 == 字段名时自动映射，未映射列原样保留）
zhclean table --input docs/examples/sample.csv
```

**2.3 措辞统一**（`README.md` 全文，`grep -c` 收尾为 0）

```
八类 = 老六类（M1 四类 + M2 金额/日期）+ …      →  八类 = M1+M2 六类（M1 四类 + M2 金额/日期）+ …
| 老六类（对照 M2 定版，逐位复现） | …          →  | M1+M2 六类（对照 M2 定版，逐位复现） | …
不与老六类的 87.92% 相比                        →  不与 M1+M2 六类的 87.92% 相比
train 对照：老六类 person 72.12% …              →  train 对照：M1+M2 六类 person 72.12% …
报数分列：老六类（可对照 M2 定版）与新两类 …      →  报数分列：M1+M2 六类（可对照 M2 定版）与新两类 …
```

**2.4 release-checklist 重写要点**（`[x]`/`[ ]` 与事实逐条对齐）

| 节 | `[x]` 已核 | `[ ]` 待办 |
|---|---|---|
| A 测试与安装 | 689 passed；五个 demo OK；快速上手 4 条 exit 0；CI YAML 语法过 | **干净机器实跑 `uv tool install .`**（本机 PATH 无 `zhclean`）；**CI 首跑**（未推 GitHub）；发布提交后核工作区干净 |
| B 评测数字 | 八类定版分列表；README ↔ findings ↔ failures-m3 **三处逐格一致**；train 数字确认 | — |
| C 失败案例公开 | 三份 failures 都在、链接与锚点可点达、已知限制逐条有出处 | 失败明细产物（不入库，按需重生成） |
| D 许可证与元信息 | LICENSE=MIT / README `## License` / `version = "0.1.0"` | — |
| E 打 tag / 建仓 | （维护者执行，手不代跑） | `git tag v0.1.0`；GitHub 建仓 + 推送 |
| F 文档面 | table 一节、快速上手 4 条、README「老六类」零残留 | **failures-m3.md 4 处**（越界，见 §5-1） |

## 3. 我亲跑过的自测（真实输出）

> 环境：`PYTHONIOENCODING=utf-8`；命令一律 `uv run --project .` 前缀（TASK §6）。
> 除明确标注 `| tail -N` 的两处外，**以下均为原样粘贴、无截断、无过滤**。

**3.1 基线（TASK §1.5，开工前第一件事）**

```
$ cd "G:/Agentwork_mvp/s2-中文脏数据净化器-zhclean" && echo "=== git status --porcelain -uall ===" && git status --porcelain -uall && echo "=== HEAD ===" && git rev-parse --short HEAD && echo "=== git log -3 --oneline ===" && git log -3 --oneline && echo "=== docs/ 目录 ===" && ls -1 docs/
=== git status --porcelain -uall ===
=== HEAD ===
263cd01
=== git log -3 --oneline ===
263cd01 chore(handoff): TASK-027 已通过(edca08f 验收结论，五子命令齐全) + 派 TASK-028 发布前文档收尾 + aoci 同步
edca08f feat(table): TASK-027 交付——整表清洗 zhclean table（CSV 逐格规范化+可选整行去重，五子命令齐全）
497b8c7 chore(handoff): TASK-026 已通过(14d0d23 验收结论，M2 字段层收官) + 派 TASK-027 整表清洗 + aoci 同步
=== docs/ 目录 ===
examples
failures-m1.md
failures-m2.md
failures-m3.md
release-checklist.md
```
（`git status --porcelain -uall` 无输出 = 工作区干净，本单两个待改文件那时都还没动。）

**3.2 判据 1 —— 全量测试**（`| tail -2` 截尾）

```
$ PYTHONIOENCODING=utf-8 uv run --project . pytest tests/ -q 2>&1 | tail -2
.........................................                                [100%]
689 passed in 6.65s
```

**3.3 五个 demo 自检**（= release-checklist A 节所示命令，末尾加 `; echo "全部退出码=$?"` 打印退出码）

```
$ for m in zhclean.loop zhclean.tools.audit zhclean.tools.dedupe zhclean.llm zhclean.tools.table; do uv run --project . python -m $m; done; echo "全部退出码=$?"
loop._demo: OK
audit._demo: OK
dedupe._demo: OK
llm._demo: OK
table._demo: OK
全部退出码=0
```

**3.4 判据 2 —— 快速上手 4 条命令逐条实跑**

> 本机**未**全局安装 `zhclean`（`which zhclean` 无输出），故用 README 自己给的等价前缀 `uv run --project . zhclean …` 跑；
> README 里的写法是不带前缀的 `zhclean …`（安装后即可）。**4 条均退出码 0**。

```
$ uv run --project . zhclean normalize --input docs/examples/sample.jsonl; echo "exit=$?"
normalize：共 8 行，规范值与原值不同 3 行
{"id": "1", "field": "person", "value": "范 童言", "normalized": "范童言", "confidence": 0.9}
{"id": "2", "field": "person", "value": "范童言", "normalized": "范童言", "confidence": 0.95}
{"id": "3", "field": "person", "value": "孟露峰", "normalized": "孟露峰", "confidence": 0.95}
{"id": "4", "field": "phone", "value": "+86 138-0013-8000", "normalized": "13800138000", "confidence": 0.9}
{"id": "5", "field": "phone", "value": "13800138000", "normalized": "13800138000", "confidence": 0.95}
{"id": "6", "field": "company", "value": "公司名称：嘉兴 数联贸易集团有限公司", "normalized": "嘉兴数联贸易集团有限公司", "confidence": 0.9}
{"id": "7", "field": "company", "value": "嘉兴数联贸易集团有限公司", "normalized": "嘉兴数联贸易集团有限公司", "confidence": 0.95}
{"id": "8", "field": "address", "value": "贵州省贵阳市城关区建设路596号", "normalized": "贵州省贵阳市城关区建设路596号", "confidence": 0.95}
exit=0

$ uv run --project . zhclean dedupe --input docs/examples/sample.jsonl; echo "exit=$?"
dedupe（adaptive，threshold=0.85）：共 8 行 → 5 组（其中多行组 3 个，可去掉 3 行）
{"id": "1", "field": "person", "value": "范 童言", "_group": 0}
{"id": "2", "field": "person", "value": "范童言", "_group": 0}
{"id": "3", "field": "person", "value": "孟露峰", "_group": 1}
{"id": "4", "field": "phone", "value": "+86 138-0013-8000", "_group": 2}
{"id": "5", "field": "phone", "value": "13800138000", "_group": 2}
{"id": "6", "field": "company", "value": "公司名称：嘉兴 数联贸易集团有限公司", "_group": 3}
{"id": "7", "field": "company", "value": "嘉兴数联贸易集团有限公司", "_group": 3}
{"id": "8", "field": "address", "value": "贵州省贵阳市城关区建设路596号", "_group": 4}
exit=0

$ uv run --project . zhclean audit --input docs/examples/sample.jsonl; echo "exit=$?"
清洗报告（dry-run 预览，未应用）
总行数 8　改动 3（37.50%）　未改 5
按字段：
  person    总     3  改     1  未改     2
  phone     总     2  改     1  未改     1
  company   总     2  改     1  未改     1
  address   总     1  改     0  未改     1
按置信度：
  0.95       5
  0.9        3
  0.7        0
  0.1        0
  other      0
改动明细：列出 3 条
exit=0

$ uv run --project . zhclean table --input docs/examples/sample.csv; echo "exit=$?"
table：共 3 行 × 8 列，改了 8 格，输出 3 行
id,person,phone,company,address,idcard,email,备注
1,范童言,13800138000,嘉兴数联贸易集团有限公司,贵州省贵阳市城关区建设路596号,110412197605131500,sbe1hdy@hotmail.com,未映射列原样保留
2,范童言,13800138000,嘉兴数联贸易集团有限公司,贵州省贵阳市城关区建设路596号,110412197605131500,sbe1hdy@hotmail.com,本行已是干净值
3,孟露峰,13800138000,数联贸易集团有限公司,贵阳市城关区建设路596号,110412197605131500,sbe1hdy@hotmail.com,第三行
exit=0
```

**3.5–3.8 措辞核验 / 数字比对 / 锚点 / 元信息**（一条命令跑完，输出**原样粘贴、未截断未过滤**，含 `=== n) ===` 标记）

```
$ cd "G:/Agentwork_mvp/s2-中文脏数据净化器-zhclean"; export PYTHONIOENCODING=utf-8; echo "=== 1) README 里的「老六类」 ==="; grep -n "老六类" README.md; echo "grep exit=$?"; echo "=== 2) README 里的「M1+M2 六类」行数 ==="; grep -c "M1+M2 六类" README.md; echo "=== 3) failures-m3.md 的标题 ==="; grep -n "^#" docs/failures-m3.md; echo "=== 4) failures-m3.md 的关键数字 ==="; grep -n "87.92\|76.25\|85.00\|1055\|305/400\|1360" docs/failures-m3.md; echo "=== 5) LICENSE 头三行 ==="; head -3 LICENSE; echo "=== 6) pyproject version ==="; grep -n "^version" pyproject.toml; echo "=== 7) CI 语法 ==="; python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8'))"; echo "exit=$?"; echo "=== 8) 工作流文件 ==="; ls .github/workflows/
=== 1) README 里的「老六类」 ===
grep exit=1
=== 2) README 里的「M1+M2 六类」行数 ===
5
=== 3) failures-m3.md 的标题 ===
1:# M3 失败案例公开（八类字段定版）
9:## 总览：规范化（heldout，规则版）
36:## 第三批新增字段的失败归因
38:### 身份证 idcard（100.00%，失败 0 行）
53:### 邮箱 email（52.50%，失败 95 行）
69:## 老六类字段的归因（M2 老账，数字与 M2 定版逐位一致）
81:## 合成数据的局限
85:## 如何复现评测
91:# 规范化：heldout（定版数字，只跑一次）
94:# 规范化：train（调参参照，可反复跑）
97:# 去重：train（真实水平基准）
100:# 去重：heldout
=== 4) failures-m3.md 的关键数字 ===
26:| 老六类（对照 M2 定版，逐位复现） | 1055/1200 = **87.92%** |
27:| 新两类（首次定版） | 305/400 = **76.25%** |
28:| 八类总平均（仅参考，不与 87.92% 比） | 1360/1600 = **85.00%** |
30:失败共 **240 行**（1600 − 1360）：老六类 145（见 [failures-m2.md](failures-m2.md)）+ **email 95**（sep 40 / abbrev 40 / typo 15）；**idcard 0 失败**。
=== 5) LICENSE 头三行 ===
MIT License

Copyright (c) 2026 qlheric
=== 6) pyproject version ===
3:version = "0.1.0"
=== 7) CI 语法 ===
exit=0
=== 8) 工作流文件 ===
ci.yml
```

读法：
- **第 1 段**：`grep` 无输出且退出码 `1` = README「老六类」**零残留**；**第 2 段** `5` = 改后「M1+M2 六类」出现的**行数**（5 行各 1 处，与改前 5 处一一对应）。
- **第 3 段**：README 第 110 行链接 `docs/failures-m3.md#如何复现评测` → 标题在第 85 行 ⇒ **锚点有效**（未断链）。
- **第 4 段**：`README.md` 第 92/96/98 行 ↔ `findings.md` 第 45/46 行 ↔ `failures-m3.md` 第 26–28 行 ⇒ **三处逐格一致**（`1055/1200 = 87.92%`、`305/400 = 76.25%`、`1360/1600 = 85.00%`；train `88.40 / 75.75 / 85.23`、dedupe heldout `100.00 / 100.00` 同源）。
- **第 7 段**：用**系统** python —— 项目环境未装 pyyaml，`uv run --with pyyaml` 会联网装包（属禁区），故不走走 uv 的那条路。

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | 测试全绿 `uv run --project . pytest tests/ -q` | ✅ `689 passed` | §3.2。零代码改动，本单只碰两个 Markdown |
| 2 | 快速上手 4 条命令逐条实跑，4 条 exit 0 | ✅ `normalize` / `dedupe` / `audit` / `table` 均 `exit=0`（含新增的 `table` 一条） | §3.4（原样输出）。本机未全局装 `zhclean`，用 README 自带的等价前缀 `uv run --project .` 跑，已注明 |
| 3 | 措辞与检查单核验（脑侧通读） | ⏳ 待脑通读。手侧已备好可机械核的判据：README「老六类」**零残留**（§3.5–3.8 第 1–2 段）、README↔台账**三处一致**（第 4 段）、锚点非断链（第 3 段）、检查单 `[x]/[ ]` 与 §3 各条事实逐条对应 | §3.5–3.8；README 现 141 行（README 纪律：一页读完） |

## 5. 遗留 / 不确定 / 需要拍板

**5-1 ⚠️ `_Boundary:_` 与 §2.5 冲突：`docs/failures-m3.md` 的 4 处「老六类」我没改（需脑拍板）**
- TASK §2.5 契约写「**措辞统一**：「老六类」→「M1+M2 六类」（README 全文；**failures-m3 若也用了同词，一并改**）」，但 §2「范围（只许动这些）」与表头 `_Boundary:_` 只列了 `README.md` 与 `docs/release-checklist.md`，且 §2 末尾有「除此之外**一律不许动**」。
- 按 v1.3 §7（越界即判不通过，用 `git diff --name-only` 机械核）与 RESULT-015 §5-1（**最窄读法 + 回执申报**），我**只改了边界内的两个文件**。`docs/failures-m3.md` 里仍有 4 处，行号与内容：
  - 第 26 行 `| 老六类（对照 M2 定版，逐位复现） | 1055/1200 = **87.92%** |` —— 与 README 第 92 行的同款表格**措辞已不一致**
  - 第 30 行 `失败共 240 行…老六类 145…`
  - 第 69 行 `## 老六类字段的归因（M2 老账…）` —— 小标题
  - 第 79 行 `**新增 idcard / email 对老六类零影响**：…`
- **请脑拍板**：授权补一单（或把该文件写进下一单边界），一行 `sed`/4 处替换即可；或明确「历史台账按原样保留、不改」。**我未擅自改。**

**5-2 其他文件里的「老六类」（本单未授权，同样未改）**
`grep -rn "老六类" --include="*.md" .` 的命中分布：`README.md` 5（**已改 0 残留**）、`docs/failures-m3.md` 4（见 §5-1）、`findings.md` 1（第 46 行）、`task_plan.md` 3、`progress.md` 5，其余在 `.handoff/**`（禁区）。后三个是历史台账/会话记录，TASK 没提，**未改**。

**5-3 README 里另外一处同类措辞我没动（不属于「老六类」字样）**
`README.md` 第 117 行描述 m2 文档时写「M2 六类定版（金额 / 日期）」——它不是「老六类」字样，是 `docs/failures-m2.md` 那份文档自己的名字，按「不叠加」原则保留。若脑要求统一成「M1+M2 六类定版」，也是一行的事。

**5-4 两处本机环境事实（已写进检查单，避免发布时踩空）**
- 项目环境**未装 pyyaml** ⇒ 检查单的 CI 语法核验必须用**系统** python（原始命令就是 `python -c …`，不带走 `uv run`）；
- 本机**未全局安装 `zhclean`** ⇒ 「安装命令实跑」这条只能在干净机器上做，检查单已标注为待办。

**5-5 检查单的「失败明细产物可复现」我打的是 `[ ]` 待办**
产物不入库（`benchmarks/results/` 被 gitignore），且生成它们要跑评测命令 —— 发布不需要这些产物、也**不该为核查重跑 heldout**（纪律）。留作按需重生成。

## 6. 建议下一步

1. **拍板 §5-1**（failures-m3 的 4 处措辞）——这是本单唯一的硬缺口；若授权，下一步一单（或下次顺手）即可清零。
2. **发布动作交维护者**：`git tag -a v0.1.0 -m "zhclean v0.1.0 — 八类字段 + 整表清洗"` → GitHub 建仓 → 推送（CI 首跑）→ 干净机器 `uv tool install .` 复核。
3. **可选的收尾小单**：统一 §5-2 / §5-3 的同类措辞（findings / task_plan / progress 属历史记录，建议**不改**，只在发布说明里注明口径）。

## 7. 下次接着做什么（写给"下一轮的你"）

- 做到哪了：TASK-028 已交付 —— `README.md`（新增「整表清洗（table）」一节 + 快速上手第 4 条 + 「老六类」→「M1+M2 六类」5 处 + 顶部工具数改四件 + 路线加一条）、`docs/release-checklist.md`（按 v0.1.0 现状重写：`[x]` 已核 / `[ ]` 待办 + 新增 F 文档面一节）。689 绿、5 个 demo OK、快速上手 4 条 exit 0、README↔台账三处数字一致。**已写 `RESULT-028.md`，停在这里等脑验收。未动 TASK 状态字段，未 git add / commit。**
- 下一步第一件事：等脑验收。**最可能的打回点 = §5-1**（`docs/failures-m3.md` 4 处「老六类」因边界冲突未改）——若脑授权，改法是 4 处字样替换（第 26 / 30 / 69 / 79 行，**含第 69 行的小标题**）；改完重跑 §3.5 的 grep 判据（`grep -n "老六类" docs/failures-m3.md` 应无输出）。若脑通过，下一步是维护者的发布动作（tag / 建仓 / 推送）。
- 要绕开的坑：
  1. **`_Boundary:_` 与 §2.5 契约冲突时，以 `_Boundary:_` 为准并申报**（v1.3 §7 用 `git diff --name-only` 机械核算边界）——本单就是这么处理的，别为了「把话说圆」去改边界外的文件。
  2. **CI 语法核验别加 `uv run`**：项目环境没有 pyyaml，加了必失败；`uv run --with pyyaml` 会联网装包 ⇒ **禁区**。用系统 `python -c …`。
  3. **`zhclean.rules.{common,email,idcard}` 的 `-m` 自检会先打 runpy 的 `RuntimeWarning`** —— 这是包内模块的正常现象，不是坏了；检查单里已把 demo 自检限定为五个公开入口。
  4. **改 README 前先通读全文**（老大 2026-10-03 令）——本单顺手发现并修了两处旧痕：「样例文件只含其中三类」实为四类（人名/电话/公司名/地址）、「三件工具」实为四件。
  5. 建议 `grep -c` 报告「行数」而 `grep -n` 报告「位置」：措辞核验时说清是行数还是处数，别混。

## 8. 脑侧验收（2026-10-09）

**判据亲跑**：①689 passed（零代码改动）✓；②快速上手 4 条逐条实跑 exit 0（含新增 table）✓；边界零越界（2 文档 + 回执豁免）✓。

**判据 3 核验（脑侧）**：README「老六类」**零残留**（grep exit=1）、「M1+M2 六类」5 处 ✓；README ↔ findings ↔ failures-m3 三处数字逐格一致（87.92/76.25/85.00 + train 对照）✓；锚点非断链 ✓；README 一页读完（141 行，顺手修了两处旧痕：「样例文件只含三类」→四类、「三件工具」→四件）。

**§5-1 裁决（脑定）**：又是我 TASK 自相矛盾（§2.5 契约要求改 failures-m3、§2 边界却没列它）——手按最窄读法守边界并申报**正确**。**授权补改，已由脑侧执行**：failures-m3 的 4 处「老六类」→「M1+M2 六类」（第 26/30/69/79 行）全部替换完成。§5-2 历史台账（findings/task_plan/progress/.handoff）按原样保留**不改**（历史记录非对外件）；§5-3 保留；§5-4/5-5 接受（检查单已如实标注待办）。

审查结论：**通过**。release-checklist 按 v0.1.0 现状重写、`[x]/[ ]` 与事实逐条对应；README 措辞统一与 table 一节符合老大 2026-10-03 纪律。

**里程碑：M2 全部完成——八类字段 + 五子命令 + 文档三线 + 发布检查单就绪。发布动作（tag/建仓/推送）待维护者执行。**

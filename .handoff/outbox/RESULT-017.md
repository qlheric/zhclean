# RESULT-017　对应 TASK-017

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code（侧边栏终端） |
| 日期 | 2026-10-08 |
| 结论 | 完成（含 2 处工具/环境说明、1 处「CI 未真跑」的诚实标注，见 §5） |

**一句话**：M1 收官三件套落地——CI 工作流（windows-latest，push/PR → uv sync → pytest → 四 demo）、
README 补 License 段（MIT / qlheric 2026）、`docs/release-checklist.md` 发布检查单。三判据全过：
**467 passed** + 四 demo `OK`（本地等价跑通 CI 步骤）+ **yaml.safe_load 解析通过**。

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `.github/workflows/ci.yml` | **新增**：CI 工作流（checkout → setup-python 3.12 → pip install uv → uv sync → pytest → 四 demo） | 55 行（新） |
| `README.md` | 末尾补 `## License` 段（`[MIT](LICENSE) © 2026 qlheric`）；其余一字未动 | +4 −0 |
| `docs/release-checklist.md` | **新增**：M1 发布检查单（A 测试与安装 / B 评测数字 / C 失败案例 / D 许可证 / E 打 tag） | 70 行（新） |

**改动集合 vs `_Boundary:_`**：`git status --porcelain -uall` 共 1 个已跟踪改动（README.md）
+ 2 个新增（ci.yml、release-checklist.md）。逐条比对，**全部在界内**，无越界。
`src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`、`LICENSE`、`docs/failures-m1.md` 一律未碰。

## 2. 关键 diff 摘要

**① CI 工作流（`.github/workflows/ci.yml`）** —— job 级 `shell: bash`（demo 是 `for` 循环，
windows runner 默认 pwsh 跑不了）：

```yaml
on:
  push:
    branches: [main]
  pull_request:

env:
  PYTHONIOENCODING: utf-8     # 显式声明；编码回归测试会主动剥掉它再 spawn 子进程，不受影响

jobs:
  test:
    runs-on: windows-latest
    defaults:
      run:
        shell: bash
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install uv
      - run: uv sync --project .                    # 含 dev 组
      - run: uv run --project . pytest tests/ -q
      - run: |
          for m in zhclean.loop zhclean.tools.audit zhclean.tools.dedupe zhclean.llm; do
            uv run --project . python -m "$m"
          done
```

**② README License 段**（放在「路线」之后）：

```markdown
## License

[MIT](LICENSE) © 2026 qlheric
```

**③ 发布检查单**（`docs/release-checklist.md`）：5 节 checkbox，首行声明「本清单由 M1 收官生成
（TASK-017，2026-10-08），发布前逐项打勾」，明写「heldout 只在定版后跑一次，发布时不再重跑」。

## 3. 我亲跑过的自测（真实输出）

### 3.1 基线（§1.5）

```
$ git status --porcelain -uall
（无输出 —— 工作区干净）

$ git log --oneline -1
058cfbe chore(handoff): TASK-016 已通过(5783929 验收+审查结论，两件功夫齐) + 派 TASK-017 M1 收官 + aoci 同步
```

### 3.2 判据 1 + 判据 2：测试全绿 + CI 步骤本地等价（整条照抄契约命令）

```
$ uv sync --project . && uv run --project . pytest tests/ -q && for m in zhclean.loop zhclean.tools.audit zhclean.tools.dedupe zhclean.llm; do uv run --project . python -m $m; done; echo "loop-of-demos-exit=$?"
Resolved 8 packages in 2ms
Checked 8 packages in 1ms
........................................................................ [ 15%]
........................................................................ [ 30%]
........................................................................ [ 46%]
........................................................................ [ 61%]
........................................................................ [ 77%]
........................................................................ [ 92%]
...................................                                      [100%]
467 passed in 6.79s
loop._demo: OK
audit._demo: OK
dedupe._demo: OK
llm._demo: OK
loop-of-demos-exit=0
```
> 说明：命令末尾的 `echo "loop-of-demos-exit=$?"` 是我自己加的（原样保留，便于一眼看退出码），
> 报的是 `for` 循环的退出状态 = 0；四个 demo 均打印 `..._demo: OK`。这就是 CI 里 `Run tests` +
> `Demo 自检` 两步的**本地等价**命令。

### 3.3 判据 3：YAML 语法有效

```
$ PYTHONUTF8=1 python -c "
import yaml
d = yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))
print('YAML OK（yaml.safe_load 解析通过）')
triggers = d.get('on') if 'on' in d else d.get(True)   # PyYAML 1.1 把裸 on: 当成布尔 True
print('triggers:', sorted(triggers.keys()))
print('env:', d['env'])
print('runs-on:', d['jobs']['test']['runs-on'])
print('shell:', d['jobs']['test']['defaults']['run']['shell'])
for s in d['jobs']['test']['steps']:
    print('  step:', s.get('name'))
"; echo "exit=$?"
YAML OK（yaml.safe_load 解析通过）
triggers: ['pull_request', 'push']
env: {'PYTHONIOENCODING': 'utf-8'}
runs-on: windows-latest
shell: bash
  step: Checkout
  step: Setup Python 3.12
  step: Install uv
  step: Sync dependencies (含 dev 组)
  step: Run tests
  step: Demo 自检（四个入口）
exit=0
```
> ⚠️ **用的是系统 Python**（`G:\develop\Python\python.exe`，PyYAML 6.0.3），**不是**项目 venv——
> venv 里没有 yaml，而「装新包」是禁区。见 §5-1。

### 3.4 检查单里的命令我也实跑过（不然检查单自带坏命令）

```
$ uv run --project . zhclean --help >/dev/null; echo "help exit=$?"
help exit=0
$ for c in normalize dedupe audit; do uv run --project . zhclean $c --input docs/examples/sample.jsonl >/dev/null; echo "$c exit=$?"; done
normalize：共 8 行，规范值与原值不同 3 行
normalize exit=0
dedupe（adaptive，threshold=0.85）：共 8 行 → 5 组（其中多行组 3 个，可去掉 3 行）
dedupe exit=0
audit exit=0
$ uv run --project . zhclean normalize --input docs/examples/sample.jsonl | head -1
normalize：共 8 行，规范值与原值不同 3 行
{"id": "1", "field": "person", "value": "范 童言", "normalized": "范童言", "confidence": 0.9}
```
> 检查单里写的是装好后的裸命令（`zhclean normalize ...`）；这里用 `uv run --project . zhclean ...`
> 做**本地等价**验证（没装全局命令）。输出里那几行「共 8 行…」是 CLI 写到 stderr 的汇总，没被 `>/dev/null` 吃掉。

### 3.5 README 数字 ↔ 台账对照（检查单 B 节声称的一致性）

```
$ grep -n "85.88\|72.00\|90.50\|100.00\|81.00" README.md docs/failures-m1.md | head
README.md:67:| 72.00% | 100.00% | 81.00% | 90.50% | 85.88% |
README.md:69:**去重**（heldout）：recall 100.00% / precision 100.00%（样本小；train 复核 recall 99.90% / precision 99.25%…）
docs/failures-m1.md:10:| 人名 person | 0.00% | 100.00% | 100.00% | 100.00% | 60.00% | **72.00%** |
docs/failures-m1.md:11:| 地址 address | 52.50% | 100.00% | 100.00% | 100.00% | 100.00% | **90.50%** |
docs/failures-m1.md:12:| 电话 phone | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | **100.00%** |
docs/failures-m1.md:13:| 公司名 company | 5.00% | 100.00% | 100.00% | 100.00% | 100.00% | **81.00%** |
docs/failures-m1.md:14:| 总盘 | | | | | | **85.88%（687/800）** |
```
→ README 总览与 `docs/failures-m1.md` 总览**逐格一致**。本节**没有重跑 heldout**（只读已有台账）。

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | 测试全绿 | **通过**：`467 passed` | §3.2 |
| 2 | CI 步骤本地等价（sync → pytest → 四 demo） | **通过**：全 exit 0、四 demo 均 `..._demo: OK` | §3.2 |
| 3 | YAML 语法有效 | **通过**：`yaml.safe_load` 解析无错，字段读得出（triggers/env/runs-on/steps） | §3.3 |

**契约逐条核对（§2.5）**：
- ci.yml 触发 `push`(main) + `pull_request` —— ✅；jobs 用 **windows-latest** —— ✅（理由已写进 yml 注释）；
  steps 顺序 = checkout → setup-python 3.12 → `pip install uv` → `uv sync --project .` → `pytest tests/ -q` → 四 demo —— ✅；
  `PYTHONIOENCODING: utf-8` 写进 job `env` —— ✅
- README License 段：一句话 + 链接（`[MIT](LICENSE) © 2026 qlheric`），放在「路线」之后 —— ✅（先通读全文，无重复）
- release-checklist.md：逐项 checkbox，覆盖 数字定版（heldout 不重跑）/ README↔台账一致 / 失败案例已公开 /
  `zhclean --help` 与三条快速上手实跑 / 安装命令实跑 / License 存在 / git tag 建议，且首行声明「由 M1 收官生成」—— ✅

## 5. 遗留 / 不确定 / 需要拍板

### 5-1（**工具说明**）YAML 校验用的是系统 Python，不是项目 venv
- 判据 3 要 `yaml.safe_load`。项目 venv（`uv run` 环境）**没有 PyYAML**，而「装新包」是禁区；
  系统 Python（`G:\develop\Python\python.exe`，PyYAML 6.0.3）里有 ⇒ 我用它跑的（只读一个文件、不联网、不装包）。
- **顺带一个坑**：PyYAML 走 YAML 1.1，**裸 `on:` 会被解析成布尔 `True`**（不是字符串 `"on"`）——
  所以上面脚本里写了 `d.get('on') if 'on' in d else d.get(True)`。**这只影响 PyYAML 的键名**，
  GitHub Actions 自己的解析器把 `on:` 当字符串，工作流不受影响。

### 5-2（**诚实标注：CI 未在 GitHub 上真跑**）本单无法联网、也不许 push
- 我**没有**（也不能）把工作流推到 GitHub 看它真跑。能给的实据是**判据 2 的本地等价**：
  在**这台 Windows 机器**上原样跑 `uv sync → pytest → 四 demo`，全绿。
  也就是说：**命令集是对的**；至于 GitHub windows runner 上的环境差异（见 §5-3），属于「真跑才知道」。
- 建议：合并后**盯第一次 CI 运行**；红了按 §5-3 的两条改。

### 5-3（**风险提示**）两处 CI 上可能的小坑（本地无法证伪）
1. `pip install uv` 把 `uv.exe` 放进 Python 的 `Scripts`，理论上 `setup-python` 已把它加进 PATH；
   但 `shell: bash`（Git Bash）下 PATH 拼装偶有差异。**若首次 CI 报 `uv: command not found`**，
   改成 `python -m pip install uv`（装法一样，只是绕开 `pip` 这个入口名）。
2. 备用：把 `Install uv` 换成官方 action `astral-sh/setup-uv@v5`（更稳，但引入了第三方 action）。
   —— 契约要求用 `pip install uv`，我没擅自换。

### 5-4（其余说明 / 申报）
- 新增文件：`.github/workflows/ci.yml`、`docs/release-checklist.md`（均在界内）。
- **未跑评测**（判据没要求，且本单没碰 `src/**`/`benchmarks/**`）⇒ heldout 纪律不受影响。
- 工具副产品：`__pycache__/`、`.pytest_cache/`（gitignore 覆盖）。`benchmarks/results/*` 未刷新（没跑 evaluate）。
- 记忆库 `handoff-workflow-state.md` + `MEMORY.md`（工作区惯例，非业务代码，已在 RESULT-016/本单申报过）。
- `aoci.txt` / `aoci.code.txt` / `aoci.meta.txt` / `.aoci/` **我一行没碰**（那是脑的收尾动作）。

## 6. 建议下一步

1. 合并后盯**第一次 CI 运行**；按 §5-3 的两条兜底改（`python -m pip install uv` / `astral-sh/setup-uv`）。
2. 可选：README 加 CI 徽章（需要仓库 URL）——本单没加（无 URL，且属 README 范围外的最小改动）。
3. 可选：`.gitattributes` 补 `*.yml text eol=lf`（当前靠 `* text=auto` 也够）。
4. 发布时按 `docs/release-checklist.md` 逐项打勾；`git tag -a v0.1.0` **由维护者执行**（本单不代跑）。
5. 若要对第三方 action 做供应链加固，把 `@v4`/`@v5` 换成 commit SHA（另开 TASK）。

## 7. 下次接着做什么（**写给"下一轮的你"**）

- **做到哪了**：TASK-017（M1 收官）全部落地，**未 commit、未动 TASK 状态字段**（归脑）。关键文件：
  `.github/workflows/ci.yml`（新）、`README.md`（+License 段，末尾）、`docs/release-checklist.md`（新）。
  回执即本文件；三判据实据在 §3.2（467 passed + 四 demo）、§3.3（YAML 解析）。
  **M1 到此收官**；下一单应进 **M2（金额 / 日期 / 身份证 / 邮箱 + 真实行政区划表）**（见 `task_plan.md`）。
- **下一步第一件事**：读 `.handoff/inbox/` 里**编号最大**的 TASK（可能是 TASK-018 / M2 启动单）；
  先看脑对 §5-3（CI 首跑风险）的处置，再动手。
- **要绕开的坑**：
  1. **`rm -rf` 是禁区**（沿用 TASK-016 教训）；清临时文件用 `mkdir -p <全新名字>`。
  2. **判据里要 YAML 解析时**：项目 venv **没有 PyYAML**，别 `uv run python -c "import yaml"`（会 ModuleNotFoundError）；
     用系统 `python`（`G:\develop\Python`，有 PyYAML 6.0.3）。且记住 PyYAML 1.1 把裸 `on:` 当布尔 `True`。
  3. **CI 用 windows-latest + `shell: bash`**：demo 是 `for` 循环，runner 默认 pwsh 会挂；改 ubuntu 也行但少一层编码保护。
  4. 判据命令一律 `uv run --project .` 前缀；看中文是否真 utf-8 用 `od -An -tx1` 看**字节**。
  5. 一次性证据脚本的中文输出：本机默认 cp936，临时 `PYTHONUTF8=1` 才可读（产品入口自己调 `utf8_stdio()`，不用加）。
  6. README 纪律：**只加 License 段**，先通读全文确认不重复（老大 2026-10-03 令）。

## 8. 脑侧验收（2026-10-08）

**判据亲跑**：①467 passed ✓；②CI 本地等价四 demo 全 OK ✓；③系统 python yaml.safe_load 解析通过（triggers/env/runs-on/steps 可读）✓；边界零越界（README License 段 + ci.yml + release-checklist，均在界内）。

**审查结论：通过**。ci.yml 结构正确（windows-latest + shell: bash 处理 for 循环、PYTHONIOENCODING 显式）；README License 段符合「只加一段、先通读无重复」纪律；检查单命令全部实跑过（不自带坏命令）；README↔failures-m1 数字逐格一致。

**§5 处置（脑定）**：①YAML 用系统 python 校验合理（venv 无 PyYAML 且禁装包）；②**CI 未真跑属诚实标注**——合并后盯首次 CI，红了按 §5-3 两条兜底（`python -m pip install uv` / `astral-sh/setup-uv`）；③`git tag` 由维护者（老大/脑）执行，手不代跑正确。

**里程碑：M1 全部收官**——四类规范化（heldout 85.88% / train 86.16%）+ 去重（heldout R100/P100，train R99.90/P99.25）+ 三工具 + CLI 一键 + 评测体系（留出集隔离 + 失败案例公开）+ LLM 兜底三级流 + CI + 发布检查单。下一单进 M2。

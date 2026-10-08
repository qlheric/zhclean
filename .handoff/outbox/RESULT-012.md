# RESULT-012　对应 TASK-012

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | **完成**。判据 1、2 都通过。改了 2 个文件，都在 `_Boundary:_` 里。 |

## 0. 开工基线（TASK-012 §1.5）

```
$ git status --porcelain -uall
（空输出）
$ git rev-parse --short HEAD
bba71c5
```

完工后：

```
$ git status --porcelain -uall
 M src/zhclean/cli.py
?? tests/test_cli.py
```

## 1. 改了哪些文件

```
$ git diff --stat
 src/zhclean/cli.py | 296 ++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 291 insertions(+), 5 deletions(-)
```

（`tests/test_cli.py` 是新文件，还没被 git 跟踪，所以没进 diff --stat。共 41 个用例。）

| 文件 | 改了什么 |
|---|---|
| `src/zhclean/cli.py` | 原来只有一个模块头（5 行）。现在实现了 argparse 和 4 个子命令（normalize / dedupe / audit / rollback），还有 `main(argv, stdin, stdout, stderr) -> int`、退出码语义、中文帮助和错误信息。 |
| `tests/test_cli.py` | 新建，41 个用例。 |

## 2. 关键设计

### 2-1 契约落地

| 子命令 | 行为 |
|---|---|
| `normalize --input x [--field F] [--out y]` | 逐行调用 `normalize_with_confidence`。输出行是原字段加上 `normalized` 和 `confidence` 两键。传了 `--field` 就按它清洗，这时行里可以不带 field。 |
| `dedupe --input x [--adaptive \| --plain] [--threshold 0.85] [--out y]` | 默认用 `dedupe_adaptive`，`--plain` 改用 `dedupe`，两个开关互斥。输出保持输入行序，每行加 `_group`（组序号，从 0 起，按各组首行出现的顺序编号）。汇总打印组数、多行组个数和可去掉的行数。 |
| `audit --input x [--apply [--out y] [--force]]` | 默认 dry-run，只打印 `format_report`，**一个文件都不写**。`--apply` 时写 `y.jsonl`（清洗结果）和旁边的 `y.backup.json`（含 checksum），并打印报告和回滚命令。 |
| `rollback --cleaned y --backup y.backup.json [--out z]` | 调用 `rollback()`。checksum 不匹配、备份结构不对或备份不是合法 JSON，都以退出码 1 退出，并且不写任何输出。 |

退出码（写在模块头和 `--help` 末尾）：**0 成功 / 1 运行错 / 2 参数错**。`main()` 会把 argparse 抛出的 SystemExit 转成返回值，所以测试里可以直接断言退出码。

### 2-2 契约空白处我定的口径（请脑拍板，见 §5-2）

1. **`--input` 缺省或写 `-` 时读 stdin**。判据 2 要求 `echo … | normalize`，所以必须支持 stdin。stdin 按字节读再用 utf-8 解码，不受 Windows 控制台 cp936 的影响。
2. **输出流分工**：没写 `--out` 时，数据 jsonl 写 stdout，汇总写 stderr，这样 stdout 是纯 jsonl，可以直接接管道。写了 `--out` 时汇总写 stdout。
3. **`audit --apply` 不写 `--out` 时**，默认写到 `<input>.cleaned.jsonl`。输入来自 stdin 时没法推出文件名，直接报错退出码 1。
4. **`--apply` 默认不覆盖已存在的清洗结果或备份文件**，要覆盖需加 `--force`。防止误操作盖掉上一次的备份，导致无法回滚。
5. **先写备份，再写清洗结果**。中途失败时至少原数据还能找回。
6. **中文化范围**：`-h/--help` 的说明、所有子命令和参数的说明、所有错误提示都是中文。argparse 内置的标题「usage: / options: / positional arguments:」还是英文，它们是标准库写死的文案，我没去改私有实现。错误行会以「参数错误：…」开头，下一行附「（加 --help 查看用法）」。

## 3. 我亲跑过的自测（真实输出）

> 都在项目根、Windows bash 下跑，命令可以原样复制。

**判据 1**：

```
$ uv run --project . pytest tests/ -q 2>&1 | tail -3; echo "exit=${PIPESTATUS[0]}"
........................................................................ [ 88%]
.............................................                            [100%]
405 passed in 13.56s
exit=0
```

（命令里用了 `tail -3`，只贴最后 3 行。写回执前又重跑了一遍，这里贴的是这次的输出。405 = 原 364 + `tests/test_cli.py` 的 41 个。单独跑：`PYTHONIOENCODING=utf-8 uv run --project . pytest tests/test_cli.py -q` → `41 passed in 3.73s`。）

**判据 2a：`--help`**

```
$ uv run --project . python -m zhclean.cli --help; echo "exit=$?"
usage: zhclean [-h] <子命令> ...

中文脏数据净化器：规范化 / 去重 / 清洗报告（jsonl 进出）

positional arguments:
  <子命令>
    normalize  字段级规范化：输出行加 normalized 与 confidence
    dedupe     两级去重（默认 adaptive）：输出行加 _group 组序号
    audit      清洗报告（默认 dry-run 不写文件；--apply 写清洗结果 + 备份）
    rollback   用 audit --apply 的备份恢复原数据（checksum 不匹配即拒绝）

options:
  -h, --help   显示帮助并退出

退出码：0 成功；1 运行错（文件/数据/校验问题）；2 参数错
exit=0
```

**判据 2b：端到端 normalize（echo 一行脏数据，通过管道传入）**

```
$ echo '{"id":"1","field":"person","value":"范 童言"}' | uv run --project . python -m zhclean.cli normalize; echo "exit=$?"
normalize：共 1 行，规范值与原值不同 1 行
{"id": "1", "field": "person", "value": "范 童言", "normalized": "范童言", "confidence": 0.9}
exit=0
```

（第一行是写到 stderr 的汇总，终端里和 stdout 混在一起显示。没加 `PYTHONIOENCODING` 中文也正常，因为 `__main__` 里把 stdout/stderr 设成了 utf-8。）

再跑一个公司名的例子：

```
$ echo '{"id":"1","field":"company","value":"公司名称：嘉兴 数联贸易集团有限公司"}' | uv run --project . python -m zhclean.cli normalize; echo "exit=$?"
normalize：共 1 行，规范值与原值不同 1 行
{"id": "1", "field": "company", "value": "公司名称：嘉兴 数联贸易集团有限公司", "normalized": "嘉兴数联贸易集团有限公司", "confidence": 0.9}
exit=0
```

**退出码冒烟（参数错 → 2）**：

```
$ uv run --project . python -m zhclean.cli dedupe --threshold 2; echo "exit=$?"
usage: zhclean dedupe [-h] [--input INPUT] [--adaptive | --plain]
                      [--threshold THRESHOLD] [--out OUT]
参数错误：argument --threshold: 阈值须在 [0,1]，收到 2（注意不是 0~100）
（加 --help 查看用法）
exit=2
```

不带子命令时，打印帮助，再输出「参数错误：缺少子命令」，exit=2。这条 2-6 已经提过，输出不再重复贴。

## 4. 逐条对照验收判据

| # | 判据 | 结果 | 证据（`tests/test_cli.py` 用例名） |
|---|---|---|---|
| 1 | 全绿，test_cli 至少 12 个用例 | **通过**：405 passed，test_cli 有 41 个 | §3 |
| 1a | ↳ 三命令端到端（tmp 文件进出真实数据） | 通过 | `test_normalize_end_to_end_file` / `test_dedupe_default_is_adaptive` / `test_audit_apply_writes_cleaned_and_backup`，真实数据是 train 脏行 100 条 |
| 1b | ↳ 默认 dedupe=adaptive | 通过 | `test_dedupe_default_is_adaptive`（分组和直接调 `dedupe_adaptive` 逐组相同）、`test_dedupe_explicit_adaptive_equals_default` |
| 1c | ↳ --plain 对照 | 通过 | `test_dedupe_plain_vs_adaptive`（plain 的结果等于 `dedupe`；真实数据上 adaptive 分出的组更少）、`test_dedupe_threshold_passed_through` |
| 1d | ↳ audit dry-run 不写文件 | 通过 | `test_audit_dry_run_writes_nothing`（比对运行前后目录里的文件列表） |
| 1e | ↳ --apply 写 cleaned + backup | 通过 | `test_audit_apply_writes_cleaned_and_backup`、`test_audit_apply_default_out_name`、`test_audit_apply_refuses_overwrite_without_force`、`test_audit_apply_stdin_requires_out` |
| 1f | ↳ **rollback 往返恢复原值** | 通过 | `test_rollback_round_trip_restores_original`（先断言清洗结果和原数据不同，再断言恢复后和原数据逐行相等）、`test_rollback_to_stdout` |
| 1g | ↳ checksum 破坏被拒 | 通过 | `test_rollback_rejects_tampering`：分别篡改 cleaned、备份 rows、checksum 三种情况，都返回 1，且不写输出；`test_rollback_bad_backup_exit_1` |
| 1h | ↳ 退出码语义 | 通过 | 0：各成功用例；1：`test_missing_input_file_exit_1`、`test_bad_jsonl_exit_1_with_line_number`（3 个命令 × 4 种坏行）；2：`test_usage_errors_exit_2`（9 种）；子进程实测：`test_subprocess_pipe_smoke`、`test_subprocess_usage_error_exit_2` |
| 1i | ↳ 参数校验 | 通过 | `test_usage_errors_exit_2`：缺子命令、未知子命令、阈值 85/abc/nan、互斥开关同用、未知字段、缺 --backup、未知参数 |
| 2 | `--help` exit 0 且列出三个子命令；端到端 normalize 输出规范值且 exit 0 | **通过** | §3 判据 2a、2b |
| 3 | 边界：改动 ⊆ `_Boundary:_` | **通过** | 见下表 |

| 实际改动 | 在 `_Boundary:_` 里声明了吗 | 判定 |
|---|---|---|
| `src/zhclean/cli.py` | ✔ | 界内 |
| `tests/test_cli.py` | ✔ | 界内 |
| 其他 | — | **无越界**；`tools/**`、`rules/**`、`benchmarks/**`、`pyproject.toml` 都没动 |

## 5. 遗留 / 不确定 / 需要拍板

- **5-1 没有 `zhclean` 这个可执行命令**。`pyproject.toml` 里没有 `[project.scripts]`，所以现在只能用 `python -m zhclean.cli` 调用，契约写的也是这种方式。要让 `zhclean normalize …` 直接能用，需要在 pyproject 加一行 `zhclean = "zhclean.cli:main"`，但这超出本单范围。另外 `main` 返回的是退出码，console script 包装器会把它当作 `sys.exit(main())` 处理，可以直接用。
- **5-2 §2-2 里的 6 条口径**，最需要脑决定的是：
  - ③ `--apply` 不写 `--out` 时默认写 `<input>.cleaned.jsonl`；
  - ④ 默认不覆盖已有文件，要覆盖须加 `--force`。
  契约里没有 `--force` 这个参数，是我加的安全阀。
- **5-3 cli 没接 `loop.py`**。原模块头写的是「分发到 Agent Loop 或工具」，本单契约只要求串接三个工具，所以模块头改成了「分发到三工具」。Agent Loop 什么时候接进来，由脑排期。
- **5-4 测试读了真实数据**。Capability 里写的是「读 `src/zhclean/**`」，没有明说可以读 `benchmarks/dirty`；但判据 1 要求「tmp 文件进出真实数据」，所以测试在运行时读取 `benchmarks/dirty/*.jsonl`：
  - 只取 **train** 行，每个字段 5 个 id，共 100 行；
  - 只保留 id/field/value，**丢掉 truth**；
  - 没碰 heldout，也**没读** `benchmarks/generate.py`。
- **5-5 dedupe 是 O(u²)**：cli 没做分桶，大文件（每个字段上万个不同值）会比较慢。分桶方案是 RESULT-011 §6-3 的遗留项。
- **5-6 申报副产品**：
  - pytest 在系统临时目录下生成的 `tmp_path`（仓库外）；
  - `__pycache__/*.pyc` 和 `.pytest_cache/`（属于豁免清单第 1 类）。
  - 冒烟命令都走管道，没往仓库里写任何文件。**没有清单外的新文件。**

## 6. 建议下一步

- **6-1**：在 `pyproject.toml` 加 `[project.scripts] zhclean = "zhclean.cli:main"`（见 5-1），让「一键」能直接敲 `zhclean`。
- **6-2（M1 验收汇总）**：README 可以直接用模块头里的 5 条用法示例。「失败案例公开」可以引用 RESULT-011 §5-3 的 hub 桥接局限，以及 train 上 person 的 10 个漏并对和 72 个误并对。
- **6-3**：CLI 可以加一个 `pipeline` 子命令（audit --apply → dedupe 一步完成），是否需要请脑定。本单没有做。

## 7. 下次接着做什么（写给下一轮的你）

- **做到哪了**：TASK-012 已完成。`python -m zhclean.cli` 有 normalize / dedupe / audit / rollback 四个子命令，退出码 0/1/2，全量 405 个测试通过。**没提交，没动 TASK 状态字段。**
- **下一步第一件事**：等脑验收，重点是 §5-2 的 `--force` 和默认输出名、§5-1 的 console script。验收后去读 `.handoff/inbox/` 里编号最大的那个 TASK，预期是 M1 验收汇总（README、失败案例、发布准备）。
- **要绕开的坑**：
  1. `main()` 支持注入 stdin/stdout/stderr。测试里传的是 `StringIO`，它没有 `.buffer`，所以 `_read_text` 有回退分支，别删。
  2. 子进程跑中文时，靠 `__main__` 里的 `_utf8_stdio()` 保证 utf-8 输出。如果有人改成 `main()` 里直接 `print`，并把 sys.stdout 传进去，要先确认这一步还在。
  3. dedupe 用 `id(row)` 把组映射回行，**前提是三个工具返回的是原行对象**（TASK-008 的约定）。工具层如果改成返回拷贝，cli 会报 KeyError。
  4. 判据命令都要加 `uv run --project .` 前缀。heldout 已经在 TASK-011 用过一次，以后调参只用 train。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 bba71c5）｜可审文件: 2 ｜已审: 2 ｜跳过: 0 ｜覆盖率: 2/2
（cli.py 293 行全文 + test_cli.py 41 用例）
按严重度: critical 0, high 0, medium 0, low 2

| path | severity | category | content |
|---|---|---|---|
| src/zhclean/cli.py | low | maintainability | `_cmd_normalize`/`_cmd_dedupe` 的 `{**r, 新增键}` 会静默覆盖输入行同名字段（normalized/confidence/_group）——输出约定已隐含，可文档化 |
| src/zhclean/cli.py | low | performance | `_cmd_audit` 里 `apply` + `audit(dry_run=False)` 各跑一遍（后者内部再调 apply）——重复计算，纯函数保证结果一致；大批量时与 TASK-010 的 low 项一并优化 |

审查结论：**通过**。stdin/stdout/stderr 可注入设计让 41 个用例能直接断言退出码与内容；错误带行号；「无 --out 时 stdout 纯 jsonl、汇总走 stderr」的流分工是管道友好的正确设计；先备份后清洗 + --force 覆盖保护是合格的安全阀。

**§5-2 六条口径裁决（脑定，全采纳）**：stdin 缺省 / 输出流分工 / 默认输出名 / --force 不覆盖 / 先备份后清洗 / 中文化——全部合理且已实现。

**亲跑核验**：405 passed；`--help` exit 0；normalize 管道端到端 ✓；audit --apply + rollback 往返**逐行数据相等**（脑亲验，文件哈希差异仅为行尾编码）✓。

**§5-1 处置（脑侧执行）**：`[project.scripts] zhclean = "zhclean.cli:main"` 由脑在验收后直接加进 pyproject 并亲验 `zhclean` 命令（「一键」卖点的最后一步，属治理件不占手单）。§5-3 loop 未接：Agent Loop（Phase 2）排 M1 验收后。**里程碑：M1 功能全齐（四类 normalize + dedupe + audit + CLI）。**

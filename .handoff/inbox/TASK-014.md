# TASK-014　乱码修复（一行）+ Agent Loop 骨架（observe→think→act + HITL）

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `src/zhclean/cli.py`（乱码修复）、`src/zhclean/loop.py`、`tests/test_cli.py`（乱码回归用例）、`tests/test_loop.py`（新建）、`README.md`（删乱码提示行） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `src/zhclean/**`（normalize/dedupe/audit 接口）、`task_plan.md`、`findings.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件（尤其 benchmarks/generate.py 词典常量——不可读）** |
| **_Depends:**（依赖） | TASK-013（已通过，`65be228`） |
| **_Commit:**（对应提交） | `3c28a97`（脑验收通过后提交） |

## 1. 目标（一句话）

两件事：①修复 `zhclean` console script 在 Windows 的中文乱码（`_utf8_stdio()` 挪进 `main()` 的注入守卫内，一行级别 + 子进程中文回归测试 + 删 README 乱码提示行）；②`src/zhclean/loop.py` 写**手写 Agent Loop 骨架**（observe→think→act + 最大步数 + 停止条件 + 单条失败不中断 + 低置信 HITL）——这是本项目的 #1 件功夫练习件。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/cli.py`（仅乱码修复：`_utf8_stdio` 位置调整）
- `src/zhclean/loop.py`（Agent Loop 骨架实现）
- `tests/test_cli.py`（新增子进程中文回归用例）
- `tests/test_loop.py`（新建，loop 单测）
- `README.md`（仅删「安装」一节乱码提示那段）
- 除此之外**一律不许动**（尤其 `src/zhclean/{rules,tools}/**`、`benchmarks/**`、`pyproject.toml`、`docs/**`）

## 2.5 契约（脑定，照此实现）

**① 乱码修复**：把 `_utf8_stdio()` 移进 `main()`（在参数解析前、仅当 `stdout/stderr` 是 `sys.stdout/sys.stderr` 原对象时调用——`io.TextIOWrapper` 判断已天然跳过注入的 StringIO）；`__main__` 里去掉调用。新增子进程测试：真实 `uv run --project . zhclean normalize` 或 `--help`，断言 stdout 里中文正常（子进程环境不带 PYTHONIOENCODING）。

**② loop 骨架**（M1 最小闭环版，LLM 兜底后续接）：

- `run_loop(rows, *, max_steps: int | None = None, hitl_threshold: float = 0.2) -> dict`：
  - **observe**：逐行读 field/value（缺 field 的行 → errors 记录，不中断）；
  - **think**：对每行调 `normalize_with_confidence`；置信度 < `hitl_threshold` → 结果进 `hitl` 列表（原值保留，不猜）；
  - **act**：置信度 ≥ 阈值 → 应用规范值（cleaned 行 value 替换，`_before` 存原值——对齐 audit 口径）；
  - **单条失败不中断**：单行 normalize 抛异常 → 记入 `errors`（行号 + 异常信息），继续下一行；
  - **最大步数**：`max_steps` 限制处理行数（None = 全部）；**停止条件**：行处理完或步数耗尽；
  - 返回 `{"cleaned": [...], "hitl": [...], "errors": [...], "steps": n}`；确定性（同输入同输出）。
- 模块头 F/R/A/S 四行对齐既有风格；`python -m zhclean.loop --demo` 自检（≥6 断言：正常清洗、低置信 HITL、单条异常不中断、max_steps 停止、空输入、确定性）。
- 设计取舍写模块头：loop 只做**编排**，清洗逻辑全在 normalize 里；LLM 兜底预留 think 阶段的扩展点（低置信行进 hitl，就是将来 LLM 的输入）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 405 + 新增 test_loop ≥10 用例 + test_cli 乱码回归 ≥1）；乱码回归：子进程跑 zhclean 入口断言中文输出正常 |
| 2 | 乱码修复亲验 + loop 自检 | `uv run --project . zhclean --help`（不带 PYTHONIOENCODING）+ `uv run --project . python -m zhclean.loop` | `--help` 中文正常显示 exit 0；loop 输出 `loop._demo: OK` exit 0 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/{rules,tools}/**`（cli.py 乱码行除外）、`benchmarks/**`、`pyproject.toml`、`docs/**`（README 乱码提示行除外）、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-014）
- 不许跑：`rm -rf`、git commit / push / add
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 `benchmarks/generate.py` 词典常量

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀（乱码回归测试的子进程除外——它要模拟真实用户环境）。
- loop 是 #1 件功夫（Agent Loop）的核心练习；llm.py 兜底在下一单接进 think 扩展点。
- 手脑方案：干完写 `.handoff\outbox\RESULT-014.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。两条判据均经脑亲跑：①`uv run --project . pytest tests/ -q` → 425 passed；②无 PYTHONIOENCODING 时 `zhclean --help` 中文正常 exit 0（乱码修复生效）+ `python -m zhclean.loop` → `loop._demo: OK`。
- 边界检查：5 个改动文件 ⊆ `_Boundary:_`（零越界）。
- **结构化代码审查**（5/5 覆盖 100%）：critical/high/medium/low 全 0；回归用例经脑侧验证非摆设（旧码下必红）。
- §5-2 六条空白口径全采纳。
- **§5-1 口径缺陷裁决**：采纳修法 ①+②（rules 拆 CONF_CLEAN=0.95 + loop HITL 判据改为「低置信且 after != value」+ unchanged 桶），排 TASK-015 一单做完；手按契约字面实现+钉测试是正确的，缺陷在契约。
- §5-6 三个 demo 入口同病：排 TASK-015 把 `_utf8_stdio` 抽公共模块统一。
- **里程碑：乱码修复生效 + Agent Loop 骨架落地（#1 件功夫练习件就位）。**
- `_Status: 已完成`；`_Commit: 3c28a97`。

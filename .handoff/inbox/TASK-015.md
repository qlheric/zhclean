# TASK-015　置信度语义拆分（CONF_CLEAN）+ loop 桶语义 + demo 入口编码统一

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 待执行 |
| **_Boundary:**（只许动） | `src/zhclean/rules/common.py`、`src/zhclean/rules/{person,phone,company,address}.py`、`src/zhclean/tools/audit.py`、`src/zhclean/loop.py`、`src/zhclean/cli.py`、`src/zhclean/_compat.py`（新建）、`tests/{test_normalize,test_phone,test_company,test_address,test_audit,test_loop,test_cli}.py`、`docs/failures-m1.md` |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `src/zhclean/**`、`task_plan.md`、`findings.md`、train 失败样本（可）。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外文件（尤其 benchmarks/generate.py 词典常量——不可读；heldout 不跑）** |
| **_Depends:**（依赖） | TASK-014（已通过，`3c28a97`） |
| **_Commit:**（对应提交） | 脑验收后填 |

## 1. 目标（一句话）

三件口径修正一单做完（脑裁决 RESULT-014 §5-1 + §5-6）：①**置信度语义拆分**——`CONF_CLEAN=0.95`（值已规范、结构上本就干净）与 `CONF_NONE=0.1`（无法处理/拿不准）分开，四字段「结构干净且像本字段合法值」给 0.95；②**loop 桶语义**——HITL 判据改为「低置信**且 after != value**」，低置信且未改的行进新增 `unchanged` 桶（对齐 audit）；audit `_BANDS` 加 "0.95" 档（reason "clean"）；③**demo 入口编码统一**——`_utf8_stdio` 抽到新建 `src/zhclean/_compat.py`，cli/loop/audit/dedupe 四个入口统一使用，`docs/failures-m1.md` 里残留的 `PYTHONIOENCODING` 前缀清掉。**评测数字必须不变**（train 复跑对照台账）。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/rules/common.py`、`rules/{person,phone,company,address}.py`（置信度档位语义）
- `src/zhclean/tools/audit.py`（_BANDS 加 0.95 档）
- `src/zhclean/loop.py`（unchanged 桶 + HITL 判据）
- `src/zhclean/cli.py`、`src/zhclean/_compat.py`（_utf8_stdio 抽公共；audit/dedupe/loop 的 __main__ 同步改）
- 七个测试文件（断言随口径更新）
- `docs/failures-m1.md`（清 PYTHONIOENCODING 前缀）
- 除此之外**一律不许动**（尤其 `tools/{normalize,dedupe}.py`、`benchmarks/**`、`pyproject.toml`、`README.md`）

## 2.5 契约（脑定，照此实现）

- `CONF_CLEAN = 0.95`（值已规范）：各字段在「结构清洗没命中、值本身已像本字段合法值」时返回 `(value, CONF_CLEAN)`——判据用各字段已有的 `_looks_like_*` / `_is_valid`；**无法处理/拿不准**仍 `CONF_NONE=0.1`。
- **评测数字不变是硬约束**：规范化**输出值**（after）必须与改动前逐字节一致——变的只有置信度。train 复跑对照：总盘 85.88%（687/800）、person 72 / phone 100 / company 81 / address 90.5；heldout **不跑**（已定版）。
- loop 返回结构改为 `{"cleaned", "unchanged", "hitl", "errors", "steps"}`：`conf < hitl_threshold 且 after == value` → unchanged（原行浅拷贝 + confidence）；`conf < hitl_threshold 且 after != value` → hitl（M1 里为空，LLM 接入后才有内容）；其余 → cleaned（同现状）。
- `_compat.py`：`utf8_stdio()`（原 `_utf8_stdio` 实现）；四个模块的 `__main__` 与 cli.main 统一调用；demo 入口在无 PYTHONIOENCODING 时中文输出正常（新增/更新回归测试）。
- audit `_BANDS` 加 `("0.95", CONF_CLEAN, "clean")`；`by_confidence` 键含 "0.95"；format_report 显示该档。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 425 更新后 + 新增：四字段「已规范值→0.95」用例、loop unchanged/hitl 桶语义用例、audit 0.95 档用例、demo 入口中文回归） |
| 2 | 评测数字零漂移（train 复跑） | `uv run --project . python -m benchmarks.evaluate --impl rules`（默认 heldout 不跑；改 `--split train`） | train 数字与改动前一致（规范化输出逐字节不变）；**heldout 不跑** |
| 3 | demo 入口编码 | `uv run --project . python -m zhclean.loop --bogus` 等四个入口（无 PYTHONIOENCODING） | 错误提示中文正常（utf-8 字节，非 GBK） |

## 4. 禁区（碰了即作废）

- 不许改：`tools/{normalize,dedupe}.py`、`benchmarks/**`、`pyproject.toml`、`README.md`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-015）
- 不许跑：`rm -rf`、git commit / push / add；**heldout 评测不跑**
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**；不读 `benchmarks/generate.py` 词典常量

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 本单是「口径修正」不是功能开发：改动后的 normalize **输出值**不许变（评测数字零漂移是判据 2），变的只是置信度语义与桶划分。
- 手脑方案：干完写 `.handoff\outbox\RESULT-015.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

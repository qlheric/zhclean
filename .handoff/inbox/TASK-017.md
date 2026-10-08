# TASK-017　M1 收官：CI 工作流 + README 许可证段 + 发布检查单

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `.github/workflows/ci.yml`（新建）、`README.md`（补 License 段）、`docs/release-checklist.md`（新建） |
| **_Capability:**（只许用） | 写 YAML/Markdown 文档；跑 `uv run` / `pytest` 命令（本地等价验证 CI 步骤）；读 `pyproject.toml`、`README.md`、`LICENSE`、`task_plan.md`。**禁止：联网、装新包/改依赖、git commit、调用其他 agent、动范围外任何文件** |
| **_Depends:**（依赖） | TASK-016（已通过，`5783929`） |
| **_Commit:**（对应提交） | `1e3213b`（脑验收通过后提交） |

## 1. 目标（一句话）

M1 收官三件套：①`.github/workflows/ci.yml`（push/PR 触发：uv 装依赖 → pytest 全量 → 三个 demo 自检）；②README 补 License 段（MIT，qlheric 2026）；③`docs/release-checklist.md` 发布检查单（发布前的逐项清单：数字定版、失败案例、安装验证、README 纪律）。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `.github/workflows/ci.yml`（新建）
- `README.md`（补 License 段，其余不动）
- `docs/release-checklist.md`（新建）
- 除此之外**一律不许动**（尤其 `src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`、`LICENSE`、`docs/failures-m1.md`）

## 2.5 契约（脑定，照此实现）

- ci.yml：
  - 触发：`push`（main）+ `pull_request`。
  - jobs：`ubuntu-latest`（或 windows 亦可——**建议 windows-latest**，因为本项目在 Windows 开发、有编码回归测试；若跑不通改 ubuntu 并在回执说明）→ steps：`checkout` → `setup-python 3.12` → `pip install uv` → `uv sync --project .`（含 dev 组）→ `uv run --project . pytest tests/ -q` → 三个 demo（`python -m zhclean.loop / tools.audit / tools.dedupe / llm`）。
  - `PYTHONIOENCODING=utf-8` 写入 env（部分断言依赖中文输出）。
- README License 段：一句话 + 链接（`[MIT](LICENSE) © 2026 qlheric`），放在「路线」之后。
- release-checklist.md：逐项清单（每个 checkbox 一行），至少覆盖：评测数字定版（heldout 不重跑）、README 数字与台账一致、失败案例已公开、`zhclean --help` 与三条快速上手命令实跑通过、安装命令实跑、License 存在、git tag 建议。声明「本清单由 M1 收官生成，发布前逐项打勾」。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 467 passed |
| 2 | CI 步骤本地等价验证 | `uv sync --project . && uv run --project . pytest tests/ -q && for m in zhclean.loop zhclean.tools.audit zhclean.tools.dedupe zhclean.llm; do uv run --project . python -m $m; done` | 全部 exit 0、四个 demo 均 `OK` |
| 3 | YAML 语法有效 | 回执贴 Python `yaml.safe_load` 解析 ci.yml 通过（或注明用哪个工具验证） | 解析无错 |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/**`、`tests/**`、`benchmarks/**`、`pyproject.toml`、`LICENSE`、`docs/failures-m1.md`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-017）
- 不许跑：`rm -rf`、git commit / push / add（**不许真的 push 到 GitHub**）
- 不许动：`.credentials.yaml` 及任何密钥；**不联网**

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- README 纪律（老大 2026-10-03 令）：只加 License 段，先通读全文确认不重复。
- 本单是 M1 的收尾单；完成后 M1 全部收官，进入 M2（金额/日期/身份证/邮箱）。
- 手脑方案：干完写 `.handoff\outbox\RESULT-017.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。三条判据均经脑亲跑：①467 passed；②CI 本地等价四 demo 全 OK；③系统 python yaml.safe_load 解析通过。
- 边界：3 个改动文件 ⊆ `_Boundary:_`（零越界）。
- §5 处置：YAML 用系统 python 合理；**CI 未真跑属诚实标注**——合并后盯首跑，红了按 §5-3 两条兜底；git tag 由维护者执行。
- **里程碑：M1 全部收官。** 下一单进 M2。
- `_Status: 已完成`；`_Commit: 1e3213b`。

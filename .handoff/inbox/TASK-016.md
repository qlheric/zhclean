# TASK-016　llm.py 兜底接入（三级：规则 → LLM → HITL）+ 文档档位补记

| 项 | 值 |
|---|---|
| 发起（大脑） | DSH |
| 日期 | 2026-10-08 |
| 执行（手） | Claude Code（侧边栏终端） |
| 项目路径 | G:\Agentwork_mvp\s2-中文脏数据净化器-zhclean |
| 状态 | 已通过 |
| **_Boundary:**（只许动） | `src/zhclean/llm.py`（新建）、`src/zhclean/loop.py`（think 扩展点接入 llm_fn）、`tests/test_llm.py`（新建）、`tests/test_loop.py`（扩展用例）、`README.md`（档位描述补 0.95，两处）、`findings.md`（档位行补 0.95，一处）、`tests/test_normalize.py`（第 91 行过期注释） |
| **_Capability:**（只许用） | 写 Python 代码（stdlib + 已声明依赖）；跑 `uv run` / `pytest` 命令；读 `src/zhclean/**`、`task_plan.md`、`findings.md`。**禁止：联网（测试用 mock，不发真 API 请求）、装新包/改依赖、git commit、调用其他 agent、动范围外文件（尤其 benchmarks/generate.py 词典常量——不可读；heldout 不跑）** |
| **_Depends:**（依赖） | TASK-015（已通过，`47959c4`） |
| **_Commit:**（对应提交） | `5783929`（脑验收通过后提交） |

## 1. 目标（一句话）

`src/zhclean/llm.py` 实现可插拔 LLM 兜底客户端（OpenAI 兼容协议，deepseek/qwen；GPT-6 用 `max_completion_tokens`——注释写死），`loop.py` 的 think 扩展点接入：**规则低置信 → LLM 兜底 → 仍低置信 → HITL** 三级闭环。**测试全部用 mock（不发真 API、不联网）；真调用留给使用方。** 另把 README/findings 三处旧档位描述补上 0.95 档（RESULT-015 §5-4）。

## 1.5 基线（开工前第一件事，必须做）

在项目根跑一次并**把输出贴进回执**：

```
git status --porcelain -uall
```

## 2. 范围（只许动这些）

- `src/zhclean/llm.py`（新建：客户端 + 提示词 + 兜底函数）
- `src/zhclean/loop.py`（仅 think 段加 `llm_fn` 可选参数接线）
- `tests/test_llm.py`（新建）、`tests/test_loop.py`（扩展用例）
- `README.md`（两处档位描述）、`findings.md`（一处档位行）、`tests/test_normalize.py`（过期注释一行）
- 除此之外**一律不许动**（尤其 `src/zhclean/rules/**`、`tools/**`、`benchmarks/**`、`pyproject.toml`、`docs/failures-m1.md`）

## 2.5 契约（脑定，照此实现）

- `LLMClient(base_url: str, api_key: str, model: str, timeout: float = 30)`：
  - `complete(prompt: str) -> str`：POST `{base_url}/chat/completions`，body 用 `max_completion_tokens`（GPT-6 系）+ `messages`；非 200 抛 `LLMError`（带状态码与响应摘要）。
  - 实现用 stdlib `urllib.request`（不新增依赖）。
- `llm_normalize(value: str, field: str, client) -> tuple[str, float]`：
  - 提示词要求：只输出规范值（不要解释）；若无法确定，输出原值。
  - 响应解析：strip 后若等于原值 → `(原值, 0.1)`；否则 `(结果, 0.85)`（LLM 兜底置信档，常量 `CONF_LLM = 0.85`，与 rules 档位区分）。
  - 解析失败/异常 → `(原值, 0.1)`，不抛出（兜底失败即回 HITL）。
- `run_loop(rows, *, max_steps=None, hitl_threshold=0.2, llm_fn=None)`：
  - think 段：规则置信度 < hitl_threshold 的行，若提供 `llm_fn`，先试 `llm_fn(value, field)`（签名同 llm_normalize）；LLM 结果置信度 ≥ hitl_threshold → 落 cleaned（同 act 口径，_before 只给真改过的）；否则 → hitl。
  - **不提供 llm_fn 时行为与 TASK-015 逐字相同**（有用例锁住）。
  - 成本护栏：`llm_max_calls: int | None = None`——超过上限后剩余低置信行直接进 hitl，不再调 LLM。
- 模块头 F/R/A/S 四行 + 三级流说明；`python -m zhclean.llm --demo` 自检（mock 客户端 ≥6 断言）。

## 3. 验收判据（必须可执行）

| # | 判据 | 怎么验（命令） | 期望结果 |
|---|---|---|---|
| 1 | 测试全绿 | `uv run --project . pytest tests/ -q` | 全绿（原 437 + 新增：三级流（规则成功不调 LLM / 低置信走 LLM 成功 / LLM 失败回 HITL）、LLM 返回原值、解析失败、**llm_max_calls 护栏**、无 llm_fn 行为不变、mock 客户端不联网） |
| 2 | demo 自检 | `uv run --project . python -m zhclean.llm` | 输出 `llm._demo: OK`，exit 0（全程 mock，零网络请求） |

## 4. 禁区（碰了即作废）

- 不许改：`src/zhclean/rules/**`、`tools/**`、`benchmarks/**`、`pyproject.toml`、`docs/failures-m1.md`、`AGENTS.md`/`CLAUDE.md`、`.handoff/**`（除 RESULT-016）
- 不许跑：`rm -rf`、git commit / push / add；**任何真实 API 请求**
- 不许动：`.credentials.yaml` 及任何密钥（读 key 只通过环境变量名约定，**不读文件**）；不读 `benchmarks/generate.py` 词典常量

## 5. 回滚方式

未提交前：删除本单新增/修改文件即回原状。若脑已提交：`git revert <sha>`。

## 6. 备注

- 判据命令一律 `uv run --project .` 前缀。
- 模型渠道参考（findings）：DeepSeek 官方 `DEEPSEEK_API_KEY` / 智谱 `ZHIPU_API_KEY`，OpenAI 兼容协议；GPT-6 系列用 `max_completion_tokens`。
- LLM 兜底是 S2 架构「规则 80% + LLM 20%」的 20% 部分；真调用控量（llm_max_calls + 批量）是使用方责任，本单只给护栏。
- 手脑方案：干完写 `.handoff\outbox\RESULT-016.md`（判据/命令/输出/证据 + 第 7 节），然后停下；不动 TASK 状态字段。

## 7. 验收结论（2026-10-08 · 脑）

- **已通过**。两条判据均经脑亲跑：①`uv run --project . pytest tests/ -q` → 467 passed；②`uv run --project . python -m zhclean.llm` → `llm._demo: OK` exit 0（mock 零网络）。
- 边界检查：6 个改动文件 ⊆ `_Boundary:_`（零越界）。
- **结构化代码审查**（6/6 覆盖 100%）：critical/high/medium/low 全 0；「不给 llm_fn 逐字不变」有 3206 行 × 4 组参数全等实据。
- 三拍板裁决：①findings 已改确认（脑侧派单时已写好）；②unchanged 恒空采纳契约字面语义（LLM 存在时低置信行就该进人工队列）；③client_from_env 采纳（生产构造必需、零 key 硬编码）。
- 手自报 rm -rf 被拦不记失分（没执行过）。
- **里程碑：Agent Loop（#1）+ Tool Design（#3）两件功夫练齐。**
- `_Status: 已完成`；`_Commit: 5783929`。

# Task Plan: S2「中文脏数据净化器」(zhclean)

## Goal

做一个**真实解决需求、按产品/生产级标准做**的中文脏数据净化 CLI：M1 四类（人名/地址/电话/公司名）做透（规范化 + 去重 + audit，留出集每类规范化 ≥95%、去重 recall ≥95%），M2 扩展金额/日期/身份证/邮箱到整表清洗；练 6 件功夫里的 #1 Agent Loop + #3 Tool Design。

## 口径锁定（老大 2026-10-06 grilling 对齐，全量锁定）

1. **S 档也要做完美、真实解决需求**，不是「当天可玩」demo；涨星公式的「极小实现(当天可玩)」因子不作数——按产品/生产级做。
2. 形态 **CLI**；Agent Loop **手写**（while + 最大步数 + 停止条件 + 错误恢复 + 低置信度 HITL）。
3. 清洗策略：**规则打底 80% + LLM(API) 兜底 20%**（可插拔；deepseek/qwen，OpenAI 兼容协议；GPT-6 系列用 `max_completion_tokens`）。
4. 评测体系：**程序化扰动 + 留出集**；ground truth = 扰动前原值；每类规范化 ≥95%、去重 recall ≥95%、**失败案例公开**。
5. **≥95% 是目标不是承诺**——地址/公司名语义清洗难，M1 结束前实测报真实数。
6. **benchmark 先行**（可核是命门）；规则库不得针对测试扰动模式调参（留出集防过拟合）。
7. 三工具：`normalize`（脏值→规范值+置信度，schema 显式）/ `dedupe`（hash 精确 + rapidfuzz 语义）/ `audit`（报告 + dry-run + 可回滚）。

## 开发流程（手脑方案 · 老大 2026-10-07 令）

- **脑**（DSH 对接入口会话）写 `.handoff/inbox/TASK-NNN.md`（七项必填：目标/基线/`_Boundary:_`/`_Capability:_`/`_Depends:_`/判据/状态）；**手**（本会话）读 TASK → 干生产活 → 写 `.handoff/outbox/RESULT-NNN.md`（四项必填：判据/命令/输出/证据）；**状态只有脑能改**。
- 手**不递归委派**（不调动其他模型写码）、不越 `_Boundary:_`；单条数据失败不中断整体。
- **索引纪律**：aoci 认知索引先行并随改动同步（`update-entry` + `check`），防止越做越歪。

## Current Phase

Phase 0（立项骨架）→ 本会话完成中

## Next Step

等脑派 **TASK-001（benchmark 先行）**；收到即开工。

## Phases

### Phase 0: 立项骨架

- [x] 目录结构（§五锁定：src 布局 + tools/ + rules/ + tests/ + benchmarks/）
- [x] git 初始化 + 基线提交
- [ ] aoci 认知索引（23 条 + check）
- [ ] .handoff 机制安装（handoff-init.ps1）
- [ ] 规划件落盘（task_plan / findings / progress）
- **Status:** in_progress

### Phase 1: benchmark 先行（可核是命门）

- [ ] 干净集（ground truth：人名/地址/电话/公司名 各 N 条）
- [ ] 程序化扰动生成器（加空格/错别字/简称/重复/格式乱；ground truth = 扰动前原值）
- [ ] 留出集划分（规则库不得针对测试扰动模式调参）
- [ ] 评测脚本骨架（规范化率 / 去重 recall 计算 + 失败案例落 results/）
- **Status:** pending

### Phase 2: Agent Loop 骨架

- [ ] `loop.py`：observe（读数据→识别脏字段）→ think（选工具：规则 or LLM）→ act（调工具）
- [ ] 最大步数 + 停止条件 + 单条失败不中断 + 低置信度走 HITL
- **Status:** pending

### Phase 3: normalize 四类做透（最小闭环先行）

- [ ] normalize(人名) 打通最小闭环（含置信度、schema 显式）
- [ ] 电话 → 地址 → 公司名 逐个补规则词典
- **Status:** pending

### Phase 4: dedupe + audit

- [ ] dedupe：hash 精确去重 + rapidfuzz 语义去重（阈值可配）
- [ ] audit：清洗报告 + dry-run 预览 + 可回滚
- **Status:** pending

### Phase 5: LLM 兜底 + M1 验收

- [ ] `llm.py` 可插拔 API 兜底（规则低置信 → LLM → 仍低置信 → HITL）
- [ ] M1 留出集实测：每类规范化 ≥95%、去重 recall ≥95%，**报真实数**；失败案例公开
- **Status:** pending

### Phase 6: M2 扩展（金额/日期/身份证/邮箱 → 整表清洗）

- [ ] 金额/日期规则词典
- [ ] 身份证/邮箱校验（格式级，不做真实性查询）
- [ ] 整表清洗（CSV/XLSX 进出）
- **Status:** pending

## Key Questions

1. GitHub 仓库名与发布时机（涨星相关，待脑/老大拍板）。
2. 规则词典数据源：姓氏/行政区划官方公开数据从哪取（避免版权与准确性坑）。
3. LLM 兜底的成本护栏：单次清洗的 token 预算与批处理控量口径。

## Decisions Made

| 决策 | 理由 |
|------|------|
| 目录 `s2-中文脏数据净化器-zhclean`、包名 `zhclean` | 镜像 S1 惯例（`s1-惜字如金-中文省token`） |
| src 布局 | 交接件 §五 锁定 |
| 开发走手脑方案 .handoff 单据 | 老大 2026-10-07 令 |
| aoci 索引先行 | 老大令「防越做越歪」；条目不含索引件自身（stock-tool 有 code_orphan 教训） |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| 沙箱 grantWrite(G:\Agentwork_mvp\plan) 失败（Win32 5） | 1 | diagnose-windows-sandbox-acl 修复：补当前账户 FullControl，读回验证通过；备份/撤销件在 G:\Agentwork_mvp\acl-recovery\ |

## Notes

- 模型渠道与 key 引用见 findings.md；词典与竞品事实以脑侧知识库为准。
- 启动收工规程（手）：开工读 `.handoff/outbox/` 最近两份 RESULT + inbox TASK；收工写 RESULT（四项必填）+ 第 7 节「下次接着做什么」。

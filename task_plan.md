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

- **脑** = 本会话（DSH）：与老大讨论、拆单（`.handoff/inbox/TASK-NNN.md`，七项必填）、亲跑判据验收、改状态、填 `_Commit:_` 并提交。
- **手** = 侧边栏 Claude Code（老大开终端）：读 TASK → 干生产活 → 写 `.handoff/outbox/RESULT-NNN.md`（四项必填：判据/命令/输出/证据 + 第 7 节「下次接着做什么」），然后停下。
- **状态只有脑能改**；手不递归委派、不越 `_Boundary:_`；单条数据失败不中断整体。
- **索引纪律**：aoci 认知索引随每单同步（新文件经 `scope activate` 放行 + 逐文件写条目 + `check`），防止越做越歪。

## Current Phase

**Phase 3 完成**（四类 normalize 收齐：person 72% / phone 100% / company 81% / address 90.5%，总盘 85.88%）；**TASK-007（维护单：common.py 合并 + 方位构词位置约束）已派**，手执行中

## Next Step

手交 `.handoff/outbox/RESULT-007.md` 后验收；之后进入 Phase 4（dedupe + audit）。

## Phases

### Phase 0: 立项骨架

- [x] 目录结构（§五锁定：src 布局 + tools/ + rules/ + tests/ + benchmarks/）
- [x] git 初始化 + 基线提交（3 次提交）
- [x] aoci 认知索引（28 条，check 五净可提交，S 覆盖 28/28）
- [x] .handoff 机制安装（handoff-init.ps1：inbox/outbox + 双模板 + AGENTS/CLAUDE 契约块）
- [x] 规划件落盘（task_plan / findings / progress）
- **Status:** complete

### Phase 1: benchmark 先行（可核是命门）

- [x] TASK-001 已通过（`32311d4`）：干净集 4×200 + 脏集 4×1000（5 类扰动）+ 留出集 8:2 + 9 条不变式测试
- [x] 干净集（ground truth：人名/地址/电话/公司名 各 200 条）
- [x] 程序化扰动生成器（加空格/错别字/简称/重复/格式乱；ground truth = 扰动前原值）
- [x] 留出集划分（train:heldout=8:2，seed 洗牌前 20% heldout；规则库不得针对测试扰动模式调参）
- [x] 评测脚本（TASK-002 已通过 `aab345a`：规范化率计算 + 失败案例落 results/ + stub/perfect 能红断言；脑侧结构化代码审查 2/2 通过）
- **Status:** complete

### Phase 2: Agent Loop 骨架

- [ ] `loop.py`：observe（读数据→识别脏字段）→ think（选工具：规则 or LLM）→ act（调工具）
- [ ] 最大步数 + 停止条件 + 单条失败不中断 + 低置信度走 HITL
- **Status:** pending

### Phase 3: normalize 四类做透（最小闭环先行）

- [x] normalize(人名) 最小闭环（TASK-003 已通过 `e64f6ac`：规则打底 + 置信度接口 + `--impl rules` 接入；**person heldout 72%**——space/sep/noise 100%、typo 60%、abbrev 0% 属预期）
- [x] 电话（TASK-004 已通过 `e44d3b0`：结构清洗 + 数字形近修复 + 校验闸门；**phone heldout 100%**）
- [x] 公司名（TASK-005 已通过 `01f03d5`：软闸门+缩写补全+错字修复；**company heldout 81%**，改坏 0）
- [x] 地址（TASK-006 已通过 `ddedddc`：行政区划词典+标记补全+三条单字守卫；**address heldout 90.5%**，改坏 8 条全为市字歧义已知限制）
- [x] 维护单（TASK-007 已派：抽 rules/common.py + 方位构词位置约束）
- **Status:** complete（四类收齐；Phase 4 dedupe+audit 待 TASK-007 通过后启动）

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
| **本会话=脑，Claude Code（侧边栏）=手** | 老大 2026-10-07 令（角色反转，脑不写业务代码） |
| aoci 索引先行 | 老大令「防越做越歪」；条目不含索引件自身（stock-tool 有 code_orphan 教训） |
| .handoff 单据与锁文件也入索引，逐文件写条目 | 排除规则=覆盖缩减需真人 TTY，且单据本身是认知资产 |
| pytest 入 dev 依赖（脑侧环境预备） | 手侧判据可离线跑，不碰 pyproject 边界 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| 沙箱 grantWrite(G:\Agentwork_mvp\plan) 失败（Win32 5） | 1 | diagnose-windows-sandbox-acl 修复：补当前账户 FullControl，读回验证通过；备份/撤销件在 G:\Agentwork_mvp\acl-recovery\ |
| aoci scope 变化要求 6 项真人 TTY 复核（含 2 条排除规则=覆盖缩减） | 1 | 撤销排除规则 → `scope activate` 放行安全自动变更 → 策略对齐；排除规则改为「.handoff 单据也入索引、逐张写条目」的既定口径 |
| AGENTS.md 条目 write_conflict（git eol=lf 重写工作区 → 基线 sha 错位） | 1 | 用磁盘实算 sha256 作为 `--source-sha256` 重写 → 零写入对齐，check 转绿 |

## Notes

- 模型渠道与 key 引用见 findings.md；词典与竞品事实以脑侧知识库为准。
- 启动收工规程（手）：开工读 `.handoff/outbox/` 最近两份 RESULT + inbox TASK；收工写 RESULT（四项必填）+ 第 7 节「下次接着做什么」。

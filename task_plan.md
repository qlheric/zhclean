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

**Phase 6（M2）** → TASK-026 已通过（`14d0d23`，**M2 字段层全部收官**：八类定版文档三线同步）；**TASK-027（整表清洗：table.py CSV + cli table 子命令，发布前最后一块功能）已派**，手执行中

## Next Step

手交 `.handoff/outbox/RESULT-027.md` 后：亲跑三条判据 + 结构化代码审查 → 边界 → 置状态 → 提交；之后发布准备（release-checklist 逐项 + 大写数字轴可选）。

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

- [x] dedupe 工具（TASK-008 已通过 `30e32eb`：hash 精确 + rapidfuzz 语义 + 先规范化；审查零发现）
- [x] dedupe 评测接入（TASK-009 已通过 `5229d99`：pair P/R/F1 + train 选阈；**heldout R85.42% / P100%**——recall 未达 95% 如实报，攻坚排 TASK-011）
- [x] audit 工具（TASK-010 已通过 `c40fc9b`：清洗报告 + dry-run 预览 + checksum 回滚；**M1 三工具齐**）
- [x] recall 攻坚（TASK-011 已通过 `8ef8adc`：按字段相似度 + link 守卫；**heldout R100/P100，train R99.90/P99.25**——达标，100/100 不作泛化承诺）
- [x] cli.py 串接（TASK-012 已通过 `9220c53`：四子命令 + `zhclean` 一键入口；脑侧加 [project.scripts] 并亲验）
- **Status:** complete（Phase 4 全绿）

### Phase 5: LLM 兜底 + M1 验收

- [x] 乱码修复 + Agent Loop 骨架（TASK-014 已通过 `3c28a97`：zhclean 无环境变量中文正常 + loop observe→think→act + HITL）
- [x] 置信度语义拆分 + loop 桶语义 + 编码统一（TASK-015 已通过 `47959c4`：CONF_CLEAN=0.95 / unchanged 桶 / _compat.py；评测零漂移）
- [x] `llm.py` 可插拔 API 兜底（TASK-016 已通过 `5783929`：规则 → LLM → HITL 三级 + llm_max_calls 护栏；**两件功夫练齐**）
- [x] M1 收官（TASK-017 已通过 `1e3213b`：CI + License 段 + 发布检查单）
- [x] M1 留出集实测：规范化总盘 85.88%（heldout）/ 86.16%（train）；去重 recall heldout 100% / train 99.90%——**报真实数**；失败案例公开（docs/failures-m1.md）
- **Status:** complete（M1 全部收官）

### Phase 6: M2 扩展（金额/日期/身份证/邮箱 → 整表清洗）

- [x] M2 评测集扩展（TASK-018 已通过 `714997a`：generate.py 加 amount/date，老四类逐字节不变）
- [x] 金额/日期规则 + 评测接入（TASK-019 已通过 `938dd6a`：**date 85.75% 顶天花板**（abbrev 可回收 100%）；amount 40.88% 瓶颈 = 干净集双形态混装（脑侧 TASK 规格缺陷认账：判据 1 与边界自相矛盾致 4 红挂账））
- [x] 修复单（TASK-020 已通过 `4eff077`：A 纯数字口径 + B _wan 去截断 + C 测试派生；**amount 99.00%**、4 红消除、老五类零漂移）
- [x] 定版单（TASK-021 已通过 `ce36e97`：amount 尾零修复 + **M2 heldout 定版**——总 87.92%、六类 72.00/90.50/100.00/81.00/100.00/84.00）
- [x] M2 文档更新（TASK-022 已通过 `16d02f4`：README 六类定版表 + failures-m2 + 台账）
- [x] 第三批字段评测集（TASK-023 已通过 `597b8b8`：generate.py 加 idcard/email，老六类逐字节不变；生日范围裁定 1970–1999）
- [x] 身份证/邮箱规则（TASK-024 已通过 `6f8d2db`：15→18 展开 + GB 11643 闸门 + email 位置判定修复；idcard 100% / email 51.5%、双零改坏；§5-a 收窄采纳 (A)）
- [x] 评测接入 + heldout 重定版（TASK-025 已通过 `bd80f42`：老六类 87.92% 逐位复现；idcard 100% / email 52.5% 首次定版；分列口径锁定）
- [x] 八类定版文档（TASK-026 已通过 `14d0d23`：README 分列表 + failures-m3 + 台账；**M2 字段层全部收官**）
- [ ] 整表清洗（TASK-027 执行中：table.py CSV + cli table 子命令；XLSX 待加依赖另单）
- [ ] 大写数字轴（壹/贰/叁）单独一单（已裁定，排队）
- [ ] 整表清洗（CSV/XLSX 进出）
- **Status:** in_progress

## Key Questions

1. GitHub 仓库名与发布时机（**已裁决 2026-10-09 老大：等 M2 全部完成一起发布**；仓库名暂定 zhclean，署名 qlheric，发布前再确认）。
2. 规则词典数据源：姓氏/行政区划官方公开数据从哪取（避免版权与准确性坑）。
3. LLM 兜底的成本护栏：单次清洗的 token 预算与批处理控量口径。

## Decisions Made

| 决策 | 理由 |
|------|------|
| **GitHub 发布时机 = M2 全部完成后一起发布** | 老大 2026-10-09 拍板（现在不发）；发布时仓库名暂定 `zhclean`、署名 qlheric，走 docs/release-checklist.md |
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

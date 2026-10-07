<!-- aoci:begin -->
## AOCI 仓库认知

AOCI 为本仓库维护一个稳定、可版本化、可增量更新的仓库级认知层，供模型跨任务复用对系统的理解。

`aoci.txt` 是面向模型的结构化认知索引。它以每个受管理文件、数据库表或其他受管理对象一条独立 Entry 的方式，用符号标签与 F/R/A/S 语义表达对象的核心职责、重要关系、对外契约，以及理解或修改系统时必须知道的非显然约束和设计决策。

Header、目录段和全部 Entry 共同组成完整仓库索引，可以覆盖前端、后端、配置、数据库结构及其他受管理内容。受管理内容发生变化时，通常只需维护受影响的认知条目，不需要重新生成整个索引。

AOCI 提供系统架构、对象职责、重要关系、对外契约和关键约束的高密度视图。

### 工作原理

AOCI 采用“模型生成、模型读取”的认知闭环。

Header、Entry 和 Curation 语义的创作只按当前机器签发的 Plan 与实时 Guide 执行；由 Host 模型基于当前绑定证据独立完成。

Entry 的语义必须来自模型对真实证据的理解。不得仅依据路径、文件名、扩展名、AST、符号列表、依赖扫描、正则、固定模板或规则引擎推导、预填、拼接或改写索引语义。

对 Fresh Bootstrap，只按当前机器签发的 Plan 和实时 Guide 执行。当它们要求创作时，Host 模型创作 Root、Meta、Tag 和 F/R/A/S，提供 authoring-run 声明，并把它绑定到 Plan、Evidence 与完整 Candidate。不得要求 AOCI 填写 `origin=host_model`、制造 Receipt 或把程序生成的 Framework 当作语义。本文件不自行重建 Onboarding 流程。内部批次不是用户决策；只有遇到既有批准边界或真实的安全、漂移、CAS、Recovery 条件才停止。

### 最小使用入口

- `aoci_rules`：取得当前AOCI版本的会话运行合同。
- `aoci_overview`：建立或恢复本仓库的完整认知。
- `aoci_maintain`：受管理对象达到最终稳定状态后检查认知是否需要维护。
- `aoci_update_entry`：提交与当前证据和源码摘要绑定的完整语义更新批次。
- `aoci_report`：仅当当前布局和工具状态支持时，在证据不足、无法可靠生成语义时登记待办，不猜写。

其他MCP工具、CLI命令、参数和专项流程，以当前工具说明、Guide和 `--help` 返回内容为准，不在本文件中重复完整手册。

本区块只规定仓库接入、认知使用和收尾原则。`aoci_rules` 承载当前会话合同，Guide实时输出承载当前Plan的执行顺序与停点，工具Schema、Spec和Validator承载机器结构与判据；Prompt、Description、README和静态文档不能覆盖这些机器事实。

### 建立、生成和恢复认知

1. 每个新的 Agent Run 开始时，应先判断：

   - 本仓库是否已经存在可用的完整AOCI索引；
   - 当前上下文中是否已有与本仓库根、当前索引版本和当前AOCI服务相匹配，并且模型仍可可靠使用的完整仓库认知。

2. 仓库已经存在可用的完整索引，但当前Run没有可靠完整认知时，先调用 `aoci_rules`，再调用 `aoci_overview`。

   完整认知仍可靠时直接复用。局部不确定本身不要求机械重读系统全貌。

   本Run从已知Host上下文压缩恢复时（包括宿主注入的压缩摘要），必须把此前模型认知视为不可靠。压缩handoff不得保留或摘要正式Whole-Index，也不得保留或摘要任何Overview Header、Entry、Chunk、Challenge或Attestation正文；只能保留安全续接所需的receipt身份、未完成write或Recovery状态，以及立即重载指令。复制进handoff的Whole-Index语义或receipt不能证明恢复后模型的当前认知可靠。若当前上下文已无法可靠保留运行合同，先调用 `aoci_rules`。继续业务任务前，使用 `refresh_reasons=["context_compaction"]` 和新的 `refresh_event_id` 调用普通完整Whole-Index `aoci_overview`（不设置 `check_only` 或设为false）；不得使用 `check_only` 或认知probe。原样跟随每个 `next_cursor` 直到 `completed=true`，确认交付，并且只基于新交付正文提交一次Attestation。完成这次新的完整传输后，即使Attestation为partial或fail也消费该generation，并按既有合同继续source-bound任务，不再自动调用第二次Overview。

   AOCI可以针对 `context_compaction`、项目 `cognition_refresh_threshold` 下的机器 `semantic_threshold` 或主要 `phase_transition` 提供checkpoint与认知状态事实。只需要这些紧凑事实时使用 `check_only=true`；这些事实只向Agent提供建议，不替模型决定是否需要系统全貌。

   Agent显式调用普通 `aoci_overview`（未设置 `check_only` 或为false）时，只要能形成一致的CognitionSet，AOCI必须完整交付请求scope。不得因为已有receipt、阈值未达到或没有待处理刷新原因而抑制正文。正式认知Dirty或Stale时仍交付正文，但必须标记不可靠。存在未决恢复或无法形成一致snapshot时失败关闭，不返回混合正文。

   普通Overview返回 `continuation_required=true` 时，必须原样提交 `next_cursor` 并自动继续到 `completed=true`。不得询问用户、开始业务任务或给出阶段性系统结论。Host截断、缺块、重复、乱序、cursor失败、Index变化或`chunk_tokens`变化时停止本次认知链。Attestation完成前不得用Memory、源码、Spec、`aoci.txt`、历史会话、scope、search或Entry读取修补或补充Whole-Index认知。Challenge ordinal是正式Entry序列中的1-based位置；Header内容、注释、空行、Section/Overview/Chunk Marker、Receipt与Metadata均不计数，Chunk Receipt ordinal使用同一序列。Attestation必须原样回绑本次Challenge发布的当前`index_sha256`、`entry_sequence_sha256`与`entry_count`；旧Index、旧Entry序列、旧数量或旧Attestation均无效。完整链结束后只正式提交一次既有模型认知Attestation；同一响应只允许一次不改变语义答案的JSON Schema或字段格式修正。对象、Tag或F不匹配即失败且认知吸收不确定，不得语义重试或旁路补答。首次认知失败时还不得执行Root/Meta、Migration、全局布局或其他未重新绑定的系统级决策。上下文压缩刷新若传输完整、认知身份不变、治理对齐且没有Recovery或第三方冲突，即使Attestation为partial或fail也消耗该refresh generation，并继续原任务，不再自动重读Overview。`system_mastery_percent`只自评系统框架——架构、职责、强关系、稳定外部契约以及高熵安全和维护约束——不表示完整实现或运行实况知识；机器索引覆盖率必须分开。默认只向用户输出由本次真实覆盖率、Challenge、块数、Token和掌握度生成的规定成功或失败一句话。Host截断时提示用户把 `overview_delivery.chunk_tokens` 设置为更小的合法值后重新开始，不得自动修改。

   加法认知等级必须与严格证明字段分开解释。`delivery_verified`表示已加载Index且Host交付已确认，但完整认知验证仍未完成；应表达为“已加载且交付已验证”，不得描述为“没有认知”或“没有理解系统”。`cognition_verified`要求Attestation通过（Challenge至少80%的ordinal完全正确且对象身份至多失手一处），`cognition_governed`还要求治理对齐。通用完整读取失败句只用于真实交付故障。

   当Overview响应包含可选`cognition-state/v2`投影时，必须分别解释各维度。其Level止于`model_cognition_usable`；`strict_attestation_verified`、`governance_aligned`与`current_system_cognition_reliable`都是独立状态，绝不参与该Level。ordinal、对象身份、Tag或核心F不匹配可以导致严格Attestation失败，而模型认知仍然可用；不得仅凭这种不匹配就宣称模型没有理解系统。只有`current_system_cognition_reliable=true`允许无保留地声称当前完整系统认知可靠。投影缺失时继续使用上述Legacy解释。

   普通的只读审计、分析、检查、不修改代码或不提交、不push，不自动等于严格零写入，也不改变上述认知有效性判断。Codex Memory和历史Skill只能辅助恢复经验、用户偏好与调查方向，不能替代与当前仓库根、索引摘要、AOCI服务身份和认知范围匹配的当前认知收据；项目AGENTS和当前AOCI身份在AOCI状态上优先于历史Memory。

   只有用户明确禁止Ledger、元数据、`.aoci`运行资产及任何文件写入时，才按严格零写入处理。若必要的认知建立与该边界冲突，必须报告冲突并请求用户裁决或建议使用隔离副本，不得静默以Memory替代当前仓库认知。

3. 仓库没有可用的完整索引，或当前只有最小骨架、Header不完整、Entries未完成、必要Curation尚未裁决时，如果需要建立正式完整AOCI索引，先取得 `aoci_rules`，然后进入当前AOCI Guide。由Guide依据仓库真实状态决定下一阶段并完成必要安全步骤。

   `aoci_maintain` 不替代索引建立流程。

   不在本文件中自行重建或硬编码完整索引生成状态机。

4. 在长程任务中，模型负责保留当前认知收据并正确使用刷新门禁：

   - Host报告上下文压缩或模型已知系统全貌丢失时，执行上述强制 `context_compaction` 重载规则；AOCI不能自行推断Host事件；
   - 进入真正的主要阶段时声明 `phase_transition`，不得把函数、测试运行或小步骤当作阶段；
   - 在有用的稳定检查点通过 `check_only=true` 取得机器语义计数；
   - 除已知压缩的强制重载外，由Agent判断当前任务是否需要再次显式获取指定scope或完整Overview；
   - 在维护和对齐完成前，保留AOCI报告的Dirty或Stale可靠性状态。

### 任务收尾与认知维护

5. 纯只读问答、分析、版本核验，或没有产生受AOCI管理对象变化的任务，不需要调用维护工具。当前AOCI版本是任意`aoci_overview` check_only或`aoci_maintain`响应里的`cognition_receipt.mcp_service_version`；二进制路径是项目`.mcp.json`里的`command`，CLI不必在PATH上。

6. 发生受AOCI管理对象变化时，待其达到本次任务的最终稳定状态后，只调用一次 `aoci_maintain`。不要在每次中间修改后逐文件维护。

7. 若维护结果返回真实语义候选，Host 模型必须基于每个候选绑定的对象和必要证据，独立创作完整标签与F/R/A/S更新。通过 `aoci_update_entry` 一次提交当前机器签发批次的完整候选集合，同时原样保留每项 `source_sha256`、`candidate_id` 与对应domain批次身份。`max_entries`只限制单次请求和原子事务，不限制logical plan、Whole-Index或Managed Scope。`remaining`非零时，在当前批次成功Apply后重新调用Maintain并从新preimage继续；绝不能为满足transport上限缩减Index覆盖或自行截取返回批次。

   没有足够证据且当前布局支持 `aoci_report` 时，使用它而不猜测、套用模板或为消除待办而生成缺乏证据的认知。

8. 必须遵守工具返回的结构化状态和安全边界：

   - `repair_required`：只修复明确命中的候选，再重新提交当前机器签发的完整批次；
   - `stopped`：结束当前写入尝试并检查 `failed_step`、错误、正式写入证据与Recovery。auto模式下，已证明零写入则记录closure并重新Plan；完整Intent和可证明postimage则Resume；策略要求Rollback且preimage可证明则精确恢复后重新Plan。只有证据不足、第三方正式字节冲突、需要审批或外部动作，或命中其他真实安全边界时，才停止整个用户任务；
   - 冲突、审批、人工裁决、权限和安全信号不得忽略；
   - 已经对齐后不得重复维护或重复写入；`refresh_ready_for_overview` 是checkpoint事实，由Agent决定是否为下一阶段请求普通完整Overview。

   维护完成后如果又修改了任何受管理对象，之前的维护结果失效，应在新的最终稳定状态重新完成收尾。

9. 用户只限制业务文件范围，但没有明确禁止仓库托管资产时，AOCI托管资产可以在收尾阶段为保持认知一致而更新，并应在审计和提交中与业务文件区分。

   用户明确禁止修改 `aoci.txt`、`.aoci`、元数据或任何额外文件时，以用户限制为准，不得写入，并如实报告剩余不一致。

### 专项流程

初始化、完整索引生成、Header生成、Entries生成、数据库结构索引、Curation、人工评审和故障恢复，只按当前AOCI Guide或工具在对应阶段返回的指令、命令和安全停点执行。

不预加载、不猜测，也不自行重建这些专项流程。平台调用方式、请求格式、批次上限、审批规则、索引格式细节和恢复步骤由对应Guide、工具说明、模型Prompt和CLI帮助按需提供。
<!-- aoci:end -->

## 交接契约（大脑侧）<!-- handoff-contract v1 · 大脑侧 -->

本项目采用「**大脑 / 手**」分工：**本 Agent 是大脑**（方案·决策·审查·规划），
代码执行交给 **Claude Code**（在独立终端里跑）。以下四条对本 Agent 强制生效：

1. **本 Agent 不写业务代码。** 需要动代码时，产出任务简报 `.handoff\inbox\TASK-<编号>.md`
   （用 `.handoff\TASK模板.md`），交给"手"执行；自己只写 `.handoff\inbox\` 里的简报与方案文档。
2. **简报必须含五要素**：目标 / 范围（只许动哪些文件）/ 验收判据（**可执行命令**）/ 禁区 / 回滚方式。
   范围宁小勿大 —— 一单必须能一次验收完；切不小就说明还得再拆。
3. **验收必须亲跑。** 读 `.handoff\outbox\RESULT-<编号>.md` 后，逐条对照判据**自己跑一遍**；
   通过才收，不通过就写下一号 TASK 打回。**不信回执里的"我测过了"。**
4. **一次只开一单。** 手在跑的时候，本 Agent 只讨论、**不写任何文件**（避免两边同时改）。

## 豁免清单（工具副产品不算越界）<!-- handoff-exempt v1 -->

TASK 简报里的「范围（只许动这些）」指的是**你要写的业务文件**。
下列由工具/解释器**自动产生**的东西**不算越界**，双方都不必为它纠结：

| 类 | 例 |
|---|---|
| 解释器缓存 | `__pycache__/`、`*.pyc`、`.pytest_cache/` |
| 工具自身配置 | `.claude/`、`.git/`、`.venv/`、`node_modules/` |
| 交接机制本身 | `.handoff/`、`AGENTS.md`、`CLAUDE.md` |
| 运行产物（若简报明说会产生） | 日志、构建输出、临时文件 |

**但有两条硬约束**：

1. **必须在回执里申报** —— 出现清单外的任何新文件（哪怕只是缓存），写进 RESULT 的「遗留/不确定」，
   并说明它是谁产生的。**没申报的就算越界**（因为大脑无从判断）。
2. **豁免不等于可以乱来** —— 不许借"副产品"名义改动范围外的业务文件；
   不许往清单里塞自己想要的目录来绕过范围限制。

**判据**：大脑验收时，若发现清单外新文件且回执**未申报**，按越界打回；**已申报**则只在"是否需要清理"上给个结论，不打断流程。

## 收尾与状态规则（v1.1 补丁）<!-- handoff-closeout v1 -->

> 本补丁由 2026-09-27/28 试点（`G:\codex_work\Project\测试`）的真实往返逼出来，三条各自对应一次实际失分。

### 一、判据命令必须"能直接复制单独跑"
写验收判据、贴自测输出时，命令要能**原样复制到终端**执行。
**禁止**把命令嵌进多层 shell（例如在 bash 里套 `powershell.exe -Command "..."`）——
引号会被逐层吃掉，结果与预期不符而自己还不知道。
（26-09-27 实测：一条嵌套命令自报匹配数 `13`，实际 `22` —— 数字不实，判据虽仍成立但可信度受损。）
若确实必须嵌套，回执里要**同时贴出可读的真实输出**，并注明所用 shell 与转义方式。

### 二、状态流转归大脑，且是"验收通过"的必要组成部分
- 派单时 TASK 状态写 `待执行`。
- **手不动状态字段**（它不在手的范围内）。
- **大脑验收通过后，必须把该 TASK 置 `已完成`**；判不通过则置 `已打回`，并写下一号 TASK。
- 一句话：**状态字段没人改 = 收尾没做完**，不算验收通过。
（2026-09-27 实测：两张简报至今仍写"待执行"，大脑却报"遗留：无"。）

### 三、各自"惯用收尾动作"的豁免
各 Agent 可能有自己的工作区惯例（如写记忆库/日志、刷新索引计数、按铁律提交 git）。
这类动作**不算越界**，前提三条：
1. 它是**惯例要求的固定动作**，不是为了绕过范围限制；
2. **必须在回执或验收结论里申报**（做了什么、动了哪些文件）；
3. **绝不触碰业务代码** —— 业务文件的修改时间必须与派单时保持一致。
（2026-09-27 实测：大脑按工作区铁律写了 `brain/HOME.md` + `brain/LOG` 并提交 git，未碰业务代码。）

## 收尾与状态规则（v1.2 补丁）<!-- handoff-closeout v1.2 -->

> 由 2026-09-28 的**独立审查**（换了一个不带第一轮结论的审查者）逼出来的两条，每条各对应一次实际失分。
> 与 v1 冲突时**以本条为准**。

### 四、回执里贴的"真实输出"，必须与所示命令真的对得上

- 贴输出时**只有两种合法写法**：
  1. **命令与输出严格对应**（原样复制命令到终端，得到的就是贴的那段）；
  2. 若命令里有截断/过滤，**必须标注**：「此处为全长，命令已截断到 N 字符」。
- **实测反例（2026-09-28）**：`RESULT-002` 宣称「真实输出（13 处命中，**原样**）」，
  但所贴命令里含 `Substring(0,60)`；独立审查者**原样复跑**得到的是**被截断的输出**，
  而回执贴的是 200+ 字全长 ⇒ **贴出的输出不可能来自所示命令**。
- 这条与 v1 第一条同宗：**判据与证据的可信度，取决于它能不能被原样复跑。**

### 五、规则改进必须与提交同批入库

- 任何**对规则／契约／模板的改进**，**必须与触发它的那次提交同批入库**；
  确实要分开时，**紧接着单独入库并在消息里写明出处**。
- **实测反例（2026-09-28）**：试点 `AGENTS.md` 的 v1.1 补丁写在**被审提交之后**
  （文件 mtime `00:55:53` 晚于提交 `00:50:31`），且**未跟踪、无提交** ⇒
  **「规则已改进」这件事等于没发生**，下一次同一个坑还会踩。
- **判据**：说「规则已改进」，要能给出**该规则文件自身的 `git ls-files` 行**（不是「最近有提交」）。

## 收尾与状态规则（v1.3 补丁）<!-- handoff-closeout v1.3 -->

> 来源：2026-09-28 读 `gotalab/cc-sdd`（spec 驱动开发，⭐3,687）的设计后**抄其三条**。
> 它值得记的核心主张：**「spec 是系统各部分之间的契约，不是交给 agent 的指令文书；代码仍是唯一真相。
> 把边界显式化，人 与 agent 才能并行工作而不必持续同步。边界不是开销 —— 边界是让你在里面自由行动、保护外面的东西。」**
> 与 v1 / v1.2 冲突时**以本条为准**。

### 六、任务卡必须带 `_Boundary:_` 与 `_Depends:_` 标注

（cc-sdd 原文：`Tasks carry _Boundary:_ and _Depends:_ annotations`）

- **`_Boundary:_`** = 这单**只许动哪些文件/目录**。**写路径，不写"相关模块"这类模糊词。**
- **`_Depends:_`** = 它**依赖哪些已完成件**（TASK 编号或提交 sha）。
- 理由：范围写成散文时，**"有没有越界"无法机械判定**；写成路径清单后，`git diff --name-only` 直接就能比对。

### 七、验收必须检查「边界违规」，不只是「对不对」

（cc-sdd 原文：`Review and validation look for boundary violations, not just style issues`）

- 脑验收时**逐条比对**：手**实际改动过的文件集合** ⊆ `_Boundary:_` **声明的集合**？
- **越界即判不通过**（哪怕代码本身是对的）—— 因为越界会让"下一单的边界"失效，**协作会慢慢崩**。
- 判据命令（可直接复制到终端跑）：

  ```bash
  # 本单实际改动过的文件（相对基线 sha）
  git diff --name-only <基线sha>..HEAD
  # 再与 TASK 里 _Boundary:_ 的清单逐条比对，逐行给出「在界内 / 越界」
  ```

### 八、任务状态要支持「续做」，不靠记忆重开

（cc-sdd 原文：`recorded task state supports resumption after checking unfinished work`）

- 每单完成后，TASK 里记 **`_Status:_`**（已完成 / 已打回）与 **`_Commit:_`**（对应提交 sha）。
- **接手者先查「未完成的 TASK ＋ 活跃会话」，再决定从哪继续** —— 不要凭记忆重开头。
- 这条同时补掉一个真实失分：v1.1 定的「状态字段没人改 = 收尾没做完」在试点里**又犯过一次**（见 `round18` / `简报-handoff试点收尾四处缺口.md`）；加上 `_Commit:_` 之后，**"规则改进了没有"也能被 mechanical 核到**。

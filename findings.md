# Findings: S2 zhclean 环境与事实底账

> 本文件只装**事实与发现**（可核的），不装计划。开工/复现前先读。

## 1. 本机环境（2026-10-07 实测）

- Python 3.14.7（PATH）；uv 0.11.7；Node v24.18.0；pnpm 11.22.0；torch 未装（本项目不需要）。
- LLM 走 API：DeepSeek 官方 `DEEPSEEK_API_KEY` / 智谱 `ZHIPU_API_KEY`；协议 OpenAI 兼容；**GPT-6 系列用 `max_completion_tokens`（不是 `max_tokens`）**。key 在 `.credentials.yaml`。
- aoci 工具：`G:\workagent1\tools\aoci\aoci.exe`（0.1.0-rc17）。

## 2. S1 先例（目录命名与工程惯例）

- S1 目录：`G:\Agentwork_mvp\s1-惜字如金-中文省token`；git 身份 `qlheric <qinlihang@163.com>`。
- 结构惯例：`pyproject.toml`(setuptools) + `uv.lock` + `.github/workflows/ci.yml` + `docs/`(PROGRESS.md、launch-copy 等) + `eval/`(bench+judge+traps 防假绿) + `review-receipts/`(gitignore) + `00-S1-详细方案.md` + `assets/logo.svg`。
- S1 **未用** aoci 索引、未用手脑方案 ⇒ S2 是首个「索引先行 + .handoff」的项目。

## 3. aoci 索引口径（照抄，勿改）

- 条目格式：`文件名[层模块重要度体量]: F:职责 | R:code:相对路径 | A:入口 | S:约束`。
- 标签字典（来源 `G:\workagent1\stock-tool\aoci.meta.txt`）：
  - 层 A：C共享基础 E入口边界 A应用编排 D领域逻辑 K算法计算 M中间件 P持久化 I集成适配 R运行基础 L库与SDK F声明配置 O运维交付 T测试验证 S文档规范 X开发工具 Z其他
  - 模块 B：G跨域通用 U用户交互 B核心业务 D数据状态 I身份权限 N网络协议 M消息事件 S安全隐私 C配置策略 O可观测性 R可靠性恢复 P性能资源 W流程调度 A分析智能 H硬件设备 L本地化 V构建发布 Q质量保障 E扩展插件 Z其他
  - 重要度 C：9 最高 ~ 1 最低；体量 E：L>400 M200-400 S100-200 T<100。
- **硬规则**：`R` 至少一条且指向真实文件；`S` 要短（30 字内稳妥）；`E` 位机器核；有 `--source-sha256` 才是正式写；进度看 `check`；**缩范围只能真人真 TTY 批**。
- **stock-tool 教训**：aoci 三索引件自身被写进 code 卷 ⇒ `volume_ownership_conflict`（code_orphan）⇒ **本仓不索引 aoci 三件自身**。

## 4. 手脑方案（唯一正文：`G:\Obsidian\超级大脑\40-治理\手脑交接.md`）

- 脑不承担生产实现；**状态只有脑能改**；**手不得再派手**（禁止递归委派）。
- TASK 七项必填（目标/基线/`_Boundary:_`/`_Capability:_`/`_Depends:_`/判据/状态=待执行）；RESULT 四项必填（判据/命令/输出/证据）+ 第 7 节「下次接着做什么」。
- 验收四步：亲跑判据 → 边界检查（diff ⊆ `_Boundary:_`）→ 入库可核（贴 `git ls-files` 行）→ 收尾对账。
- 机制脚本：`G:\CodexData\handoff-init.ps1`（幂等）、模板 `G:\CodexData\handoff-templates\`、第三方复检 `G:\CodexData\check-handoff-collab.ps1`。

## 5. 本项目技术要点备忘

- dedupe 依赖 rapidfuzz（pyproject 已声明 ≥3.0）；语义去重阈值需按留出集校准（不得用测试集调参）。
- 整表清洗（M2）如需 XLSX 支持再引入 openpyxl（当前未加依赖）。
- 评测口径：规范化率按「规范值 == ground truth」计；去重 recall 按「应合并对是否被合并」计；失败案例落 `benchmarks/results/` 并公开。

## 6. 环境修复台账

- 2026-10-07：工作区 `G:\Agentwork_mvp\plan` 沙箱 grantWrite 失败（Win32 5）→ diagnose-windows-sandbox-acl 修复（补 FullControl，verified）。备份/回滚：`G:\Agentwork_mvp\acl-recovery\acl-backup-ce3da07739114289b6a0046e6b4553bc.json(.ps1)`。会话已切完全权限。

## 7. aoci 治理实录（本仓首次跑通，留档复用）

- 流程：`init --locale zh-CN` → `scan` → `update-entry --stdin --source-sha256`（sha 取自 `.aoci\baseline.json`）→ `check` → 提交。
- **范围治理**：新增 exclude 规则=覆盖缩减 ⇒ **永不能自动授权**，需真人真 TTY（`scope approve`）。本仓最终口径：**不给 .handoff 加排除规则**，TASK/RESULT 单据逐张写索引条目（单据本身就是认知资产）。安全自动变更用 `scope activate` 放行。
- **sha 错位坑**：`.gitattributes` 的 `eol=lf` 会让 `git add` 就地重写工作区文件（CRLF→LF）→ 基线 sha 失效 → 条目 `code_stale` / `write_conflict`。解法：**用磁盘实算 sha256 作为 `--source-sha256` 重写条目**（内容相同则零写入、只对齐绑定）。
- **不索引 aoci 三件自身**（aoci.txt / aoci.meta.txt / aoci.code.txt）——stock-tool 把它们写进 code 卷曾产生 code_orphan（volume_ownership_conflict）。
- 完工态：28 条 / check 五净可提交 / S 覆盖 28/28 / 基线 32 文件。

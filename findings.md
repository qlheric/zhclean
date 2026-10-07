# Findings: S2 zhclean 环境与事实底账

> 本文件只装**事实与发现**（可核的），不装计划。开工/复现前先读。

## 1. 本机环境（2026-10-07 实测）

- Python 3.14.7（PATH）；uv 0.11.7；Node v24.18.0；pnpm 11.22.0；torch 未装（本项目不需要）。
- **pytest 未装**（2026-10-07 实测 `No module named pytest`）⇒ 判据命令用 `uv run --project . pytest tests/ -q`（会自动装 dev 依赖），或先 `uv add --dev pytest`。
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
- **benchmark 数据契约（TASK-001 定稿，`32311d4`）**：clean 行三字段（id/field/value）；dirty 行六字段（id/field/value/truth/perturbation/split）；每类 200 干净值 × 5 类扰动 = 1000 脏行；划分 = seed 洗牌后前 20% heldout；同 seed 逐字节一致；`tests/test_benchmark.py` 的 `test_repo_artifacts_fresh` 守着「生成器改动必须重生成产物」。
- **合成数据已知限制**（不阻塞，规则开发时留意）：区划是「省级+地级+通用区名」随机组合，会出现「上海市西城区」这类不存在的组合；部分名字组合少见；手机号段只保形状不保在用。若要求真实区县对应关系，需要官方行政区划数据源（task_plan Key Question 2）。
- **评测管线口径（TASK-002 定稿，`aab345a`）**：`benchmarks/evaluate.py`，注入点 `--impl stub|perfect|rules`（rules 为真实规则名，2026-10-07 脑拍板）；默认只评 heldout；summary 三张分组表同源计数；失败案例含真值 = 「失败案例公开」口径有意为之，**脱敏开关留发布前**。
- **真实数台账（heldout，rules 实现）**：person 72.00%（space/sep/noise 100%、typo 60%、abbrev 0%）；**phone 100.00%**（五类全对，`e44d3b0`；⚠️ 含测试集容量小成分——生成器 PHONE_TYPOS 仅 6 对，如实声明）；**company 81.00%**（`01f03d5`；space/sep/noise/typo 全 100%、abbrev 5%=不猜策略天花板 2/40；改坏 0、干净值零误伤）；address 未注册 0%（TASK-006）。总盘 63.25%（506/800）。≥95% 是目标不是承诺。
- **留出集纪律升级（2026-10-08 固化）**：手不得读 `benchmarks/generate.py` 的词典常量做规则设计（RESULT-005 手自踩一次并撤回，脑裁定靠机制不靠自觉）——已写进 `.handoff/TASK模板.md` 禁区；查缺漏只看 train 失败样本。
- **软闸门机制（company 贡献，可复用）**：推断层判据集合必须用「常识闭集」（组织形式∪行业词∪行政区划∪道路词），品牌/小区名是开集不可入——这是「高分又不改坏」的全部原因。
- **abbrev 语义差异（读表口径）**：person=缺字（不可恢复 0%）、phone=加国家码（可剥离 100%）、company=缩写（部分可补）；同标签难度迥异，汇总行会掩盖，读表按 field 分开看。
- **回归护栏惯例（TASK-004 确立）**：每注册一个字段，该字段测试必须带 person/已注册字段的回归断言（防注册表污染）。
- **规则层口径（TASK-003 定稿，`e64f6ac`）**：接口 `normalize(value, field) -> str` / `normalize_with_confidence -> (str, float)`（value 在前，docstring 若与之矛盾以契约为准）；置信度 0.9 结构 / 0.7 推断 / 0.1 无证据；**结构层命中即返回、不叠加推断层**；错字表只收「错字几乎不可能当名用字」。
- **遗留 medium 记账**：person.py TYPO_TO_CORRECT 含「田→天」「路→露」「木→沐」「果→国」等与收录标准不自洽条目（heldout 零误伤已核验），后续扩表 TASK 时统一自检。
- **判据命令规范（2026-10-07 裁定）**：凡 import zhclean 的命令，判据一律 `uv run --project . python ...`（裸 python 3.14.7 无 zhclean）；脑派单前亲跑验证。
- **评测产物不入库（2026-10-07 脑侧治理）**：`benchmarks/results/*.json(jsonl)` 进 .gitignore（可 100% 重生成）；「失败案例公开」走发布物而非 git 入库。
- **aoci 已知限制（挂账）**：`remove-entry` 的 CLI 兼容路径报 `volume_read_only`，按设计只能走 MCP 管道（本机未接入）⇒ 4 条已出库评测产物的孤儿条目暂挂账（check 恒 blocked 4 项，属诚实态）。处置：接入 aoci MCP 后 `remove-entry` 清除，或等工具升级；不影响索引使用（孤儿目标文件不存在，不会误导）。
- **给老大的 .cmd 必须 GBK 编码**：cmd.exe 按 GBK 解析批处理文件，UTF-8 写的中文路径/echo 全乱（2026-10-07 实测翻车一次）。写法：`[System.IO.File]::WriteAllText(path, content, [System.Text.Encoding]::GetEncoding(936))`。

## 6. 环境修复台账

- 2026-10-07：工作区 `G:\Agentwork_mvp\plan` 沙箱 grantWrite 失败（Win32 5）→ diagnose-windows-sandbox-acl 修复（补 FullControl，verified）。备份/回滚：`G:\Agentwork_mvp\acl-recovery\acl-backup-ce3da07739114289b6a0046e6b4553bc.json(.ps1)`。会话已切完全权限。

## 8. 手脑角色与 aoci 新文件流程（2026-10-07 定）

- **角色**：本会话 = 脑（拆单/验收/改状态/提交，不写业务代码）；手 = 侧边栏 Claude Code（老大开终端）；主人 = 老大（按按钮 + 最终拍板）。
- **判据环境前提**：脑派单前必须亲跑判据命令（§11.1）。已预装：pytest 9.1.1 进 dev 依赖（`dependency-groups.dev`）+ uv.lock 提交（`cdb02dd`）；判据离线可跑：`uv run --project . pytest tests/ -q`。
- **aoci 新文件流程（实测）**：新文件出现 → `scope plan`（会报 authoring + 人工复核数，正常）→ `scope acknowledge --reviewed-by dsh-brain`（observe 指纹复核，脑=复核人）→ `scope activate`（安全自动变更直接应用、刷新 Baseline）→ 逐文件 `update-entry`（先试 baseline sha，write_conflict 时改用磁盘实算 sha）→ `check` 五净 → 提交。**不需要真人 TTY**，每单照此维护。

## 7. aoci 治理实录（本仓首次跑通，留档复用）

- 流程：`init --locale zh-CN` → `scan` → `update-entry --stdin --source-sha256`（sha 取自 `.aoci\baseline.json`）→ `check` → 提交。
- **范围治理**：新增 exclude 规则=覆盖缩减 ⇒ **永不能自动授权**，需真人真 TTY（`scope approve`）。本仓最终口径：**不给 .handoff 加排除规则**，TASK/RESULT 单据逐张写索引条目（单据本身就是认知资产）。安全自动变更用 `scope activate` 放行。
- **sha 错位坑**：`.gitattributes` 的 `eol=lf` 会让 `git add` 就地重写工作区文件（CRLF→LF）→ 基线 sha 失效 → 条目 `code_stale` / `write_conflict`。解法：**用磁盘实算 sha256 作为 `--source-sha256` 重写条目**（内容相同则零写入、只对齐绑定）。
- **不索引 aoci 三件自身**（aoci.txt / aoci.meta.txt / aoci.code.txt）——stock-tool 把它们写进 code 卷曾产生 code_orphan（volume_ownership_conflict）。
- 完工态：28 条 / check 五净可提交 / S 覆盖 28/28 / 基线 32 文件。

# zhclean 发布物料（v0.1.0）

生成：2026-10-09 ｜ 来源：脑（DSH）按 M1/M2 定版数字整理 ｜ 用途：GitHub 发布时直接粘贴

## 1. 仓库 About 设置

- **Description**（GitHub About 字段，≤350 字符）：
  `中文脏数据净化器 —— 人名/地址/电话/公司名/金额/日期/身份证/邮箱八类字段，一键规范化 + 去重 + 清洗报告（CLI，规则为主 + LLM 兜底，宁可漏改绝不改坏）`
- **Topics**（逗号分隔，GitHub 里逐个添加）：
  `chinese, data-cleaning, data-quality, deduplication, nlp, agent-tools, cli, python`
- **Website**：留空（README 即主页）

## 2. qlheric 主页 README 新增段（粘贴到项目列表末尾）

```markdown
### 🧹 [zhclean](https://github.com/qlheric/zhclean) — 中文脏数据净化器

给你的 agent 一个中文脏数据净化器：人名 / 地址 / 电话 / 公司名 / 金额 / 日期 / 身份证 / 邮箱，一键规范化 + 去重 + 清洗报告。

- **八类字段**规范化，heldout 定版真实数：电话 / 金额 / 身份证 100%，总盘 85%（benchmark 数字与失败案例全部公开在仓库里）
- **五子命令** CLI：`normalize` / `dedupe` / `audit`（可回滚）/ `rollback` / `table`（CSV 整表清洗）
- 设计口径：**宁可漏改，绝不改坏**——每类规则带校验闸门，零改坏有评测背书
- 技术栈：Python + rapidfuzz，Agent Loop + LLM 兜底（规则 → LLM → 人工三级）
```

## 3. 发布动作清单（维护者执行）

1. GitHub 建仓 `zhclean`（public，不初始化 README/LICENSE——本地已带）
2. 本地添加远程并推送：
   ```bash
   git remote add origin https://github.com/qlheric/zhclean.git
   git push -u origin main
   git push origin v0.1.0
   ```
3. 仓库 Settings 填 About（§1 文案）
4. 盯首次 CI（`.github/workflows/ci.yml`；红了按两条预案：`pip install uv` → `python -m pip install uv`，或换 `astral-sh/setup-uv`）
5. 干净机器复核 `uv tool install git+https://github.com/qlheric/zhclean.git` 或 clone 后 `uv tool install .`

## 4. 放大器建议（按推荐序）

1. **V2EX「分享创造」发帖**（最大杠杆）：标题带「agent + 中文数据清洗」，贴一段 3 命令 demo 输出 + benchmark 表；回帖保持活跃 24h。
2. **即刻 / X 短帖**：一句话卖点 + 仓库链接 + README 里的命令输出截图。
3. **掘金专栏**：《给 agent 做中文脏数据清洗器：宁可漏改绝不改坏》——讲校验闸门设计（身份证 GB 11643 / 电话硬校验 / email 弱闸门位置判定）这套「闸门强度决定修复激进程度」的方法，这是本仓库最有传播力的技术点。
4. （数据反馈后再决定）awesome 列表 PR、HN Show HN——中文受众优先观望前三个的效果。

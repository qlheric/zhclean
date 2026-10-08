# zhclean · 中文脏数据净化器

给你的 agent 一个中文脏数据净化器——人名/地址/电话/公司名，一键规范化 + 去重 + 清洗报告。

- **输入输出**：jsonl，每行 `{"id", "field", "value"}`，`field` ∈ `person / address / phone / company`
- **三件工具**：`normalize`（规范化 + 置信度）、`dedupe`（分组去重）、`audit`（清洗报告 + 可回滚的应用），外加 `rollback`
- **口径**：宁可漏改，绝不改坏——已规范的值原样返回、置信度 **0.95**；**没把握**的原样返回、置信度 **0.1**

## 安装

在仓库根目录二选一（一条命令）：

```bash
uv tool install .        # 推荐：装成全局命令 zhclean
pip install -e .         # 或：装进当前 Python 环境
```

然后：

```bash
zhclean --help
```

> 不想安装也行：仓库里用 `uv run --project . zhclean --help`。

## 快速上手

仓库自带 8 行样例 `docs/examples/sample.jsonl`，以下命令在仓库根目录可直接复制运行：

```bash
# 1. 规范化：每行追加 normalized 与 confidence（0.95 已规范 / 0.9 结构 / 0.7 推断 / 0.1 无把握原样）
zhclean normalize --input docs/examples/sample.jsonl

# 2. 去重：每行追加 _group 组序号（默认 adaptive 按字段相似度；--plain 为单一 ratio 对照）
zhclean dedupe --input docs/examples/sample.jsonl

# 3. 清洗报告：默认 dry-run 只看不写；加 --apply 写清洗结果 + 带 checksum 的备份
zhclean audit --input docs/examples/sample.jsonl
```

样例上的实际效果（节选）：

```
范 童言                              → 范童言                    （置信度 0.9）
+86 138-0013-8000                    → 13800138000              （置信度 0.9）
公司名称：嘉兴 数联贸易集团有限公司    → 嘉兴数联贸易集团有限公司   （置信度 0.9）
dedupe：共 8 行 → 5 组（其中多行组 3 个，可去掉 3 行）
```

应用与回滚：

```bash
zhclean audit --input rows.jsonl --apply --out clean.jsonl     # 写 clean.jsonl + clean.backup.json
zhclean rollback --cleaned clean.jsonl --backup clean.backup.json --out restored.jsonl
```

- `--apply` 默认拒绝覆盖已有文件（加 `--force` 才覆盖）；`rollback` 遇 checksum 不匹配即拒绝。
- 不写 `--out` 时数据写 stdout、汇总写 stderr，可直接接管道。
- 退出码：`0` 成功 / `1` 运行错（文件、数据、校验问题）/ `2` 参数错。

## Benchmark 真实数（M1 实测）

**规范化率**（heldout，规则版）：

| 人名 | 电话 | 公司名 | 地址 | 总盘 |
|---|---|---|---|---|
| 72.00% | 100.00% | 81.00% | 90.50% | 85.88% |

**去重**（heldout）：recall 100.00% / precision 100.00%（样本小；train 复核 recall 99.90% / precision 99.25%，作真实水平基准）。

**口径声明**：

- ≥95% 是目标不是承诺。
- 评测 = 程序化扰动 + 留出集（ground truth = 扰动前原值）；规范化按「规范值 == 原值」逐字符计，去重按「应合并的对是否被合并」计。
- 数字可复现（同 seed 逐字节一致）。复现命令见 [docs/failures-m1.md](docs/failures-m1.md#如何复现评测)。

## 失败案例公开

逐字段 × 扰动类型的失败归因与代表性案例：**[docs/failures-m1.md](docs/failures-m1.md)**。

## 已知限制

- **人名缩写缺字不猜**：abbrev 0%——缺掉的字不可恢复，正确行为是原样返回。
- **公司名缩写天花板 2/40**：只有「股份公司」型能无歧义补回，去城市/去后缀型不猜。
- **地址「市/市中区」歧义**：8 条改坏——缺「市」字时无法判断它属于城市还是区名（市中区/市北区/市南区），根因是真实区县表缺失（M2 引入区县表后消歧）。
- **dedupe hub 桥接**：两个人的唯一最佳匹配都指向同一条缩写时会被三合一（train 72 个误并对全部是这一型）。
- **合成数据区划组合不真实**：评测集的「省 + 市 + 区」是随机组合，会出现现实中不存在的地名。

## 路线

- **M1（当前）**：四类字段的规范化 + 去重 + audit，CLI 一键可用。
- **M2**：金额 / 日期 / 身份证 / 邮箱，整表清洗；引入真实行政区划表。

开发流程走 `.handoff/`（手脑方案），方案口径见 `task_plan.md`。

## License

[MIT](LICENSE) © 2026 qlheric

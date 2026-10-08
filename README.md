# zhclean · 中文脏数据净化器

给你的 agent 一个中文脏数据净化器——人名/地址/电话/公司名/金额/日期/身份证/邮箱，一键规范化 + 去重 + 清洗报告 + 整表清洗。

- **输入输出**：jsonl，每行 `{"id", "field", "value"}`，`field` ∈ `person / address / phone / company / amount / date / idcard / email`（八类）；`table` 走 CSV 整表进出
- **四件工具**：`normalize`（规范化 + 置信度）、`dedupe`（分组去重）、`audit`（清洗报告 + 可回滚的应用）、`table`（CSV 整表清洗），外加 `rollback`
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

支持八类字段：`person`（人名）/ `address`（地址）/ `phone`（电话）/ `company`（公司名）/ `amount`（金额）/ `date`（日期）/ `idcard`（身份证）/ `email`（邮箱）。

仓库自带两份样例：`docs/examples/sample.jsonl`（8 行，含人名/电话/公司名/地址四类）、`docs/examples/sample.csv`（8 列 × 3 行整表）。以下命令在仓库根目录可直接复制运行：

```bash
# 1. 规范化：每行追加 normalized 与 confidence（0.95 已规范 / 0.9 结构 / 0.7 推断 / 0.1 无把握原样）
zhclean normalize --input docs/examples/sample.jsonl

# 2. 去重：每行追加 _group 组序号（默认 adaptive 按字段相似度；--plain 为单一 ratio 对照）
zhclean dedupe --input docs/examples/sample.jsonl

# 3. 清洗报告：默认 dry-run 只看不写；加 --apply 写清洗结果 + 带 checksum 的备份
zhclean audit --input docs/examples/sample.jsonl

# 4. 整表清洗：CSV 逐格规范化（列名 == 字段名时自动映射，未映射列原样保留）
zhclean table --input docs/examples/sample.csv
```

样例上的实际效果（节选）：

```
范 童言                              → 范童言                    （置信度 0.9）
+86 138-0013-8000                    → 13800138000              （置信度 0.9）
公司名称：嘉兴 数联贸易集团有限公司    → 嘉兴数联贸易集团有限公司   （置信度 0.9）
dedupe：共 8 行 → 5 组（其中多行组 3 个，可去掉 3 行）
table：共 3 行 × 8 列，改了 8 格，输出 3 行
```

应用与回滚：

```bash
zhclean audit --input rows.jsonl --apply --out clean.jsonl     # 写 clean.jsonl + clean.backup.json
zhclean rollback --cleaned clean.jsonl --backup clean.backup.json --out restored.jsonl
```

- `--apply` 默认拒绝覆盖已有文件（加 `--force` 才覆盖）；`rollback` 遇 checksum 不匹配即拒绝。
- 不写 `--out` 时数据写 stdout、汇总写 stderr，可直接接管道。
- 退出码：`0` 成功 / `1` 运行错（文件、数据、校验问题）/ `2` 参数错。

## 整表清洗（table）

上面几个工具一次处理一行 jsonl；`table` 一次处理**整张表**——按列名把每列映射到八类字段，逐格规范化，未映射的列一格都不动。

```bash
zhclean table --input docs/examples/sample.csv                   # 列名 == 字段名时自动匹配
zhclean table --input docs/examples/sample.csv --dedupe          # 清洗后整行去重
zhclean table --input docs/examples/sample.csv --out clean.csv   # 写文件（缺省写 stdout）
```

- **列映射**：缺省按「列名 == 字段名」自动匹配（列就叫 `person` / `phone` / … 即可）；表头是中文或自定义名时用 `--columns 列名=字段,列名=字段` 显式指定，例如 `--columns 姓名=person,手机=phone`（字段须是八类之一）。
- **未映射的列原样保留**：`sample.csv` 的 `id`、`备注` 两列不属于八类，清洗后逐字不变，汇总里会列出它们（`unmapped_columns`）。
- **汇总**：`table：共 N 行 × M 列，改了 X 格，输出 K 行`。「改了 X 格」= 规范值与原格值**逐字符**不同的格数，可据此核对。
- **整行去重**（`--dedupe`）：**每一列都判为同组**的两行才算重复行（保留首行）。只有个别列相同——比如两个人共用同一手机号——不会并。
- **流向与退出码**同字段级工具：有 `--out` 时数据写文件、汇总写 stdout；缺省时数据写 stdout、汇总写 stderr；`0` 成功 / `1` 运行错 / `2` 参数错。
- **暂只支持 CSV**（用 stdlib，零新依赖）；**XLSX 待支持**（需引入 openpyxl，另单排期）。

## Benchmark 真实数（M3 定版 · 八类）

八类 = M1+M2 六类（M1 四类 + M2 金额/日期）+ 第三批两类（身份证/邮箱）。**分两组报**——两组口径不同，混算会误导：

**规范化率**（heldout，规则版）：

| 组 | 人名 | 地址 | 电话 | 公司名 | 金额 | 日期 | 组内合计 |
|---|---|---|---|---|---|---|---|
| M1+M2 六类（对照 M2 定版，逐位复现） | 72.00% | 90.50% | 100.00% | 81.00% | 100.00% | 84.00% | **87.92%**（1055/1200） |

| 组 | 身份证 | 邮箱 | 组内合计 |
|---|---|---|---|
| 新两类（首次定版） | 100.00% | 52.50% | **76.25%**（305/400） |

> **八类总平均 1360/1600 = 85.00% 仅作信息，不与 M1+M2 六类的 87.92% 相比**——分母含「邮箱」这个有已知天花板的字段，两组不可混为一谈。

train 对照（同口径，仅供调参参照）：M1+M2 六类 person 72.12% / address 91.00% / phone 100.00% / company 81.50% / amount 100.00% / date 85.75% → 88.40%；新两类 idcard 100.00% / email 51.50% → 75.75%；八类总盘 85.23%。

**去重**（heldout）：recall 100.00% / precision 100.00%（样本小；train 复核 recall 99.90% / precision 99.25%，作真实水平基准）。

**口径声明**：

- ≥95% 是目标不是承诺。
- **报数分列**：M1+M2 六类（可对照 M2 定版）与新两类（首次定版）分开报；八类总平均仅作信息。
- 定版数字**以 heldout 为准**，train 只作调参参照；heldout 只在定版后跑一次，规则或数据一改即作废、须重跑。
- 评测 = 程序化扰动 + 留出集（ground truth = 扰动前原值）；规范化按「规范值 == 原值」逐字符计，去重按「应合并的对是否被合并」计。
- 数字可复现（同 seed 逐字节一致）。复现命令见 [docs/failures-m3.md](docs/failures-m3.md#如何复现评测)。

## 失败案例公开

逐字段 × 扰动类型的失败归因与代表性案例：

- **[docs/failures-m3.md](docs/failures-m3.md)** —— **M3 八类定版**（含新增的身份证 / 邮箱）。
- [docs/failures-m2.md](docs/failures-m2.md) —— M2 六类定版（金额 / 日期）。
- [docs/failures-m1.md](docs/failures-m1.md) —— M1 四类字段归因（历史文档，数字仍有效）。

## 已知限制

- **人名缩写缺字不猜**：abbrev 0%——缺掉的字不可恢复，正确行为是原样返回。
- **公司名缩写天花板 2/40**：只有「股份公司」型能无歧义补回，去城市/去后缀型不猜。
- **地址「市/市中区」歧义**：8 条改坏——缺「市」字时无法判断它属于城市还是区名（市中区/市北区/市南区），根因是真实区县表缺失（后续引入区县表后消歧）。
- **日期缩写缺年 / 年月不猜**：abbrev 只补「缺零」（`2026-1-5` → `2026-01-05`）；缺年（`1-5`）与年月（`2026-10`）是信息缺失，原样返回、不猜——这是该字段 abbrev 的天花板（20.00%）。
- **邮箱分隔符 / 缩写不猜**：email 的 sep（`_` 等分隔符）与 abbrev（缺 TLD）都是 0%——邮箱没有校验和，无法判断 `_` 是分隔符还是合法字符、也无法恢复缺失的 `.com`，按「不猜」原样返回；typo 只修「位置可判定」的字符（62.50%），user 段内部的错字不猜。
- **15 位身份证只补 19xx 世纪**：15→18 展开固定补 `19`；2000 年后出生者的 15 位号无法还原，原样返回、不猜。
- **dedupe hub 桥接**：两个人的唯一最佳匹配都指向同一条缩写时会被三合一（train 72 个误并对全部是这一型）。
- **合成数据区划组合不真实**：评测集的「省 + 市 + 区」是随机组合，会出现现实中不存在的地名。

## 路线

- **M1（已完成）**：四类字段（人名 / 地址 / 电话 / 公司名）的规范化 + 去重 + audit，CLI 一键可用。
- **M2（字段层已完成）**：在 M1 之上扩金额 / 日期 / 身份证 / 邮箱四类（定版数字见上）。
- **整表清洗（CSV 已完成）**：`zhclean table` 一次清洗整张 CSV（见上）。**XLSX**、大写数字轴、真实行政区划表另排。

开发流程走 `.handoff/`（手脑方案），方案口径见 `task_plan.md`。

## License

[MIT](LICENSE) © 2026 qlheric

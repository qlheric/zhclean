# 发布检查单（v0.1.0 · 八类字段 + 整表清洗）

> **本清单由 M1 收官生成（TASK-017，2026-10-08），发布前文档收尾时按现状更新（TASK-028，2026-10-09）。**
> 用法：在仓库根目录，逐条把命令原样复制到终端跑一遍，勾上。`[x]` = 已亲跑核实；`[ ]` = 待办（后面注明还差什么）。
> 判据命令一律带 `uv run --project .` 前缀；**heldout 只在定版后跑一次，发布时不再重跑**。

## A. 测试与安装

- [x] **测试全绿** —— `uv run --project . pytest tests/ -q` → **`689 passed`**（TASK-028 亲跑）
- [x] **demo 自检全过**（零网络）—— 五个公开 `-m` 入口各打一行 `..._demo: OK`、退出码 0（TASK-028 亲跑）：

      for m in zhclean.loop zhclean.tools.audit zhclean.tools.dedupe zhclean.llm zhclean.tools.table; do uv run --project . python -m $m; done

      另：`zhclean.rules.{common,email,idcard}` 也有 `-m` 自检（同样打 `..._demo: OK`、退出码 0），但会先各打一行 runpy 的
      `RuntimeWarning: ... found in sys.modules after import of package 'zhclean.rules'`——包内模块的正常现象，无碍。

- [ ] **安装命令实跑（干净机器）** —— 待办：本机 **未** 全局安装（`zhclean` 不在 PATH，TASK-028 核）。发布前在干净环境跑 `uv tool install .`（或 `pip install -e .`）→ `zhclean --help` 出中文帮助
- [x] **快速上手 4 条命令实跑**（仓库自带样例，均退出码 0；本机未全局装 ⇒ 用等价的 `uv run --project . zhclean ...` 前缀跑）—— TASK-028 亲跑：

      uv run --project . zhclean normalize --input docs/examples/sample.jsonl
      uv run --project . zhclean dedupe    --input docs/examples/sample.jsonl
      uv run --project . zhclean audit     --input docs/examples/sample.jsonl
      uv run --project . zhclean table     --input docs/examples/sample.csv

- [x] **CI 工作流语法有效** —— `.github/workflows/ci.yml` 能过 YAML 解析（TASK-028 亲跑，退出码 0；注意项目环境未装 pyyaml，用系统 python）：

      python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8'))"

- [ ] **CI 首跑** —— 待办：`.github/workflows/ci.yml` 已存在且语法通过，但仓库未推 GitHub ⇒ 首跑待建仓后
- [ ] **工作区干净** —— 发布时核：`git status --porcelain -uall` 无输出（发布提交入库后再核）

## B. 评测数字（**定版，不重跑**）

> 定版口径：heldout 只在定版后跑一次报数；调规则只看 train 的失败样本。
> 复现命令见 [docs/failures-m3.md](failures-m3.md#如何复现评测)。**报数必须分列**（六类 / 新两类 / 八类总平均，三者不可混）。

- [x] **heldout 定版（八类，分列报）与 `README.md`「Benchmark 真实数」逐格一致**（TASK-028 核）：

  | 组 | 人名 | 地址 | 电话 | 公司名 | 金额 | 日期 | 组内合计 |
  |---|---|---|---|---|---|---|---|
  | M1+M2 六类（对照 M2 定版，逐位复现） | 72.00% | 90.50% | 100.00% | 81.00% | 100.00% | 84.00% | 87.92%（1055/1200） |

  | 组 | 身份证 | 邮箱 | 组内合计 |
  |---|---|---|---|
  | 新两类（首次定版） | 100.00% | 52.50% | 76.25%（305/400） |

  八类总平均 1360/1600 = **85.00% —— 仅作信息，不与 87.92% 比**。

- [x] **去重 heldout**（R/P）与 README 一致：recall 100.00% / precision 100.00%；
      并附 train 真实水平基准 recall 99.90% / precision 99.25%
- [x] **README 数字 ↔ 台账一致**：与 `findings.md` 的「M2 定版数字」「M3 定版数字」两行
      和 [docs/failures-m3.md](failures-m3.md) 的总览表（第 26–28 行）**三处对得上**（TASK-028 三处比对，逐格一致）
- [x] **train 数字**确为 train、**别把 heldout 当 train**：train 六类 88.40% / 新两类 75.75% / 八类总盘 85.23%

## C. 失败案例公开

- [x] **失败案例已公开** —— [docs/failures-m1.md](failures-m1.md) / [failures-m2.md](failures-m2.md) /
      [failures-m3.md](failures-m3.md) 三份都在，各含「按字段 × 扰动类型的失败归因」与代表性案例（脏 → 真）
- [x] README「失败案例公开」段的链接可点达（相对路径 `docs/failures-{m1,m2,m3}.md`）；
      README 引用的锚点 `docs/failures-m3.md#如何复现评测` 对应标题存在（第 85 行，TASK-028 核）
- [ ] 失败明细产物可复现：`failures-rules-heldout.jsonl`、`dedupe-errors-{train,heldout}.jsonl`
      （跑复现命令生成；**不入库**，`benchmarks/results/` 被 gitignore 覆盖）—— 待办：发布不需要产物，留作可按需重生成
- [x] 已知限制与失败归因无矛盾（README「已知限制」逐条能在 failures-m{1,2,3}.md 找到出处）

## D. 许可证与元信息

- [x] **LICENSE 文件存在** —— 仓库根 `LICENSE`，内容为 MIT，`Copyright (c) 2026 qlheric`（TASK-028 核）
- [x] **README License 段存在** —— README 末尾 `## License`，链接 `[MIT](LICENSE) © 2026 qlheric`
- [x] `pyproject.toml` 的 `version` 与拟发布的 tag 一致（当前 `0.1.0`，TASK-028 核）

## E. 打 tag / 建仓（建议，**由维护者执行；本单不代跑**）

- [ ] **git tag 建议**：本版打 `v0.1.0`（与 `pyproject.toml` 的 `version` 对齐）——
      `git tag -a v0.1.0 -m "zhclean v0.1.0 — 八类字段 + 整表清洗"`
- [ ] tag 落在**发布提交**上，且该提交的工作区干净、CI 已绿
- [ ] **GitHub 建仓 + 推送**（CI 首跑在这一步之后）

## F. 文档面（v0.1.0 新增）

- [x] README 有 **`## 整表清洗（table）`** 一节：用法、列映射（自动 / `--columns`）、未映射列原样保留、
      `--dedupe` 语义、流向与退出码、XLSX 待支持（TASK-028）
- [x] README 快速上手有**第 4 条命令**（`zhclean table --input docs/examples/sample.csv`），四件工具说明与子命令数一致
- [x] **措辞统一**：`README.md` 中「老六类」**零残留**（已全部改为「M1+M2 六类」）
- [ ] **`docs/failures-m3.md` 仍有 4 处「老六类」**（第 26 / 30 / 69 / 79 行）—— **待办：需脑授权**。
      TASK-028 的 `_Boundary:_` 只含 `README.md` 与 `docs/release-checklist.md`（§2.5 的「failures-m3 一并改」未进边界表），
      **本次未改**，见 `RESULT-028 §5`。

---

## 备注

- 本清单覆盖 **v0.1.0 发布面**：八类字段（M1 四类 + M2 金额/日期 + 第三批身份证/邮箱）+ `table` 整表清洗（CSV）。
- 「未重跑 heldout」是纪律不是懒：数字一旦定版，重复跑只会引入观测噪声与「数字调参」的嫌疑。
- 任何对规则/口径的改动，都必须先跑 train 对照 + 全量测试，再更新台账与 README；**heldout 一定版就锁死**（见 `failures-m3.md` 的复现命令）。
- 本机环境注意：**项目环境未装 pyyaml**（CI 语法核验用系统 python）；**未全局安装 `zhclean`**（快速上手用 `uv run --project .` 前缀跑）。

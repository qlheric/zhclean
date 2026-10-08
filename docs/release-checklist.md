# 发布检查单（M1）

> **本清单由 M1 收官生成（TASK-017，2026-10-08），发布前逐项打勾。**
> 用法：在仓库根目录，逐条把命令原样复制到终端跑一遍，勾上。
> 判据命令一律带 `uv run --project .` 前缀；**heldout 只在定版后跑一次，发布时不再重跑**。

## A. 测试与安装

- [ ] **测试全绿** —— `uv run --project . pytest tests/ -q` → `467 passed`
- [ ] **四个 demo 自检通过**（零网络）——
      `for m in zhclean.loop zhclean.tools.audit zhclean.tools.dedupe zhclean.llm; do uv run --project . python -m $m; done`
      → 四行 `..._demo: OK`，退出码 0
- [ ] **安装命令实跑** —— 二选一后 `zhclean --help` 能出中文帮助：
      `uv tool install .`（或 `pip install -e .`）→ `zhclean --help`
- [ ] **三条快速上手命令实跑**（仓库自带样例）——
      `zhclean normalize --input docs/examples/sample.jsonl`、
      `zhclean dedupe --input docs/examples/sample.jsonl`、
      `zhclean audit --input docs/examples/sample.jsonl`
      → 均退出码 0，normalize 输出含 `normalized` 与 `confidence`
- [ ] **CI 工作流语法有效** —— `.github/workflows/ci.yml` 能过 YAML 解析
      （`python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8'))"`）
- [ ] **工作区干净** —— `git status --porcelain -uall` 无输出（发布物都已入库）

## B. 评测数字（**定版，不重跑**）

> 定版口径：heldout 只在定版后跑一次报数；调规则只看 train 的失败样本。
> 复现命令见 [docs/failures-m1.md](failures-m1.md#如何复现评测)。

- [ ] **heldout 数字定版**（规范化率，规则版）与 `README.md`「Benchmark 真实数」逐格一致：

  | 人名 | 电话 | 公司名 | 地址 | 总盘 |
  |---|---|---|---|---|
  | 72.00% | 100.00% | 81.00% | 90.50% | 85.88%（687/800） |

- [ ] **去重 heldout**（R/P）与 README 一致：recall 100.00% / precision 100.00%；
      并附 train 真实水平基准 recall 99.90% / precision 99.25%
- [ ] **README 数字 ↔ 台账一致**：与 `findings.md` 的「规则层口径 / dedupe 自适应配置」两行
      和 `docs/failures-m1.md` 的总览表**三处对得上**（字段×扰动分格也一致）
- [ ] **train 数字**（若引用）确为 train、**别把 heldout 当 train**：train 规范化率
      2757/3200 = 86.16%（person 72.12 / address 91.00 / phone 100.00 / company 81.50）

## C. 失败案例公开

- [ ] **失败案例已公开** —— [docs/failures-m1.md](failures-m1.md) 存在，
      含「按字段 × 扰动类型的失败归因」与代表性案例（脏 → 真）
- [ ] README「失败案例公开」段的链接可点达（相对路径 `docs/failures-m1.md`）
- [ ] 失败明细产物可复现：`failures-rules-heldout.jsonl`、`dedupe-errors-{train,heldout}.jsonl`
      （跑复现命令生成；**不入库**，`benchmarks/results/` 被 gitignore 覆盖）
- [ ] 已知限制与失败归因无矛盾（README「已知限制」逐条能在 failures-m1.md 找到出处）

## D. 许可证与元信息

- [ ] **LICENSE 文件存在** —— 仓库根 `LICENSE`，内容为 MIT，`Copyright (c) 2026 qlheric`
- [ ] **README License 段存在** —— README 末尾 `## License`，链接 `[MIT](LICENSE) © 2026 qlheric`
- [ ] `pyproject.toml` 的 `version` 与拟发布的 tag 一致（当前 `0.1.0`）

## E. 打 tag（建议）

- [ ] **git tag 建议**：本版打 `v0.1.0`（与 `pyproject.toml` 的 `version` 对齐）——
      `git tag -a v0.1.0 -m "zhclean v0.1.0 — M1 收官"`（**由维护者执行；本单不代跑 tag**）
- [ ] tag 落在**发布提交**上，且该提交的工作区干净、CI 已绿

---

## 备注

- 本清单只覆盖 **M1（person/address/phone/company）**。M2（金额/日期/身份证/邮箱 + 真实区划表）
  收官时另出对应清单。
- 「未重跑 heldout」是纪律不是懒：数字一旦定版，重复跑只会引入观测噪声与「数字调参」的嫌疑。
- 任何对规则/口径的改动，都必须先跑 train 对照 + 全量测试，再更新台账与 README。

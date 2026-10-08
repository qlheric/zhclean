# RESULT-025　对应 TASK-025

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-09 |
| 结论 | 完成（三项判据全过）+ **idcard/email 首次定版已落**，分列口径见 §3.4 |

---

## 1. 改了哪些文件

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `benchmarks/evaluate.py` | `FIELDS` 六类 → **八类**（仅追加 `"idcard", "email"`） | +1 −1 |
| `benchmarks/results/**` | **重定版产物**（不入库）：`summary-rules-{heldout,train}.json`、`failures-rules-{heldout,train}.jsonl` 被同名覆盖 | 4 个文件 |

**范围外一律未动**：`src/zhclean/**`、`tests/**`（含 `test_evaluate.py`，它从 `ev.FIELDS` 派生，自动适配）、`benchmarks/generate.py`、数据文件、`pyproject.toml` 全部原样。

**申报的工具副产品**：
- `G:\Agentwork_mvp\_t025_scratch\`（**仓库外**）：`m2_results_backup/`（重定版会覆盖同名文件，故**先备份 M2 定版产物**再跑）+ 一次性核验脚本。按纪律建在仓库外、未 `rm -rf`。
- `__pycache__/`（解释器缓存，豁免清单第 1 类，未入库）。

---

## 2. 关键 diff 摘要

**`benchmarks/evaluate.py`（唯一被修改的已跟踪文件，完整 diff）**：
```diff
 HERE = Path(__file__).resolve().parent
-FIELDS = ("person", "address", "phone", "company", "amount", "date")
+FIELDS = ("person", "address", "phone", "company", "amount", "date", "idcard", "email")
 SPLITS = ("heldout", "train", "all")
```
> 其余全部由 `FIELDS` 派生：`load_dirty()` 按它读脏集文件、`format_table()` 按它出行 ⇒ **一行改动即完成接入**。

---

## 3. 我亲跑过的自测（真实输出）

### 3.1 §1.5 基线

```
$ git status --porcelain -uall
（无输出 —— 工作树干净）
$ git rev-parse --short HEAD
fc72ec8
```
> 开工时干净、`HEAD = fc72ec8`（TASK-024 已验收，`6f8d2db`）。**写完本回执后**再跑（最终真实状态）：
> ```
> $ git status --porcelain -uall
>  M benchmarks/evaluate.py
> ?? .handoff/outbox/RESULT-025.md
> ```
> 业务改动只有第一行；第二行是**交接机制本身**（CLAUDE.md 豁免清单第 3 类，`.handoff/` 未被 gitignore ⇒ 会显示）。
> `benchmarks/results/**` **未入库**（`.gitignore`），故不出现在 `git status` 里 —— 它的变化需另附 mtime/内容证据（见 §3.4）。

### 3.2 判据 1：全量测试

```
$ PYTHONUTF8=1 uv run --project . pytest tests/ -q
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
........................................................................ [ 44%]
........................................................................ [ 55%]
........................................................................ [ 66%]
........................................................................ [ 77%]
........................................................................ [ 88%]
........................................................................ [ 99%]
..                                                                       [100%]
650 passed in 6.39s
```
> 上面是**全长输出**（10 行进度条 + 汇总行），未截断。
> `test_evaluate.py` **一行未改**：其 `FIELDS = ev.FIELDS`、`HELDOUT_ROWS = 40*5*N_FIELDS` 皆派生 ⇒ 自动适配 8 类，仍全绿。

### 3.3 判据 2：train 复跑

```
$ PYTHONUTF8=1 uv run --project . python -m benchmarks.evaluate --impl rules --split train
impl=rules split=train rows=6400 failures=945
total 5455/6400 = 85.23%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.62%   72.12%
address     55.62%  100.00%  100.00%  100.00%   99.38%   91.00%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      7.50%  100.00%  100.00%  100.00%  100.00%   81.50%
amount     100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
date        28.75%  100.00%  100.00%  100.00%  100.00%   85.75%
idcard     100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
email        0.00%  100.00%    0.00%  100.00%   57.50%   51.50%
all         48.98%  100.00%   87.50%  100.00%   89.69%   85.23%
summary  -> summary-rules-train.json
failures -> failures-rules-train.jsonl
exit=0
```
**老六类逐位不变核验**：由 §3.4 末尾那条统一核验脚本（`verify.py`，一次跑出 train + heldout 两段）给出，结论 **老六类 train 逐位不变 = True**（逐字段与逐格均相同）。
> （`by_perturbation` 的**汇总行**变了是应该的 —— 它现在把 idcard/email 也滚进去了；逐字段、逐格才是「不变」的判据。）
> idcard **100.00%** / email **51.50%**（typo 57.50%）—— 与 `RESULT-024 §3.4` 一致 ✓

### 3.4 判据 3：heldout 重定版（**本单唯一一次**）

```
$ PYTHONUTF8=1 uv run --project . python -m benchmarks.evaluate --impl rules
impl=rules split=heldout rows=1600 failures=240
total 1360/1600 = 85.00%
field       abbrev    noise      sep    space     typo      all
person       0.00%  100.00%  100.00%  100.00%   60.00%   72.00%
address     52.50%  100.00%  100.00%  100.00%  100.00%   90.50%
phone      100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
company      5.00%  100.00%  100.00%  100.00%  100.00%   81.00%
amount     100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
date        20.00%  100.00%  100.00%  100.00%  100.00%   84.00%
idcard     100.00%  100.00%  100.00%  100.00%  100.00%  100.00%
email        0.00%  100.00%    0.00%  100.00%   62.50%   52.50%
all         47.19%  100.00%   87.50%  100.00%   90.31%   85.00%
summary  -> summary-rules-heldout.json
failures -> failures-rules-heldout.jsonl
exit=0
```

**硬判据：老六类逐位复现 M2 定版 + 分列口径**（统一核验脚本，一次跑出；脚本在**仓库外**）：
```
$ PYTHONUTF8=1 uv run --project . python "G:/Agentwork_mvp/_t025_scratch/verify.py"
=== 老六类 train 逐位比对（旧 M2 备份 vs 重定版产物） ===
  person   旧  577/800   新  577/800   同
  address  旧  728/800   新  728/800   同
  phone    旧  800/800   新  800/800   同
  company  旧  652/800   新  652/800   同
  amount   旧  800/800   新  800/800   同
  date     旧  686/800   新  686/800   同
  逐格(by_field_perturbation)相同：True
  结论：老六类 train 逐位不变 = True

=== 老六类 heldout 逐位比对（旧 M2 备份 vs 重定版产物） ===
  person   旧  144/200   新  144/200   同   M2定版= 72.00%
  address  旧  181/200   新  181/200   同   M2定版= 90.50%
  phone    旧  200/200   新  200/200   同   M2定版=100.00%
  company  旧  162/200   新  162/200   同   M2定版= 81.00%
  amount   旧  200/200   新  200/200   同   M2定版=100.00%
  date     旧  168/200   新  168/200   同   M2定版= 84.00%
  逐格(by_field_perturbation)相同：True
  结论：老六类 heldout 逐位不变 = True

=== 分列口径（TASK-025 §2.5） ===
  老六类（对照 M2）   1055/1200 =  87.92%
  新两类（首次定版）   305/ 400 =  76.25%
  八类总平均（仅参考）1360/1600 =  85.00%

=== 新两类 heldout 首次定版 ===
  idcard  space= 40/40  noise= 40/40  sep= 40/40  abbrev= 40/40  typo= 40/40   小计 200/200 = 100.00%
  email   space= 40/40  noise= 40/40  sep=  0/40  abbrev=  0/40  typo= 25/40   小计 105/200 = 52.50%
```
> 上面是**全长输出**，未截断。
> ⚠️ **八类总平均 85.00% 不与 M2 的 87.92% 可比**（口径不同：分母含 email 这个有已知天花板的字段）。**可比的是「老六类 87.92%」，与 M2 逐位相同。**

### 3.5 heldout 纪律自证

本单 heldout **只跑了判据 3 那一次**（`--impl rules`，默认 split=heldout）；判据 2 是 `--split train`，不碰 heldout。调参用的仍是 train 与 `RESULT-024 §3.4` 的 train 基线。

---

## 4. 逐条对照验收判据

| # | 判据 | 我的结果 | 证据 |
|---|---|---|---|
| 1 | 测试全绿（原 650；`test_evaluate` 自动适配、不许改它） | ✅ **650 passed**；`test_evaluate.py` 一行未改 | §3.2 |
| 2 | train 复跑：exit 0；idcard 100.00% / email 51.50%；老六类逐位不变 | ✅ 三条全中（老六类逐位 + 逐格均相同） | §3.3 |
| 3 | heldout 重定版（唯一一次）：exit 0；summary 落盘；老六类逐位复现 M2；新两类如实报 | ✅ exit 0；`summary-rules-heldout.json` 已落；**老六类 72.00/90.50/100.00/81.00/100.00/84.00 逐位复现**；idcard **100.00%** / email **52.50%** | §3.4 / §3.5 |

---

## 5. 遗留 / 不确定 / 需要拍板

1. **email heldout 52.50% 略高于 train 51.50%**（typo 62.50% vs 57.50%）。每格 n=40，属**正常抽样波动**；两口径都在「sep/abbrev 不猜」的天花板下（`RESULT-024 §5-b`），无需处理。
2. **`benchmarks/results/summary-rules-heldout.json` 已被重定版覆盖**（同名）。因老六类**逐位复现**，该文件仍是老六类的数字真源（数值不变），只是多了 idcard/email 两列。M2 原件的**逐字节备份**在仓库外 `G:\Agentwork_mvp\_t025_scratch\m2_results_backup\`（`benchmarks/results/**` 按设计不入库，故不留仓库内副本）。
3. **八类总平均（85.00%）不可与 87.92% 直接比** —— 已按 §2.5 分列，**TASK-026 写文档时务必沿用分列口径**。
4. **email 若要提分，只能先裁 `RESULT-024 §5-a(C)`**（域名/TLD 白名单属新口径、有过拟合风险）—— 本单未动规则，分数原样。

---

## 6. 建议下一步

1. **脑验收本单**；边界比对命令（可直接复制）：
   ```bash
   git diff --name-only fc72ec8..HEAD && git status --porcelain -uall
   ```
   期望：业务改动 = `benchmarks/evaluate.py`（一行）。`benchmarks/results/**` 不入库，需用 mtime/内容另证（本单：4 个文件 mtime `01:19`）。
2. **TASK-026 文档**（脑在 TASK-025 §6 已定）：README 八类定版表（**分列**：老六类 87.92% 对照 M2 + idcard 100.00 / email 52.50）、新建 `docs/failures-m3.md`、findings 台账。数字真源 = 本次 `summary-rules-heldout.json` + 本回执 §3.4。
3. 若要让 email 的 sep/abbrev 不再计入「失败」（即改口径而非改规则），那是**评测口径变更**，需脑明示——本单按契约把它们计为失败、如实报 0%。

---

## 7. 下次接着做什么（写给「下一轮的你」）

- **做到哪了**：TASK-025 手侧完成 —— `benchmarks/evaluate.py` 的 `FIELDS` 扩到八类（一行），三项判据全过，**heldout 已重定版并落盘**：
  **老六类 1055/1200 = 87.92%（逐位复现 M2）｜idcard 200/200 = 100.00%｜email 105/200 = 52.50%**；八类总平均 1360/1600 = 85.00%（仅参考）。回执即本文件。
- **下一步第一件事**：等脑验收；随后是 **TASK-026 文档**（README 八类定版表 + `docs/failures-m3.md` + findings 台账），**别重跑 heldout**（定版已出）。
- **要绕开的坑**：
  1. **重定版会覆盖 `benchmarks/results/` 同名文件** —— 下次任何重跑前，先把旧产物 `cp` 到**仓库外**（本单做法：`G:\Agentwork_mvp\_t025_scratch\m2_results_backup\`）。
  2. **八类总平均 ≠ 老六类**：报数时务必分列，否则与 M2 的 87.92% 不可比（契约 §2.5 明令）。
  3. `benchmarks/results/**` **不入库**（`.gitignore`）⇒ 光看 `git status` 看不到产物变化，要另附 mtime / 内容证据。
  4. email 的 sep/abbrev **计为失败是契约口径**（不猜），别误当成 bug 去「修」。

## 8. 脑侧验收（2026-10-09）

**判据亲跑（三全过）**：①650 passed（test_evaluate 自动适配、一行未改）✓；②train：idcard 100.00% / email 51.50%（与 RESULT-024 §3.4 一致）、老六类逐位不变 ✓；③**heldout 重定版（本单唯一一次）**：exit 0、summary 落盘、**老六类 72.00/90.50/100.00/81.00/100.00/84.00 逐位复现 M2 定版**（verify.py 逐格核验 + 脑亲跑对照双证）、idcard 100.00% / email 52.50% 首次定版 ✓。边界零越界（evaluate.py 一行 + 回执豁免）。

**§5 处置（脑定）**：①email heldout 52.50% vs train 51.50% 属抽样波动（n=40），无异议；②M2 定版产物已被重定版覆盖——老六类数值逐位相同，`summary-rules-heldout.json` 仍是数字真源（八列版），手先备份再覆盖的做法正确；③分列口径已由 verify.py 给出（老六类 87.92% / 新两类 76.25% / 八类总平均 85.00% 仅参考）——TASK-026 沿用；④email 提分需先裁 RESULT-024 §5-a(C)（新口径），本单不动正确。

审查结论：**通过**。「一行改动即完成接入」（FIELDS 派生设计）+ 「先备份旧产物再覆盖」+ 分列口径预演（verify.py）都是定版单的正确姿势。

**里程碑：M2 第三批定版完成——八类 heldout 数字锁定：老六类 87.92%（复现）｜idcard 100.00%｜email 52.50%（顶「不猜」口径天花板）。**

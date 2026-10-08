# RESULT-013　对应 TASK-013

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | **完成**。判据 1、3 实测通过；判据 2 归脑核验。未改任何代码。另发现 1 个代码缺陷，在本单范围外，见 §5-1，需脑拍板。 |

## 0. 开工基线

```
$ git status --porcelain -uall
（空输出）
$ git log --oneline -1
a4469d5 chore(handoff): TASK-012 已通过(9220c53 验收+审查结论，zhclean 一键) + 派 TASK-013 M1 验收汇总 + aoci 同步
```

完工后：

```
$ git status --porcelain -uall
 M README.md
?? docs/examples/sample.jsonl
?? docs/failures-m1.md
```

## 1. 改了哪些文件

```
$ git diff --stat
 README.md | 94 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 92 insertions(+), 2 deletions(-)
```

| 文件 | 内容 |
|---|---|
| `README.md` | **重构**。旧版只有 5 行。删掉了两处过时内容：「金额 / 日期」（属于 M2，还没实现），以及「开发中」的说明。按读者视角重排成：一句话卖点 → 安装 → 快速上手 → Benchmark 真实数 → 失败案例 → 已知限制 → 路线。 |
| `docs/failures-m1.md` | 新建。内容包括：规范化分字段 × 扰动的总表；四个字段逐类的失败归因和代表案例；去重 heldout/train 对照和误并归因；合成数据局限；「如何复现评测」的命令。 |
| `docs/examples/sample.jsonl` | 新建。8 行手写样例，供 README 的快速上手命令直接复制运行，在 `docs/**` 范围内。值取自历史 RESULT 里出现过的样例，没有取 heldout。 |

## 2. 关键取舍

1. **数字逐字照抄台账**，来源是 findings.md 第 44、45、38 行，以及 RESULT-003/005/006/009/011 的脑侧核验段。没有重跑 heldout，也没有读 generate.py。
2. **failures-m1 的代表案例全部来自历史回执**里已经核验过的输出：
   - person/typo 的 5 例取自 RESULT-003 §3.4。那批样本当时就是从 heldout 失败文件里列出来的，本单只是转引，没有新读 heldout。
   - 地址「乐山市中区」例取自 RESULT-006 §3.4。
   - dedupe 例取自 RESULT-011 的 train 输出。
3. **改坏 8 条的口径**我写明了是「全量 1000 行」的数，heldout 里占 2 条（RESULT-006 §3.5 的 21/23）。台账没写分母，我补了说明，避免读者误以为是 heldout 数。
4. **快速上手用 `zhclean` 命令**，没用 `python -m`，这是契约 §2.5-2 定的「安装后 `zhclean --help`」。另外加了一行 Windows 乱码提示，原因见 §5-1。

## 3. 我亲跑过的命令与真实输出

> 项目根、Windows bash，命令原样可复制。

**判据 1**：

```
$ uv run --project . pytest tests/ -q 2>&1 | tail -2; echo "exit=${PIPESTATUS[0]}"
.............................................                            [100%]
405 passed in 14.91s
exit=0
```

**判据 3**：

```
$ uv run --project . zhclean --help > /dev/null; echo "exit=$?"
exit=0
```

不重定向直接跑，exit 也是 0，但**中文是乱码**（cp936）。下面是原样输出的前 3 行，乱码原样保留：

```
usage: zhclean [-h] <������> ...

���������ݾ��������淶�� / ȥ�� / ��ϴ���棨jsonl ������
```

加了环境变量后正常：

```
$ PYTHONIOENCODING=utf-8 uv run --project . zhclean --help | head -3; echo "exit=${PIPESTATUS[0]}"
usage: zhclean [-h] <子命令> ...

中文脏数据净化器：规范化 / 去重 / 清洗报告（jsonl 进出）
exit=0
```

**README 快速上手三条逐条可跑**：

```
$ for c in normalize dedupe audit; do PYTHONIOENCODING=utf-8 uv run --project . zhclean $c --input docs/examples/sample.jsonl > /dev/null 2>&1; echo "$c exit=$?"; done
normalize exit=0
dedupe exit=0
audit exit=0
```

README 里「样例上的实际效果」节选的来源：

```
$ PYTHONIOENCODING=utf-8 uv run --project . zhclean dedupe --input docs/examples/sample.jsonl; echo "exit=$?"
dedupe（adaptive，threshold=0.85）：共 8 行 → 5 组（其中多行组 3 个，可去掉 3 行）
{"id": "1", "field": "person", "value": "范 童言", "_group": 0}
{"id": "2", "field": "person", "value": "范童言", "_group": 0}
{"id": "3", "field": "person", "value": "孟露峰", "_group": 1}
{"id": "4", "field": "phone", "value": "+86 138-0013-8000", "_group": 2}
{"id": "5", "field": "phone", "value": "13800138000", "_group": 2}
{"id": "6", "field": "company", "value": "公司名称：嘉兴 数联贸易集团有限公司", "_group": 3}
{"id": "7", "field": "company", "value": "嘉兴数联贸易集团有限公司", "_group": 3}
{"id": "8", "field": "address", "value": "贵州省贵阳市城关区建设路596号", "_group": 4}
exit=0
```

normalize 的输出里，id 1/4/6 的 normalized 分别是 `范童言` / `13800138000` / `嘉兴数联贸易集团有限公司`，confidence 都是 0.9，exit=0。完整 8 行输出我看过，这里不重复贴。

**发布快照：apply → rollback 往返**（产物写在 `benchmarks/results/`，已被 gitignore）：

```
$ PYTHONIOENCODING=utf-8 uv run --project . zhclean rollback --cleaned benchmarks/results/sample.cleaned.jsonl --backup benchmarks/results/sample.cleaned.backup.json --out benchmarks/results/sample.restored.jsonl; echo "exit=$?"; diff docs/examples/sample.jsonl benchmarks/results/sample.restored.jsonl && echo "IDENTICAL"; git check-ignore -v benchmarks/results/sample.cleaned.jsonl benchmarks/results/sample.cleaned.backup.json benchmarks/results/sample.restored.jsonl
rollback：已恢复 8 行（checksum 校验通过）
exit=0
IDENTICAL
.gitignore:20:benchmarks/results/*.jsonl	benchmarks/results/sample.cleaned.jsonl
.gitignore:19:benchmarks/results/*.json	benchmarks/results/sample.cleaned.backup.json
.gitignore:20:benchmarks/results/*.jsonl	benchmarks/results/sample.restored.jsonl
```

在它之前先跑了 `audit --apply`，命令是 `PYTHONIOENCODING=utf-8 uv run --project . zhclean audit --input docs/examples/sample.jsonl --apply --out benchmarks/results/sample.cleaned.jsonl | tail -4`，exit=0。输出的最后 4 行是：

- 「改动明细：列出 3 条」
- 「已写清洗结果」
- 「已写备份」
- 回滚命令

## 4. 逐条对照判据

| # | 判据 | 结果 | 证据 |
|---|---|---|---|
| 1 | 405 passed | **通过** | §3 判据 1 |
| 2 | 数字与台账一致 | **归脑核验**（按 TASK 约定不自报） | 涉及的位置：README「Benchmark 真实数」一节和「已知限制」一节；failures-m1 的总览表和去重表 |
| 3 | `uv run --project . zhclean --help` exit 0 | **通过**，exit 0；但中文乱码，见 §5-1 | §3 判据 3 |

**边界比对**：

| 实际改动 | `_Boundary:_` | 判定 |
|---|---|---|
| `README.md` | ✔ | 界内 |
| `docs/failures-m1.md` | ✔ `docs/**` | 界内 |
| `docs/examples/sample.jsonl` | ✔ `docs/**` | 界内 |
| `benchmarks/results/sample.{cleaned.jsonl, cleaned.backup.json, restored.jsonl}` | ✔ `benchmarks/results/**`（不入库） | 界内，已 ignore |
| `src/**`、`tests/**`、`pyproject.toml` 等 | — | **未动** |

## 5. 遗留 / 不确定 / 需拍板

- **5-1【代码缺陷，范围外，未修】`zhclean` 入口在 Windows 上中文乱码**
  - 原因：`_utf8_stdio()` 只在 `cli.py` 的 `if __name__ == "__main__"` 里调用。console script 直接调 `main()`，跳过了这一步，于是 stdout/stderr 用的是 cp936。
  - 影响范围：用 `python -m zhclean.cli` 的入口不受影响，exit 码也不受影响。
  - 修法（一行）：把 `_utf8_stdio()` 挪到 `main()` 开头，并且只在没有注入流的时候调用。或者给 console script 单独提供一个 `def entry(): _utf8_stdio(); raise SystemExit(main())`，再改 pyproject 的指向。
  - 本单禁止改代码，所以 README 里暂时用 `PYTHONIOENCODING` 的提示兜底。**建议作为 TASK-014 的第一件事来修，修完删掉 README 那行提示。**
- **5-2 安装命令没有实跑**：`uv tool install .` 和 `pip install -e .` 会装到全局或当前环境，并且需要联网拉 rapidfuzz，属于本单禁区。实测的只有 `uv run --project . zhclean`，它走的是同一个 console script。
- **5-3 audit 报告只给条数，不列明细**：`format_report` 只输出「改动明细：列出 N 条」，不打印具体每一条，看起来像有截断。README 没有展示这一行。是否让 CLI 打印明细，请脑定，这需要改代码。
- **5-4 failures 文件含真值**：README 和 failures-m1 都写了「脱敏开关留发布前」。如果真要对外发布，需要先拍板。
- **5-5 副产品申报**：
  - `benchmarks/results/sample.*` 3 个文件，是发布快照，已 gitignore，在范围内；
  - pytest 生成的 `__pycache__/`、`.pytest_cache/`，在豁免清单内。
  - **没有其他清单外的新文件。**

## 6. 建议下一步

- **6-1** 修 §5-1 的乱码（一行代码，再加一个子进程测试，跑 `zhclean` 入口并断言输出中文）。
- **6-2** 发布前补 CI（`.github/workflows`）和 LICENSE。README 目前没写许可证。
- **6-3** M2 的第一单建议引入真实行政区划表，一次解决两个限制：「市 / 市中区」歧义和「合成区划组合不真实」。

## 7. 下次接着做什么

- **做到哪了**：TASK-013 已交付。README 已重构，新建了 `docs/failures-m1.md` 和 `docs/examples/sample.jsonl`，405 个测试全部通过。**没提交，没动 TASK 状态字段。**
- **下一步第一件事**：等脑核验判据 2，然后读 `.handoff/inbox/` 里编号最大的 TASK，预期是 §5-1 的乱码修复，或者 M2 开头。
- **要绕开的坑**：
  1. 在 Windows bash 里跑 `zhclean` 必须加 `PYTHONIOENCODING=utf-8`，§5-1 修好之前都一样。
  2. README 的数字以 findings 台账为准，**不许重跑 heldout 来更新**。
  3. 修好乱码后，记得删掉 README「安装」一节里的乱码提示。按 README 纪律，先通读全文再改。

## 8. 脑侧验收（2026-10-08）

**判据亲跑**：①405 passed ✓；②`zhclean --help` exit 0 ✓（**乱码复现属实**——cp936 输出，`_utf8_stdio` 只挂在 `__main__`，console script 绕过）；③边界零越界（README + docs 2 新文件）✓。

**判据 2 数字核验（脑侧对照 findings 台账，逐项通过）**：规范化 72.00/100.00/81.00/90.50/85.88 ✓；dedupe heldout 100/100 + train 99.90/99.25 ✓；失败 113 行分解（person 56 = abbrev 40 + typo 16、company 38、address 19 = 17+2）✓；8 条改坏「全量 1000 行、heldout 占 2 条」口径标注 ✓；abbrev 四字段语义分开看 ✓。文档诚实度高（合成数据局限、phone 100% 题量小的声明都在）。

**四个拍板点裁决（脑定）**：
1. **乱码修复**：采纳手建议——排 TASK-014 第一件事（`_utf8_stdio` 移进 main 注入守卫内 + 子进程中文回归测试 + 删 README 提示行）。
2. 安装命令未实跑（联网禁区）：接受，发布时再验。
3. audit 明细不打印：**保持现状**（changes 明细在报告 dict 里；CLI --verbose 属增强排后续）。
4. 失败案例带真值：**保持并如实声明**（合成数据无真实隐私；「失败案例公开」是评测透明性的核心口径；真实数据发布场景再谈脱敏）——记 findings。

审查结论：**通过**。README 符合老大 10-03 纪律（一页读完、删过时项「金额/日期」、按读者视角重排）。

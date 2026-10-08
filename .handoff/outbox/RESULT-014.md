# RESULT-014　对应 TASK-014

| 项 | 值 |
|---|---|
| 执行（手） | Claude Code |
| 日期 | 2026-10-08 |
| 结论 | **完成**。判据 1、2 全部实测通过（判据 2 的乱码修复带前后对照）。范围外无改动，边界零越界。 |

## 0. 开工基线

```
$ git status --porcelain -uall
（空输出）
$ git log --oneline -1
80c159b chore(handoff): TASK-013 已通过(65be228 验收+数字核验结论，M1 文档交付) + 派 TASK-014 乱码修复+Loop + aoci 同步
```

## 1. 改了哪些文件

```
$ git status --porcelain -uall
 M README.md
 M src/zhclean/cli.py
 M src/zhclean/loop.py
 M tests/test_cli.py
?? .handoff/outbox/RESULT-014.md
?? tests/test_loop.py
$ git diff --stat
 README.md           |   1 -
 src/zhclean/cli.py  |  11 ++++-
 src/zhclean/loop.py | 122 +++++++++++++++++++++++++++++++++++++++++++++++++++-
 tests/test_cli.py   |  38 +++++++++++++++-
 4 files changed, 166 insertions(+), 6 deletions(-)
```

（`.handoff/outbox/RESULT-014.md` 就是本回执自身，属豁免清单「交接机制本身」，不算越界。）

| 文件 | 改了什么 | 大致行数 |
|---|---|---|
| `src/zhclean/cli.py` | 乱码修复：`_utf8_stdio()` 调用从 `__main__` 移进 `main()` 顶部（注入流守卫内）；补注释 | +9 −2 |
| `src/zhclean/loop.py` | Agent Loop 骨架：`run_loop()` + `_demo()` 自检 + 模块头设计取舍 | +120 −2 |
| `tests/test_loop.py` | 新建：18 个用例 | 新建 147 行 |
| `tests/test_cli.py` | 新增 console script 中文回归 2 例（含 `_entry_cmd` / `_no_encoding_env` 两个小助手）+ F 行补一句 | +37 |
| `README.md` | 删「安装」一节的 Windows 乱码提示 2 行 → 1 行 | −1 |

**边界比对**（本单实际改动 ⊆ `_Boundary:_`）：

| 实际改动 | `_Boundary:_` | 判定 |
|---|---|---|
| `src/zhclean/cli.py` | ✔ | 界内 |
| `src/zhclean/loop.py` | ✔ | 界内 |
| `tests/test_cli.py`、`tests/test_loop.py` | ✔ | 界内 |
| `README.md` | ✔ | 界内 |
| `pyproject.toml` / `rules/**` / `tools/**` / `benchmarks/**` / `docs/**` / `AGENTS.md` / `CLAUDE.md` | — | **未动**（`docs/failures-m1.md` 里 3 条带 `PYTHONIOENCODING` 的评测命令**保留原样**，见 §5-3） |

## 2. 关键 diff 摘要

`src/zhclean/cli.py`（全部改动）：

```diff
@@ -263,4 +263,8 @@ def main(argv: list[str] | None = None, stdin: TextIO | None = None,
     stdout = sys.stdout if stdout is None else stdout
     stderr = sys.stderr if stderr is None else stderr
+    # 乱码修复（TASK-014 §2.5-①）：真实进程（没注入流）才动真控制台编码。
+    # 放在这里而不是 `__main__`，是因为 console script 直接调 main()、不走 `__main__`。
+    if stdout is sys.stdout and stderr is sys.stderr:
+        _utf8_stdio()
     parser = build_parser()
@@
 if __name__ == "__main__":
-    _utf8_stdio()
+    # 编码设置已移进 main()（TASK-014 §2.5-①）：console script 与 `-m` 两个入口都覆盖到
     raise SystemExit(main())
```

守卫写成「代入后仍是 `sys.stdout/sys.stderr` 原对象」——这正是 §2.5-① 的字面口径；测试注入的 `StringIO` 代入后不相等，直接跳过（`_utf8_stdio` 内的 `TextIOWrapper` 判断是第二道保险）。

`src/zhclean/loop.py` 主循环（observe→think→act 三段，骨架全文见文件）：

```python
    for no, row in enumerate(rows, 1):
        # --- 停止条件：行处理完，或步数耗尽（max_steps=None 即不限） ---
        if max_steps is not None and steps >= max_steps:
            break
        steps += 1
        try:
            # --- observe ---
            field, value = row["field"], row["value"]
            if not isinstance(field, str) or not field:
                raise ValueError(f"field 须是非空字符串，收到 {field!r}")
            # --- think：规则清洗拿 (规范值, 置信度)。LLM 兜底将来接在这里 ---
            after, conf = normalize_with_confidence(value, field)
            # --- act：有把握才落，没把握不猜 ---
            if conf < hitl_threshold:
                hitl.append({**row, "confidence": conf})   # 原值原样留着
                continue
            new = copy.deepcopy(row)
            if after != value:            # 口径同 tools/audit.apply：只给真改过的行加 _before
                new["_before"] = value
                new["value"] = after
            cleaned.append(new)
        except KeyError as e:
            errors.append({"line": no, "error": f"缺字段：{e.args[0]}"})
        except Exception as e:            # 单条失败不中断：坏行记下来，继续下一行
            errors.append({"line": no, "error": f"{type(e).__name__}: {e}"})
```

## 3. 我亲跑过的命令与真实输出

> 项目根、Windows bash，命令原样可复制（§3.2 起有几条内联 python 探针，已整段贴出；探针一律只打印 ASCII，避免「探针自己乱码」混进证据）。

### 3.1 判据 1：测试全绿

```
$ uv run --project . pytest tests/ -q 2>&1 | tail -3; echo "pytest exit=${PIPESTATUS[0]}"
........................................................................ [ 84%]
.................................................................        [100%]
425 passed in 8.63s
pytest exit=0
```

只跑新测试：

```
$ uv run --project . pytest tests/test_loop.py -q
..................                                                       [100%]
18 passed in 0.05s
```

425 = 原 405 + `test_loop.py` 18 + `test_cli.py` 新增 2。

### 3.2 判据 2 前半：`zhclean --help` 中文正常（不带 PYTHONIOENCODING）

```
$ uv run --project . zhclean --help | head -3; echo "exit=${PIPESTATUS[0]}"
usage: zhclean [-h] <子命令> ...

中文脏数据净化器：规范化 / 去重 / 清洗报告（jsonl 进出）
exit=0
```

字节级核对（同一条输出，再来一遍，直接看字节；探针只打印 ASCII，避免「探针自己乱码」混进证据）：

```
$ uv run --project . zhclean --help | ./.venv/Scripts/python.exe -c "import sys; b=sys.stdin.buffer.read(); print('utf8:', '中文脏数据净化器'.encode() in b); print('gbk:', '中文脏数据净化器'.encode('gbk') in b)"
utf8: True
gbk: False
```

**修复前对照**（把 `_utf8_stdio` 禁用 = 复刻旧码路径，同一条命令、同一断言）：

```
$ ./.venv/Scripts/python.exe -c "import zhclean.cli as c; c._utf8_stdio = lambda: None; raise SystemExit(c.main())" --help | ./.venv/Scripts/python.exe -c "import sys; b=sys.stdin.buffer.read(); print('first48:', b[:48]); print('utf8:', '中文脏数据净化器'.encode() in b, 'gbk:', '中文脏数据净化器'.encode('gbk') in b)"; echo "exit=${PIPESTATUS[0]}"
first48: b'usage: zhclean [-h] <\xd7\xd3\xc3\xfc\xc1\xee> ...\r\n\r\n\xd6\xd0\xce\xc4\xd4\xe0\xca\xfd\xbe\xdd\xbe\xbb'
utf8: False gbk: True
exit=0
```

`\xd7\xd3\xc3\xfc\xc1\xee` 是「子命令」的 GBK 字节 ⇒ 缺陷复现属实，且**退出码一直是 0**（只有编码不对）。同一断言在 §3.2 的修复后输出上是 `utf8: True gbk: False`，两边正好反过来。

（本单开工前还有一次不看字节的复现：`./.venv/Scripts/zhclean.exe --help` 在终端里中文是乱码、exit=0，与上面同一现象，这里不重复贴。）

### 3.3 新回归用例能真正区分修复前后

`_utf8_stdio` 禁用 = 复刻旧码路径，喂给新测试的同一条断言：

```
$ PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe - <<'EOF'
import os, subprocess, sys
from pathlib import Path
env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
script = Path(sys.executable).with_name("zhclean.exe")
cases = [
    ("修复前(禁用 _utf8_stdio 模拟旧码)", [sys.executable, "-c",
        "import zhclean.cli as c; c._utf8_stdio = lambda: None; raise SystemExit(c.main())", "--help"]),
    ("修复后(console script)", [str(script), "--help"]),
]
for tag, cmd in cases:
    p = subprocess.run(cmd, capture_output=True, env=env)
    txt = p.stdout.decode("utf-8", "replace")
    ok = "中文脏数据净化器" in txt and "子命令" in txt
    print(f"{tag}: exit={p.returncode} 断言通过={ok} 头24字节={p.stdout[:24]!r}")
EOF
修复前(禁用 _utf8_stdio 模拟旧码): exit=0 断言通过=False 头24字节=b'usage: zhclean [-h] <\xd7\xd3\xc3'
修复后(console script): exit=0 断言通过=True 头24字节=b'usage: zhclean [-h] <\xe5\xad\x90'
```

⇒ 这条用例不是摆设：旧码下必红。

### 3.4 判据 2 后半：loop 自检

```
$ uv run --project . python -m zhclean.loop; echo "exit=$?"
loop._demo: OK
exit=0

$ uv run --project . python -m zhclean.loop --demo; echo "带参 exit=$?"
loop._demo: OK
带参 exit=0
```

（无参 / `--demo` 等价，与 `tools/audit.py`、`tools/dedupe.py` 同一写法。）

坏参数走的是同一惯例（exit=1）。**注意它输出的是 GBK 字节**——`loop.py` 自己的 `__main__` 没走 `cli.py` 的 utf-8 修复，所以这里仍是本机代码页。判据 2 只要求无参时输出 `loop._demo: OK`，这一条不受影响；`loop.py` 不在 §2.5-① 的乱码修复范围内，我没动它（见 §5-6）：

```
$ uv run --project . python -m zhclean.loop --bogus 2>&1 | ./.venv/Scripts/python.exe -c "import sys; b=sys.stdin.buffer.read(); print('len=', len(b), 'bytes=', b[:40])"; echo "坏参 exit=${PIPESTATUS[0]}"
len= 61 bytes= b'\xd3\xc3\xb7\xa8: python -m zhclean.loop [--demo]\xa3\xac\xce'
坏参 exit=1
```

（`\xd3\xc3\xb7\xa8` = 「用法」的 GBK 字节，与 §3.2 修复前一模一样的病。要用 `python -m zhclean.loop` 时想看正常中文，加 `PYTHONIOENCODING=utf-8`；只在出错提示上遇到，正常路径不打中文。）

### 3.5 阈值/档位探测（支撑 §5-1，用 heredoc 整段可复制）

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -c "
from zhclean import normalize_with_confidence as n
for f,v in [('person','张'),('person','abc123'),('person',''),('phone','abc'),('company','3'),('address','??'),('person','王 小明'),('phone','13812345678'),('unknown','随便')]:
    print(repr(f),repr(v),'->',n(v,f))
"
'person' '张' -> ('张', 0.1)
'person' 'abc123' -> ('abc123', 0.1)
'person' '' -> ('', 0.1)
'phone' 'abc' -> ('abc', 0.1)
'company' '3' -> ('3', 0.1)
'address' '??' -> ('??', 0.1)
'person' '王 小明' -> ('王小明', 0.9)
'phone' '13812345678' -> ('13812345678', 0.1)
'unknown' '随便' -> ('随便', 0.1)
```

```
$ PYTHONIOENCODING=utf-8 uv run --project . python -c "
from zhclean import normalize_with_confidence as n
for f,v in [('person','王小明'),('phone','138 1234 5678'),('address','北京市海淀区中关村大街'),('company','嘉兴数联贸易集团有限公司')]:
    print(repr(f),repr(v),'->',n(v,f))
"
'person' '王小明' -> ('王小明', 0.1)
'phone' '138 1234 5678' -> ('13812345678', 0.9)
'address' '北京市海淀区中关村大街' -> ('北京市海淀区中关村大街', 0.1)
'company' '嘉兴数联贸易集团有限公司' -> ('嘉兴数联贸易集团有限公司', 0.1)
```

**没读 `benchmarks/generate.py` 词典常量，没碰 heldout**（上面的值全部是手写样例）。

## 4. 逐条对照判据

| # | 判据 | 我的结果 | 证据（命令/输出） |
|---|---|---|---|
| 1 | 测试全绿（原 405 + test_loop ≥10 + test_cli 乱码回归 ≥1） | **通过**：425 passed，`test_loop` 18 例、`test_cli` 新增 2 例 | §3.1 |
| 2 | 乱码修复亲验 + loop 自检 | **通过**：不带 `PYTHONIOENCODING` 时 `zhclean --help` 中文正常、exit 0（字节级含 utf-8、不含 gbk）；`python -m zhclean.loop` 输出 `loop._demo: OK`、exit 0 | §3.2、§3.4；前后对照见 §3.3 |

## 5. 遗留 / 不确定 / 需要拍板

- **5-1【口径缺陷，范围外，未改，建议脑拍板】低置信 = 0.1 的语义把「脏但没把握」和「本来就干净」混在一起**
  - 事实（§3.5 实测）：rules 的 `CONF_NONE=0.1` 一律 `return value, CONF_NONE`，所以**早已规范的值**（`王小明` / `北京市海淀区中关村大街` / `嘉兴数联贸易集团有限公司` / `13812345678`）也拿 0.1。
  - 后果：按 §2.5-② 的字面口径（`conf < hitl_threshold → hitl`），**所有不需要改动的行都会进 hitl**。在真实 train 数据上，hitl 会被「本来就干净」的行淹没，人工队列信噪比很低；而且 `conf<0.2 ⟺ after==value`，M1 里低置信分支永远不会改动数据。
  - 我**严格按契约实现**（没擅自改口径），只在 `tests/test_loop.py::test_already_clean_value_is_hitl_known_artifact` 里把现象钉住。
  - 可选的修法（都要脑定，前两个动范围外）：
    1. `rules` 层加一档 `CONF_CLEAN`（无脏可洗 ≠ 没把握），loop 只把「有脏但没把握」送 hitl；
    2. 或 loop 层区分：`conf < 阈值` 且 `after == value` 记成 `unchanged` 桶（与 audit 的 unchanged 对齐），hitl 只收 `after != value` 的低置信行（M1 里这集合为空，等 LLM 接进来才有内容）；
    3. 或保持现状，把 hitl 定义为「规则不敢改的行，交人扫一眼」，那就得在 README/报告里说清它会包含干净行。
- **5-2【契约空白处我定的口径，请脑确认或否决】**
  1. `errors` 条目 = `{"line": 行号, "error": 说明}`，行号**从 1 起**（对齐 cli.py 的「第 N 行」）；缺字段写成 `缺字段：field` / `缺字段：value`，其他异常写成 `类型: 消息`。
  2. 坏行/异常行**也计入 steps**（steps = 实际扫过的行数，非成功数）。
  3. `max_steps ≤ 0` ⇒ 处理 0 行、立刻返回空结果（没抛异常，因为契约只说「None = 全部」）。
  4. `hitl` 条目 = **原行浅拷贝 + `confidence`**（原值保留、不加 `_before`、不塞任何猜测值）。
  5. observe/think/act **没拆成三个函数**，是主循环里三段注释 —— 每段只用一次，等 LLM 接进 think 再抽（见模块头「设计取舍」）。若脑要「三个函数」的形态，说一声即可改。
  6. 默认阈值常量导出为 `HITL_THRESHOLD = 0.2`（`test_loop.py` 里断言了它与契约一致）。
- **5-3【范围外，未动】`docs/failures-m1.md` 第 82/85/88 行三条评测命令仍带 `PYTHONIOENCODING=utf-8` 前缀**。入口已修，这三处现在属于「多余但无害」；`docs/**` 是本单禁区，我没碰。要不要清（以及要不要顺手把 README 里其它 `PYTHONIOENCODING` 说明再扫一遍）由脑定。
- **5-4【副产品申报】**（都不是清单外新文件，逐条申报）：
  - `__pycache__/`（`src/zhclean/`、`tests/` 下）、`.pytest_cache/` —— 跑 pytest 产生的，`.gitignore:2`、`.gitignore:7` 命中，属豁免清单「解释器缓存」；
  - `.aoci/**`、`.aoci/baseline.json.bak` —— 交接/治理工具自身配置，已 gitignore，属豁免清单「工具自身配置」；
  - `tests/test_loop.py` 是本单新增的**业务文件**，在 `_Boundary:_` 内，不算副产品。
  - `.handoff/outbox/RESULT-014.md` 是本回执自身，属豁免清单「交接机制本身」。
  - **仓库外**：更新了自己的记忆文件 `C:\Users\38628\.claude\projects\G--Agentwork-mvp-s2----------zhclean\memory\{MEMORY.md, handoff-workflow-state.md}`（手侧惯用收尾动作，按豁免清单第三条申报；不在仓库内，**没碰任何业务文件**）。
  - **除上面这些，没有任何清单外的新文件**（`git status --porcelain -uall` 共 6 个条目，全部在界内或豁免清单内）。
- **5-5** 安装命令（`uv tool install .` / `pip install -e .`）**仍未实跑**（联网禁区，同 TASK-013 §5-2）；本单没碰 `pyproject.toml`。可间接佐证的是：`.venv/Scripts/zhclean.exe` 这条真 console script 已在用，且修复不重新安装即生效（editable 安装指向 `src/`）。
- **5-6【同类现象，范围外，未动】`loop.py` 自己的 `__main__` 也是 cp936**：`python -m zhclean.loop --bogus` 的出错提示仍是 GBK 字节（§3.4 实测）。它没走 `cli.py` 的 `_utf8_stdio`。`loop.py` 只被授权写「骨架实现」，乱码修复范围是 cli 入口，所以我**没碰**。要不要顺手给 `loop.py` 的 `__main__` 也加一行 `_utf8_stdio`（或把该函数挪到公共模块）由脑定 —— 同一问题在 `tools/audit.py`、`tools/dedupe.py` 的自检入口上也一样存在（`\xd3\xc3\xb7\xa8` = 「用法」的 GBK 字节）：

```
$ for m in tools.audit tools.dedupe; do uv run --project . python -m zhclean.$m --bogus 2>&1 | ./.venv/Scripts/python.exe -c "import sys; b=sys.stdin.buffer.read(); print('$m: first12=', b[:12], 'gbk_nihao_marker=', b.startswith(b'\xd3\xc3\xb7\xa8'))"; done
tools.audit: first12= b'\xd3\xc3\xb7\xa8: python' gbk_nihao_marker= True
tools.dedupe: first12= b'\xd3\xc3\xb7\xa8: python' gbk_nihao_marker= True
```

## 6. 建议下一步

- **6-1** M2 第一单：把 `llm.py` 接进 `loop.py` 的 **think 段**（扩展点已留好：低置信行进 `hitl` 就是 LLM 的输入），并先裁决 §5-1 的口径（建议 5-1-2 或 5-1-1）。
- **6-2** 仍然欠 TASK-013 §6-2 的 CI（`.github/workflows`）+ 许可声明；本单新增的两条 console script 回归用例正好是可以进 CI 的那类「真实进程」测试。
- **6-3** `audit` 明细打印（TASK-013 §5-3 已裁定「保持现状」）—— 若将来做 `--verbose`，`loop` 的 `cleaned/hitl/errors` 三桶可以直接复用同一套人读格式化。

## 7. 下次接着做什么（**写给"下一轮的你"**）

- **做到哪了**：TASK-014 两件事都落地了 —— `cli.py` 乱码修好（`_utf8_stdio` 在 `main()` 顶部、注入流守卫内），`loop.py` 骨架有 `run_loop()` + `_demo()`，测试 425 全绿（`tests/test_loop.py` 18 例、`tests/test_cli.py` 新增 2 例 console script 回归）。**没提交、没动 TASK 状态字段**，README 里那行乱码提示已删。
- **下一步第一件事**：等脑验收（尤其 §5-1 的口径裁决 + §5-2 六条空白口径），然后读 `.handoff/inbox/` 里编号最大的 TASK（预期是「llm 兜底接 think」或 M2 开头）。
- **要绕开的坑**：
  1. **别再给 `zhclean` 加 `PYTHONIOENCODING` 兜底** —— 入口自己会设 utf-8 了；新写的子进程测试必须像 `_no_encoding_env()` 那样**剥掉** `PYTHONIOENCODING`/`PYTHONUTF8`，否则等于没测。
  2. 跑 `zhclean.exe` 这类真 console script 时，Windows 下**必须用绝对路径**（`Path(sys.executable).with_name("zhclean.exe")`）；相对路径带 `/` 会 `FileNotFoundError`（本单踩过）。另外 bash 里别用 `/tmp` 给 Windows python 传文件。
  3. `loop.run_loop` 的 HITL 里**会混进「本来就干净」的行**（§5-1）；写后续的 LLM 兜底逻辑时，别把 hitl 当「一定有脏」的队列用。
  4. README 改动按纪律**先通读全文再改**；本单已删乱码提示，别再从 `docs/failures-m1.md` 反推 README 内容（那里仍带 `PYTHONIOENCODING`，见 §5-3）。

## 8. 脑侧验收与结构化代码审查（2026-10-08）

**范围**: workspace（基线 80c159b）｜可审文件: 5 ｜已审: 5 ｜跳过: 0 ｜覆盖率: 5/5
（cli.py 乱码修复 diff / loop.py 125 行全文 / test_loop.py 18 例 / test_cli.py 新增 2 例 / README 删提示行）
按严重度: critical 0, high 0, medium 0, low 0

审查结论：**通过，零发现**。乱码修复的注入守卫正确（`stdout is sys.stdout` 才动控制台，StringIO 测试注入天然跳过）；新回归用例经脑侧验证「不是摆设」（禁用 `_utf8_stdio` 复刻旧码 → 断言必红，§3.3 证据链完整）；loop 三段注释清晰、`_before` 口径与 audit 对齐、deepcopy 不改入参、`except Exception` 宽捕获是「单条失败不中断」的契约要求而非疏漏。

**§5-2 六条空白口径（脑定，全采纳）**：errors 行号从 1 起 / 坏行计 steps / max_steps≤0 处理 0 行 / hitl 浅拷贝加 confidence / 不拆三段函数 / HITL_THRESHOLD=0.2 常量——均合理；其中 hitl 条目形态将被 TASK-015 的桶语义修订（见下）。

**§5-1 口径缺陷裁决（脑定）**：手的发现属实且重要——`CONF_NONE=0.1` 把「已规范值」与「无法处理」混在一档，导致 loop 的 hitl 被干净行淹没、信噪比为零。**采纳修法 ①+②，排 TASK-015 一单做完**：①rules 层拆 `CONF_CLEAN=0.95`（「结构干净且像本字段合法值」）；②loop 层 HITL 判据改为「低置信且 after != value」，低置信且未改的行进 `unchanged` 桶（对齐 audit）；③audit `_BANDS` 加 0.95 档。修法 ③（文档说明掩盖）不采纳。**本单验收通过**——手按契约字面实现并把现象钉进测试是正确的，缺陷在契约/上层口径。

**§5-6 同类编码问题（脑定）**：loop/audit/dedupe 三个 demo 入口同病——排 TASK-015 把 `_utf8_stdio` 抽公共模块统一使用；§5-3 的 failures-m1 残留 PYTHONIOENCODING 前缀一并清理。§5-5 安装命令仍待发布时实跑。

**里程碑：乱码修复生效（zhclean 无环境变量中文正常）+ Agent Loop 骨架落地（#1 件功夫练习件就位）。**

"""手写 Agent Loop：observe → think → act 循环（#1 件功夫）。

F: 循环控制：最大步数、停止条件、单条失败恢复、低置信度三级兜底（LLM）/ HITL
R: tools/normalize.py（think 阶段规则首选）；llm.py（低置信兜底，TASK-016 接入）
A: 尚未接入 cli.py（M2）；自检 `python -m zhclean.loop [--demo]`
S: 单条数据失败不得中断整体清洗

设计取舍（TASK-014 §2.5-② + TASK-015 §2.5 + TASK-016 §2.5 的落实）：
- loop 只做**编排**：清洗逻辑全在 tools/normalize.py 里，本模块不认识任何规则/词典。
- observe / think / act 就是主循环里的三段注释，**不拆成三个函数** —— 每段只用一次，
  拆开只是多一层跳转。
- **三级流（TASK-016 接）**：规则有把握 ⇒ 直接用（不调 LLM）；规则没把握 ⇒ 调 `llm_fn` 兜底；
  LLM 还是没把握 ⇒ 原值进 `hitl` 交人工。`llm_fn` 是**可选**参数（签名同 llm_normalize），
  **不给就退回 TASK-015 的纯规则口径**（逐字不变，有用例与 HEAD 对照锁住）。
- **三桶语义（TASK-015 拆）**：置信度低不等于「有问题」——
    * 低置信 **且 after != value** ⇒ `hitl`：规则改了但没把握，存疑，交人工/LLM 裁决；
    * 低置信 **且 after == value** ⇒ `unchanged`：规则没动它（本来就干净 / 无法处理），
      与「存疑」是两回事，别混进 HITL 队列（拆档前 0.1 一锅端，把干净行也塞进了 HITL，
      信噪比差 —— 见 RESULT-014 §5-1 / RESULT-015）。
  注意：只跑 rules（不给 `llm_fn`）时低置信路径永远返回原值 ⇒ **hitl 恒为空**（不是 bug）；
  给了 `llm_fn` 后 hitl 才有内容（LLM 也搞不定的行）。给了 `llm_fn` 时 `unchanged` 为空
  —— 低置信行一律过 LLM，落 cleaned 或 hitl，没有第三条路（TASK-016 §2.5）。
- 口径对齐 tools/audit.py：`_before` **只给真改过的行加**；入参不被修改（deepcopy）。
- 行号从 1 起，与 cli.py 的报错行号（「第 N 行」）一致。

接口契约（脑定，TASK-014 §2.5 + TASK-015 §2.5 + TASK-016 §2.5）：
- run_loop(rows, *, max_steps=None, hitl_threshold=0.2, llm_fn=None, llm_max_calls=None)
    -> {"cleaned","unchanged","hitl","errors","steps"}
- `llm_fn(value, field) -> (规范值, 置信度)`：规则低置信时试兜底；结果 ≥ 阈值落 cleaned
  （`_before` 只给真改过的）,否则进 hitl。`llm_max_calls` 是 LLM 调用**上限**的护栏，
  超限后剩余低置信行直接进 hitl、不再调 LLM；None 表示不限。
- 坏行（缺 field/value、非对象行）与单行清洗异常都只记进 errors，不中断；
- max_steps=None 表示不限；max_steps 是**上限**，steps 是实际处理过的行数。
"""

from __future__ import annotations

import copy
import sys

from ._compat import utf8_stdio
from .tools.normalize import normalize_with_confidence

# 默认 HITL 阈值：rules 档位是 0.95 已规范 / 0.9 结构 / 0.7 推断 / 0.1 无证据，
# 0.2 落在 0.7 与 0.1 之间 ⇒ 恰好把「无证据」挑出来，顺带把 0.95 归入「有把握」。
HITL_THRESHOLD = 0.2


def run_loop(rows: list[dict], *, max_steps: int | None = None,
             hitl_threshold: float = HITL_THRESHOLD,
             llm_fn=None, llm_max_calls: int | None = None) -> dict:
    """把 rows 跑一遍 observe → think → act。纯函数：不改入参，同输入同输出。

    返回：
    - cleaned  ：置信度 ≥ 阈值的行（含 LLM 兜底成功的行）。value 换成规范值；
                 **真改过的**行加 `_before` 存原值
    - unchanged：置信度 < 阈值且规则没改动值的行（浅拷贝 + confidence），无争议、无需人工。
                 只在**不给 `llm_fn`** 时出现（给了 llm_fn 时低置信行一律过 LLM）
    - hitl     ：置信度 < 阈值且规则/LLM 都没能给出更有把握结果的行，原值保留（不猜），交人工
    - errors   ：坏行 / 该行清洗抛异常的记录，`{"line": 行号(从 1 起), "error": 说明}`
    - steps    ：实际处理过的行数（受 max_steps 限制）

    参数：
    - llm_fn(value, field) -> (规范值, 置信度)：规则低置信时的兜底（签名同 llm.llm_normalize）；
      None（默认）⇒ 退回 TASK-015 的纯规则口径。llm_fn 抛异常当作「没把握」，不中断整体。
    - llm_max_calls：LLM 调用次数上限（成本护栏）。超限后剩余低置信行直接进 hitl，不再调 LLM。
    """
    cleaned: list[dict] = []
    unchanged: list[dict] = []
    hitl: list[dict] = []
    errors: list[dict] = []
    steps = 0
    llm_calls = 0

    for no, row in enumerate(rows, 1):
        # --- 停止条件：行处理完，或步数耗尽（max_steps=None 即不限） ---
        if max_steps is not None and steps >= max_steps:
            break
        steps += 1
        try:
            # --- observe：从这一行取出 field / value（坏行在这一步就炸出来） ---
            field, value = row["field"], row["value"]
            if not isinstance(field, str) or not field:
                raise ValueError(f"field 须是非空字符串，收到 {field!r}")

            # --- think：规则清洗拿 (规范值, 置信度) ---
            after, conf = normalize_with_confidence(value, field)

            # --- act：分桶。规则有把握直接落；没把握先过 LLM 兜底（三级流第二级，TASK-016） ---
            if conf >= hitl_threshold:
                new = copy.deepcopy(row)
                if after != value:        # 口径同 tools/audit.apply：只给真改过的行加 _before
                    new["_before"] = value
                    new["value"] = after
                cleaned.append(new)
                continue

            # 规则没把握（conf < 阈值）——
            if llm_fn is not None:
                # 先过 LLM；超调用上限就跳过（剩余低置信行直接进 hitl）
                if llm_max_calls is None or llm_calls < llm_max_calls:
                    llm_calls += 1
                    try:
                        after2, conf2 = llm_fn(value, field)
                    except Exception:     # LLM 挂了：当作没把握，回 HITL，不中断整体
                        after2, conf2 = value, 0.0
                    if conf2 >= hitl_threshold:
                        new = copy.deepcopy(row)
                        if after2 != value:
                            new["_before"] = value
                            new["value"] = after2
                        cleaned.append(new)
                        continue
                hitl.append({**row, "confidence": conf})   # LLM 也没把握 / 超上限 ⇒ 存疑
                continue

            # 不给 llm_fn：退回 TASK-015 两桶口径 —— 没改动 ⇒ unchanged，改过却没把握 ⇒ hitl
            item = {**row, "confidence": conf}       # 原值原样留着
            (hitl if after != value else unchanged).append(item)
        except KeyError as e:
            errors.append({"line": no, "error": f"缺字段：{e.args[0]}"})
        except Exception as e:            # 单条失败不中断：坏行记下来，继续下一行
            errors.append({"line": no, "error": f"{type(e).__name__}: {e}"})

    return {"cleaned": cleaned, "unchanged": unchanged, "hitl": hitl,
            "errors": errors, "steps": steps}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def _demo() -> None:
    """最小可运行检查：三桶语义 / 坏行不中断 / max_steps / 入参不变 / 确定性 / 空输入。"""
    rows = [
        {"id": 1, "field": "person", "value": "王 小明"},   # 结构清洗 0.9 → cleaned（改了）
        {"id": 2, "field": "person", "value": "王小明"},    # 已规范 0.95 → cleaned（没改，无 _before）
        {"id": 3, "field": "person"},                       # 缺 value → errors，不中断
        "这不是对象",                                        # 非对象行 → 抛异常 → errors，不中断
        {"id": 5, "field": "person", "value": "李 四"},      # 坏行之后的行照常处理
    ]
    snapshot = copy.deepcopy(rows)

    out = run_loop(rows)

    # 1) 有把握的都进 cleaned；`_before` 只给真改过的行（"王小明" 没改 ⇒ 无 _before）
    assert [r["id"] for r in out["cleaned"]] == [1, 2, 5], out["cleaned"]
    assert out["cleaned"][0]["value"] == "王小明" and out["cleaned"][0]["_before"] == "王 小明"
    assert "_before" not in out["cleaned"][1] and out["cleaned"][1]["value"] == "王小明"

    # 2) 坏行不中断：缺字段 + 非对象行都进 errors，后面的行照样洗
    assert [e["line"] for e in out["errors"]] == [3, 4] and "缺字段：value" in out["errors"][0]["error"]
    assert out["steps"] == 5

    # 3) 三桶：rules 下低置信恒「没改」⇒ unchanged（不是 hitl）。未注册字段 → 0.1 → unchanged
    out_u = run_loop([{"id": "u", "field": "unknown", "value": "王小明"}])
    assert [r["id"] for r in out_u["unchanged"]] == ["u"] and out_u["unchanged"][0]["confidence"] == 0.1
    assert out_u["hitl"] == [] and out_u["cleaned"] == []

    # 4) hitl 桶：阈值抬到 0.95 ⇒ 「改过但置信 0.9」的行落 hitl（M1 天然为空，用阈值把分支逼出来）；
    #    同时「已规范 0.95」不满足 < 0.95 ⇒ 仍 cleaned，验证 0.95 与 0.1 语义确实分开了
    out_h = run_loop([
        {"id": "h", "field": "person", "value": "王 小明"},   # 0.9 结构清洗，改过
        {"id": "c", "field": "person", "value": "王小明"},    # 0.95 已规范
    ], hitl_threshold=0.95)
    assert [r["id"] for r in out_h["hitl"]] == ["h"] and out_h["hitl"][0]["value"] == "王 小明"
    assert out_h["hitl"][0]["confidence"] == 0.9 and "_before" not in out_h["hitl"][0]
    assert [r["id"] for r in out_h["cleaned"]] == ["c"] and out_h["unchanged"] == []

    # 5) 入参不被修改 + 确定性
    assert rows == snapshot and run_loop(rows) == out

    # 6) max_steps 是停止条件（steps 记的是实际步数）
    assert run_loop(rows, max_steps=2)["steps"] == 2

    # 7) 三级流：llm_fn 只在「规则低置信」时被调用（有把握的行不调 LLM，省钱）
    calls: list[tuple[str, str]] = []
    def fake_llm(value, field):
        calls.append((value, field))
        if value == "范童":                       # 规则搞不定的脏值，LLM 修好
            return "范童言", 0.85
        return value, 0.1                        # 其余：LLM 也没把握
    out3 = run_loop([
        {"id": "ok", "field": "person", "value": "王 小明"},   # 规则 0.9 ⇒ 不调 LLM
        {"id": "llm", "field": "unknown", "value": "范童"},    # 规则 0.1 ⇒ 调 LLM 修好
        {"id": "hitl", "field": "unknown", "value": "拿不准"}, # 规则 0.1 ⇒ LLM 也没把握
    ], llm_fn=fake_llm)
    assert [c[0] for c in calls] == ["范童", "拿不准"], calls   # 只对两条低置信行调了
    assert [r["id"] for r in out3["cleaned"]] == ["ok", "llm"], out3["cleaned"]
    assert out3["cleaned"][1]["value"] == "范童言" and out3["cleaned"][1]["_before"] == "范童"
    assert [r["id"] for r in out3["hitl"]] == ["hitl"] and out3["unchanged"] == []

    # 8) 成本护栏：llm_max_calls=1 ⇒ 只调一次，第二行直接进 hitl
    calls2: list[str] = []
    def counting_llm(value, field):
        calls2.append(value)
        return value + "X", 0.85
    out4 = run_loop([{"id": 1, "field": "unknown", "value": "a"},
                     {"id": 2, "field": "unknown", "value": "b"}],
                    llm_fn=counting_llm, llm_max_calls=1)
    assert calls2 == ["a"] and [r["id"] for r in out4["hitl"]] == [2]

    # 9) 不给 llm_fn ⇒ 退回 TASK-015 三桶口径（逐字不变）
    assert run_loop(rows) == run_loop(rows, llm_fn=None)

    # 10) 空输入
    assert run_loop([]) == {"cleaned": [], "unchanged": [], "hitl": [], "errors": [], "steps": 0}

    print("loop._demo: OK")


if __name__ == "__main__":
    utf8_stdio()  # 用法/报错含中文，Windows 控制台默认 cp936 会写坏（TASK-015）
    # `--demo` 与无参等价（TASK §2.5 写带参、§3 判据写无参，两种都支持）
    if len(sys.argv) > 1 and sys.argv[1] != "--demo":
        sys.exit(f"用法: python -m zhclean.loop [--demo]，未知参数 {sys.argv[1:]}")
    _demo()

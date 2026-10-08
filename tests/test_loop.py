"""Agent Loop 骨架的不变式测试。

F: observe→think→act 编排：有把握才落（`_before` 口径同 audit）/ 三桶语义（cleaned /
   unchanged / hitl，TASK-015）/ 坏行与单行异常都只记 errors 不中断 / max_steps 停止条件 /
   空输入 / 确定性 / 入参不被修改
R: src/zhclean/loop.py、src/zhclean/tools/normalize.py
A: uv run --project . pytest tests/test_loop.py -q
S: 只用手写样例，不读 benchmarks 数据/词典；不联网
"""

from __future__ import annotations

import copy

import pytest

import zhclean.loop as loop_mod
from zhclean.loop import HITL_THRESHOLD, run_loop


def row(i, v, f="person"):
    return {"id": i, "field": f, "value": v}


# 档位已亲测（RESULT-010 §3 + TASK-015）：0.95 已规范 / 0.9 结构清洗 / 0.7 错字修复 / 0.1 原样
ROWS = [
    row(1, "王 小明"),                  # → 王小明，0.9 → cleaned，带 _before
    row(2, "李 四"),                    # → 李四，  0.9 → cleaned，带 _before
    row(3, "王小明"),                   # 不改，0.95 → cleaned（值已规范，TASK-015），无 _before
    row(4, "138-1234-5678", "phone"),   # → 13812345678，0.9 → cleaned，带 _before
]


@pytest.fixture
def rows():
    return copy.deepcopy(ROWS)


# ---- 正常清洗（observe→think→act 走通） --------------------------------------
def test_cleaned_replaces_value_and_keeps_before(rows):
    out = run_loop(rows)
    assert [r["id"] for r in out["cleaned"]] == [1, 2, 3, 4]
    assert (out["cleaned"][0]["value"], out["cleaned"][0]["_before"]) == ("王小明", "王 小明")
    assert out["cleaned"][3]["value"] == "13812345678" and out["cleaned"][3]["_before"] == "138-1234-5678"
    assert out["errors"] == [] and out["steps"] == 4


def test_before_only_added_when_value_really_changed(rows, monkeypatch):
    """高置信但规范值 == 原值时不加 `_before`（对齐 audit 口径）。"""
    monkeypatch.setattr(loop_mod, "normalize_with_confidence", lambda v, f: (v, 0.9))
    out = run_loop(rows)
    assert len(out["cleaned"]) == 4 and all("_before" not in r for r in out["cleaned"])


def test_return_shape_and_extra_keys_are_preserved(rows):
    out = run_loop(rows)
    assert set(out) == {"cleaned", "unchanged", "hitl", "errors", "steps"}  # TASK-015 加 unchanged
    assert out["cleaned"][0]["id"] == 1 and out["cleaned"][0]["field"] == "person"  # 原字段保留


# ---- 三桶语义（TASK-015）：低置信再按「改没改」分 unchanged / hitl -------------
def test_clean_value_is_cleaned_not_hitl(rows):
    """TASK-014 §5-2 记录的「已规范值进 hitl」现象：TASK-015 拆档后消失。"""
    out = run_loop(rows)
    assert [r["id"] for r in out["cleaned"]] == [1, 2, 3, 4] and out["cleaned"][2]["value"] == "王小明"
    assert out["hitl"] == [] and out["unchanged"] == []


def test_low_confidence_unmodified_goes_to_unchanged():
    """未注册字段：normalize 原样返回 + 0.1 ⇒ 没改 ⇒ unchanged（不是 hitl）。"""
    out = run_loop([row(1, "随便什么", "unknown")])
    assert out["unchanged"] == [{"id": 1, "field": "unknown", "value": "随便什么", "confidence": 0.1}]
    assert out["cleaned"] == [] and out["hitl"] == []


def test_hitl_is_empty_for_rules_only_m1(rows):
    """M1 只有 rules：低置信路径恒返回原值 ⇒ 全落 unchanged，hitl 恒空（这是对的，不是 bug）。"""
    out = run_loop(rows + [row(5, "随便什么", "unknown")])
    assert out["hitl"] == []
    assert [r["id"] for r in out["unchanged"]] == [5]


def test_low_confidence_but_changed_goes_to_hitl(monkeypatch):
    """「改了但没把握」才进 hitl：原值保留 + confidence，不落 cleaned。"""
    monkeypatch.setattr(loop_mod, "normalize_with_confidence", lambda v, f: ("改过的", 0.1))
    out = run_loop([row(1, "原文")])
    assert out["hitl"] == [{"id": 1, "field": "person", "value": "原文", "confidence": 0.1}]
    assert out["unchanged"] == [] and out["cleaned"] == []


def test_hitl_threshold_is_configurable(rows):
    # 阈值抬到 0.95：改过的 0.9 行（1/2/4）落 hitl；已规范的 0.95 行（3）不满足 < ⇒ 仍 cleaned
    out = run_loop(rows, hitl_threshold=0.95)
    assert [r["id"] for r in out["hitl"]] == [1, 2, 4] and out["unchanged"] == []
    assert [r["id"] for r in out["cleaned"]] == [3]


def test_default_threshold_constant_matches_contract():
    assert HITL_THRESHOLD == 0.2


# ---- 单条失败不中断 -----------------------------------------------------------
@pytest.mark.parametrize("bad, hint", [
    ({"id": 9, "value": "王 小明"}, "缺字段：field"),
    ({"id": 9, "field": "person"}, "缺字段：value"),
])
def test_missing_key_is_error_and_loop_continues(bad, hint):
    rows = [bad, row(2, "王 小明")]
    out = run_loop(rows)
    assert out["errors"] == [{"line": 1, "error": hint}]
    assert [r["id"] for r in out["cleaned"]] == [2] and out["steps"] == 2  # 坏行也算一步


def test_non_dict_row_is_error_and_loop_continues():
    out = run_loop(["这不是对象", row(2, "王 小明")])
    assert out["errors"][0]["line"] == 1 and "TypeError" in out["errors"][0]["error"]
    assert [r["id"] for r in out["cleaned"]] == [2]


def test_normalize_exception_does_not_stop_loop(monkeypatch):
    """真正的「单行清洗抛异常」：该行记 errors，其余行照常。"""
    def boom(value, field):
        if value == "炸":
            raise RuntimeError("模拟规则崩了")
        return value, 0.9

    monkeypatch.setattr(loop_mod, "normalize_with_confidence", boom)
    out = run_loop([row(1, "炸"), row(2, "正常")])
    assert out["errors"] == [{"line": 1, "error": "RuntimeError: 模拟规则崩了"}]
    assert [r["id"] for r in out["cleaned"]] == [2]


# ---- 最大步数 / 停止条件 ------------------------------------------------------
def test_max_steps_limits_processing(rows):
    out = run_loop(rows, max_steps=2)
    assert out["steps"] == 2 and [r["id"] for r in out["cleaned"]] == [1, 2]


def test_max_steps_none_processes_everything(rows):
    assert run_loop(rows, max_steps=None)["steps"] == len(rows)


@pytest.mark.parametrize("n", [0, -1])
def test_max_steps_below_one_processes_nothing(rows, n):
    out = run_loop(rows, max_steps=n)
    assert out == {"cleaned": [], "unchanged": [], "hitl": [], "errors": [], "steps": 0}


# ---- 空输入 / 确定性 / 不改入参 -----------------------------------------------
def test_empty_input():
    assert run_loop([]) == {"cleaned": [], "unchanged": [], "hitl": [], "errors": [], "steps": 0}


def test_deterministic_and_input_not_mutated(rows):
    snapshot = copy.deepcopy(rows)
    first, second = run_loop(rows), run_loop(rows)
    assert first == second and rows == snapshot

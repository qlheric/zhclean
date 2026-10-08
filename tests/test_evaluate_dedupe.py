"""dedupe 评测口径的不变式测试。

F: 真组构造（每 id 6 行、无跨 id 混组、不带 truth）；小数据手算 recall/precision（含误并惩罚）；
   阈值边界；--select-threshold 只在 train 上扫（注入假 dedupe 记录调用）；空/缺文件报错；落盘确定性
R: benchmarks/evaluate_dedupe.py
A: uv run --project . pytest tests/test_evaluate_dedupe.py -q
S: 计分用例全用手造小数据；真实数据只用 train 做结构检查，不在测试里跑 heldout 打分
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import benchmarks` 不依赖 pytest 的启动方式

from benchmarks import evaluate_dedupe as ev  # noqa: E402

CLEAN, DIRTY = ROOT / "benchmarks" / "clean", ROOT / "benchmarks" / "dirty"


def r(i, v="x", f="person", split="heldout"):
    return {"id": i, "field": f, "value": v, "kind": "dirty", "split": split, "perturbation": "space"}


# ---- 真组构造（真实数据，只读 train） -----------------------------------------
@pytest.fixture(scope="module")
def train_rows():
    return ev.load_rows(CLEAN, DIRTY, "train")


def test_true_groups_have_six_rows_one_clean(train_rows):
    by_id = Counter(x["id"] for x in train_rows)
    assert set(by_id.values()) == {6} and len(by_id) == 4 * 160
    clean = Counter(x["id"] for x in train_rows if x["kind"] == "clean")
    assert set(clean.values()) == {1} and len(clean) == len(by_id)


def test_true_groups_single_field_and_split(train_rows):
    """无跨 id 混组：同 id 的行 field 唯一、split 唯一。"""
    seen: dict[str, set] = {}
    for x in train_rows:
        seen.setdefault(x["id"], set()).add((x["field"], x["split"]))
    assert all(len(s) == 1 for s in seen.values())
    assert {x["split"] for x in train_rows} == {"train"}


def test_rows_do_not_carry_truth(train_rows):
    assert all("truth" not in x for x in train_rows)


# ---- 手算 recall / precision ------------------------------------------------
def test_perfect_grouping():
    rows = [r("a"), r("a"), r("b"), r("b")]
    s, errs = ev.score(rows, [[rows[0], rows[1]], [rows[2], rows[3]]])
    t = s["total"]
    assert (t["tp"], t["true_pairs"], t["pred_pairs"]) == (2, 2, 2)
    assert t["recall"] == t["precision"] == t["f1"] == 1.0 and errs == []


def test_all_singletons_zero_recall():
    rows = [r("a"), r("a"), r("a")]
    s, errs = ev.score(rows, [[x] for x in rows])
    t = s["total"]
    assert (t["tp"], t["true_pairs"], t["pred_pairs"]) == (0, 3, 0)
    assert t["recall"] == t["precision"] == t["f1"] == 0.0
    assert s["missed_pairs"] == 3 and [e["type"] for e in errs] == ["missed"] * 3


def test_wrong_merge_penalizes_precision():
    """a×3 正确并起 + 误把 b 也并进来：tp=3，pred=C(4,2)=6 ⇒ P=0.5，R=1，F1=2/3。"""
    rows = [r("a"), r("a"), r("a"), r("b")]
    s, errs = ev.score(rows, [list(rows)])
    t = s["total"]
    assert (t["tp"], t["true_pairs"], t["pred_pairs"]) == (3, 3, 6)
    assert t["recall"] == 1.0 and t["precision"] == 0.5 and t["f1"] == round(2 / 3, 6)
    assert s["wrong_merge_pairs"] == 3 and {e["type"] for e in errs} == {"wrong_merge"}


def test_partial_recall_hand_computed():
    """真组 a 有 4 行，预测拆成 {0,1,2}+{3}：tp=C(3,2)=3，true=C(4,2)=6 ⇒ R=0.5，P=1。"""
    rows = [r("a") for _ in range(4)]
    s, _ = ev.score(rows, [rows[:3], rows[3:]])
    t = s["total"]
    assert (t["tp"], t["true_pairs"], t["pred_pairs"]) == (3, 6, 3)
    assert t["recall"] == 0.5 and t["precision"] == 1.0


def test_by_field_split_and_total_sums():
    rows = [r("a", f="person"), r("a", f="person"), r("c", f="phone"), r("c", f="phone"), r("d", f="phone")]
    s, _ = ev.score(rows, [rows[:2], rows[2:]])
    assert s["by_field"]["person"]["recall"] == 1.0 and s["by_field"]["person"]["precision"] == 1.0
    ph = s["by_field"]["phone"]
    assert (ph["tp"], ph["true_pairs"], ph["pred_pairs"]) == (1, 1, 3)
    assert s["total"]["tp"] == 2 and s["total"]["pred_pairs"] == 4


def test_errors_capped_and_in_input_order(monkeypatch):
    monkeypatch.setattr(ev, "ERROR_SAMPLE_CAP", 4)
    rows = [r(f"id{k}") for k in range(10)]  # 10 个不同 id 全并一组 ⇒ 45 个误并对
    s, errs = ev.score(rows, [list(rows)])
    assert s["wrong_merge_pairs"] == 45 and len(errs) == 4
    assert [(e["a"]["id"], e["b"]["id"]) for e in errs] == [("id0", "id1"), ("id0", "id2"),
                                                            ("id0", "id3"), ("id0", "id4")]


def test_score_rejects_row_count_mismatch():
    rows = [r("a"), r("a")]
    with pytest.raises(ValueError):
        ev.score(rows, [[rows[0]]])


# ---- 阈值 -------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["-0.01", "1.01", "85", "nan"])
def test_cli_threshold_out_of_range_rejected(bad, tmp_path):
    with pytest.raises(SystemExit):
        ev.main(["--threshold", bad, "--out", str(tmp_path)])


def test_cli_threshold_and_select_are_exclusive(tmp_path):
    with pytest.raises(SystemExit):
        ev.main(["--threshold", "0.9", "--select-threshold", "--out", str(tmp_path)])


@pytest.mark.parametrize("ok", ["0", "1"])
def test_cli_threshold_boundaries_accepted(ok, tmp_path):
    calls = []
    fake = lambda rows, t: (calls.append(t), [[x] for x in rows])[1]  # noqa: E731
    assert ev.main(["--split", "train", "--threshold", ok, "--out", str(tmp_path)], dedupe_fn=fake) == 0
    assert calls == [float(ok)]


def test_select_picks_best_f1_first_on_tie():
    rows = [r("a", split="train"), r("a", split="train"), r("b", split="train")]

    def fake(rs, t):  # 0.80/0.85：全并（P=1/3）；0.90/0.95：正确分组（P=R=1）
        return [list(rs)] if t < 0.9 else [rs[:2], rs[2:]]

    best, sweep = ev.select_threshold(rows, fake)
    assert best == 0.90 and [s["threshold"] for s in sweep] == list(ev.THRESHOLD_GRID)


def test_select_refuses_non_train_rows():
    with pytest.raises(ValueError):
        ev.select_threshold([r("a", split="heldout")], lambda rs, t: [rs])


def test_select_threshold_never_sees_heldout(tmp_path):
    """注入假 dedupe：网格每个阈值各调一次且只见 train 行；heldout 只跑一次、用选定阈值。"""
    calls: list[tuple[float, set]] = []

    def fake(rows, t):
        calls.append((t, {x["split"] for x in rows}))
        return [[x] for x in rows]

    assert ev.main(["--split", "heldout", "--select-threshold", "--out", str(tmp_path)], dedupe_fn=fake) == 0
    assert calls[:-1] == [(t, {"train"}) for t in ev.THRESHOLD_GRID]
    assert calls[-1] == (ev.THRESHOLD_GRID[0], {"heldout"})  # 全 0 分并列 ⇒ 取网格首个
    assert sum(1 for _, sp in calls if "heldout" in sp) == 1

    summary = json.loads((tmp_path / "dedupe-summary-heldout.json").read_text(encoding="utf-8"))
    assert summary["threshold_source"] == "select@train"
    assert summary["selection"]["on_split"] == "train"


# ---- 空 / 缺文件 ------------------------------------------------------------
def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ev.load_rows(tmp_path, tmp_path, "heldout")


def test_empty_file_raises(tmp_path):
    for d in ("clean", "dirty"):
        (tmp_path / d).mkdir()
        for f in ev.FIELDS:
            (tmp_path / d / f"{f}.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        ev.load_rows(tmp_path / "clean", tmp_path / "dirty", "heldout")


def test_unknown_split_rejected():
    with pytest.raises(ValueError):
        ev.load_rows(CLEAN, DIRTY, "all")


# ---- 落盘确定性 --------------------------------------------------------------
def test_outputs_byte_identical_across_runs(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        assert ev.main(["--split", "train", "--threshold", "0.95", "--out", str(d)]) == 0
    for name in ("dedupe-summary-train.json", "dedupe-errors-train.jsonl"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    s = json.loads((a / "dedupe-summary-train.json").read_text(encoding="utf-8"))
    assert s["threshold"] == 0.95 and s["threshold_source"] == "explicit" and s["true_groups"] == 640

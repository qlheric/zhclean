"""评测管线的不变式测试（能红能绿：证明评测本身可信）。

F: stub → 0% 且失败数 = heldout 行数；perfect → 100% 且 0 失败；
   分组数字与手算一致；同输入两次产物逐字节一致；默认只评 heldout
R: benchmarks/evaluate.py
A: uv run --project . pytest tests/ -q
S: 只测评测管线，不测清洗规则
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让 `import benchmarks` 不依赖 pytest 的启动方式

from benchmarks import evaluate as ev  # noqa: E402

FIELDS = ("person", "address", "phone", "company")
PERTURBATIONS = ("abbrev", "noise", "sep", "space", "typo")
HELDOUT_ROWS = 40 * 5 * 4  # 每类 40 个 heldout id × 5 扰动 × 4 类


def _run(impl: str, out: Path, *extra: str) -> subprocess.CompletedProcess:
    """以真实 CLI 方式跑评测（覆盖 -m 入口），产物写临时目录不污染仓库。"""
    return subprocess.run(
        [sys.executable, "-m", "benchmarks.evaluate", "--impl", impl, "--out", str(out), *extra],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )


def _summary(out: Path, impl: str, split: str = "heldout") -> dict:
    return json.loads((out / f"summary-{impl}-{split}.json").read_text(encoding="utf-8"))


def _failures(out: Path, impl: str, split: str = "heldout") -> list[dict]:
    text = (out / f"failures-{impl}-{split}.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# ---------- 能红：stub 恒原值 → 0%，失败数 = heldout 行数 ----------

def test_stub_is_red(tmp_path):
    _run("stub", tmp_path)
    s = _summary(tmp_path, "stub")
    assert s["impl"] == "stub" and s["split"] == "heldout"
    assert s["total"] == {"correct": 0, "total": HELDOUT_ROWS, "rate": 0}
    fails = _failures(tmp_path, "stub")
    assert len(fails) == HELDOUT_ROWS
    assert all(f["normalized"] == f["value"] != f["truth"] for f in fails)
    assert all(set(f) == {"id", "field", "value", "normalized", "truth", "perturbation"}
               for f in fails)


# ---------- 能绿：perfect 回 truth → 100%，0 失败（文件仍落盘） ----------

def test_perfect_is_green(tmp_path):
    _run("perfect", tmp_path)
    s = _summary(tmp_path, "perfect")
    assert s["total"] == {"correct": HELDOUT_ROWS, "total": HELDOUT_ROWS, "rate": 1.0}
    assert all(v["rate"] == 1.0 for v in s["by_field"].values())
    assert all(v["rate"] == 1.0 for v in s["by_perturbation"].values())
    assert (tmp_path / "failures-perfect-heldout.jsonl").read_bytes() == b""


# ---------- 分组：真实 heldout 上的形状 + 手造数据上的手算 ----------

def test_grouping_shape_on_real_heldout(tmp_path):
    _run("stub", tmp_path)
    s = _summary(tmp_path, "stub")
    assert sorted(s["by_field"]) == sorted(FIELDS)
    assert sorted(s["by_perturbation"]) == list(PERTURBATIONS)
    assert all(v["total"] == 40 * 5 for v in s["by_field"].values())
    assert all(v["total"] == 40 * 4 for v in s["by_perturbation"].values())
    for field in FIELDS:
        cells = s["by_field_perturbation"][field]
        assert sorted(cells) == list(PERTURBATIONS)
        assert all(c["total"] == 40 for c in cells.values())


def test_grouping_matches_hand_count():
    """手造 6 行 + 只修好 space 的注入实现，逐格手算核对。"""
    rows = [
        {"id": "person-0001", "field": "person", "value": "王 小明", "truth": "王小明", "perturbation": "space", "split": "heldout"},
        {"id": "person-0001", "field": "person", "value": "王晓明", "truth": "王小明", "perturbation": "typo", "split": "heldout"},
        {"id": "person-0002", "field": "person", "value": "李 华", "truth": "李华", "perturbation": "space", "split": "heldout"},
        {"id": "phone-0001", "field": "phone", "value": "138 0000 0000", "truth": "13800000000", "perturbation": "space", "split": "heldout"},
        {"id": "phone-0001", "field": "phone", "value": "138-0000-0000", "truth": "13800000000", "perturbation": "sep", "split": "heldout"},
        {"id": "phone-0001", "field": "phone", "value": "+8613800000000", "truth": "13800000000", "perturbation": "abbrev", "split": "heldout"},
    ]
    summary, failures = ev.evaluate(rows, lambda r: r["value"].replace(" ", ""))
    # 手算：space 3/3 对；typo/sep/abbrev 各 0/1
    assert summary["total"] == {"correct": 3, "total": 6, "rate": 0.5}
    assert summary["by_field"] == {
        "person": {"correct": 2, "total": 3, "rate": round(2 / 3, 6)},
        "phone": {"correct": 1, "total": 3, "rate": round(1 / 3, 6)},
    }
    assert summary["by_perturbation"] == {
        "space": {"correct": 3, "total": 3, "rate": 1.0},
        "typo": {"correct": 0, "total": 1, "rate": 0.0},
        "sep": {"correct": 0, "total": 1, "rate": 0.0},
        "abbrev": {"correct": 0, "total": 1, "rate": 0.0},
    }
    assert summary["by_field_perturbation"]["person"]["space"] == {"correct": 2, "total": 2, "rate": 1.0}
    assert summary["by_field_perturbation"]["phone"]["space"] == {"correct": 1, "total": 1, "rate": 1.0}
    # 失败行按输入顺序
    assert [(f["id"], f["perturbation"]) for f in failures] == [
        ("person-0001", "typo"), ("phone-0001", "sep"), ("phone-0001", "abbrev")]
    assert failures[1]["normalized"] == "138-0000-0000"


# ---------- 可复现：同输入两次运行产物逐字节一致 ----------

@pytest.mark.parametrize("impl", ["stub", "perfect"])
def test_results_byte_identical(tmp_path, impl):
    a, b = tmp_path / "a", tmp_path / "b"
    _run(impl, a)
    _run(impl, b)
    for name in (f"summary-{impl}-heldout.json", f"failures-{impl}-heldout.jsonl"):
        raw = (a / name).read_bytes()
        assert raw == (b / name).read_bytes(), f"{name} 两次运行不一致"
        assert b"\r" not in raw and b"\\u" not in raw  # LF + ensure_ascii=False


# ---------- 口径：默认只评 heldout；train / all 行数正确 ----------

def test_split_filter(tmp_path):
    _run("stub", tmp_path, "--split", "train")
    _run("stub", tmp_path, "--split", "all")
    assert _summary(tmp_path, "stub", "train")["total"]["total"] == 160 * 5 * 4
    assert _summary(tmp_path, "stub", "all")["total"]["total"] == 200 * 5 * 4
    ids_heldout = {r["id"] for r in ev.load_dirty(ROOT / "benchmarks" / "dirty", "heldout")}
    ids_train = {r["id"] for r in ev.load_dirty(ROOT / "benchmarks" / "dirty", "train")}
    assert ids_heldout and not (ids_heldout & ids_train)

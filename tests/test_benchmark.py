"""benchmark 生成器的不变式测试（数据契约的可核证据）。

F: 守住 TASK-001 数据契约——六类各 200 干净值 / 每条 ≥3 脏变体且 truth 一致 /
   划分无重叠且比例≈0.2 / 同 seed 逐字节可复现 / 五类扰动覆盖 / 脏值≠干净值 /
   heldout 覆盖全部扰动类型；并守住 amount/date（TASK-018）的形态与 truth 正确
R: benchmarks/generate.py
A: uv run --project . pytest tests/ -q
S: 只测生成器与产物，不测清洗逻辑
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("person", "address", "phone", "company", "amount", "date")
PERTURBATIONS = ("space", "typo", "abbrev", "sep", "noise")
PER_FIELD = 200
SPLIT_RATIO = 0.2
SEED = 42


def _generate(out: Path, seed: int = SEED, per_field: int = PER_FIELD) -> subprocess.CompletedProcess:
    """以真实 CLI 方式跑生成器（覆盖 -m 入口）。"""
    return subprocess.run(
        [sys.executable, "-m", "benchmarks.generate",
         "--seed", str(seed), "--per-field", str(per_field), "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory) -> Path:
    """跑一次生成器（临时目录），全模块共用。"""
    out = tmp_path_factory.mktemp("zb")
    _generate(out)
    return out


@pytest.fixture(scope="module")
def data(artifacts) -> dict[str, dict[str, list[dict]]]:
    """六类 clean / dirty 装载。"""
    return {
        field: {
            "clean": read_jsonl(artifacts / "clean" / f"{field}.jsonl"),
            "dirty": read_jsonl(artifacts / "dirty" / f"{field}.jsonl"),
        }
        for field in FIELDS
    }


# ---------- 不变式 1：四类各 200 条干净值（id / value 唯一） ----------

def test_clean_counts_and_uniqueness(data):
    for field in FIELDS:
        rows = data[field]["clean"]
        assert len(rows) == PER_FIELD, f"{field} 干净值条数 {len(rows)} != {PER_FIELD}"
        ids = [r["id"] for r in rows]
        values = [r["value"] for r in rows]
        assert len(set(ids)) == PER_FIELD, f"{field} 干净 id 有重复"
        assert len(set(values)) == PER_FIELD, f"{field} 干净值有重复"
        # 契约字段：clean 行只有 id / field / value
        assert all(set(r) == {"id", "field", "value"} for r in rows)
        assert all(r["field"] == field for r in rows)


# ---------- 不变式 2：每条干净值 ≥3 条脏变体，truth 一致且指向干净值 ----------

def test_dirty_variants_truth_and_coverage(data):
    for field in FIELDS:
        clean_by_id = {r["id"]: r["value"] for r in data[field]["clean"]}
        variants: dict[str, list[dict]] = defaultdict(list)
        for r in data[field]["dirty"]:
            assert set(r) == {"id", "field", "value", "truth", "perturbation", "split"}
            assert r["field"] == field
            assert r["perturbation"] in PERTURBATIONS, f"未知扰动类型 {r['perturbation']}"
            assert r["id"] in clean_by_id, f"脏值 id {r['id']} 没有对应干净值"
            assert r["truth"] == clean_by_id[r["id"]], "truth 必须等于扰动前原值"
            variants[r["id"]].append(r)
        assert len(variants) == PER_FIELD, f"{field} 未覆盖全部干净 id"
        for rid, rows in variants.items():
            types = {r["perturbation"] for r in rows}
            assert len(rows) >= 3, f"{field} {rid} 只有 {len(rows)} 条脏变体"
            assert types == set(PERTURBATIONS), f"{field} {rid} 扰动类型不全：{types}"
            # 脏值 ≠ 干净值
            assert all(r["value"] != r["truth"] for r in rows), f"{field} {rid} 脏值等于干净值"


# ---------- 不变式 3：train/heldout 无 id 重叠且比例 ≈ 0.2 ----------

def test_split_no_overlap_and_ratio(data):
    for field in FIELDS:
        clean_ids = {r["id"] for r in data[field]["clean"]}
        by_split = {s: {r["id"] for r in data[field]["dirty"] if r["split"] == s}
                    for s in ("train", "heldout")}
        assert by_split["train"] & by_split["heldout"] == set(), f"{field} train/heldout 有重叠"
        assert by_split["train"] | by_split["heldout"] == clean_ids, f"{field} split 未覆盖全部 id"
        # 同一条脏变体的 split 必须与它所在 id 一致（防泄漏）
        for rid in clean_ids:
            splits = {r["split"] for r in data[field]["dirty"] if r["id"] == rid}
            assert len(splits) == 1, f"{field} {rid} 的脏变体跨了 split"
        ratio = len(by_split["heldout"]) / len(clean_ids)
        assert abs(ratio - SPLIT_RATIO) <= 1e-9, f"{field} heldout 比例 {ratio} 偏离 {SPLIT_RATIO}"


# ---------- 不变式 4：同 seed 两次运行产物逐字节一致 ----------

def test_same_seed_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _generate(a)
    _generate(b)
    names = [f"{kind}/{field}.jsonl" for kind in ("clean", "dirty") for field in FIELDS]
    for name in names:
        assert (a / name).read_bytes() == (b / name).read_bytes(), f"{name} 两次运行不一致"
    # 归一化确认：LF 无 CRLF、ensure_ascii=False（中文以原字面出现）
    raw = (a / "clean" / "person.jsonl").read_bytes()
    assert b"\r" not in raw, "产物含 CRLF"
    assert b"\\u" not in raw, "中文被转义成 \\uXXXX（应 ensure_ascii=False）"


# ---------- 不变式 5：五类扰动 × 四类字段，train / heldout 都要覆盖 ----------

def test_all_perturbations_present(data):
    for field in FIELDS:
        for split in ("train", "heldout"):
            counts = Counter(r["perturbation"] for r in data[field]["dirty"]
                             if r["split"] == split)
            missing = [p for p in PERTURBATIONS if counts[p] == 0]
            assert not missing, f"{field}/{split} 缺扰动类型 {missing}"


# ---------- 不变式 6：不同 seed 产物不同（确认 seed 真的在起作用） ----------

def test_different_seed_differs(tmp_path):
    a, b = tmp_path / "s42", tmp_path / "s43"
    _generate(a, seed=42)
    _generate(b, seed=43)
    assert (a / "clean" / "person.jsonl").read_bytes() != (b / "clean" / "person.jsonl").read_bytes()


# ---------- 不变式 8：amount / date 干净值形态与 truth 正确（TASK-018） ----------

def test_new_field_shapes(data):
    # amount：干净值 = 纯数字 + 「元」（TASK-020 起**不带千分位**，千分位只留在 sep 扰动里）
    for r in data["amount"]["clean"]:
        assert re.fullmatch(r"\d+(\.\d+)?元", r["value"]), \
            f"amount 干净值非「纯数字+元」：{r['value']!r}"
    # date：干净值 = ISO 日期，年份落在 1970–2026
    for r in data["date"]["clean"]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["value"]), f"date 干净值非 ISO：{r['value']!r}"
        y, m, d = (int(x) for x in r["value"].split("-"))
        assert 1970 <= y <= 2026 and 1 <= m <= 12 and 1 <= d <= 28


# ---------- 不变式 7：仓库内已落盘的产物 == 当前生成器 seed 42 的产物（防陈旧） ----------

def test_repo_artifacts_fresh(tmp_path):
    fresh = tmp_path / "fresh"
    _generate(fresh)
    for kind in ("clean", "dirty"):
        for field in FIELDS:
            committed = ROOT / "benchmarks" / kind / f"{field}.jsonl"
            assert committed.exists(), f"仓库缺产物 {committed}"
            assert committed.read_bytes() == (fresh / kind / f"{field}.jsonl").read_bytes(), \
                f"{kind}/{field}.jsonl 已过期，请重跑 python -m benchmarks.generate"

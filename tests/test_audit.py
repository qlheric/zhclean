"""audit 工具的不变式测试。

F: 报告计数（changed/unchanged/by_field/by_confidence）；dry-run 不改数据不落盘；apply 替换 + `_before`；
   rollback 恢复；checksum 不匹配拒绝；max_changes 截断；空输入；确定性；format_report
R: src/zhclean/tools/audit.py、src/zhclean/tools/normalize.py
A: uv run --project . pytest tests/test_audit.py -q
S: 只用手写样例，不读 benchmarks 数据/词典
"""

from __future__ import annotations

import copy
import os

import pytest

from zhclean.tools.audit import DEFAULT_MAX_CHANGES, apply, audit, format_report, rollback


def row(i, v, f="person"):
    return {"id": i, "field": f, "value": v}


# 档位已亲测（RESULT-010 §3）：0.9 结构清洗 / 0.7 错字修复 / 0.1 原样
ROWS = [
    row(1, "王 小明"),                  # → 王小明，0.9
    row(2, "王小明"),                   # 不改，0.1
    row(3, "范同言"),                   # → 范童言，0.7
    row(4, "138-1234-5678", "phone"),   # → 13812345678，0.9
    row(5, "13812345678", "phone"),     # 不改，0.1
]


@pytest.fixture
def rows():
    return copy.deepcopy(ROWS)


# ---- 报告计数 ---------------------------------------------------------------
def test_report_totals(rows):
    rep = audit(rows)
    assert (rep["total"], rep["changed"], rep["unchanged"]) == (5, 3, 2)


def test_report_by_field(rows):
    rep = audit(rows)
    assert rep["by_field"] == {
        "person": {"total": 3, "changed": 2, "unchanged": 1},
        "phone": {"total": 2, "changed": 1, "unchanged": 1},
    }


def test_report_by_confidence(rows):
    assert audit(rows)["by_confidence"] == {"0.9": 2, "0.7": 1, "0.1": 2, "other": 0}


def test_non_string_value_counts_as_other_unchanged():
    rep = audit([row(1, 12345)])
    assert rep["by_confidence"]["other"] == 1 and rep["changed"] == 0


def test_changes_detail_only_changed_rows(rows):
    ch = audit(rows)["changes"]
    assert [c["id"] for c in ch] == [1, 3, 4]
    assert ch[0] == {"id": 1, "field": "person", "before": "王 小明", "after": "王小明",
                     "confidence": 0.9, "reason": "structural"}
    assert ch[1]["reason"] == "infer" and ch[1]["after"] == "范童言"


# ---- dry-run -----------------------------------------------------------------
def test_dry_run_does_not_mutate_input(rows):
    snap = copy.deepcopy(rows)
    rep = audit(rows, dry_run=True)
    assert rows == snap
    assert rep["dry_run"] is True and "cleaned_rows" not in rep and "backup" not in rep


def test_dry_run_writes_no_files(rows, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audit(rows)
    assert os.listdir(tmp_path) == []


def test_non_dry_run_carries_apply_result_with_same_counts(rows):
    snap = copy.deepcopy(rows)
    wet, dry = audit(rows, dry_run=False), audit(rows)
    assert rows == snap  # 非 dry-run 也不改入参，结果放在报告里
    assert wet["cleaned_rows"] == apply(rows)[0]
    strip = lambda r: {k: v for k, v in r.items() if k not in ("dry_run", "cleaned_rows", "backup")}  # noqa: E731
    assert strip(wet) == strip(dry)


# ---- apply -------------------------------------------------------------------
def test_apply_replaces_and_keeps_before(rows):
    cleaned, _ = apply(rows)
    assert [r["value"] for r in cleaned] == ["王小明", "王小明", "范童言", "13812345678", "13812345678"]
    assert cleaned[0]["_before"] == "王 小明" and cleaned[2]["_before"] == "范同言"


def test_apply_leaves_unchanged_rows_untouched(rows):
    cleaned, _ = apply(rows)
    assert cleaned[1] == ROWS[1] and cleaned[4] == ROWS[4]  # 无 _before


def test_apply_does_not_mutate_input_and_backup_is_independent(rows):
    snap = copy.deepcopy(rows)
    cleaned, backup = apply(rows)
    assert rows == snap and backup["rows"] == snap
    rows[0]["value"] = "改了入参"
    assert backup["rows"][0]["value"] == "王 小明"  # 备份是深拷贝


def test_backup_shape(rows):
    _, backup = apply(rows)
    assert set(backup) == {"rows", "checksum"}
    assert len(backup["checksum"]) == 64 and int(backup["checksum"], 16) >= 0


# ---- rollback ----------------------------------------------------------------
def test_rollback_restores_original(rows):
    cleaned, backup = apply(rows)
    assert rollback(cleaned, backup) == ROWS


def test_rollback_rejects_tampered_cleaned_rows(rows):
    cleaned, backup = apply(rows)
    cleaned[0]["value"] = "李四"
    with pytest.raises(ValueError, match="checksum"):
        rollback(cleaned, backup)


def test_rollback_rejects_tampered_backup(rows):
    cleaned, backup = apply(rows)
    backup["rows"][1]["value"] = "张三"
    with pytest.raises(ValueError, match="checksum"):
        rollback(cleaned, backup)


def test_rollback_rejects_backup_from_another_apply(rows):
    cleaned, _ = apply(rows)
    _, other = apply(rows[:2])
    with pytest.raises(ValueError, match="checksum"):
        rollback(cleaned, other)


@pytest.mark.parametrize("bad", [None, {}, {"rows": []}, {"checksum": "x"}])
def test_rollback_rejects_malformed_backup(bad, rows):
    cleaned, _ = apply(rows)
    with pytest.raises(ValueError):
        rollback(cleaned, bad)


# ---- max_changes 截断 ---------------------------------------------------------
def test_max_changes_truncates(rows):
    rep = audit(rows, max_changes=2)
    assert [c["id"] for c in rep["changes"]] == [1, 3] and rep["truncated"] is True
    assert rep["changed"] == 3  # 计数不受截断影响


def test_max_changes_exact_fit_not_truncated(rows):
    rep = audit(rows, max_changes=3)
    assert len(rep["changes"]) == 3 and rep["truncated"] is False


def test_max_changes_default_and_zero(rows):
    assert DEFAULT_MAX_CHANGES == 1000
    rep = audit(rows, max_changes=0)
    assert rep["changes"] == [] and rep["truncated"] is True


@pytest.mark.parametrize("bad", [-1, 1.5, True, "10"])
def test_max_changes_invalid_rejected(bad, rows):
    with pytest.raises(ValueError):
        audit(rows, max_changes=bad)


# ---- 空输入 / 确定性 / 人读报告 ------------------------------------------------
def test_empty_input():
    rep = audit([])
    assert (rep["total"], rep["changed"], rep["unchanged"], rep["changes"]) == (0, 0, 0, [])
    assert rep["by_field"] == {} and rep["truncated"] is False
    cleaned, backup = apply([])
    assert cleaned == [] and rollback(cleaned, backup) == []
    assert "总行数 0" in format_report(rep)


def test_deterministic(rows):
    assert audit(rows) == audit(rows)
    assert apply(rows) == apply(rows)  # 含 checksum 逐字相同


def test_format_report_contents(rows):
    text = format_report(audit(rows))
    for s in ("dry-run", "总行数 5", "改动 3", "未改 2", "person", "phone", "0.9", "0.7", "0.1", "列出 3 条"):
        assert s in text
    assert "已截断" in format_report(audit(rows, max_changes=1))
    assert "已应用" in format_report(audit(rows, dry_run=False))

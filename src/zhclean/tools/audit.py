"""audit 工具：清洗报告 + dry-run 预览 + 可回滚。

F: 输出清洗报告（改了什么/为什么/置信度）；dry-run 不落盘；支持回滚
R: tools/normalize.py（normalize_with_confidence）、rules/common.py（置信度档位常量）
A: 被 cli.py 调用；自检 `python -m zhclean.tools.audit [--demo]`
S: 报告数字必须可复现（同输入同输出）；任何函数都不改入参、不写文件

接口契约（脑定，TASK-010 §2.5）：
- audit(rows, dry_run=True, max_changes=1000) -> 报告 dict
    total / changed / unchanged / by_field / by_confidence / changes / truncated / dry_run
- apply(rows) -> (cleaned_rows, backup)
    changed 行：value 换成规范值，加 `_before` 存原值；unchanged 行原样（拷贝）
    backup = {"rows": 原行深拷贝, "checksum": sha256}
- rollback(cleaned_rows, backup) -> 原行列表；checksum 不匹配即抛 ValueError
- format_report(report) -> 人读文本

口径说明（契约空白处我定的，已在 RESULT-010 申报）：
1. 「改动」= 规范值 != 原值（逐字符）；非字符串 value 由 normalize 原样返回（置信度 0.0）⇒ 计 unchanged、档位 other。
2. changes 明细在契约五字段外多一个 `reason`（clean / structural / infer / none / other），由置信度档位推出 ——
   这就是报告里的「为什么」。TASK-015 加 `clean`（0.95，值已规范，与 none 互斥；changes 里不会出现它，
   因为它必然 after == value ⇒ 不计入 changes）。
3. dry_run=False 时，报告额外带 `cleaned_rows` 与 `backup`（即 apply 的结果）；计数部分与 dry_run=True 完全相同。
4. checksum 同时绑定「原行」与「清洗后行」：sha256(规范 JSON {"rows": 原行, "cleaned": 清洗后行})。
   所以拿错备份、备份被篡改、清洗结果在回滚前被改过，都会被拒。
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
from typing import Any

from .._compat import utf8_stdio
from ..rules.common import CONF_CLEAN, CONF_INFER, CONF_NONE, CONF_STRUCTURAL
from .normalize import normalize_with_confidence

DEFAULT_MAX_CHANGES = 1000

# 置信度档位：键是报告里的字符串（JSON 友好），值是 (档位值, 原因说明)。
# 顺序即报告显示顺序（高 → 低）；TASK-015 加 "0.95" = 值已规范（与 "0.1" 语义互斥）。
_BANDS: tuple[tuple[str, float, str], ...] = (
    ("0.95", CONF_CLEAN, "clean"),           # 值已规范：结构干净 + 像合法值，无需改动
    ("0.9", CONF_STRUCTURAL, "structural"),  # 结构清洗命中（去空白/分隔符/噪声）
    ("0.7", CONF_INFER, "infer"),            # 推断层命中（错字修复/缩写补全）
    ("0.1", CONF_NONE, "none"),              # 无证据 / 拿不准，原样返回
)
_OTHER = ("other", "other")


def _band(conf: float) -> tuple[str, str]:
    """置信度 → (档位键, 原因)。用 isclose 防浮点表示差异。"""
    for key, val, reason in _BANDS:
        if isinstance(conf, (int, float)) and math.isclose(conf, val):
            return key, reason
    return _OTHER


def _clean_one(row: dict) -> tuple[Any, float]:
    return normalize_with_confidence(row["value"], row["field"])


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def audit(rows: list[dict], dry_run: bool = True,
          max_changes: int = DEFAULT_MAX_CHANGES) -> dict:
    """对每行跑 normalize_with_confidence，汇总成报告。入参不被修改。"""
    if isinstance(max_changes, bool) or not isinstance(max_changes, int) or max_changes < 0:
        raise ValueError(f"max_changes 须为非负整数，收到 {max_changes!r}")

    by_field: dict[str, dict[str, int]] = {}
    by_conf = {key: 0 for key, _, _ in _BANDS} | {_OTHER[0]: 0}
    changes: list[dict] = []
    changed = 0
    truncated = False

    for row in rows:
        after, conf = _clean_one(row)
        band, reason = _band(conf)
        by_conf[band] += 1
        f = by_field.setdefault(row["field"], {"total": 0, "changed": 0, "unchanged": 0})
        f["total"] += 1
        if after != row["value"]:
            changed += 1
            f["changed"] += 1
            if len(changes) < max_changes:
                changes.append({"id": row.get("id"), "field": row["field"],
                                "before": row["value"], "after": after,
                                "confidence": conf, "reason": reason})
            else:
                truncated = True
        else:
            f["unchanged"] += 1

    report: dict[str, Any] = {
        "dry_run": dry_run,
        "total": len(rows),
        "changed": changed,
        "unchanged": len(rows) - changed,
        "by_field": by_field,
        "by_confidence": by_conf,
        "changes": changes,
        "truncated": truncated,
    }
    if not dry_run:
        report["cleaned_rows"], report["backup"] = apply(rows)
    return report


# ---------------------------------------------------------------------------
# 应用 / 回滚
# ---------------------------------------------------------------------------
def _checksum(original: list[dict], cleaned: list[dict]) -> str:
    """规范 JSON（sort_keys、紧凑分隔、保留中文）→ sha256。不可序列化的值按 repr 落字。"""
    blob = json.dumps({"rows": original, "cleaned": cleaned}, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"), default=repr)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def apply(rows: list[dict]) -> tuple[list[dict], dict]:
    """把清洗真正应用到行副本上；返回 (清洗后行, 备份)。入参不被修改。

    注：若某个 changed 行本来就带 `_before` 键，会被覆盖；原值仍完整保存在 backup 里。
    """
    original = copy.deepcopy(rows)
    cleaned: list[dict] = []
    for row in rows:
        after, _ = _clean_one(row)
        new = copy.deepcopy(row)
        if after != row["value"]:
            new["_before"] = new["value"]
            new["value"] = after
        cleaned.append(new)
    return cleaned, {"rows": original, "checksum": _checksum(original, cleaned)}


def rollback(cleaned_rows: list[dict], backup: dict) -> list[dict]:
    """用备份恢复原行。备份与清洗结果对不上（checksum 不匹配）就拒绝。"""
    if not isinstance(backup, dict) or "rows" not in backup or "checksum" not in backup:
        raise ValueError("backup 结构不对：须为 {'rows': [...], 'checksum': '...'}")
    if _checksum(backup["rows"], cleaned_rows) != backup["checksum"]:
        raise ValueError("checksum 不匹配：备份与清洗结果不是同一次 apply 的产物，拒绝回滚")
    return copy.deepcopy(backup["rows"])


# ---------------------------------------------------------------------------
# 人读报告
# ---------------------------------------------------------------------------
def format_report(report: dict) -> str:
    t, c = report["total"], report["changed"]
    rate = f"{c / t:.2%}" if t else "-"
    lines = [
        f"清洗报告（{'dry-run 预览，未应用' if report.get('dry_run', True) else '已应用，可回滚'}）",
        f"总行数 {t}　改动 {c}（{rate}）　未改 {report['unchanged']}",
        "按字段：",
    ]
    for field, s in report["by_field"].items():
        lines.append(f"  {field:<9} 总 {s['total']:>5}  改 {s['changed']:>5}  未改 {s['unchanged']:>5}")
    lines.append("按置信度：")
    for key, n in report["by_confidence"].items():
        lines.append(f"  {key:<6} {n:>5}")
    shown = len(report["changes"])
    lines.append(f"改动明细：列出 {shown} 条" + ("（已截断）" if report["truncated"] else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def _demo() -> None:
    """最小可运行检查：报告计数 / dry-run 不改数据 / apply / rollback / checksum 拒绝 / 空输入。"""
    rows = [
        {"id": 1, "field": "person", "value": "王 小明"},   # 结构清洗 → 王小明
        {"id": 2, "field": "person", "value": "王小明"},    # 已规范，不改
        {"id": 3, "field": "phone", "value": "138-1234-5678"},
    ]
    snapshot = copy.deepcopy(rows)

    # 1) 报告计数
    rep = audit(rows)
    assert (rep["total"], rep["changed"], rep["unchanged"]) == (3, 2, 1)
    assert rep["by_field"]["person"] == {"total": 2, "changed": 1, "unchanged": 1}
    assert [c["id"] for c in rep["changes"]] == [1, 3] and rep["truncated"] is False

    # 2) dry-run 不改数据
    assert rows == snapshot and "cleaned_rows" not in rep

    # 3) apply 替换正确 + _before 留存；unchanged 行不加 _before
    cleaned, backup = apply(rows)
    assert cleaned[0]["value"] == "王小明" and cleaned[0]["_before"] == "王 小明"
    assert "_before" not in cleaned[1] and rows == snapshot

    # 4) rollback 恢复
    assert rollback(cleaned, backup) == snapshot

    # 5) checksum 拒绝：清洗结果被改过 / 拿错备份
    tampered = copy.deepcopy(cleaned)
    tampered[0]["value"] = "李四"
    _, other_backup = apply(rows[:1])
    for c, b in ((tampered, backup), (cleaned, other_backup)):
        try:
            rollback(c, b)
        except ValueError:
            pass
        else:
            raise AssertionError("checksum 不匹配应被拒绝")

    # 6) 空输入
    empty = audit([])
    assert (empty["total"], empty["changed"], empty["changes"]) == (0, 0, [])
    assert apply([])[0] == [] and rollback(*apply([])) == []

    # 7) 确定性
    assert audit(rows) == audit(rows) and apply(rows)[1]["checksum"] == backup["checksum"]

    print("audit._demo: OK")


if __name__ == "__main__":
    utf8_stdio()  # 用法/报错含中文，Windows 控制台默认 cp936 会写坏（TASK-015）
    # `--demo` 与无参等价（TASK §2.5 写带参、§3 判据写无参，两种都支持）
    if len(sys.argv) > 1 and sys.argv[1] != "--demo":
        sys.exit(f"用法: python -m zhclean.tools.audit [--demo]，未知参数 {sys.argv[1:]}")
    _demo()

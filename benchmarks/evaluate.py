"""评测管线：脏集 → normalize → 规范化率（按 field × perturbation 分组）+ 失败案例。

F: 计算 normalize(value) == truth 的比例，落 summary / failures 到 benchmarks/results/
R: benchmarks/dirty/*.jsonl（TASK-001 产物）
A: python -m benchmarks.evaluate --impl stub [--split heldout]
S: 默认只评 heldout；口径逐字符相等，不做空白宽容

normalize 可插拔：IMPLS 里的函数接收一整行 dirty 记录、返回规范化后的字符串。
- stub    恒返回原值（能红：规范化率应为 0%）
- perfect 直接回 truth（能绿：规范化率应为 100%，只用于验证管线本身）
真实规则接入时在 IMPLS 里加一项即可，例如
    "rules": lambda row: zhclean.normalize(row["value"], row["field"])
（rules 实现会 import src/zhclean，见文件头 import）

产物：
- results/summary-<impl>-<split>.json   总分 + by_field + by_perturbation + by_field_perturbation
- results/failures-<impl>-<split>.jsonl 失败行（按输入顺序）
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import zhclean  # rules 实现需要（TASK-003 接入）

HERE = Path(__file__).resolve().parent
FIELDS = ("person", "address", "phone", "company", "amount", "date", "idcard", "email")
SPLITS = ("heldout", "train", "all")

IMPLS: dict[str, Callable[[dict], str]] = {
    "stub": lambda row: row["value"],
    "perfect": lambda row: row["truth"],
    "rules": lambda row: zhclean.normalize(row["value"], row["field"]),
}


def load_dirty(dirty_dir: Path, split: str) -> list[dict]:
    """按 FIELDS 固定顺序读四个脏集文件，按 split 过滤（all = 不过滤）。"""
    rows: list[dict] = []
    for field in FIELDS:
        with open(dirty_dir / f"{field}.jsonl", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if split == "all" or row["split"] == split:
                        rows.append(row)
    return rows


def _score(correct: int, total: int) -> dict:
    # 空分组 rate 记 0.0（正常数据不会出现：每 split 都覆盖五类扰动）
    return {"correct": correct, "total": total,
            "rate": round(correct / total, 6) if total else 0.0}


def evaluate(rows: list[dict], impl: Callable[[dict], str]) -> tuple[dict, list[dict]]:
    """跑一遍 normalize，返回 (分组计数, 失败行)。"""
    counts: dict[tuple[str, str], list[int]] = {}  # (field, perturbation) -> [correct, total]
    failures: list[dict] = []
    for row in rows:
        normalized = impl(row)
        ok = normalized == row["truth"]
        c = counts.setdefault((row["field"], row["perturbation"]), [0, 0])
        c[0] += ok
        c[1] += 1
        if not ok:
            failures.append({"id": row["id"], "field": row["field"], "value": row["value"],
                             "normalized": normalized, "truth": row["truth"],
                             "perturbation": row["perturbation"]})

    def rollup(key_of: Callable[[tuple[str, str]], str]) -> dict:
        acc: dict[str, list[int]] = {}
        for k, (ok, n) in counts.items():
            a = acc.setdefault(key_of(k), [0, 0])
            a[0] += ok
            a[1] += n
        return {k: _score(*v) for k, v in acc.items()}

    by_fp: dict[str, dict] = {}
    for (field, pert), (ok, n) in counts.items():
        by_fp.setdefault(field, {})[pert] = _score(ok, n)

    summary = {
        "total": _score(sum(c[0] for c in counts.values()), sum(c[1] for c in counts.values())),
        "by_field": rollup(lambda k: k[0]),
        "by_perturbation": rollup(lambda k: k[1]),
        "by_field_perturbation": by_fp,
    }
    return summary, failures


def write_results(out_dir: Path, impl_name: str, split: str,
                  summary: dict, failures: list[dict]) -> tuple[Path, Path]:
    """落盘：utf-8 + LF；summary sort_keys，failures 按输入顺序（逐字节可复现）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    s_path = out_dir / f"summary-{impl_name}-{split}.json"
    f_path = out_dir / f"failures-{impl_name}-{split}.jsonl"
    payload = {"impl": impl_name, "split": split, **summary}
    with open(s_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    with open(f_path, "w", encoding="utf-8", newline="\n") as f:
        for row in failures:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return s_path, f_path


def format_table(summary: dict) -> str:
    """stdout 用：总分 + field × perturbation 百分比表。"""
    t = summary["total"]
    perts = sorted(summary["by_perturbation"])
    lines = [f"total {t['correct']}/{t['total']} = {t['rate']:.2%}",
             f"{'field':<9}" + "".join(f"{p:>9}" for p in perts) + f"{'all':>9}"]
    for field in FIELDS:
        if field not in summary["by_field"]:
            continue
        cells = summary["by_field_perturbation"][field]
        lines.append(f"{field:<9}"
                     + "".join(f"{cells[p]['rate']:>9.2%}" if p in cells else f"{'-':>9}"
                               for p in perts)
                     + f"{summary['by_field'][field]['rate']:>9.2%}")
    lines.append(f"{'all':<9}"
                 + "".join(f"{summary['by_perturbation'][p]['rate']:>9.2%}" for p in perts)
                 + f"{t['rate']:>9.2%}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="评测规范化率（默认只评 heldout）")
    parser.add_argument("--impl", choices=sorted(IMPLS), required=True, help="normalize 实现")
    parser.add_argument("--split", choices=SPLITS, default="heldout", help="评测集（默认 heldout）")
    parser.add_argument("--dirty-dir", default=str(HERE / "dirty"), help="脏集目录")
    parser.add_argument("--out", default=str(HERE / "results"), help="产物目录")
    args = parser.parse_args(argv)

    rows = load_dirty(Path(args.dirty_dir), args.split)
    summary, failures = evaluate(rows, IMPLS[args.impl])
    s_path, f_path = write_results(Path(args.out), args.impl, args.split, summary, failures)
    print(f"impl={args.impl} split={args.split} rows={len(rows)} failures={len(failures)}")
    print(format_table(summary))
    print(f"summary  -> {s_path.name}")
    print(f"failures -> {f_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

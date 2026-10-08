"""dedupe 评测：同 id 的 clean + 5 条 dirty = 一个应合并组 → pair recall / precision / F1。

F: 真组按 id 聚合；pair 口径算 recall + precision（同看，防只追 recall 调低阈值）；落 summary / errors
R: benchmarks/clean|dirty/*.jsonl、src/zhclean/tools/dedupe.py
A: python -m benchmarks.evaluate_dedupe [--split heldout] [--threshold 0.85 | --select-threshold] [--adaptive]
S: 阈值只在 train 上扫选；heldout 只用给定/选定阈值跑一次；同输入同输出

口径（TASK-009 §2.5）：
- 真组：按 id 聚合。clean 行没有 split 字段，取同 id dirty 行的 split（数据里每 id 恰一个 split）。
- pair recall    = 真组内行对中，被并进同一预测组的比例（分母 = Σ C(组大小, 2)）。
- pair precision = 预测组内行对中，属于同一真组的比例（不同 id 被误并即扣分）。
- F1 = 2PR/(P+R)；分母为 0 时该项记 0.0（与 evaluate.py 的空分组口径一致）。
- dedupe 只在同 field 内合并（RESULT-008 §5-2），故按 field 拆分 = 预测组按首行 field 归类。

--select-threshold：只读 train 行，按 THRESHOLD_GRID 逐个跑 dedupe，F1 最大者胜（并列取网格里靠前的）；
然后用选定阈值在 --split 上跑**一次**。train 的扫描结果也写进 summary（selection 字段）。

产物：
- results/dedupe-summary-<split>.json  总分 + by_field + 阈值（及选择过程）
- results/dedupe-errors-<split>.jsonl  漏并对 / 误并对样例各 ≤ ERROR_SAMPLE_CAP 条（按输入序）
"""

from __future__ import annotations

import argparse
import heapq
import json
from collections.abc import Callable
from itertools import islice
from pathlib import Path

from zhclean.tools.dedupe import DEFAULT_THRESHOLD, dedupe, dedupe_adaptive, describe_adaptive

HERE = Path(__file__).resolve().parent
FIELDS = ("person", "address", "phone", "company")
SPLITS = ("heldout", "train")
THRESHOLD_GRID = (0.80, 0.85, 0.90, 0.95)
ERROR_SAMPLE_CAP = 50

DedupeFn = Callable[[list[dict], float], list[list[dict]]]


# ---------------------------------------------------------------------------
# 读数据
# ---------------------------------------------------------------------------
def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"缺数据文件: {path}")
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows:
        raise ValueError(f"数据文件为空: {path}")
    return rows


def load_rows(clean_dir: Path, dirty_dir: Path, split: str) -> list[dict]:
    """按 FIELDS 固定顺序读 clean + dirty，给每行带上 split，按 split 过滤。

    返回行只保留 id / field / value / kind（"clean" | "dirty"）/ split / perturbation，
    **不带 truth**——dedupe 只该看到 value。
    """
    if split not in SPLITS:
        raise ValueError(f"split 须为 {SPLITS} 之一，收到 {split!r}")
    out: list[dict] = []
    for field in FIELDS:
        dirty = _read_jsonl(dirty_dir / f"{field}.jsonl")
        clean = _read_jsonl(clean_dir / f"{field}.jsonl")

        split_of: dict[str, str] = {}
        for r in dirty:
            prev = split_of.setdefault(r["id"], r["split"])
            if prev != r["split"]:
                raise ValueError(f"id {r['id']} 同时出现在 {prev} 与 {r['split']}")
        for r in clean:
            if r["id"] not in split_of:
                raise ValueError(f"clean 行 id {r['id']} 在 dirty 集里找不到")
            if split_of[r["id"]] == split:
                out.append({"id": r["id"], "field": r["field"], "value": r["value"],
                            "kind": "clean", "split": split, "perturbation": None})
        for r in dirty:
            if r["split"] == split:
                out.append({"id": r["id"], "field": r["field"], "value": r["value"],
                            "kind": "dirty", "split": split, "perturbation": r["perturbation"]})
    if not out:
        raise ValueError(f"split={split} 下没有任何行")
    return out


# ---------------------------------------------------------------------------
# 计分
# ---------------------------------------------------------------------------
def _pairs(n: int) -> int:
    return n * (n - 1) // 2


def _prf(tp: int, true_pairs: int, pred_pairs: int) -> dict:
    p = tp / pred_pairs if pred_pairs else 0.0
    r = tp / true_pairs if true_pairs else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"true_pairs": true_pairs, "pred_pairs": pred_pairs, "tp": tp,
            "precision": round(p, 6), "recall": round(r, 6), "f1": round(f1, 6)}


def score(rows: list[dict], groups: list[list[dict]]) -> tuple[dict, list[dict]]:
    """rows = 评测集（输入序），groups = dedupe 输出。返回 (summary 计分部分, 错误样例)。

    组内行用对象身份（id()）映射回输入下标，所以 groups 必须是 rows 里那些行对象。
    """
    pos = {id(r): i for i, r in enumerate(rows)}
    pred = [0] * len(rows)  # 输入下标 → 预测组号
    for g_no, g in enumerate(groups):
        for r in g:
            pred[pos[id(r)]] = g_no
    if sum(len(g) for g in groups) != len(rows):
        raise ValueError("dedupe 输出的行数与输入不一致")

    # 真组：id → 输入下标列表（输入序）
    true_groups: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        true_groups.setdefault(r["id"], []).append(i)

    # 计数：按 field 累加 [tp, true_pairs, pred_pairs]
    acc: dict[str, list[int]] = {f: [0, 0, 0] for f in FIELDS if any(r["field"] == f for r in rows)}
    for idxs in true_groups.values():
        a = acc[rows[idxs[0]]["field"]]
        a[1] += _pairs(len(idxs))
        cnt: dict[int, int] = {}
        for i in idxs:
            cnt[pred[i]] = cnt.get(pred[i], 0) + 1
        a[0] += sum(_pairs(c) for c in cnt.values())  # 真组内被分进同一预测组的对
    for g in groups:
        if g:
            acc[g[0]["field"]][2] += _pairs(len(g))

    by_field = {f: _prf(*v) for f, v in acc.items()}
    total = _prf(*(sum(v[k] for v in acc.values()) for k in range(3)))

    # 错误样例：漏并 = 同 id 不同预测组；误并 = 同预测组不同 id。各按 (i, j) 输入序取前 CAP 条
    def brief(i: int) -> dict:
        r = rows[i]
        return {"id": r["id"], "value": r["value"], "kind": r["kind"], "perturbation": r["perturbation"]}

    def pair_iter(idxs: list[int], bad: Callable[[int, int], bool]):
        # idxs 已升序 ⇒ 产出的 (i, j) 按字典序升序
        return ((i, j) for a_, i in enumerate(idxs) for j in idxs[a_ + 1:] if bad(i, j))

    def first_k(iters) -> list[tuple[int, int]]:
        # 多路归并取全局最小的 CAP 对：惰性，不物化全部错误对（低阈值时大组可达百万对）
        return list(islice(heapq.merge(*iters), ERROR_SAMPLE_CAP))

    missed = first_k(pair_iter(idxs, lambda i, j: pred[i] != pred[j]) for idxs in true_groups.values())
    wrong = first_k(pair_iter(sorted(pos[id(r)] for r in g), lambda i, j: rows[i]["id"] != rows[j]["id"])
                    for g in groups)
    errors = (
        [{"type": "missed", "field": rows[i]["field"], "a": brief(i), "b": brief(j)} for i, j in missed]
        + [{"type": "wrong_merge", "field": rows[i]["field"], "a": brief(i), "b": brief(j)} for i, j in wrong]
    )

    summary = {"rows": len(rows), "true_groups": len(true_groups), "pred_groups": len(groups),
               "missed_pairs": total["true_pairs"] - total["tp"],
               "wrong_merge_pairs": total["pred_pairs"] - total["tp"],
               "total": total, "by_field": by_field}
    return summary, errors


def evaluate(rows: list[dict], threshold: float, dedupe_fn: DedupeFn = dedupe) -> tuple[dict, list[dict]]:
    """跑一次 dedupe 并计分。"""
    return score(rows, dedupe_fn(rows, threshold))


def select_threshold(train_rows: list[dict], dedupe_fn: DedupeFn = dedupe,
                     grid: tuple[float, ...] = THRESHOLD_GRID) -> tuple[float, list[dict]]:
    """只在 train 行上扫网格，按总 F1 选阈值（并列取靠前的）。返回 (阈值, 扫描记录)。"""
    if not train_rows or any(r["split"] != "train" for r in train_rows):
        raise ValueError("select_threshold 只接受非空的 train 行")
    sweep: list[dict] = []
    best_t, best_f1 = grid[0], -1.0
    for t in grid:
        s, _ = evaluate(train_rows, t, dedupe_fn)
        sweep.append({"threshold": t, **s["total"]})
        if s["total"]["f1"] > best_f1:
            best_t, best_f1 = t, s["total"]["f1"]
    return best_t, sweep


# ---------------------------------------------------------------------------
# 落盘 / 输出
# ---------------------------------------------------------------------------
def write_results(out_dir: Path, split: str, summary: dict, errors: list[dict]) -> tuple[Path, Path]:
    """utf-8 + LF；summary sort_keys，errors 按输入序（逐字节可复现）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    s_path = out_dir / f"dedupe-summary-{split}.json"
    e_path = out_dir / f"dedupe-errors-{split}.jsonl"
    with open(s_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    with open(e_path, "w", encoding="utf-8", newline="\n") as f:
        for e in errors:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return s_path, e_path


def format_table(summary: dict) -> str:
    lines = [f"{'field':<9}{'recall':>10}{'precision':>11}{'f1':>9}{'tp':>7}{'true':>7}{'pred':>7}"]
    for name, s in [*summary["by_field"].items(), ("all", summary["total"])]:
        lines.append(f"{name:<9}{s['recall']:>10.2%}{s['precision']:>11.2%}{s['f1']:>9.2%}"
                     f"{s['tp']:>7}{s['true_pairs']:>7}{s['pred_pairs']:>7}")
    return "\n".join(lines)


def _threshold_arg(s: str) -> float:
    v = float(s)
    if not 0.0 <= v <= 1.0:  # NaN 也会落到这里
        raise argparse.ArgumentTypeError(f"阈值须在 [0,1]，收到 {s}（注意不是 0~100）")
    return v


def main(argv: list[str] | None = None, dedupe_fn: DedupeFn = dedupe,
         adaptive_fn: DedupeFn = dedupe_adaptive) -> int:
    """dedupe_fn / adaptive_fn 可注入（测试用）；--adaptive 时选择与评测都走 adaptive_fn。"""
    parser = argparse.ArgumentParser(description="dedupe 评测（pair recall / precision；默认 heldout）")
    parser.add_argument("--split", choices=SPLITS, default="heldout", help="评测集（默认 heldout）")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--threshold", type=_threshold_arg, default=None,
                      help=f"显式阈值 [0,1]（缺省 {DEFAULT_THRESHOLD}）")
    mode.add_argument("--select-threshold", action="store_true",
                      help=f"在 train 上扫 {list(THRESHOLD_GRID)} 按 F1 选阈值，再跑 --split 一次")
    parser.add_argument("--adaptive", action="store_true",
                        help="按字段自适应配置（DEFAULT_ADAPTIVE）；未覆盖字段仍用 --threshold")
    parser.add_argument("--clean-dir", default=str(HERE / "clean"), help="clean 集目录")
    parser.add_argument("--dirty-dir", default=str(HERE / "dirty"), help="脏集目录")
    parser.add_argument("--out", default=str(HERE / "results"), help="产物目录")
    args = parser.parse_args(argv)
    clean_dir, dirty_dir = Path(args.clean_dir), Path(args.dirty_dir)
    if args.adaptive:
        dedupe_fn = adaptive_fn

    selection = None
    if args.select_threshold:
        # 选择只读 train；heldout 行此时还没加载
        threshold, sweep = select_threshold(load_rows(clean_dir, dirty_dir, "train"), dedupe_fn)
        selection = {"on_split": "train", "grid": list(THRESHOLD_GRID), "by": "f1", "sweep": sweep}
        for s in sweep:
            print(f"[select@train] t={s['threshold']:.2f} recall={s['recall']:.2%} "
                  f"precision={s['precision']:.2%} f1={s['f1']:.2%}")
    else:
        threshold = DEFAULT_THRESHOLD if args.threshold is None else args.threshold

    rows = load_rows(clean_dir, dirty_dir, args.split)
    summary, errors = evaluate(rows, threshold, dedupe_fn)
    summary = {"split": args.split, "threshold": threshold, "threshold_source":
               "select@train" if selection else ("default" if args.threshold is None else "explicit"),
               "selection": selection, "adaptive": args.adaptive,
               "adaptive_config": describe_adaptive() if args.adaptive else None, **summary}
    s_path, e_path = write_results(Path(args.out), args.split, summary, errors)

    print(f"split={args.split} threshold={threshold} adaptive={args.adaptive} rows={summary['rows']} "
          f"true_groups={summary['true_groups']} pred_groups={summary['pred_groups']} "
          f"missed_pairs={summary['missed_pairs']} wrong_merge_pairs={summary['wrong_merge_pairs']}")
    print(format_table(summary))
    print(f"summary -> {s_path.name}")
    print(f"errors  -> {e_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

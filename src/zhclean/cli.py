"""CLI 入口：子命令与参数解析，分发到三工具（normalize / dedupe / audit + rollback）。

F: CLI 入口（normalize / dedupe / audit / rollback 子命令）；jsonl 进出（每行 id / field / value）
R: tools/normalize.py、tools/dedupe.py、tools/audit.py（三工具，本模块不含清洗逻辑）
A: python -m zhclean.cli <子命令> --help
S: 落盘只在本层发生（工具本体保持纯函数）；退出码语义固定（见下）

退出码（TASK-012 §2.5）：
- 0  成功
- 1  运行错：输入文件不存在 / 不是合法 jsonl / 行缺字段 / checksum 不匹配 / 拒绝覆盖备份 等
- 2  参数错：argparse 解析失败（未知子命令、缺必填参数、阈值越界、互斥参数同用）

I/O 约定：
- --input 缺省或写 `-` 时读 stdin（utf-8）；文件按 utf-8 读，容忍 BOM；空行跳过。
- 数据行写到 --out（无 --out 时写 stdout）；汇总信息写 stdout（有 --out 时）或 stderr（无 --out 时），
  保证「无 --out」时 stdout 是纯 jsonl，可以直接接管道。
- 输出 jsonl：utf-8、LF、ensure_ascii=False，字段顺序 = 原行顺序 + 新增键追加在末尾。

用法示例：
  echo '{"id":"1","field":"person","value":"范 童言"}' | python -m zhclean.cli normalize
  python -m zhclean.cli dedupe --input rows.jsonl --out grouped.jsonl          # 默认 adaptive
  python -m zhclean.cli audit  --input rows.jsonl                              # dry-run 报告
  python -m zhclean.cli audit  --input rows.jsonl --apply --out clean.jsonl    # 写 clean.jsonl + clean.backup.json
  python -m zhclean.cli rollback --cleaned clean.jsonl --backup clean.backup.json --out restored.jsonl
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import TextIO

from .tools.audit import apply, audit, format_report, rollback
from .tools.dedupe import DEFAULT_THRESHOLD, dedupe, dedupe_adaptive
from .tools.normalize import normalize_with_confidence

FIELDS = ("person", "address", "phone", "company")
EXIT_OK, EXIT_RUNTIME, EXIT_USAGE = 0, 1, 2


class CliError(Exception):
    """运行错（退出码 1）：消息直接展示给用户，必须是中文。"""


class _Parser(argparse.ArgumentParser):
    """中文化的 ArgumentParser：-h/--help 说明中文；出错补中文提示，退出码保持 argparse 默认的 2。

    注：「usage:」「options:」等 argparse 内置标题仍是英文（标准库固定文案，不 hack 私有实现）。
    """

    def __init__(self, *args, **kwargs):
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action="help", help="显示帮助并退出")

    def error(self, message: str):  # noqa: D401
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"参数错误：{message}\n（加 --help 查看用法）\n")


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def _read_text(path: str, stdin: TextIO) -> str:
    if path == "-":
        buf = getattr(stdin, "buffer", None)
        # 真终端 / 管道：按字节读再 utf-8 解码，不受 Windows 控制台代码页（cp936）影响
        return buf.read().decode("utf-8-sig") if buf is not None else stdin.read()
    p = Path(path)
    if not p.is_file():
        raise CliError(f"输入文件不存在：{path}")
    return p.read_text(encoding="utf-8-sig")


def _read_jsonl(path: str, stdin: TextIO, need_field: bool = True) -> list[dict]:
    """读 jsonl；每行须是 JSON 对象且含 value（need_field 时还须含 field）。错误带行号。"""
    rows: list[dict] = []
    for no, line in enumerate(_read_text(path, stdin).splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            raise CliError(f"{path} 第 {no} 行不是合法 JSON：{e.msg}（列 {e.colno}）") from None
        if not isinstance(row, dict):
            raise CliError(f"{path} 第 {no} 行须是 JSON 对象，收到 {type(row).__name__}")
        missing = [k for k in (("field", "value") if need_field else ("value",)) if k not in row]
        if missing:
            raise CliError(f"{path} 第 {no} 行缺字段：{', '.join(missing)}")
        rows.append(row)
    return rows


def _dump_jsonl(rows: list[dict], fp: TextIO) -> None:
    for r in rows:
        fp.write(json.dumps(r, ensure_ascii=False) + "\n")


def _write_jsonl(rows: list[dict], out: str | None, stdout: TextIO) -> None:
    """有 out 写文件（utf-8 + LF），否则写 stdout。"""
    if out is None:
        _dump_jsonl(rows, stdout)
        return
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        _dump_jsonl(rows, f)


def _write_json(obj, path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------
# 每个 _cmd_* 返回退出码；info 是汇总信息流（见模块头「I/O 约定」）
def _info_stream(args, stdout: TextIO, stderr: TextIO) -> TextIO:
    return stdout if getattr(args, "out", None) else stderr


def _cmd_normalize(args, stdin, stdout, stderr) -> int:
    rows = _read_jsonl(args.input, stdin, need_field=args.field is None)
    out = []
    for r in rows:
        field = args.field or r["field"]
        norm, conf = normalize_with_confidence(r["value"], field)
        out.append({**r, "normalized": norm, "confidence": conf})
    _write_jsonl(out, args.out, stdout)
    changed = sum(1 for r in out if r["normalized"] != r["value"])
    print(f"normalize：共 {len(out)} 行，规范值与原值不同 {changed} 行", file=_info_stream(args, stdout, stderr))
    return EXIT_OK


def _cmd_dedupe(args, stdin, stdout, stderr) -> int:
    rows = _read_jsonl(args.input, stdin)
    fn = dedupe if args.plain else dedupe_adaptive
    try:
        groups = fn(rows, args.threshold)
    except (TypeError, ValueError) as e:  # 例：value 不可 hash 之外的异常输入
        raise CliError(f"dedupe 失败：{e}") from None
    # 组内是原行对象 ⇒ 用 id() 映射回输入下标；输出保持输入行序，每行加 _group（组首行序，从 0 起）
    group_of = {id(r): g_no for g_no, g in enumerate(groups) for r in g}
    out = [{**r, "_group": group_of[id(r)]} for r in rows]
    _write_jsonl(out, args.out, stdout)
    multi = sum(1 for g in groups if len(g) > 1)
    mode = "plain" if args.plain else "adaptive"
    print(f"dedupe（{mode}，threshold={args.threshold}）：共 {len(rows)} 行 → {len(groups)} 组"
          f"（其中多行组 {multi} 个，可去掉 {len(rows) - len(groups)} 行）",
          file=_info_stream(args, stdout, stderr))
    return EXIT_OK


def _backup_path(out: Path) -> Path:
    """y.jsonl → y.backup.json（TASK-012 §2.5 约定的旁写名）。"""
    return out.with_name(out.stem + ".backup.json") if out.suffix == ".jsonl" else \
        out.with_name(out.name + ".backup.json")


def _cmd_audit(args, stdin, stdout, stderr) -> int:
    rows = _read_jsonl(args.input, stdin)
    if not args.apply:
        # dry-run：只打印报告，不写任何文件
        print(format_report(audit(rows, dry_run=True)), file=stdout)
        return EXIT_OK

    if args.out is None:
        if args.input == "-":
            raise CliError("从 stdin 读入时 --apply 必须配 --out（没有可推导的输出文件名）")
        src = Path(args.input)
        out = src.with_name(src.stem + ".cleaned.jsonl")
    else:
        out = Path(args.out)
    bak = _backup_path(out)
    if not args.force:
        for p in (out, bak):
            if p.exists():
                raise CliError(f"拒绝覆盖已存在的文件：{p}（确认要覆盖请加 --force）")

    cleaned, backup = apply(rows)
    # 先写备份再写清洗结果：中途失败时至少原数据有据可查
    _write_json(backup, bak)
    _write_jsonl(cleaned, str(out), stdout)
    report = audit(rows, dry_run=False)
    print(format_report(report), file=stdout)
    print(f"已写清洗结果：{out}", file=stdout)
    print(f"已写备份（含 checksum）：{bak}", file=stdout)
    print(f"回滚：python -m zhclean.cli rollback --cleaned {out} --backup {bak}", file=stdout)
    return EXIT_OK


def _cmd_rollback(args, stdin, stdout, stderr) -> int:
    cleaned = _read_jsonl(args.cleaned, stdin)
    try:
        backup = json.loads(_read_text(args.backup, stdin))
    except json.JSONDecodeError as e:
        raise CliError(f"备份文件不是合法 JSON：{args.backup}（{e.msg}）") from None
    try:
        restored = rollback(cleaned, backup)
    except ValueError as e:
        raise CliError(f"回滚被拒：{e}") from None
    _write_jsonl(restored, args.out, stdout)
    print(f"rollback：已恢复 {len(restored)} 行（checksum 校验通过）", file=_info_stream(args, stdout, stderr))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
def _threshold_arg(s: str) -> float:
    try:
        v = float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"阈值须是数字，收到 {s!r}") from None
    if not 0.0 <= v <= 1.0:  # NaN 也落到这里
        raise argparse.ArgumentTypeError(f"阈值须在 [0,1]，收到 {s}（注意不是 0~100）")
    return v


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="zhclean", description="中文脏数据净化器：规范化 / 去重 / 清洗报告（jsonl 进出）",
                epilog="退出码：0 成功；1 运行错（文件/数据/校验问题）；2 参数错")
    sub = p.add_subparsers(dest="command", metavar="<子命令>", parser_class=_Parser)
    inp = dict(default="-", help="输入 jsonl（每行 id/field/value；缺省或 - 读 stdin）")

    n = sub.add_parser("normalize", help="字段级规范化：输出行加 normalized 与 confidence")
    n.add_argument("--input", **inp)
    n.add_argument("--field", choices=FIELDS, help="强制按此字段类型清洗（缺省用每行自带的 field）")
    n.add_argument("--out", help="输出 jsonl（缺省写 stdout）")
    n.set_defaults(func=_cmd_normalize)

    d = sub.add_parser("dedupe", help="两级去重（默认 adaptive）：输出行加 _group 组序号")
    d.add_argument("--input", **inp)
    mode = d.add_mutually_exclusive_group()
    mode.add_argument("--adaptive", action="store_true", help="按字段自适应配置（默认）")
    mode.add_argument("--plain", action="store_true", help="退回全局 fuzz.ratio + 单一阈值")
    d.add_argument("--threshold", type=_threshold_arg, default=DEFAULT_THRESHOLD,
                   help=f"相似度阈值 [0,1]（缺省 {DEFAULT_THRESHOLD}；adaptive 下只作用于未单独配置的字段）")
    d.add_argument("--out", help="输出 jsonl（缺省写 stdout）")
    d.set_defaults(func=_cmd_dedupe)

    a = sub.add_parser("audit", help="清洗报告（默认 dry-run 不写文件；--apply 写清洗结果 + 备份）")
    a.add_argument("--input", **inp)
    a.add_argument("--apply", action="store_true", help="真正应用：写 --out 与旁边的 <out>.backup.json")
    a.add_argument("--out", help="--apply 时的输出 jsonl（缺省 <input>.cleaned.jsonl）")
    a.add_argument("--force", action="store_true", help="--apply 时允许覆盖已存在的输出/备份文件")
    a.set_defaults(func=_cmd_audit)

    r = sub.add_parser("rollback", help="用 audit --apply 的备份恢复原数据（checksum 不匹配即拒绝）")
    r.add_argument("--cleaned", required=True, help="audit --apply 写出的清洗结果 jsonl")
    r.add_argument("--backup", required=True, help="对应的 .backup.json")
    r.add_argument("--out", help="恢复结果 jsonl（缺省写 stdout）")
    r.set_defaults(func=_cmd_rollback)
    return p


def main(argv: list[str] | None = None, stdin: TextIO | None = None,
         stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """CLI 主函数。stdin/stdout/stderr 可注入（测试用）；返回退出码，不抛 SystemExit。"""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:  # argparse：--help → 0，参数错 → 2
        return e.code if isinstance(e.code, int) else EXIT_USAGE
    if args.command is None:
        parser.print_help(stderr)
        print("参数错误：缺少子命令", file=stderr)
        return EXIT_USAGE
    try:
        return args.func(args, stdin, stdout, stderr)
    except CliError as e:
        print(f"错误：{e}", file=stderr)
        return EXIT_RUNTIME
    except OSError as e:  # 写文件失败、权限等
        print(f"错误：文件读写失败：{e}", file=stderr)
        return EXIT_RUNTIME


def _utf8_stdio() -> None:
    """真实进程里把 stdout/stderr 设成 utf-8（Windows 控制台默认 cp936 会写坏部分汉字）。"""
    for s in (sys.stdout, sys.stderr):
        if isinstance(s, io.TextIOWrapper):
            s.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    _utf8_stdio()
    raise SystemExit(main())

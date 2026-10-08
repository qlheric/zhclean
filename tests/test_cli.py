"""CLI 端到端测试：normalize / dedupe / audit / rollback 四个子命令。

F: tmp 文件进出（真实 train 脏数据子集）；默认 dedupe=adaptive 与 --plain 对照；audit dry-run 不写文件；
   --apply 写 cleaned + backup；rollback 往返恢复原值；checksum 破坏被拒；退出码 0/1/2；参数校验；
   stdin/stdout 管道；真实子进程冒烟；console script 中文输出回归（不带 PYTHONIOENCODING）
R: src/zhclean/cli.py
A: uv run --project . pytest tests/test_cli.py -q
S: 真实数据只取 benchmarks/dirty/*.jsonl 的 train 行，且只保留 id/field/value（不带 truth）；不碰 heldout
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zhclean import normalize_with_confidence
from zhclean.cli import main
from zhclean.tools.dedupe import dedupe, dedupe_adaptive

ROOT = Path(__file__).resolve().parents[1]
DIRTY = ROOT / "benchmarks" / "dirty"
FIELDS = ("person", "address", "phone", "company")


# ---- 工具 ---------------------------------------------------------------------
def run(argv, stdin_text: str = ""):
    """进程内跑 CLI：返回 (退出码, stdout 文本, stderr 文本)。"""
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdin=io.StringIO(stdin_text), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(p: Path, rows: list[dict]) -> Path:
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def real_rows() -> list[dict]:
    """真实 train 脏数据：每字段前 5 个 id × 5 条 dirty = 100 行，只留 id/field/value。"""
    rows: list[dict] = []
    for f in FIELDS:
        lines = [json.loads(x) for x in (DIRTY / f"{f}.jsonl").read_text(encoding="utf-8").splitlines() if x]
        train = [x for x in lines if x["split"] == "train"]
        keep = list(dict.fromkeys(x["id"] for x in train))[:5]
        rows += [{"id": x["id"], "field": x["field"], "value": x["value"]} for x in train if x["id"] in keep]
    assert len(rows) == 100
    return rows


@pytest.fixture
def real_file(tmp_path, real_rows) -> Path:
    return write_jsonl(tmp_path / "rows.jsonl", real_rows)


# ---- --help / 退出码 / 参数校验 ------------------------------------------------
def test_help_lists_four_subcommands(capsys):
    assert main(["--help"]) == 0
    text = capsys.readouterr().out
    for cmd in ("normalize", "dedupe", "audit", "rollback"):
        assert cmd in text
    assert "退出码" in text


@pytest.mark.parametrize("cmd", ["normalize", "dedupe", "audit", "rollback"])
def test_subcommand_help_exit_0(cmd, capsys):
    assert main([cmd, "--help"]) == 0
    assert "--" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [
    [],                                                   # 缺子命令
    ["clean"],                                            # 未知子命令
    ["dedupe", "--threshold", "85"],                      # 阈值越界（不是 0~100）
    ["dedupe", "--threshold", "abc"],                     # 阈值非数字
    ["dedupe", "--threshold", "nan"],                     # NaN
    ["dedupe", "--adaptive", "--plain"],                  # 互斥
    ["normalize", "--field", "email"],                    # 字段不在四类内
    ["rollback", "--cleaned", "x.jsonl"],                 # 缺 --backup
    ["audit", "--bogus"],                                 # 未知参数
])
def test_usage_errors_exit_2(argv, capsys):
    assert main(argv) == 2
    assert "参数错误" in capsys.readouterr().err


def test_missing_input_file_exit_1(tmp_path):
    code, _, err = run(["normalize", "--input", str(tmp_path / "nope.jsonl")])
    assert code == 1 and "输入文件不存在" in err


@pytest.mark.parametrize("bad, hint", [
    ('{"id":1,"field":"person"', "不是合法 JSON"),
    ('["person","王小明"]', "须是 JSON 对象"),
    ('{"id":1,"field":"person"}', "缺字段：value"),
    ('{"id":1,"value":"王小明"}', "缺字段：field"),
])
def test_bad_jsonl_exit_1_with_line_number(tmp_path, bad, hint):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"id":0,"field":"person","value":"李四"}\n' + bad + "\n", encoding="utf-8")
    for cmd in ("normalize", "dedupe", "audit"):
        code, out, err = run([cmd, "--input", str(p)])
        assert code == 1 and hint in err and "第 2 行" in err and out == ""


# ---- normalize ---------------------------------------------------------------
def test_normalize_end_to_end_file(tmp_path, real_file, real_rows):
    out = tmp_path / "norm.jsonl"
    code, so, _ = run(["normalize", "--input", str(real_file), "--out", str(out)])
    assert code == 0 and "共 100 行" in so
    got = read_jsonl(out)
    assert len(got) == len(real_rows)
    for src, g in zip(real_rows, got):
        norm, conf = normalize_with_confidence(src["value"], src["field"])
        assert g == {**src, "normalized": norm, "confidence": conf}  # 原字段保留 + 两键追加


def test_normalize_stdin_to_stdout_is_pure_jsonl():
    code, out, err = run(["normalize"], '{"id":"1","field":"person","value":"范 童言"}\n\n')
    assert code == 0
    assert [json.loads(x) for x in out.splitlines()] == [
        {"id": "1", "field": "person", "value": "范 童言", "normalized": "范童言", "confidence": 0.9}]
    assert "共 1 行" in err  # 汇总走 stderr，不污染管道


def test_normalize_field_flag_overrides_row_field():
    """--field 指定时不要求行内 field，且以 --field 为准。"""
    code, out, _ = run(["normalize", "--field", "phone"], '{"id":"1","value":"138 1234 5678"}\n')
    assert code == 0 and json.loads(out)["normalized"] == normalize_with_confidence("138 1234 5678", "phone")[0]


def test_empty_input_ok():
    code, out, err = run(["normalize"], "")
    assert code == 0 and out == "" and "共 0 行" in err


# ---- dedupe ------------------------------------------------------------------
def _groups_from_output(rows: list[dict]) -> list[list[int]]:
    by: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        by.setdefault(r["_group"], []).append(i)
    return list(by.values())


def _groups_from_fn(fn, rows):
    pos = {id(r): i for i, r in enumerate(rows)}
    return [[pos[id(r)] for r in g] for g in fn(rows, 0.85)]


def test_dedupe_default_is_adaptive(tmp_path, real_file, real_rows):
    out = tmp_path / "g.jsonl"
    code, so, _ = run(["dedupe", "--input", str(real_file), "--out", str(out)])
    got = read_jsonl(out)
    assert code == 0 and "adaptive" in so
    assert [{k: v for k, v in r.items() if k != "_group"} for r in got] == real_rows  # 行序、原字段不变
    assert _groups_from_output(got) == _groups_from_fn(dedupe_adaptive, real_rows)
    # 组号 = 组首行序：首次出现的组号严格递增
    firsts = list(dict.fromkeys(r["_group"] for r in got))
    assert firsts == list(range(len(firsts)))


def test_dedupe_plain_vs_adaptive(tmp_path, real_file, real_rows):
    """--plain 走 dedupe；在真实脏数据上两者分组确实不同（adaptive 并得更多）。"""
    pa, pp = tmp_path / "a.jsonl", tmp_path / "p.jsonl"
    assert run(["dedupe", "--input", str(real_file), "--out", str(pa)])[0] == 0
    code, so, _ = run(["dedupe", "--input", str(real_file), "--plain", "--out", str(pp)])
    assert code == 0 and "plain" in so
    plain, adap = _groups_from_output(read_jsonl(pp)), _groups_from_output(read_jsonl(pa))
    assert plain == _groups_from_fn(dedupe, real_rows)
    assert len(adap) < len(plain)


def test_dedupe_explicit_adaptive_equals_default(real_file):
    assert run(["dedupe", "--input", str(real_file), "--adaptive"])[1] == run(["dedupe", "--input", str(real_file)])[1]


def test_dedupe_threshold_passed_through():
    rows = '{"id":1,"field":"address","value":"北京市海淀区中关村大街"}\n{"id":2,"field":"address","value":"北京市海淀区中关村大道"}\n'
    g = lambda out: [json.loads(x)["_group"] for x in out.splitlines()]  # noqa: E731
    assert g(run(["dedupe", "--plain", "--threshold", "0.85"], rows)[1]) == [0, 0]
    assert g(run(["dedupe", "--plain", "--threshold", "0.95"], rows)[1]) == [0, 1]


# ---- audit / rollback --------------------------------------------------------
def test_audit_dry_run_writes_nothing(tmp_path, real_file):
    before = sorted(p.name for p in tmp_path.iterdir())
    code, out, _ = run(["audit", "--input", str(real_file)])
    assert code == 0 and "dry-run 预览，未应用" in out and "总行数 100" in out
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_audit_apply_writes_cleaned_and_backup(tmp_path, real_file, real_rows):
    out = tmp_path / "clean.jsonl"
    code, so, _ = run(["audit", "--input", str(real_file), "--apply", "--out", str(out)])
    bak = tmp_path / "clean.backup.json"
    assert code == 0 and out.is_file() and bak.is_file()
    assert "已应用，可回滚" in so and str(bak) in so
    cleaned = read_jsonl(out)
    for src, c in zip(real_rows, cleaned):
        norm = normalize_with_confidence(src["value"], src["field"])[0]
        assert c["value"] == norm
        assert c.get("_before", src["value"]) == src["value"]
    backup = json.loads(bak.read_text(encoding="utf-8"))
    assert backup["rows"] == real_rows and len(backup["checksum"]) == 64


def test_audit_apply_default_out_name(tmp_path, real_file):
    assert run(["audit", "--input", str(real_file), "--apply"])[0] == 0
    assert (tmp_path / "rows.cleaned.jsonl").is_file() and (tmp_path / "rows.cleaned.backup.json").is_file()


def test_audit_apply_stdin_requires_out():
    code, _, err = run(["audit", "--apply"], '{"id":1,"field":"person","value":"王 小明"}\n')
    assert code == 1 and "--out" in err


def test_audit_apply_refuses_overwrite_without_force(tmp_path, real_file):
    out = tmp_path / "clean.jsonl"
    assert run(["audit", "--input", str(real_file), "--apply", "--out", str(out)])[0] == 0
    code, _, err = run(["audit", "--input", str(real_file), "--apply", "--out", str(out)])
    assert code == 1 and "拒绝覆盖" in err
    assert run(["audit", "--input", str(real_file), "--apply", "--out", str(out), "--force"])[0] == 0


def test_rollback_round_trip_restores_original(tmp_path, real_file, real_rows):
    out, restored = tmp_path / "clean.jsonl", tmp_path / "restored.jsonl"
    assert run(["audit", "--input", str(real_file), "--apply", "--out", str(out)])[0] == 0
    assert read_jsonl(out) != real_rows  # 前提：确实改过
    code, so, _ = run(["rollback", "--cleaned", str(out), "--backup", str(tmp_path / "clean.backup.json"),
                       "--out", str(restored)])
    assert code == 0 and "已恢复 100 行" in so
    assert read_jsonl(restored) == real_rows


def test_rollback_to_stdout(tmp_path, real_file, real_rows):
    out = tmp_path / "clean.jsonl"
    run(["audit", "--input", str(real_file), "--apply", "--out", str(out)])
    code, so, err = run(["rollback", "--cleaned", str(out), "--backup", str(tmp_path / "clean.backup.json")])
    assert code == 0 and [json.loads(x) for x in so.splitlines()] == real_rows and "checksum" in err


@pytest.mark.parametrize("tamper", ["cleaned", "backup_rows", "checksum"])
def test_rollback_rejects_tampering(tmp_path, real_file, tamper):
    out, bak = tmp_path / "clean.jsonl", tmp_path / "clean.backup.json"
    assert run(["audit", "--input", str(real_file), "--apply", "--out", str(out)])[0] == 0
    if tamper == "cleaned":
        rows = read_jsonl(out)
        rows[0]["value"] += "X"
        write_jsonl(out, rows)
    else:
        b = json.loads(bak.read_text(encoding="utf-8"))
        if tamper == "backup_rows":
            b["rows"][0]["value"] = "篡改"
        else:
            b["checksum"] = "0" * 64
        bak.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
    restored = tmp_path / "r.jsonl"
    code, _, err = run(["rollback", "--cleaned", str(out), "--backup", str(bak), "--out", str(restored)])
    assert code == 1 and "checksum 不匹配" in err and not restored.exists()


@pytest.mark.parametrize("content, hint", [("{not json", "不是合法 JSON"), ('{"rows": []}', "结构不对")])
def test_rollback_bad_backup_exit_1(tmp_path, content, hint):
    c = write_jsonl(tmp_path / "c.jsonl", [{"id": 1, "field": "person", "value": "王小明"}])
    b = tmp_path / "b.json"
    b.write_text(content, encoding="utf-8")
    code, _, err = run(["rollback", "--cleaned", str(c), "--backup", str(b)])
    assert code == 1 and hint in err


# ---- 真实子进程冒烟（stdin 管道 + utf-8 输出 + 退出码） ---------------------------
def test_subprocess_pipe_smoke():
    p = subprocess.run([sys.executable, "-m", "zhclean.cli", "normalize"],
                       input='{"id":"1","field":"person","value":"范 童言"}\n'.encode("utf-8"),
                       capture_output=True, cwd=ROOT)
    assert p.returncode == 0
    assert json.loads(p.stdout.decode("utf-8"))["normalized"] == "范童言"


def test_subprocess_usage_error_exit_2():
    p = subprocess.run([sys.executable, "-m", "zhclean.cli", "dedupe", "--threshold", "85"],
                       capture_output=True, cwd=ROOT)
    assert p.returncode == 2 and "参数错误" in p.stderr.decode("utf-8")


# ---- 乱码回归：console script 入口（TASK-014 §2.5-①） --------------------------
def _entry_cmd() -> list[str]:
    """真实 console script 命令（它直接调 main()，不走 `__main__`）。

    pyproject 里 `zhclean = "zhclean.cli:main"`，装出来的正是这个脚本；
    脚本不在（没装成脚本）时退回等价的 `-c` 调用，一样绕开 `__main__`。
    """
    script = Path(sys.executable).with_name("zhclean.exe" if os.name == "nt" else "zhclean")
    if script.exists():
        return [str(script)]
    return [sys.executable, "-c", "import zhclean.cli as c; raise SystemExit(c.main())"]


def _no_encoding_env() -> dict[str, str]:
    """模拟真实用户环境：不带 PYTHONIOENCODING / PYTHONUTF8（否则测试等于没测）。"""
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}


def test_entry_point_chinese_help_is_utf8():
    """修复前：console script 走 cp936，中文是乱码字节；修复后必须是 utf-8。"""
    p = subprocess.run([*_entry_cmd(), "--help"], capture_output=True, cwd=ROOT, env=_no_encoding_env())
    assert p.returncode == 0
    text = p.stdout.decode("utf-8", errors="replace")  # cp936 字节到这里就解不出来
    assert "中文脏数据净化器" in text and "子命令" in text


def test_entry_point_normalize_pipe_is_utf8_jsonl():
    """console script 经 stdin 管道跑 normalize：stdout 是纯 jsonl，中文正常。"""
    p = subprocess.run([*_entry_cmd(), "normalize"],
                       input='{"id":"1","field":"person","value":"范 童言"}\n'.encode("utf-8"),
                       capture_output=True, cwd=ROOT, env=_no_encoding_env())
    assert p.returncode == 0
    assert json.loads(p.stdout.decode("utf-8", errors="replace"))["normalized"] == "范童言"

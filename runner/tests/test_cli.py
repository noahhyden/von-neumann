import sys
from pathlib import Path

import pytest

from vn_runner import cli, load, progress, run
from vn_runner.spec import RunSpec

SPEC = RunSpec(name="fake", module="mod", entry="m:f", description="first line\nsecond", params={})


def test_ls(monkeypatch, capsys):
    monkeypatch.setattr(load, "discover", lambda r: [(Path("x.yaml"), SPEC)])
    assert cli.main(["ls"]) == 0
    assert capsys.readouterr().out.strip() == "fake\tmod\tm:f\tfirst line"


def test_ps(monkeypatch, capsys):
    monkeypatch.setattr(progress, "read_all", lambda r: ["rows"])
    monkeypatch.setattr(progress, "format_table", lambda rows: f"T{rows}")
    assert cli.main(["ps"]) == 0
    assert "T['rows']" in capsys.readouterr().out


@pytest.mark.parametrize("problems,code", [([], 0), (["bad spec"], 1)])
def test_validate(monkeypatch, capsys, problems, code):
    monkeypatch.setattr(load, "validate_tree", lambda r: problems)
    assert cli.main(["validate"]) == code
    assert ("bad spec" in capsys.readouterr().out) == bool(problems)


def test_run_bad_file_exit_2(monkeypatch, capsys):
    def bad(p):
        raise ValueError("x.yaml: nope")
    monkeypatch.setattr(load, "load_spec", bad)
    assert cli.main(["x.yaml"]) == 2
    assert "x.yaml" in capsys.readouterr().err


def test_run_reexecs_with_dash_O(monkeypatch):
    monkeypatch.setattr(load, "load_spec", lambda p: SPEC)
    monkeypatch.setattr(run, "needs_reexec", lambda s: True)
    calls = []

    def fake_execv(exe, args):
        calls.append(args)
        raise SystemExit(0)
    monkeypatch.setattr(cli.os, "execv", fake_execv)
    with pytest.raises(SystemExit):
        cli.main(["x.yaml"])
    assert calls[0][:4] == [sys.executable, "-O", "-m", "vn_runner.cli"]


def test_no_reexec_loop_when_optimized(monkeypatch):
    class F:
        optimize = 1
    monkeypatch.setattr(run.sys, "flags", F)
    monkeypatch.setattr(load, "load_spec", lambda p: SPEC)
    monkeypatch.setattr(cli.os, "execv", lambda *a: pytest.fail("re-exec loop"))
    monkeypatch.setattr(progress, "FileProgress", lambda s, r: object())
    monkeypatch.setattr(run, "execute", lambda s, r, p: 7)
    assert cli.main(["x.yaml"]) == 7


def test_run_returns_execute_code(monkeypatch):
    spec = SPEC.model_copy(update={"runtime": SPEC.runtime.model_copy(update={"optimize": False})})
    monkeypatch.setattr(load, "load_spec", lambda p: spec)
    monkeypatch.setattr(progress, "FileProgress", lambda s, r: object())
    monkeypatch.setattr(run, "execute", lambda s, r, p: 3)
    assert cli.main(["x.yaml"]) == 3

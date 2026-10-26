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


@pytest.mark.parametrize("rc", [0, 3])
def test_run_returns_execute_code(monkeypatch, rc):
    monkeypatch.setattr(load, "load_spec", lambda p: SPEC)
    monkeypatch.setattr(run, "execute", lambda s, r, p: rc)
    assert cli.main(["x.yaml"]) == rc


def test_no_reexec_path_remains():
    assert not hasattr(run, "needs_reexec") and not hasattr(cli, "os")

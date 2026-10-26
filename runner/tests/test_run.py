from types import SimpleNamespace

import pytest

from vn_runner import load, run
from vn_runner.spec import Backends, RunSpec, Runtime


def mk(**rt):
    return RunSpec(name="fake", module="mod", entry="fakemod:go", description="d",
                   runtime=Runtime(**rt), params={"n": 3})


@pytest.fixture
def calls(monkeypatch, tmp_path):
    class L(list):
        pass
    out = L()

    def fake_run(argv, cwd, env):
        out.append(SimpleNamespace(argv=argv, cwd=cwd, env=env))
        return SimpleNamespace(returncode=fake_run.rc)
    fake_run.rc = 0
    monkeypatch.setattr(run.subprocess, "run", fake_run)
    monkeypatch.setattr(load, "assert_clean_env", lambda: None)
    for k in ("SWARM_WORKERS", "SWARM_NO_RUST", "SWARM_NO_NJIT"):
        monkeypatch.delenv(k, raising=False)
    out.fake = fake_run
    return out


def test_optimize_flag_present_and_absent(calls, tmp_path):
    run.execute(mk(optimize=True), tmp_path, None)
    run.execute(mk(optimize=False), tmp_path, None)
    on, off = (c.argv for c in calls)
    assert on[:5] == ["uv", "run", "--extra", "dev", "python"] and on[5] == "-O"
    assert "-O" not in off and off[5] == "-c"


def test_cwd_is_module_dir_and_spec_json_passed(calls, tmp_path):
    run.execute(mk(), tmp_path, None)
    c = calls[0]
    assert c.cwd == tmp_path / "mod"
    assert c.argv[-2] == str(tmp_path)
    assert RunSpec.model_validate_json(c.argv[-1]) == mk()


def test_default_backends_set_no_switches(calls, tmp_path):
    run.execute(mk(), tmp_path, None)
    env = calls[0].env
    assert not any(k in env for k in ("SWARM_NO_RUST", "SWARM_NO_RUST_FILL",
                                      "SWARM_NO_RUST_FLAT", "SWARM_NO_NJIT", "SWARM_WORKERS"))


def test_rust_off_sets_all_three_and_njit_stays_on(calls, tmp_path):
    run.execute(mk(backends=Backends(rust=False)), tmp_path, None)
    env = calls[0].env
    assert env["SWARM_NO_RUST"] == env["SWARM_NO_RUST_FILL"] == env["SWARM_NO_RUST_FLAT"] == "1"
    assert "SWARM_NO_NJIT" not in env


def test_njit_off_and_workers(calls, tmp_path):
    run.execute(mk(backends=Backends(njit=False), workers=2), tmp_path, None)
    env = calls[0].env
    assert env["SWARM_NO_NJIT"] == "1" and env["SWARM_WORKERS"] == "2"
    assert "SWARM_NO_RUST" not in env


@pytest.mark.parametrize("rc", [0, 1, 7])
def test_returncode_propagates(calls, tmp_path, rc):
    calls.fake.rc = rc
    assert run.execute(mk(), tmp_path, None) == rc


def test_launch_failure_names_spec(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise FileNotFoundError("uv")
    monkeypatch.setattr(run.subprocess, "run", boom)
    monkeypatch.setattr(load, "assert_clean_env", lambda: None)
    assert run.execute(mk(), tmp_path, None) == 1
    assert "'fake'" in capsys.readouterr().err


def test_dirty_env_refuses_before_spawning(calls, monkeypatch, tmp_path):
    def bad():
        raise RuntimeError("SWARM_WORKERS set")
    monkeypatch.setattr(load, "assert_clean_env", bad)
    with pytest.raises(RuntimeError):
        run.execute(mk(), tmp_path, None)
    assert calls == []

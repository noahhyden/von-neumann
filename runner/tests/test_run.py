import os
import sys
import textwrap

import pytest

from vn_runner import load, run
from vn_runner.spec import Backends, RunSpec, Runtime


class Rec:
    def __init__(self):
        self.updates, self.finished = [], None

    def update(self, *, step, total=None, label=""):
        self.updates.append((step, label))

    def finish(self, state, error=None):
        self.finished = (state, error)


def mk(entry="fakemod:go", **rt):
    return RunSpec(name="fake", module="mod", entry=entry, description="d",
                   runtime=Runtime(**rt), params={"n": 3})


@pytest.fixture
def root(tmp_path, monkeypatch):
    d = tmp_path / "mod"
    d.mkdir()
    (d / "fakemod.py").write_text(textwrap.dedent("""
        import os
        SEEN = {k: os.environ.get(k) for k in
                ("SWARM_NO_RUST", "SWARM_NO_RUST_FILL", "SWARM_NO_RUST_FLAT",
                 "SWARM_NO_NJIT", "SWARM_WORKERS")}
        def go(n, progress=None):
            SEEN["n"] = n
            SEEN["cwd"] = os.getcwd()
            SEEN["progress"] = progress
        def plain(n):
            SEEN["n"] = n
        def boom(n):
            raise RuntimeError("kaboom")
    """))
    monkeypatch.setattr(load, "assert_clean_env", lambda: None)
    yield tmp_path
    sys.modules.pop("fakemod", None)


def seen():
    return sys.modules["fakemod"].SEEN


def test_needs_reexec_both_ways(monkeypatch):
    class F:
        optimize = 0
    monkeypatch.setattr(run.sys, "flags", F)
    assert run.needs_reexec(mk(optimize=True)) is True
    assert run.needs_reexec(mk(optimize=False)) is False
    F.optimize = 1  # already optimized: must not ask for another exec
    assert run.needs_reexec(mk(optimize=True)) is False


def test_workers_reach_env_and_defaults_set_nothing_else(root):
    p = Rec()
    assert run.execute(mk(workers=2), root, p) == 0
    s = seen()
    assert s["SWARM_WORKERS"] == "2"
    assert s["SWARM_NO_RUST"] is None and s["SWARM_NO_NJIT"] is None
    assert s["n"] == 3 and s["cwd"] == str(root / "mod")
    assert s["progress"] is p and p.finished == ("done", None) and p.updates
    assert "SWARM_WORKERS" not in os.environ  # env restored


def test_backends_off_sets_switches(root):
    run.execute(mk(backends=Backends(rust=False, njit=False)), root, Rec())
    s = seen()
    assert s["SWARM_NO_RUST"] == s["SWARM_NO_RUST_FILL"] == s["SWARM_NO_RUST_FLAT"] == "1"
    assert s["SWARM_NO_NJIT"] == "1" and s["SWARM_WORKERS"] is None


def test_no_progress_kwarg_when_not_accepted(root):
    assert run.execute(mk(entry="fakemod:plain"), root, Rec()) == 0
    assert seen()["n"] == 3


def test_bad_entry_names_spec(root, capsys):
    p = Rec()
    assert run.execute(mk(entry="nosuchmod:go"), root, p) != 0
    assert "'fake'" in capsys.readouterr().err and p.finished[0] == "failed"
    assert run.execute(mk(entry="fakemod:nope"), root, Rec()) != 0


def test_failing_entry_nonzero_and_named(root, capsys):
    p = Rec()
    assert run.execute(mk(entry="fakemod:boom"), root, p) == 1
    err = capsys.readouterr().err
    assert "'fake'" in err and "kaboom" in err
    assert p.finished == ("failed", "RuntimeError: kaboom")


def test_dirty_env_refuses(root, monkeypatch):
    def bad():
        raise RuntimeError("SWARM_WORKERS set")
    monkeypatch.setattr(load, "assert_clean_env", bad)
    with pytest.raises(RuntimeError):
        run.execute(mk(), root, Rec())

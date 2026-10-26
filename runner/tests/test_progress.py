import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from vn_runner import progress
from vn_runner.progress import FileProgress, format_table, read_all, status_dir
from vn_runner.spec import RunSpec, RunStatus


def _spec(name: str = "demo") -> RunSpec:
    return RunSpec(name=name, module="m", entry="a.b:c", description="d")


def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _write(root: Path, name: str, pid: int, state: str = "running", started: str = "2026-01-01T00:00:00+00:00") -> None:
    s = RunStatus(name=name, pid=pid, started_at=started, updated_at=started, state=state)  # type: ignore[arg-type]
    (status_dir(root) / f"{name}.json").write_text(s.model_dump_json())


def test_lifecycle(tmp_path):
    fp = FileProgress(_spec(), tmp_path)
    [s] = read_all(tmp_path)
    assert (s.state, s.pid, s.step, s.total) == ("running", os.getpid(), 0, None)
    fp.update(step=5, total=10, label="fill")
    [s] = read_all(tmp_path)
    assert (s.step, s.total, s.label) == (0, None, "")  # inside 1s of init, so throttled
    fp.finish("done")
    [s] = read_all(tmp_path)
    assert (s.state, s.step, s.total, s.label, s.error) == ("done", 5, 10, "fill", None)


def test_failed_carries_error(tmp_path):
    fp = FileProgress(_spec(), tmp_path)
    fp.finish("failed", "boom")
    [s] = read_all(tmp_path)
    assert (s.state, s.error) == ("failed", "boom")


def test_throttle_burst(tmp_path, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(progress.time, "monotonic", lambda: clock[0])
    fp = FileProgress(_spec(), tmp_path)
    clock[0] += 1.0
    fp.update(step=1)  # first update after the window lands
    for i in range(2, 50):
        clock[0] += 0.01
        fp.update(step=i)
    assert read_all(tmp_path)[0].step == 1  # burst suppressed
    clock[0] += 1.0
    fp.update(step=99)
    assert read_all(tmp_path)[0].step == 99
    fp.update(step=100)
    fp.finish("done")  # state change writes through with the latest step
    s = read_all(tmp_path)[0]
    assert (s.state, s.step) == ("done", 100)


def test_dead_pid_reads_failed_live_stays_running(tmp_path):
    _write(tmp_path, "dead", _dead_pid())
    _write(tmp_path, "live", os.getpid())
    rows = {s.name: s for s in read_all(tmp_path)}
    assert rows["dead"].state == "failed" and rows["dead"].error
    assert rows["live"].state == "running"
    on_disk = json.loads((status_dir(tmp_path) / "dead.json").read_text())
    assert on_disk["state"] == "running"  # a read never mutates the file


def test_dead_pid_done_stays_done(tmp_path):
    _write(tmp_path, "fin", _dead_pid(), state="done")
    assert read_all(tmp_path)[0].state == "done"


def test_newest_first(tmp_path):
    _write(tmp_path, "old", os.getpid(), started="2026-01-01T00:00:00+00:00")
    _write(tmp_path, "new", os.getpid(), started="2026-02-01T00:00:00+00:00")
    assert [s.name for s in read_all(tmp_path)] == ["new", "old"]


def test_atomic_no_temp_left_and_always_parses(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(progress.time, "monotonic", lambda: clock[0])
    fp = FileProgress(_spec(), tmp_path)
    path = status_dir(tmp_path) / "demo.json"
    for i in range(30):
        clock[0] += 2.0
        fp.update(step=i, total=30, label="x" * 1000)
        assert json.loads(path.read_text())["step"] == i
        assert [p.name for p in status_dir(tmp_path).iterdir()] == ["demo.json"]
    fp.finish("done")
    assert [p.name for p in status_dir(tmp_path).iterdir()] == ["demo.json"]


def test_garbage_file_skipped(tmp_path):
    (status_dir(tmp_path) / "junk.json").write_text("{half")
    _write(tmp_path, "ok", os.getpid())
    assert [s.name for s in read_all(tmp_path)] == ["ok"]


def test_timestamps_iso8601(tmp_path):
    FileProgress(_spec(), tmp_path)
    s = read_all(tmp_path)[0]
    for t in (s.started_at, s.updated_at):
        assert datetime.fromisoformat(t).utcoffset().total_seconds() == 0


def test_table_empty():
    assert format_table([]) == "no runs"


def test_table_mixed(tmp_path):
    _write(tmp_path, "alive", os.getpid(), started="2026-03-01T00:00:00+00:00")
    _write(tmp_path, "dead", _dead_pid(), started="2026-02-01T00:00:00+00:00")
    _write(tmp_path, "fin", os.getpid(), state="done", started="2026-01-01T00:00:00+00:00")
    rows = read_all(tmp_path)
    rows[0] = rows[0].model_copy(update={"step": 3, "total": 12, "label": "fill"})
    rows[1] = rows[1].model_copy(update={"step": 7})
    out = format_table(rows)
    lines = out.splitlines()
    assert lines[0].split() == ["NAME", "STATE", "PROGRESS", "ELAPSED", "LABEL"]
    assert len(lines) == 4
    assert lines[1].split()[:3] == ["alive", "running", "3/12"]
    assert lines[2].split()[:3] == ["dead", "failed", "7"]
    assert lines[3].split()[:2] == ["fin", "done"]
    assert "process died" in out
    assert out.isascii()

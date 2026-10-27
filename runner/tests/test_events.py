"""The append-only event log: shape, append-only-ness, and the classification contract."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from vn_runner.events import Emitter, events_path, read_events
from vn_runner.spec import RunSpec


def _spec(**kw) -> RunSpec:
    base = dict(name="demo", module="spine", entry="experiments.measure:run_measurement", description="d")
    base.update(kw)
    return RunSpec(**base)


def test_every_line_carries_ts_severity_and_payload_type(tmp_path: Path):
    e = Emitter(_spec(), tmp_path)
    e.emit("convergence_failure", check="newton", iterations=50)
    (ev,) = read_events("demo", tmp_path)
    assert set(ev) == {"ts", "severity", "payload"}
    assert ev["severity"] == "info"
    assert ev["payload"]["type"] == "convergence_failure"
    assert ev["payload"]["check"] == "newton"
    assert ev["payload"]["iterations"] == 50


def test_timestamps_are_iso8601_utc(tmp_path: Path):
    Emitter(_spec(), tmp_path).emit("run_start")
    ts = read_events("demo", tmp_path)[0]["ts"]
    assert ts.endswith("Z")
    assert datetime.fromisoformat(ts.replace("Z", "+00:00")).tzinfo is not None


def test_log_is_append_only_and_never_rewritten(tmp_path: Path):
    e = Emitter(_spec(), tmp_path)
    for i in range(5):
        e.emit("step_done", index=i)
    evs = read_events("demo", tmp_path)
    assert [x["payload"]["index"] for x in evs] == [0, 1, 2, 3, 4], "earlier events must survive later ones"
    # A second Emitter over the same run appends rather than truncating, which is what makes forked workers safe.
    Emitter(_spec(), tmp_path).emit("step_done", index=5)
    assert len(read_events("demo", tmp_path)) == 6


def test_type_must_be_a_stable_slug(tmp_path: Path):
    e = Emitter(_spec(), tmp_path)
    for bad in ["Invariant Violation", "step-42", "", "a.b"]:
        with pytest.raises(ValueError):
            e.emit(bad)


def test_digit_runs_in_type_would_collapse_so_detail_belongs_in_siblings(tmp_path: Path):
    """The consumer normalises digit runs; two steps must share one signature, not fork into two."""
    e = Emitter(_spec(), tmp_path)
    e.emit("invariant_violation", check="mass_closure", value=1.03)
    e.emit("invariant_violation", check="mass_closure", value=42.0)
    sigs = {(x["severity"], re.sub(r"\d+", "N", x["payload"]["type"])) for x in read_events("demo", tmp_path)}
    assert len(sigs) == 1, "varying values must not change the classification signature"


def test_run_start_records_whether_invariants_could_fire(tmp_path: Path):
    Emitter(_spec(runtime={"optimize": True}), tmp_path).run_start()
    opt = read_events("demo", tmp_path)[0]["payload"]
    assert opt["optimize"] is True
    assert opt["invariants_active"] is False, "-O compiles out the fold's __debug__ checks"

    Emitter(_spec(name="other", runtime={"optimize": False}), tmp_path).run_start()
    noopt = read_events("other", tmp_path)[0]["payload"]
    assert noopt["invariants_active"] is True


def test_run_start_records_the_config_that_shaped_the_run(tmp_path: Path):
    spec = _spec(runtime={"workers": 2, "optimize": True, "backends": {"rust": False, "njit": True}})
    Emitter(spec, tmp_path).run_start()
    p = read_events("demo", tmp_path)[0]["payload"]
    assert p["workers"] == 2
    assert p["backends"] == {"rust": False, "njit": True}
    assert p["module"] == "spine"


def test_failure_is_error_severity_and_names_the_exception(tmp_path: Path):
    e = Emitter(_spec(), tmp_path)
    e.run_failed(ValueError("mass did not close"), 1.5)
    ev = read_events("demo", tmp_path)[0]
    assert ev["severity"] == "error"
    assert ev["payload"]["type"] == "run_failed"
    assert ev["payload"]["error_type"] == "ValueError"
    assert "mass did not close" in ev["payload"]["message"]
    assert ev["payload"]["duration_s"] == 1.5


def test_end_carries_duration(tmp_path: Path):
    Emitter(_spec(), tmp_path).run_end(41.6789)
    p = read_events("demo", tmp_path)[0]["payload"]
    assert p["state"] == "done" and p["duration_s"] == 41.679


def test_a_half_written_line_does_not_poison_the_rest(tmp_path: Path):
    e = Emitter(_spec(), tmp_path)
    e.emit("run_start")
    with open(events_path("demo", tmp_path), "a", encoding="utf-8") as fh:
        fh.write('{"ts": "2026-01-01T00:00:00.0')
    e.emit("run_end")
    assert [x["payload"]["type"] for x in read_events("demo", tmp_path)] == ["run_start", "run_end"]


def test_missing_log_reads_as_empty(tmp_path: Path):
    assert read_events("never-ran", tmp_path) == []


def test_lines_stay_under_pipe_buf_so_appends_are_atomic(tmp_path: Path):
    """The documented ceiling: a line over PIPE_BUF could interleave across worker processes."""
    e = Emitter(_spec(), tmp_path)
    e.run_start()
    e.run_failed(ValueError("x" * 5000), 1.0)
    for raw in events_path("demo", tmp_path).read_text().splitlines():
        json.loads(raw)
        assert len(raw.encode()) < 4096, "message truncation must keep a line inside PIPE_BUF"

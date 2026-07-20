"""Issue #73: the W_inst/N paired-free plateau locator.

The ``retarget_cap`` sweep finds ``cap*(N)`` - the smallest ``max_retargets`` cap beyond which
the fuel tax stops moving - by running the full PAIRED (instant + lightspeed) sweep at a cap
ladder. The shortcut is that the plateau LOCATION is fully determined by the instant baseline's
bounce depth ``b = W_inst / N`` alone: across the ladder, ``b`` and the paired tax ``tau`` move
together, so ``Delta b -> 0`` locates the same plateau as ``Delta tau -> 0`` (see
``experiments/SPEC_PLATEAU_LOCATOR.md``).

Layers, per CLAUDE.md sec 2:
  * pure decision function ``locate_plateau`` on synthetic ladders (edges included),
  * the ``Delta b`` <-> ``Delta tau`` correspondence pinned against the committed JSONs (issue
    #73's stated verification path), plus the per-seed anticorrelation that mechanises it,
  * ``cap*`` reproduced from the committed ``b`` medians (N=400 -> 16; N >= 32768 -> None), and
  * an end-to-end fold check: the instant-only sweep reproduces the committed instant records.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import pytest

from swarm import SwarmParams, simulate_swarm
from experiments.measure import (
    SEEDS,
    _extract_opt,
    _print_plateau_report,
    _run_locate_plateau,
    bounce_depth,
    locate_plateau,
    locate_plateau_report,
    median_bounce_depth,
    record,
)

RESULTS = Path(__file__).resolve().parents[1] / "experiments" / "results"


# --------------------------------------------------------------------------------------------
# pure decision function
# --------------------------------------------------------------------------------------------

class TestLocatePlateau:
    def test_plateau_at_second_pair(self) -> None:
        # b climbs then flattens: (8,16) still moves by 0.12, (16,32) is flat -> cap* = 16.
        b = {8: 4.25, 16: 4.37, 32: 4.37}
        assert locate_plateau(b, threshold=0.05) == 16

    def test_plateau_at_first_pair(self) -> None:
        # Already flat from the first doubling -> the smallest cap wins.
        b = {8: 4.37, 16: 4.38, 32: 5.90}
        assert locate_plateau(b, threshold=0.05) == 8

    def test_no_plateau_returns_none(self) -> None:
        # Every doubling still moves b by >> threshold (the #86 large-N regime) -> None.
        b = {8: 8.93, 16: 14.29, 32: 18.32}
        assert locate_plateau(b, threshold=0.05) is None

    def test_only_uses_doubling_pairs(self) -> None:
        # 12 has no partner (24 absent) and is not the double of 8; the (8,16) pair does not
        # converge, so despite 12->16 being tiny, there is no converged doubling pair -> None.
        b = {8: 4.0, 12: 4.5, 16: 4.55}
        assert locate_plateau(b, threshold=0.05) is None

    def test_smallest_converged_doubling_pair_wins(self) -> None:
        # Both (8,16) and (16,32) converge; the locator returns the SMALLEST cap.
        b = {8: 4.30, 16: 4.31, 32: 4.32}
        assert locate_plateau(b, threshold=0.05) == 8

    def test_threshold_is_strict(self) -> None:
        # Delta b exactly equal to the threshold is NOT converged (strict <). Use exactly
        # representable halves so the boundary is not blurred by float rounding.
        b = {8: 1.0, 16: 1.5}  # delta_b == 0.5 exactly
        assert locate_plateau(b, threshold=0.5) is None
        assert locate_plateau(b, threshold=0.5000001) == 8

    def test_negative_step_counts_as_converged(self) -> None:
        # A noise-driven dip (b goes down) is below threshold, so it is converged.
        b = {8: 4.40, 16: 4.30}
        assert locate_plateau(b, threshold=0.05) == 8

    def test_threshold_scales_the_call(self) -> None:
        # A threshold between the two steps declares the ladder plateaued at its flattest
        # doubling only: (16,32)=4.03 < 5 < (8,16)=5.36, so cap* = 16 (not the smaller 8).
        b = {8: 8.93, 16: 14.29, 32: 18.32}
        assert locate_plateau(b, threshold=5.0) == 16

    def test_returns_smallest_regardless_of_insertion_order(self) -> None:
        # Both (8,16) and (16,32) converge; even with keys inserted out of order the SMALLEST
        # converged cap (8) must win - pins the ascending-order scan.
        b = {16: 4.31, 32: 4.32, 8: 4.30}
        assert locate_plateau(b, threshold=0.05) == 8

    def test_degenerate_inputs(self) -> None:
        assert locate_plateau({}, threshold=0.05) is None
        assert locate_plateau({8: 4.0}, threshold=0.05) is None  # no doubling partner
        assert locate_plateau({8: 4.0, 32: 5.0}, threshold=0.05) is None  # 16 missing -> no pair


class TestBounceDepth:
    def test_ratio(self) -> None:
        assert bounce_depth(1612, 400) == pytest.approx(4.03)

    def test_rejects_nonpositive_n(self) -> None:
        for bad in (0, -1):
            with pytest.raises(ValueError):
                bounce_depth(10, bad)

    def test_median_over_records(self) -> None:
        recs = [
            {"wasted_arrivals": 800, "n_stars": 400},
            {"wasted_arrivals": 1200, "n_stars": 400},
            {"wasted_arrivals": 1600, "n_stars": 400},
        ]
        assert median_bounce_depth(recs) == pytest.approx(3.0)  # median of 2,3,4


# --------------------------------------------------------------------------------------------
# committed-data verification (issue #73 verification path)
# --------------------------------------------------------------------------------------------

def _load(name: str) -> dict:
    path = RESULTS / f"{name}.json"
    if not path.exists():
        pytest.skip(f"{name}.json not present (run experiments.measure)")
    return json.loads(path.read_text())


def _blocks() -> list[tuple[str, dict]]:
    """Every committed retarget-cap block: top-level + p2, across both files. Skips if absent."""
    out: list[tuple[str, dict]] = []
    for fname in ("retarget_cap", "retarget_cap_scale"):
        doc = _load(fname)
        out.append((f"{fname}:top", doc))
        if "p2" in doc:
            out.append((f"{fname}:p2", doc["p2"]))
    return out


def _b_median_by_cap(block: dict) -> dict[int, float]:
    caps = block["config"]["caps"]
    return {
        cap: median_bounce_depth([ps["base"] for ps in block["data"][str(cap)]["per_seed"]])
        for cap in caps
    }


def _tau_median_by_cap(block: dict) -> dict[int, float]:
    caps = block["config"]["caps"]
    return {cap: block["data"][str(cap)]["fuel_pct"]["median"] for cap in caps}


# Seed-noise floor for the co-monotone check. In the near-zero-tax regime at large N (e.g. cap
# 2 vs 4 at N=262,144, where tau ~ 0.27%) sub-hundredth-of-a-point jitter can flip the sign of a
# step that is physically flat - the 32-seed retarget_cap p2 shows tau dipping 0.0002pp there.
# A real opposite move is >> this: the true climbing steps are +1..+6pp in tau and +2..+6
# arrivals-per-star in b, so a 0.05 floor stays far below any genuine reversal while tolerating
# the jitter. Same units as the quantities: percentage points for tau, arrivals-per-star for b.
_CO_MONOTONE_NOISE = 0.05


def test_delta_b_and_delta_tau_are_co_monotone() -> None:
    """The shortcut's load-bearing claim: across the cap ladder, b and tau never move in
    opposite directions (up to seed noise). Both climb and plateau together (issue #73's table)."""
    for label, block in _blocks():
        caps = sorted(block["config"]["caps"])
        b = _b_median_by_cap(block)
        tau = _tau_median_by_cap(block)
        for k_lo, k_hi in zip(caps, caps[1:]):
            db = b[k_hi] - b[k_lo]
            dt = tau[k_hi] - tau[k_lo]
            # Neither may fall (while the other rises) by more than the seed-noise floor.
            assert db >= -_CO_MONOTONE_NOISE, f"{label}: b fell {k_lo}->{k_hi} (db={db})"
            assert dt >= -_CO_MONOTONE_NOISE, f"{label}: tau fell {k_lo}->{k_hi} (dt={dt})"


def test_plateau_pair_has_small_tau_step() -> None:
    """Where Delta b converges (< default threshold), Delta tau is near zero too - the plateau in
    b IS the plateau in tau. Asserted only for blocks that actually contain a converged pair."""
    checked = 0
    for label, block in _blocks():
        caps = sorted(block["config"]["caps"])
        b = _b_median_by_cap(block)
        tau = _tau_median_by_cap(block)
        cap_star = locate_plateau(b, threshold=0.05)
        if cap_star is None:
            continue
        checked += 1
        k_hi = 2 * cap_star
        assert (tau[k_hi] - tau[cap_star]) < 0.5, (
            f"{label}: b plateaued at cap {cap_star} but tau still moved "
            f"{tau[k_hi] - tau[cap_star]:.3f} pp"
        )
    assert checked >= 1, "expected at least one block (N=400) with a located plateau"


def test_cap_star_reproduced_from_committed_medians() -> None:
    """Feed the committed b medians into locate_plateau: N=400 -> 16, N >= 32768 -> None."""
    by_n: dict[int, int | None] = {}
    for _, block in _blocks():
        n = block["config"]["n_stars"]
        by_n[n] = locate_plateau(_b_median_by_cap(block), threshold=0.05)
    assert by_n.get(400) == 16
    for n, cap_star in by_n.items():
        if n >= 32768:
            assert cap_star is None, f"N={n}: expected no plateau in {{2..32}}, got {cap_star}"


def test_per_seed_anticorrelation_holds() -> None:
    """The mechanism the issue cites: within each (N, cap), a seed with a deeper instant bounce
    stack pays a SMALLER tax - per-seed r(b, tau) < 0 at every block and cap, strongly so in
    the median (issue #73 quotes -0.51 .. -0.97)."""
    for label, block in _blocks():
        caps = block["config"]["caps"]
        per_cap_r: list[float] = []
        for cap in caps:
            rows = block["data"][str(cap)]["per_seed"]
            pts = []
            for ps in rows:
                base = ps["base"]["wasted_arrivals"]
                treat = ps["treat"]["wasted_arrivals"]
                if base:
                    pts.append((base / ps["base"]["n_stars"], (treat - base) / base * 100.0))
            r = _pearson([x for x, _ in pts], [y for _, y in pts])
            assert r < 0.0, f"{label} cap={cap}: expected negative r(b,tau), got {r:+.3f}"
            per_cap_r.append(r)
        assert statistics.median(per_cap_r) < -0.5, f"{label}: weak median anticorrelation"


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (sx * sy)


# --------------------------------------------------------------------------------------------
# end-to-end fold: the instant-only sweep is bit-identical to the committed instant records
# --------------------------------------------------------------------------------------------

def test_instant_sweep_reproduces_committed_records() -> None:
    """The paired-free path only ever runs the instant baseline; those runs must reproduce the
    committed ``base`` records star-for-star (same discipline as test_measure_results.py). Two
    seeds, two caps at N=400 - cheap, and it exercises cap-sensitivity of the instant fold."""
    d = _load("retarget_cap")
    cfg = d["config"]
    for cap in (8, 16):
        block = d["data"][str(cap)]
        for i in range(2):
            r = record(simulate_swarm(
                SwarmParams(n_stars=cfg["n_stars"], policy="powered", probe_speed_c=0.2,
                            speed_cap_c=0.4, stepping="event", max_retargets=cap,
                            coordination="instant"),
                seed=SEEDS[i], record_steps=False))
            want = block["per_seed"][i]["base"]
            assert r["wasted_arrivals"] == want["wasted_arrivals"], f"cap={cap} seed{i}"
            assert r["n_stars"] == want["n_stars"]


def test_locate_plateau_report_end_to_end() -> None:
    """Whole flow at a small N: the report carries the ladder, deltas and a verdict, and the
    ladder's b medians match a direct instant fold (no reliance on committed JSON)."""
    n_stars = 400
    caps = [8, 16, 32]
    seeds = SEEDS[:4]
    rep = locate_plateau_report(n_stars, caps=caps, seeds=seeds, threshold=0.05)

    assert rep["n_stars"] == n_stars
    assert rep["caps"] == caps
    assert rep["n_seeds"] == len(seeds)
    assert [row["cap"] for row in rep["ladder"]] == caps
    assert rep["ladder"][0]["delta_b"] is None  # first row has no predecessor
    # cap* must be one of the caps or None, and consistent with re-deriving from the ladder.
    b_by_cap = {row["cap"]: row["b_median"] for row in rep["ladder"]}
    assert rep["cap_star"] == locate_plateau(b_by_cap, threshold=0.05)
    assert rep["paired"] is None  # paired=False by default

    # The ladder's b medians are exactly a direct instant fold over the same seeds.
    for cap in caps:
        bs = [
            bounce_depth(
                simulate_swarm(
                    SwarmParams(n_stars=n_stars, policy="powered", probe_speed_c=0.2,
                                speed_cap_c=0.4, stepping="event", max_retargets=cap,
                                coordination="instant"),
                    seed=s, record_steps=False).wasted_arrivals,
                n_stars)
            for s in seeds
        ]
        assert b_by_cap[cap] == pytest.approx(statistics.median(bs), rel=1e-12)


def test_report_is_deterministic() -> None:
    """Pure seeded fold: two identical calls give identical reports (CLAUDE.md sec 7)."""
    kw = dict(caps=[8, 16], seeds=SEEDS[:3], threshold=0.05)
    assert locate_plateau_report(400, **kw) == locate_plateau_report(400, **kw)


def test_report_paired_branch_runs_one_measurement() -> None:
    """With paired=True and a located cap*, the report carries ONE paired tax block at cap*.
    A huge threshold forces cap* = the smallest cap so the branch runs cheaply."""
    rep = locate_plateau_report(400, caps=[8, 16], seeds=SEEDS[:2], threshold=1e9, paired=True)
    assert rep["cap_star"] == 8
    assert rep["paired"] is not None
    assert rep["paired"]["cap"] == 8
    assert rep["paired"]["fuel_pct"]["median"] is not None


# --------------------------------------------------------------------------------------------
# CLI layer
# --------------------------------------------------------------------------------------------

class TestExtractOpt:
    def test_space_form(self) -> None:
        argv = ["--locate-plateau", "400", "--plateau-caps", "8,16"]
        assert _extract_opt(argv, "--plateau-caps") == "8,16"
        assert argv == ["--locate-plateau", "400"]  # popped in place

    def test_equals_form(self) -> None:
        argv = ["--plateau-threshold=0.1", "keep"]
        assert _extract_opt(argv, "--plateau-threshold") == "0.1"
        assert argv == ["keep"]

    def test_absent(self) -> None:
        argv = ["--locate-plateau", "400"]
        assert _extract_opt(argv, "--plateau-caps") is None
        assert argv == ["--locate-plateau", "400"]


class TestRunLocatePlateau:
    def test_missing_n_raises(self) -> None:
        with pytest.raises(SystemExit, match="expects a star count"):
            _run_locate_plateau(["--locate-plateau"])

    def test_non_int_n_raises(self) -> None:
        with pytest.raises(SystemExit, match="must be an integer"):
            _run_locate_plateau(["--locate-plateau", "abc"])

    def test_happy_path_prints_verdict(self, capsys) -> None:
        _run_locate_plateau(["--locate-plateau", "400", "--plateau-caps", "8,16",
                             "--plateau-seeds", "2", "--plateau-threshold", "0.05"])
        out = capsys.readouterr().out
        assert "plateau locator: N=400" in out
        assert "cap*" in out

    def test_paired_flag_runs_and_prints_tax(self, capsys) -> None:
        # A huge threshold forces cap* = smallest cap so --plateau-paired runs one cheap
        # paired measurement (2 seeds at N=400) and prints the tax line.
        _run_locate_plateau(["--locate-plateau", "400", "--plateau-caps", "8,16",
                             "--plateau-seeds", "2", "--plateau-threshold", "1e9",
                             "--plateau-paired"])
        out = capsys.readouterr().out
        assert "cap* = 8" in out
        assert "paired tax at cap 8" in out


class TestPrintPlateauReport:
    def _report(self, cap_star, paired=None) -> dict:
        return {"n_stars": 400, "n_seeds": 8, "caps": [8, 16, 32], "threshold": 0.05,
                "ladder": [{"cap": 8, "b_median": 4.25, "delta_b": None},
                           {"cap": 16, "b_median": 4.37, "delta_b": 0.12},
                           {"cap": 32, "b_median": 4.37, "delta_b": 0.0}],
                "cap_star": cap_star, "paired": paired}

    def test_plateau_found(self, capsys) -> None:
        _print_plateau_report(self._report(16))
        out = capsys.readouterr().out
        assert "cap* = 16" in out and "+0.120" in out

    def test_no_plateau(self, capsys) -> None:
        _print_plateau_report(self._report(None))
        assert "cap* = none" in capsys.readouterr().out

    def test_paired_line(self, capsys) -> None:
        paired = {"cap": 16, "fuel_pct": {"median": 20.4, "ci_lo": 13.0, "ci_hi": 25.6}}
        _print_plateau_report(self._report(16, paired))
        out = capsys.readouterr().out
        assert "paired tax at cap 16" in out and "20.400%" in out

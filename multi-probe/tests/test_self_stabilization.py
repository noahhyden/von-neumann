"""Self-stabilization scenarios for multi-probe (issue #49).

Dijkstra's question, applied to the fleet: given a legal running system, if we
perturb it to an arbitrary state, does the survivor set converge to a legal
replication regime? Each perturbation is a deterministic state-to-state
function seeded by the caller's RNG (the same discipline as the folds, CLAUDE
§7). Perturbations are applied *between* legal `step` calls, so the
step-level invariants added in #48 do not trip on the perturbed state (they
compare consecutive-step in/out, which is where the physics runs).

The predicates and perturbations live in the test file rather than a new
module; if the suite grows meaningful shared infrastructure it can be
promoted (see spec at issue #49#issuecomment-5015587903, §8).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from multi_probe.fleet import initial_state, simulate_fleet, step
from multi_probe.models import FleetParams, FleetState, Probe, ProbeStatus
from multi_probe.rng import next_float, seed_state


# ---------- Legality predicate ----------

def is_legal_fleet(
    history: list[FleetState],
    params: FleetParams,
    *,
    v_per_child: float | None = None,
) -> bool:
    """Legality of a fleet state given a recent history of snapshots.

    All four conditions must hold on the current (last) snapshot:
    - active fraction >= 0.5 across all probes (not stranded in TRAVELING),
    - population is non-decreasing across the whole history window,
    - remaining vitamins cover at least one more child,
    - not cap-bound (cap is the ceiling, not a legality question).
    """
    if not history:
        return False
    state = history[-1]
    if not state.probes:
        return False
    v = v_per_child if v_per_child is not None else (1.0 - params.closure_ratio) * params.seed_mass_kg
    active = sum(1 for p in state.probes if p.status == ProbeStatus.ACTIVE)
    if active / len(state.probes) < 0.5:
        return False
    if state.vitamin_pool_kg < v:
        return False
    if len(state.probes) >= params.max_probes:
        return False
    populations = [len(h.probes) for h in history]
    for a, b in zip(populations, populations[1:]):
        if b < a:
            return False
    return True


# ---------- Perturbations ----------

def _shuffled(items: list, rng: int) -> tuple[list, int]:
    """Fisher-Yates shuffle threaded through our seeded RNG."""
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        u, rng = next_float(rng)
        j = int(u * (i + 1))
        if j > i:
            j = i
        arr[i], arr[j] = arr[j], arr[i]
    return arr, rng


def pert_mp_mass_loss(state: FleetState, params: FleetParams, rng: int, frac: float) -> FleetState:
    """[pert:mp-mass-loss(frac)] Delete `frac` of probes at random (active and traveling)."""
    if not 0.0 <= frac <= 1.0:
        raise ValueError("frac must be in [0, 1]")
    ids = [p.id for p in state.probes]
    n_kill = int(round(frac * len(ids)))
    if n_kill == 0:
        return state
    shuffled, _ = _shuffled(ids, rng)
    doomed = set(shuffled[:n_kill])
    survivors = [p for p in state.probes if p.id not in doomed]
    return FleetState(
        rng=state.rng, day=state.day, probes=survivors,
        vitamin_pool_kg=state.vitamin_pool_kg, next_id=state.next_id,
    )


def pert_mp_vitamin_shock(state: FleetState, params: FleetParams, rng: int, frac: float) -> FleetState:
    """[pert:mp-vitamin-shock(frac)] Multiply the vitamin pool by `frac`."""
    if frac < 0.0:
        raise ValueError("frac must be >= 0")
    return FleetState(
        rng=state.rng, day=state.day, probes=state.probes,
        vitamin_pool_kg=state.vitamin_pool_kg * frac, next_id=state.next_id,
    )


def pert_mp_stranding(state: FleetState, params: FleetParams, rng: int, frac: float) -> FleetState:
    """[pert:mp-stranding(frac)] Move `frac` of ACTIVE probes to max_distance_au."""
    if not 0.0 <= frac <= 1.0:
        raise ValueError("frac must be in [0, 1]")
    active_ids = [p.id for p in state.probes if p.status == ProbeStatus.ACTIVE]
    n_move = int(round(frac * len(active_ids)))
    if n_move == 0:
        return state
    shuffled, _ = _shuffled(active_ids, rng)
    moved = set(shuffled[:n_move])
    probes = [
        Probe(id=p.id, distance_au=(params.max_distance_au if p.id in moved else p.distance_au),
              status=p.status, arrival_day=p.arrival_day,
              built_kg=p.built_kg, children=p.children)
        for p in state.probes
    ]
    return FleetState(
        rng=state.rng, day=state.day, probes=probes,
        vitamin_pool_kg=state.vitamin_pool_kg, next_id=state.next_id,
    )


def pert_mp_status_flip(state: FleetState, params: FleetParams, rng: int, frac: float) -> FleetState:
    """[pert:mp-status-flip(frac)] Flip `frac` of ACTIVE probes back to TRAVELING.

    Applied between legal `step` calls, so [inv:mp-status-transitions] compares
    the *next* step's before/after (both TRAVELING/ACTIVE, legal transition).
    """
    if not 0.0 <= frac <= 1.0:
        raise ValueError("frac must be in [0, 1]")
    active_ids = [p.id for p in state.probes if p.status == ProbeStatus.ACTIVE]
    n_flip = int(round(frac * len(active_ids)))
    if n_flip == 0:
        return state
    shuffled, _ = _shuffled(active_ids, rng)
    flipped = set(shuffled[:n_flip])
    probes = [
        Probe(id=p.id, distance_au=p.distance_au,
              status=(ProbeStatus.TRAVELING if p.id in flipped else p.status),
              arrival_day=(state.day + params.transit_days if p.id in flipped else p.arrival_day),
              built_kg=p.built_kg, children=p.children)
        for p in state.probes
    ]
    return FleetState(
        rng=state.rng, day=state.day, probes=probes,
        vitamin_pool_kg=state.vitamin_pool_kg, next_id=state.next_id,
    )


# ---------- Convergence driver ----------

@dataclass(frozen=True)
class Convergence:
    converged: bool
    convergence_day: float | None  # sim time at which the predicate first held
    final_state: FleetState


def _run_stabilization(
    baseline: FleetState,
    params: FleetParams,
    perturb,
    seed: int,
    horizon_days: float,
    dt_days: float = 10.0,
    stable_window: float = 100.0,
) -> Convergence:
    """Perturb the baseline once at t=0, then step until legal-for-stable_window or horizon."""
    perturbed = perturb(baseline, params, seed_state(seed))
    state = perturbed
    v_per_child = (1.0 - params.closure_ratio) * params.seed_mass_kg
    history: list[FleetState] = [state]
    legal_since: float | None = None
    n_steps = int(round(horizon_days / dt_days))
    for _ in range(n_steps):
        state = step(state, params, dt_days)
        history.append(state)
        # Keep a bounded sliding window for the trend check.
        window_snaps = 5
        recent = history[-window_snaps:]
        if is_legal_fleet(recent, params, v_per_child=v_per_child):
            if legal_since is None:
                legal_since = state.day
            elif state.day - legal_since >= stable_window:
                return Convergence(True, legal_since, state)
        else:
            legal_since = None
    return Convergence(False, None, state)


# ---------- Fixtures ----------

def _params(**overrides) -> FleetParams:
    base = dict(
        seed_mass_kg=100.0, closure_ratio=0.9, e_local_kwh_per_kg=1.0,
        local_build_rate_kg_per_day=1.0, array_area_m2=10.0,
        array_efficiency=0.3, manufacturing_fraction=0.5,
        n_seed_probes=8, vitamin_pool_kg=1_000_000.0, max_probes=2000,
        transit_days=50.0,
    )
    base.update(overrides)
    return FleetParams(**base)


def _baseline(params: FleetParams | None = None, warmup_days: float = 300.0) -> tuple[FleetState, FleetParams]:
    """Warm the fleet into a growing but sub-cap regime."""
    params = params or _params()
    state = initial_state(params, seed=1)
    n = int(round(warmup_days / 10.0))
    for _ in range(n):
        state = step(state, params, 10.0)
    return state, params


# ---------- Sanity: the *unperturbed* baseline is legal ----------

def test_baseline_is_legal():
    state, params = _baseline()
    v = (1.0 - params.closure_ratio) * params.seed_mass_kg
    # Give it a short history by stepping a few more times.
    history = [state]
    for _ in range(5):
        state = step(state, params, 10.0)
        history.append(state)
    assert is_legal_fleet(history, params, v_per_child=v)


# ---------- Positive: moderate perturbation converges ----------

@pytest.mark.parametrize("frac", [0.25, 0.5])
def test_moderate_mass_loss_converges(frac):
    baseline, params = _baseline()
    result = _run_stabilization(
        baseline, params, lambda s, p, r: pert_mp_mass_loss(s, p, r, frac),
        seed=42, horizon_days=5000.0,
    )
    assert result.converged, (
        f"fleet did not converge after {frac*100:.0f}% mass loss "
        f"(final pop={len(result.final_state.probes)}, "
        f"vitamin={result.final_state.vitamin_pool_kg:.1f} kg)"
    )


# ---------- Threshold sweep: convergence time is monotone in mass-loss frac ----------

def test_convergence_time_monotone_in_mass_loss():
    baseline, params = _baseline()
    fracs = [0.1, 0.3, 0.5]
    times = []
    for f in fracs:
        result = _run_stabilization(
            baseline, params, lambda s, p, r, f=f: pert_mp_mass_loss(s, p, r, f),
            seed=42, horizon_days=5000.0,
        )
        assert result.converged, f"frac={f} failed to converge"
        times.append(result.convergence_day)
    for a, b, fa, fb in zip(times, times[1:], fracs, fracs[1:]):
        assert b >= a - 50.0, (
            f"convergence-time should not decrease with worse perturbation; "
            f"frac {fa}->{fb} gave times {a}->{b}"
        )


# ---------- Honest null: extreme mass loss cannot recover ----------

def test_total_extinction_does_not_converge():
    baseline, params = _baseline()
    result = _run_stabilization(
        baseline, params, lambda s, p, r: pert_mp_mass_loss(s, p, r, 1.0),
        seed=42, horizon_days=2000.0,
    )
    assert not result.converged
    assert result.convergence_day is None
    assert not any(p.status == ProbeStatus.ACTIVE for p in result.final_state.probes)


# ---------- Vitamin shock: a full-drain shock does not recover ----------

def test_vitamin_shock_zero_does_not_recover():
    baseline, params = _baseline()
    result = _run_stabilization(
        baseline, params, lambda s, p, r: pert_mp_vitamin_shock(s, p, r, 0.0),
        seed=42, horizon_days=2000.0,
    )
    assert not result.converged
    assert result.final_state.vitamin_pool_kg < (1.0 - params.closure_ratio) * params.seed_mass_kg


def test_vitamin_shock_partial_recovers():
    baseline, params = _baseline()
    result = _run_stabilization(
        baseline, params, lambda s, p, r: pert_mp_vitamin_shock(s, p, r, 0.5),
        seed=42, horizon_days=5000.0,
    )
    assert result.converged


# ---------- Stranding: a moderate strand still recovers ----------

def test_stranding_moderate_recovers():
    baseline, params = _baseline()
    result = _run_stabilization(
        baseline, params, lambda s, p, r: pert_mp_stranding(s, p, r, 0.3),
        seed=42, horizon_days=5000.0,
    )
    assert result.converged


# ---------- Status flip: probes eventually re-arrive; the fleet recovers ----------

def test_status_flip_moderate_recovers():
    baseline, params = _baseline()
    result = _run_stabilization(
        baseline, params, lambda s, p, r: pert_mp_status_flip(s, p, r, 0.5),
        seed=42, horizon_days=5000.0,
    )
    assert result.converged


# ---------- Determinism: same seed reproduces the run ----------

def test_stabilization_run_is_deterministic():
    baseline, params = _baseline()
    a = _run_stabilization(
        baseline, params, lambda s, p, r: pert_mp_mass_loss(s, p, r, 0.5),
        seed=42, horizon_days=2000.0,
    )
    b = _run_stabilization(
        baseline, params, lambda s, p, r: pert_mp_mass_loss(s, p, r, 0.5),
        seed=42, horizon_days=2000.0,
    )
    assert a.converged == b.converged
    assert a.convergence_day == b.convergence_day
    assert len(a.final_state.probes) == len(b.final_state.probes)

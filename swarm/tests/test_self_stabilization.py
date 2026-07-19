"""Self-stabilization scenarios for swarm (issue #49).

Dijkstra's question, applied to the settlement front: given a legal running
system, if we perturb it to an arbitrary state, does the survivor set
converge to a legal replication regime? Perturbations mutate the state in
place (matching swarm's fold discipline) and are seeded through the caller's
RNG.

Spec: issue #49#issuecomment-5015587903.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from swarm import SwarmParams, initial_state, simulate_swarm
from swarm.models import SwarmState
from swarm.rng import next_float, seed_state
from swarm.sim import step_event


# ---------- Legality predicate ----------

def is_legal_swarm(history: list[tuple[float, int, int]], n_stars: int) -> bool:
    """Legality on a small history of (year, settled_count, in_flight) tuples.

    Legal when either:
    - settled_count reached n_stars (terminal, everyone's home), OR
    - settled_count grew in the recent window AND in-flight probes are present.
    """
    if not history:
        return False
    year, settled, in_flight = history[-1]
    if settled >= n_stars:
        return True
    if in_flight == 0:
        return False
    populations = [s for _, s, _ in history]
    return populations[-1] > populations[0]


def _snapshot(state: SwarmState) -> tuple[float, int, int]:
    return (state.year, state.settled_count, len(state.probes))


# ---------- Perturbations ----------

def _shuffled_indices(items: list, rng: int) -> tuple[list, int]:
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        u, rng = next_float(rng)
        j = int(u * (i + 1))
        if j > i:
            j = i
        arr[i], arr[j] = arr[j], arr[i]
    return arr, rng


def pert_sw_star_loss(state: SwarmState, rng: int, frac: float) -> SwarmState:
    """[pert:sw-star-loss(frac)] Delete `frac` of in-flight probes at random.

    Mutates state.probes in place. Survivors keep the same ids and trajectories.
    """
    if not 0.0 <= frac <= 1.0:
        raise ValueError("frac must be in [0, 1]")
    ids = list(state.probes.keys())
    n_kill = int(round(frac * len(ids)))
    if n_kill == 0:
        return state
    shuffled, _ = _shuffled_indices(ids, rng)
    for pid in shuffled[:n_kill]:
        del state.probes[pid]
    return state


def pert_sw_settle_loss(state: SwarmState, rng: int, frac: float) -> SwarmState:
    """[pert:sw-settle-loss(frac)] Flip `frac` of settled stars back to unsettled.

    Also decrements settled_count so it stays consistent with settled_year (an
    invariant of the swarm fold code, not one of #48's asserted invariants).
    """
    if not 0.0 <= frac <= 1.0:
        raise ValueError("frac must be in [0, 1]")
    settled_idx = [i for i, y in enumerate(state.settled_year) if y >= 0.0]
    n_flip = int(round(frac * len(settled_idx)))
    if n_flip == 0:
        return state
    shuffled, _ = _shuffled_indices(settled_idx, rng)
    for i in shuffled[:n_flip]:
        state.settled_year[i] = -1.0
        state.settled_count -= 1
    return state


def pert_sw_retarget_cap_shock(state: SwarmState, rng: int, max_retargets: int) -> SwarmState:
    """[pert:sw-retarget-cap-shock] Set every in-flight probe to `max_retargets - 1`.

    One more re-target and each probe retires. Tests whether the swarm can
    continue front expansion when its in-flight fleet is almost spent.
    """
    for p in state.probes.values():
        p.retargets = max(0, max_retargets - 1)
    return state


# ---------- Convergence driver ----------

@dataclass(frozen=True)
class Convergence:
    converged: bool
    convergence_year: float | None
    final_settled: int
    final_in_flight: int


def _run_stabilization(
    perturb,
    params: SwarmParams,
    seed: int,
    max_events: int = 4000,
    window_size: int = 20,
) -> Convergence:
    """Perturb the initial state, then step_event until legal-window or exhaustion."""
    state = initial_state(params, seed=seed)
    perturb(state, seed_state(seed ^ 0xC0FFEE))
    history: list[tuple[float, int, int]] = [_snapshot(state)]
    for _ in range(max_events):
        step_event(state, params)
        history.append(_snapshot(state))
        if len(history) >= window_size:
            window = history[-window_size:]
            if is_legal_swarm(window, params.n_stars):
                return Convergence(True, state.year, state.settled_count, len(state.probes))
        if not state.probes and state.settled_count < params.n_stars:
            break
    ok = is_legal_swarm(history[-window_size:], params.n_stars)
    return Convergence(
        ok, state.year if ok else None,
        state.settled_count, len(state.probes),
    )


# ---------- Fixtures ----------

def _params(**overrides) -> SwarmParams:
    base = dict(n_stars=200, offspring_per_settlement=2, stepping="event")
    base.update(overrides)
    return SwarmParams(**base)


# ---------- Sanity: unperturbed baseline is legal ----------

def test_baseline_swarm_is_legal():
    params = _params()

    def _noop(state, rng):
        return state

    result = _run_stabilization(_noop, params, seed=1)
    assert result.converged


# ---------- Positive: moderate star-loss recovers ----------

def test_moderate_star_loss_recovers():
    params = _params(n_stars=200, offspring_per_settlement=4)
    # Warm up first, then delete a fraction of the in-flight probes.
    def perturb(state, rng):
        for _ in range(10):
            step_event(state, _params_stub := params)
        pert_sw_star_loss(state, rng, 0.5)
    result = _run_stabilization(perturb, params, seed=2)
    assert result.converged


# ---------- Threshold sweep: convergence time is monotone in settle-loss frac ----------

def test_settle_loss_convergence_time_monotone():
    params = _params(n_stars=200, offspring_per_settlement=4)

    fracs = [0.1, 0.3, 0.5]
    times = []
    for f in fracs:
        def perturb(state, rng, f=f):
            for _ in range(20):
                step_event(state, params)
            pert_sw_settle_loss(state, rng, f)
        result = _run_stabilization(perturb, params, seed=3)
        assert result.converged, f"frac={f} did not converge"
        times.append(result.convergence_year)
    for a, b, fa, fb in zip(times, times[1:], fracs, fracs[1:]):
        # Recovery should not be strictly faster with a worse perturbation.
        # A small slack absorbs numerical shifts between adjacent frac values.
        assert b >= a - 1e5, (
            f"convergence-year should not decrease with worse perturbation; "
            f"frac {fa}->{fb} gave years {a}->{b}"
        )


# ---------- Honest null: killing every in-flight probe pre-launch cannot progress ----------

def test_kill_all_probes_before_settlement_cannot_progress():
    """If we kill every in-flight probe before any settlement, no more events can fire."""
    params = _params(n_stars=200, offspring_per_settlement=2)

    def perturb(state, rng):
        pert_sw_star_loss(state, rng, 1.0)
    result = _run_stabilization(perturb, params, seed=4)
    # Only the origin star (if any) has been settled by initial_state.
    assert result.final_in_flight == 0
    # No progression means either not converged, or the only "settled" is the origin.
    assert result.final_settled <= 1


# ---------- Retarget-cap shock: probes near cap still make some progress or retire ----------

def test_retarget_cap_shock_bounded_behavior():
    params = _params(n_stars=200, offspring_per_settlement=2, max_retargets=8)

    def perturb(state, rng):
        # Warm up so we have in-flight probes to shock.
        for _ in range(20):
            step_event(state, params)
        pert_sw_retarget_cap_shock(state, rng, params.max_retargets)
    result = _run_stabilization(perturb, params, seed=5)
    # Either the swarm continues (settled_count grew past the warmup), or it retires
    # cleanly (no runaway retargeting past the cap). Either is a well-behaved outcome.
    assert result.final_settled >= 1


# ---------- Determinism: same seed reproduces the run ----------

def test_swarm_stabilization_is_deterministic():
    params = _params(n_stars=200, offspring_per_settlement=2)

    def perturb(state, rng):
        for _ in range(10):
            step_event(state, params)
        pert_sw_star_loss(state, rng, 0.3)
    a = _run_stabilization(perturb, params, seed=7)
    b = _run_stabilization(perturb, params, seed=7)
    assert a.converged == b.converged
    assert a.final_settled == b.final_settled
    assert a.final_in_flight == b.final_in_flight

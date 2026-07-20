"""Bit-identity guard for the Probe fast-path (issue: 200k event-loop speedup, Tier 1).

Two allocation-only optimizations must not move a single reported number:

  A. ``Probe`` gains ``slots=True`` - drops the per-instance ``__dict__`` so the ~1M+
     allocations in a large fill are cheaper. Storage layout only.
  B. In-place ``Probe`` reuse at the two id-reusing retarget sites (``_process_arrivals``
     wasted branch and ``_process_learns``): the just-popped probe is mutated and re-added
     instead of a fresh object being allocated. Same field values, same insertion.

Neither touches a field value, iteration order, float operation, or RNG draw (the event
loop draws no randomness), so the whole ``SwarmResult`` must be byte-for-byte unchanged.
The golden digests below were captured from the code state BEFORE the change; they are the
regression guard - a refactor that perturbs the fold fails here (see docs/HARDWARE.md and
CLAUDE.md section 7). The matrix exercises BOTH reuse sites: lightspeed/instant (retarget in
_process_arrivals) and inflight (mid-flight learn reuse in _process_learns), across all three
policies.
"""

from __future__ import annotations

import hashlib
from dataclasses import fields

import pytest

from swarm import SwarmParams, simulate_swarm
from swarm.models import Probe

# (policy, coordination, n_stars, offspring, seed) -> sha256[:16] of the full SwarmResult
# (every field except the per-event ``steps`` trace). Captured pre-change; see module docstring.
GOLDEN: dict[tuple, str] = {
    ("powered", "instant", 800, 2, 1): "a583499d26f73893",
    ("powered", "lightspeed", 800, 2, 1): "b402a666c92a0837",
    ("powered", "inflight", 800, 2, 1): "90bf8a310fab148c",
    ("slingshot_nearest", "lightspeed", 600, 3, 2): "5c66d8665d00993b",
    ("slingshot_maxboost", "inflight", 500, 2, 3): "ec260da7a623912c",
}


def _result_digest(policy: str, coord: str, n: int, off: int, seed: int) -> str:
    """Stable digest of a full SwarmResult (all fields but the trace), exact via repr().

    Runs the PYTHON fold explicitly: this guards the Tier-1 (Probe slots + in-place reuse)
    allocation change, which is a property of ``_simulate_swarm_python``. The Rust fast path
    has its own bit-identity oracle (``test_rust_fill_loop.py``); routing this digest through
    the dispatcher would make it repr-sensitive to float vs np.float64 typing, not behaviour.
    """
    import swarm.sim as sim

    p = SwarmParams(n_stars=n, policy=policy, coordination=coord,
                    offspring_per_settlement=off, probe_speed_c=0.2,
                    speed_cap_c=0.4, stepping="event")
    r = sim._simulate_swarm_python(p, seed=seed, record_steps=False)
    blob = "|".join(f"{f.name}={getattr(r, f.name)!r}"
                    for f in fields(r) if f.name != "steps")
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


@pytest.mark.parametrize("cfg,want", GOLDEN.items(), ids=[str(k) for k in GOLDEN])
def test_result_bit_identical_to_pre_change_golden(cfg: tuple, want: str) -> None:
    """The full result is byte-for-byte the pre-change value for every matrix config."""
    assert _result_digest(*cfg) == want


def test_probe_uses_slots() -> None:
    """Probe is a slots dataclass: no __dict__, and undeclared attributes are rejected."""
    assert hasattr(Probe, "__slots__")
    p = Probe(id=0, target=1, arrive_year=1.0, speed_pc_yr=0.1)
    assert not hasattr(p, "__dict__")
    with pytest.raises(AttributeError):
        p.not_a_field = 3  # slots forbids attributes outside the declared set
    # every declared field is reachable (the reuse path reassigns all of them)
    for f in fields(Probe):
        getattr(p, f.name)


def test_retarget_path_is_deterministic_across_runs() -> None:
    """A retarget-heavy fill (lightspeed, branching) is bit-identical run to run.

    Exercises change B's in-place reuse under many retargets; if the reuse left a stale field,
    two runs (or the golden above) would diverge. Complements the golden by asserting internal
    self-consistency without a pinned constant.
    """
    p = SwarmParams(n_stars=800, policy="powered", coordination="lightspeed",
                    offspring_per_settlement=3, probe_speed_c=0.2, speed_cap_c=0.4,
                    stepping="event")
    a = simulate_swarm(p, seed=5, record_steps=False)
    b = simulate_swarm(p, seed=5, record_steps=False)
    assert a.wasted_arrivals == b.wasted_arrivals > 0  # retargets actually happened
    assert a.t100_years == b.t100_years
    assert a.wasted_travel_pc == b.wasted_travel_pc

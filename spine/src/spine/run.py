"""The cross-scale fold: one factory, three scales, cadences derived not assumed.

`von-neumann` models self-replication at three scales, each its own pure fold:

  * a **single factory** (closure-sim): mass closure + a replication sim - how long one
    seed takes to reach a target output;
  * a **local fleet** (multi-probe): tens of probes copying and dispersing across AU,
    whose copy cadence is *already* derived from a closure-sim `Factory`
    (`params_from_factory`); and
  * a **galaxy** (swarm): a settlement front across parsecs, following Nicholson &
    Forgan (2013).

Until now those three told three disconnected stories: each scale that needed a
"how long to build a copy" number chose its own. In particular the swarm's per-star
**manufacturing dwell** (`settle_time_years` - the time a freshly settled probe spends
building offspring before they depart) was an ungrounded `[ESTIMATE]` defaulted to 0.0:
the front was assumed to replicate *instantaneously*.

`spine` closes that seam. It threads **one** `Factory` through all three folds and
*derives* the swarm's dwell from the very same closure-sim build physics the fleet uses
(`time_to_build_one_copy_days` at 1 AU). It introduces **no new number** - it only
routes a quantity the factory already fixes to the one scale that was guessing it.

The payoff is a quantitative, cross-scale answer to *which constraint binds at which
scale*: build time governs the local fleet (transit is days), but is dwarfed by
interstellar transit at galactic scale - so the same manufacturing cadence that sets the
fleet's doubling time is a negligible tax on galactic exploration. `measure_dwell_tax`
demonstrates that tax directly (front fill with the derived dwell vs. with zero dwell).

Pure, deterministic, plain data; zero pimas imports (CLAUDE.md §7). Every number traces
to closure-sim / multi-probe / swarm; see REFERENCES.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from closure_sim.closure import compute_closure
from closure_sim.replication import simulate
from multi_probe.fleet import params_from_factory, time_to_build_one_copy_days
from swarm.models import SwarmParams
from swarm.sim import simulate_swarm

from spine.scenario import SpineScenario

# 1 Julian year = 365.25 days = 3.15576e7 s. This is the SAME year basis the swarm uses
# for C_PC_PER_YEAR (swarm/models.py), so build-days -> years and the swarm's light-years
# are on one clock. (3.15576e7 s / 86400 s-per-day = 365.25 days.)
DAYS_PER_JULIAN_YEAR: float = 365.25


@dataclass
class SpineResult:
    """The three scales side by side, with the cross-scale cadence that links them."""

    # --- the one factory, shared by every scale ---
    closure_ratio: float
    single_factory_time_to_target_days: float | None

    # --- the derived cross-scale cadence (the seam this module closes) ---
    copy_time_days: float  # time to build one offspring's worth of local mass at 1 AU
    settle_time_years: float  # = copy_time_days / 365.25; the swarm dwell, DERIVED

    # --- scale 2: the local fleet (multi-probe) ---
    fleet_doubling_days: float | None
    fleet_final_population: int
    fleet_binding: str  # which ceiling bound the fleet, in plain words

    # --- scale 3: the galaxy (swarm), for the chosen policy, using the DERIVED dwell ---
    policy: str
    n_stars: int
    final_settled: int
    swarm_t100_years: float | None
    dwell_fraction_of_t100: float | None  # one dwell as a fraction of the whole fill

    verdict: str  # plain-language cross-scale summary (derived text, no new number)


@dataclass
class DwellTax:
    """A direct A/B of the manufacturing dwell's cost at galactic scale.

    Both runs are identical except the dwell: `settle_time_years` = the derived value vs.
    0.0 (the old ungrounded default). Run at a fine timestep on a small field so a dwell
    of order a year is actually resolved (see `SpineScenario.tax_dt_years`).
    """

    policy: str
    n_stars: int
    dt_years: float
    settle_time_years: float
    t100_with_dwell: float | None
    t100_zero_dwell: float | None
    tax_fraction: float | None  # (with - without) / without; >= 0, and ~0 when transit dominates


def _fleet_binding(binding) -> str:
    if binding.vitamin_limited:
        return "vitamin-limited (the electronics wall: the imported-parts pool ran out)"
    if binding.power_limited:
        return "power-limited (dispersed probes build too slowly to copy in time - the spatial power wall)"
    if binding.cap_limited:
        return "cap-limited (hit the fleet-size cap - a scope bound, not physics)"
    return "still growing at the horizon (no ceiling reached in the window)"


def derive_settle_time_years(scenario: SpineScenario) -> float:
    """The swarm's per-star dwell, DERIVED from the factory's build physics at 1 AU.

    A freshly settled probe orbits a Sun-like star (N&F's uniform field) and must build one
    offspring's worth of *local* structure before it can launch children. That time is
    exactly the fleet's 1-AU copy cadence - the same closure-sim `min(machinery, energy_cap)`
    regime - converted to years. No new number enters here; it is factory physics, re-used.
    """
    fleet_params = params_from_factory(scenario.factory)
    copy_time_days = time_to_build_one_copy_days(fleet_params, 1.0)
    return copy_time_days / DAYS_PER_JULIAN_YEAR


def _verify_spine_result(r: SpineResult) -> None:
    """Assert composite invariants on a completed spine run. See REFERENCES.md.

    Called under `if __debug__:` at the end of `run_spine`.
    """
    assert 0.0 <= r.closure_ratio <= 1.0, (
        f"[inv:sp-scale-order] closure_ratio={r.closure_ratio} outside [0, 1]"
    )
    assert r.copy_time_days > 0, (
        f"[inv:sp-scale-order] copy_time_days={r.copy_time_days} must be > 0"
    )
    assert r.settle_time_years > 0, (
        f"[inv:sp-scale-order] settle_time_years={r.settle_time_years} must be > 0"
    )
    # The two are strictly linked by the day/year conversion.
    expected_years = r.copy_time_days / DAYS_PER_JULIAN_YEAR
    assert abs(r.settle_time_years - expected_years) <= 1e-9 * max(1.0, expected_years), (
        f"[inv:sp-scale-order] settle_time_years={r.settle_time_years} "
        f"!= copy_time_days/{DAYS_PER_JULIAN_YEAR}={expected_years}"
    )
    assert r.fleet_final_population >= 0, (
        f"[inv:sp-scale-order] fleet_final_population={r.fleet_final_population} must be >= 0"
    )
    assert 0 <= r.final_settled <= r.n_stars, (
        f"[inv:sp-scale-order] final_settled={r.final_settled} outside [0, n_stars={r.n_stars}]"
    )
    if r.swarm_t100_years is not None:
        assert r.swarm_t100_years > 0, (
            f"[inv:sp-dwell-nonneg] swarm_t100_years={r.swarm_t100_years} must be > 0"
        )
    if r.dwell_fraction_of_t100 is not None:
        assert r.dwell_fraction_of_t100 >= 0.0, (
            f"[inv:sp-dwell-nonneg] dwell_fraction={r.dwell_fraction_of_t100} must be >= 0"
        )


def run_spine(scenario: SpineScenario) -> SpineResult:
    """Run all three scales on one factory, with the swarm dwell derived from it."""
    factory = scenario.factory
    if factory.replication is None:
        raise ValueError("spine factory needs replication params")

    # --- scale 1: the single factory (closure + replication to a target output) ---
    closure_ratio = compute_closure(factory).closure_ratio
    single = simulate(factory, factory.replication)

    # --- the derived cross-scale cadence ---
    fleet_params = params_from_factory(factory)
    copy_time_days = time_to_build_one_copy_days(fleet_params, 1.0)
    settle_time_years = copy_time_days / DAYS_PER_JULIAN_YEAR

    # --- scale 2: the local fleet (its copy cadence already derives from the factory) ---
    from multi_probe.fleet import simulate_fleet

    fleet = simulate_fleet(fleet_params)

    # --- scale 3: the galaxy, using the DERIVED dwell (not the old 0.0 guess) ---
    swarm_params = SwarmParams(
        n_stars=scenario.n_stars,
        offspring_per_settlement=scenario.offspring_per_settlement,
        settle_time_years=settle_time_years,
        policy=scenario.policy,
        dt_years=scenario.swarm_dt_years,
    )
    swarm = simulate_swarm(swarm_params, seed=scenario.seed)

    t100 = swarm.t100_years
    dwell_frac = (settle_time_years / t100) if (t100 and t100 > 0) else None

    verdict = _build_verdict(
        settle_time_years=settle_time_years,
        fleet_doubling_days=fleet.doubling_time_days,
        policy=scenario.policy,
        t100=t100,
        dwell_frac=dwell_frac,
    )

    result = SpineResult(
        closure_ratio=closure_ratio,
        single_factory_time_to_target_days=single.time_to_target_days,
        copy_time_days=copy_time_days,
        settle_time_years=settle_time_years,
        fleet_doubling_days=fleet.doubling_time_days,
        fleet_final_population=fleet.final_population,
        fleet_binding=_fleet_binding(fleet.binding),
        policy=scenario.policy,
        n_stars=scenario.n_stars,
        final_settled=swarm.final_settled,
        swarm_t100_years=t100,
        dwell_fraction_of_t100=dwell_frac,
        verdict=verdict,
    )
    if __debug__:
        _verify_spine_result(result)
    return result


def measure_dwell_tax(scenario: SpineScenario) -> DwellTax:
    """Directly measure the manufacturing dwell's cost on galactic exploration.

    An A/B on a small field at a fine timestep (so a ~year dwell is resolved): the swarm
    fill time with the DERIVED dwell vs. with dwell = 0. The gap is the exploration time
    the front spends building rather than travelling. `tax_fraction` is that gap relative
    to the zero-dwell baseline - expected near zero when interstellar transit dominates.
    """
    settle_time_years = derive_settle_time_years(scenario)

    def _t100(dwell: float) -> float | None:
        params = SwarmParams(
            n_stars=scenario.tax_n_stars,
            offspring_per_settlement=scenario.offspring_per_settlement,
            settle_time_years=dwell,
            policy=scenario.policy,
            dt_years=scenario.tax_dt_years,
        )
        return simulate_swarm(params, seed=scenario.seed).t100_years

    with_dwell = _t100(settle_time_years)
    zero_dwell = _t100(0.0)
    tax = (
        (with_dwell - zero_dwell) / zero_dwell
        if (with_dwell is not None and zero_dwell not in (None, 0.0))
        else None
    )

    return DwellTax(
        policy=scenario.policy,
        n_stars=scenario.tax_n_stars,
        dt_years=scenario.tax_dt_years,
        settle_time_years=settle_time_years,
        t100_with_dwell=with_dwell,
        t100_zero_dwell=zero_dwell,
        tax_fraction=tax,
    )


def _build_verdict(
    *,
    settle_time_years: float,
    fleet_doubling_days: float | None,
    policy: str,
    t100: float | None,
    dwell_frac: float | None,
) -> str:
    """One plain-language sentence on which constraint binds at which scale."""
    dwell_days = settle_time_years * DAYS_PER_JULIAN_YEAR
    parts = [
        f"One copy takes ~{dwell_days:.0f} days (~{settle_time_years:.2f} yr) to build.",
    ]
    if fleet_doubling_days is not None:
        parts.append(
            f"At fleet scale that build time IS the clock - the fleet doubles in "
            f"~{fleet_doubling_days:.0f} days, set by how fast a probe makes a copy."
        )
    if t100 is not None and dwell_frac is not None:
        parts.append(
            f"At galactic scale ({policy}) the same dwell is ~{dwell_frac:.1e} of the "
            f"~{t100:,.0f}-yr fill - interstellar transit dominates, so manufacturing "
            f"time is a negligible tax on exploration."
        )
    return " ".join(parts)

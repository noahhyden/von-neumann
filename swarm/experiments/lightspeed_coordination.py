"""Experiment: what does light-speed-limited coordination cost the swarm?

FRONTIER #1, slice 2. A paired A/B - for each policy, the SAME seeded galaxy is run
under `coordination="instant"` (the paper's perfect global info) and `"lightspeed"` (a
probe knows a distant star is settled only after the news-light arrives). Because the two
modes share the seed, the per-seed difference is attributable to information lag alone;
we report the distribution across a seed ensemble (median + IQR + a bootstrap CI + a
sign test), never a single run.

The result (see the printed tables): the penalty is NOT simply Lambda = v_probe/c.
Powered nearest-neighbour flight is nearly immune even when fast - a probe that loses a
race just takes the star next door, a cheap recovery. The cost appears when probes make
**long-range hops from stale views** (the slingshot regime): a wasted trip is then a long
detour, so the field fills materially later. Two facts back the mechanism directly:

- the effective probe speeds (hence Lambda_eff = v/c) of the two slingshot policies are
  within ~1.3x of each other, yet their penalties differ by ~1.5x - so Lambda cannot be
  what sets the penalty; and
- the mean wasted-trip hop length is ~3x longer for max-boost than for nearest-star,
  which IS the axis the penalty tracks.

The penalty is reported at several coverage fractions (t25..t100), not only the fragile
t100 tail, to show the shift is not an artifact of the last few stars.

Run:  python -m experiments.lightspeed_coordination      (from the swarm/ package root)
  or  uv run python -m experiments.lightspeed_coordination
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from swarm import SwarmParams, simulate_swarm
from swarm.models import C_PC_PER_YEAR, KM_S_TO_PC_YR

from experiments.stats_util import bootstrap_median_ci, sign_test_positive

# A fixed, deterministic seed ensemble. 32 distinct galaxies per (policy, mode); the two
# coordination modes share each seed so differences are paired.
SEEDS = [0x9E3779B9 + 2654435761 * k for k in range(32)]
N_STARS = 300  # small enough that even slingshot_maxboost's O(N^2) stays quick over 32x2 runs

POLICIES = ("powered", "slingshot_nearest", "slingshot_maxboost")

# Coverage fractions we report the penalty at (t100 alone is a fragile tail statistic).
COVERAGE = ("t25", "t50", "t75", "t90", "t99", "t100")


@dataclass
class Cell:
    policy: str
    # per-seed % slowdown (lightspeed vs instant) at each coverage fraction
    pen: dict[str, list[float]] = field(default_factory=dict)
    v_eff_km_s: list[float] = field(default_factory=list)   # per-seed mean launch speed (lightspeed)
    v_max_km_s: list[float] = field(default_factory=list)   # per-seed peak probe speed (lightspeed)
    wasted_hop_pc: list[float] = field(default_factory=list)  # per-seed mean wasted-trip hop length
    settle_hop_pc: list[float] = field(default_factory=list)  # per-seed mean winning-trip hop length
    waste_ratio_inst: list[float] = field(default_factory=list)
    waste_ratio_ls: list[float] = field(default_factory=list)
    filled_ls: list[bool] = field(default_factory=list)

    @property
    def dt100_pct(self) -> list[float]:
        """Back-compat: the per-seed t100 penalty list (what the figures plot)."""
        return self.pen["t100"]


def _run(policy: str, coordination: str, seed: int) -> object:
    return simulate_swarm(
        SwarmParams(n_stars=N_STARS, policy=policy, coordination=coordination), seed=seed
    )


def run_cell(policy: str, *, n_stars: int = N_STARS, seeds: list[int] | None = None) -> Cell:
    """Paired ensemble for one policy: fill each seeded galaxy under both modes."""
    seeds = seeds if seeds is not None else SEEDS
    c = Cell(policy=policy, pen={k: [] for k in COVERAGE})
    for seed in seeds:
        inst = simulate_swarm(SwarmParams(n_stars=n_stars, policy=policy, coordination="instant"), seed=seed)
        ls = simulate_swarm(SwarmParams(n_stars=n_stars, policy=policy, coordination="lightspeed"), seed=seed)
        for key in COVERAGE:
            ti = getattr(inst, f"{key}_years")
            tl = getattr(ls, f"{key}_years")
            if ti and tl:
                c.pen[key].append((tl - ti) / ti * 100.0)
        c.v_eff_km_s.append(ls.mean_launch_speed_km_s)
        c.v_max_km_s.append(ls.max_probe_speed_km_s)
        c.wasted_hop_pc.append(ls.mean_wasted_hop_pc)
        c.settle_hop_pc.append(ls.mean_settle_hop_pc)
        c.waste_ratio_inst.append(inst.wasted_arrivals / max(1, inst.total_arrivals))
        c.waste_ratio_ls.append(ls.wasted_arrivals / max(1, ls.total_arrivals))
        c.filled_ls.append(ls.final_settled == ls.n_stars)
    return c


def _iqr(xs: list[float]) -> tuple[float, float, float]:
    """Median and quartiles (matches paper_figures._iqr and the figure box)."""
    xs = sorted(xs)
    med = statistics.median(xs)
    lo = xs[len(xs) // 4]
    hi = xs[(3 * len(xs)) // 4]
    return med, lo, hi


def main() -> None:
    cells = {pol: run_cell(pol) for pol in POLICIES}

    print(f"Light-speed coordination cost - {len(SEEDS)} seeds, N={N_STARS} stars, paired A/B\n")

    # (1) Headline table: t100 penalty with spread, bootstrap CI, and sign test.
    print("Fill-100% penalty (median, IQR, bootstrap 95% CI, sign test over seeds):")
    print(f"  {'policy':<20}{'median%':>9}{'IQR%':>18}{'95% CI%':>18}{'seeds +':>10}{'p':>12}")
    for pol in POLICIES:
        xs = cells[pol].pen["t100"]
        med, lo, hi = _iqr(xs)
        _, blo, bhi = bootstrap_median_ci(xs)
        k, n, p = sign_test_positive(xs)
        ci = f"[{blo:+.1f},{bhi:+.1f}]"
        iqr = f"[{lo:+.1f},{hi:+.1f}]"
        print(f"  {pol:<20}{med:>+8.1f} {iqr:>18}{ci:>18}{f'{k}/{n}':>10}{p:>12.2e}")

    # (2) Penalty across coverage fractions (is the shift a t100 tail artifact? no).
    print("\nMedian penalty by coverage fraction (%):")
    print(f"  {'policy':<20}" + "".join(f"{k:>8}" for k in COVERAGE))
    for pol in POLICIES:
        row = "".join(f"{statistics.median(cells[pol].pen[k]):>+8.1f}" for k in COVERAGE)
        print(f"  {pol:<20}{row}")

    # (3) The mechanism: effective speed (Lambda) vs wasted-hop length (locality).
    print("\nMechanism - effective speed vs hop locality (lightspeed runs, median over seeds):")
    print(f"  {'policy':<20}{'v_eff km/s':>12}{'Lambda_eff':>12}{'wasted hop pc':>15}{'settle hop pc':>15}")
    for pol in POLICIES:
        c = cells[pol]
        v = statistics.median(c.v_eff_km_s)
        lam = v * KM_S_TO_PC_YR / C_PC_PER_YEAR
        wh = statistics.median(c.wasted_hop_pc)
        sh = statistics.median(c.settle_hop_pc)
        print(f"  {pol:<20}{v:>12.0f}{lam:>12.2e}{wh:>15.2f}{sh:>15.2f}")

    # (4) Completion + waste.
    print("\nEvery connected field still fills to 100%, and waste rises with lag:")
    print(f"  {'policy':<20}{'fills 100%':>12}{'waste% inst':>14}{'waste% ls':>12}")
    for pol in POLICIES:
        c = cells[pol]
        allfill = "yes" if all(c.filled_ls) else f"{sum(c.filled_ls)}/{len(c.filled_ls)}"
        wi = statistics.median(c.waste_ratio_inst) * 100
        wl = statistics.median(c.waste_ratio_ls) * 100
        print(f"  {pol:<20}{allfill:>12}{wi:>13.0f}%{wl:>11.0f}%")

    print(
        "\nReading: Lambda_eff = v/c for the two slingshot policies is within ~1.3x, yet the\n"
        "penalty differs by ~1.5x - Lambda does not set the penalty. The wasted-trip hop\n"
        "length is ~3x longer for max-boost, and that IS the axis the penalty tracks. Powered\n"
        "flight is immune not for lack of long wasted hops but because Lambda ~ 3e-5 is\n"
        "negligible: speed gates whether lag can bite at all, hop-locality sets how hard."
    )


if __name__ == "__main__":
    main()

"""Experiment: what does light-speed-limited coordination cost the swarm?

FRONTIER #1, slice 2. A paired A/B - for each policy, the SAME seeded galaxy is run
under `coordination="instant"` (the paper's perfect global info) and `"lightspeed"` (a
probe knows a distant star is settled only after the news-light arrives). Because the two
modes share the seed, the per-seed difference is attributable to information lag alone;
we report the distribution across a seed ensemble (median + IQR), never a single run.

The result (see the printed table): the penalty is NOT simply Λ = v_probe/c. Powered
nearest-neighbour flight is nearly immune even when fast - a probe that loses a race just
takes the star next door, a cheap recovery. The cost appears when probes make **long-range
hops from stale views** (the slingshot regime): a wasted trip is then a long detour, so the
field fills materially later. Light-speed coordination is a *long-hop / slingshot-era*
phenomenon.

Run:  python -m experiments.lightspeed_coordination      (from the swarm/ package root)
  or  .venv/bin/python experiments/lightspeed_coordination.py
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from swarm import SwarmParams, simulate_swarm

# A fixed, deterministic seed ensemble. 32 distinct galaxies per (policy, mode); the two
# coordination modes share each seed so differences are paired.
SEEDS = [0x9E3779B9 + 2654435761 * k for k in range(32)]
N_STARS = 300  # small enough that even slingshot_maxboost's O(N^2) stays quick over 32×2 runs


@dataclass
class Cell:
    policy: str
    dt100_pct: list[float]      # per-seed % slowdown in t100 (lightspeed vs instant)
    waste_ratio_inst: list[float]  # wasted_arrivals / total_arrivals, instant
    waste_ratio_ls: list[float]    # ... lightspeed
    filled_ls: list[bool]       # did lightspeed still reach 100%?


def _run(policy: str, coordination: str, seed: int) -> object:
    return simulate_swarm(
        SwarmParams(n_stars=N_STARS, policy=policy, coordination=coordination), seed=seed
    )


def run_cell(policy: str) -> Cell:
    dt100, wr_i, wr_l, filled = [], [], [], []
    for seed in SEEDS:
        inst = _run(policy, "instant", seed)
        ls = _run(policy, "lightspeed", seed)
        # t100 is defined for a connected field in both modes; guard just in case.
        if inst.t100_years and ls.t100_years:
            dt100.append((ls.t100_years - inst.t100_years) / inst.t100_years * 100.0)
        wr_i.append(inst.wasted_arrivals / max(1, inst.total_arrivals))
        wr_l.append(ls.wasted_arrivals / max(1, ls.total_arrivals))
        filled.append(ls.final_settled == ls.n_stars)
    return Cell(policy, dt100, wr_i, wr_l, filled)


def _fmt_iqr(xs: list[float]) -> str:
    if not xs:
        return "   n/a"
    xs = sorted(xs)
    med = statistics.median(xs)
    lo = xs[len(xs) // 4]
    hi = xs[(3 * len(xs)) // 4]
    return f"{med:+6.1f}  [{lo:+.1f},{hi:+.1f}]"


def main() -> None:
    print(f"Light-speed coordination cost - {len(SEEDS)} seeds, N={N_STARS} stars, paired A/B\n")
    print(f"{'policy':<20}{'Δt100 % (median [IQR])':<28}{'waste% inst→ls (median)':<26}{'fills 100%'}")
    print("-" * 84)
    for policy in ("powered", "slingshot_nearest", "slingshot_maxboost"):
        c = run_cell(policy)
        wi = statistics.median(c.waste_ratio_inst) * 100
        wl = statistics.median(c.waste_ratio_ls) * 100
        allfill = "yes" if all(c.filled_ls) else f"{sum(c.filled_ls)}/{len(c.filled_ls)}"
        print(f"{policy:<20}{_fmt_iqr(c.dt100_pct):<28}{f'{wi:.0f}% → {wl:.0f}%':<26}{allfill}")
    print(
        "\nReading: powered flight pays ~no timescale penalty (local recovery); the slingshot\n"
        "policies fill materially later under light-speed lag - the cost of long-range hops\n"
        "made from stale views. A connected field still reaches 100% in every case (no Aurora\n"
        "plateau from lag alone). Λ ≈ v/c sets the scale, hop-nonlocality decides if it bites."
    )


if __name__ == "__main__":
    main()

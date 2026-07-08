"""Generate the two publication figures for papers/coordination-tax/.

Every number plotted here is produced by the validated swarm fold (CLAUDE.md 1): we
import the real experiment (`lightspeed_coordination`) and the real `simulate_swarm`
fold - nothing is hardcoded or invented. The fold is a pure, seeded, deterministic
function of (params, seed), and the seed ensemble (`SEEDS`) and star count are fixed,
so both PDFs are bit-reproducible run to run.

Figures (vector PDF, IEEE single-column geometry, serif fonts):
  (a) fig_slowdown_by_policy.pdf - box + strip of the 32 per-seed % fill-time penalties
      from light-speed lag, for the three policies.
  (b) fig_settlement_curves.pdf - fraction of the field settled vs year on one
      representative seed for slingshot_nearest, perfect-info vs light-speed-limited.

Run (from the swarm/ package root):
    uv run --extra dev python -m experiments.paper_figures
"""

from __future__ import annotations

import statistics
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")  # deterministic, headless, file-only backend
import matplotlib.pyplot as plt

from swarm import SwarmParams, simulate_swarm

from experiments.lightspeed_coordination import N_STARS, SEEDS, run_cell

# --- IEEE single-column geometry + serif fonts (drops into a two-column IEEEtran paper) ---
COLW = 3.5
GOLDEN = (5**0.5 - 1) / 2
mpl.rcParams.update(
    {
        "font.family": "serif",
        "mathtext.fontset": "cm",
        "axes.labelsize": 9,
        "font.size": 9,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.titlesize": 9,
        "lines.linewidth": 1.0,
        "axes.linewidth": 0.6,
        "figure.dpi": 150,
    }
)

# papers/coordination-tax/ resolved from this file: .../swarm/experiments/paper_figures.py
#   parents[0] = experiments, parents[1] = swarm, parents[2] = repo root.
OUT_DIR = Path(__file__).resolve().parents[2] / "papers" / "coordination-tax"

# The three policies, in the paper's order, with readable axis labels.
POLICIES = [
    ("powered", "powered"),
    ("slingshot_nearest", "slingshot\nnearest"),
    ("slingshot_maxboost", "slingshot\nmax-boost"),
]


def _iqr(xs: list[float]) -> tuple[float, float, float]:
    """Median and quartiles matching lightspeed_coordination._fmt_iqr (32 seeds)."""
    xs = sorted(xs)
    med = statistics.median(xs)
    lo = xs[len(xs) // 4]
    hi = xs[(3 * len(xs)) // 4]
    return med, lo, hi


def fig_slowdown_by_policy() -> tuple[Path, dict[str, tuple[float, float, float]]]:
    """(a) Distribution of per-seed % fill-time penalty from light-speed lag, per policy."""
    # Pull the real per-seed % slowdown lists straight from the experiment.
    per_seed = {pol: run_cell(pol).dt100_pct for pol, _ in POLICIES}

    data = [per_seed[pol] for pol, _ in POLICIES]
    labels = [lab for _, lab in POLICIES]

    fig, ax = plt.subplots(figsize=(COLW, COLW * 0.85))  # a touch taller than golden

    positions = list(range(1, len(data) + 1))
    ax.boxplot(
        data,
        positions=positions,
        widths=0.55,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.2},
        boxprops={"linewidth": 0.8},
        whiskerprops={"linewidth": 0.8},
        capprops={"linewidth": 0.8},
    )
    # Overlay the 32 raw per-seed points (deterministic horizontal jitter, seeded offsets).
    for pos, ys in zip(positions, data):
        n = len(ys)
        # Evenly spread offsets in [-0.18, 0.18]; deterministic, no RNG.
        offs = [(-0.18 + 0.36 * i / (n - 1)) if n > 1 else 0.0 for i in range(n)]
        xs = [pos + o for o in offs]
        ax.plot(xs, ys, linestyle="none", marker="o", markersize=2.0,
                markerfacecolor="0.35", markeredgecolor="none", alpha=0.55)

    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_ylabel("fill-time penalty from light-speed lag (%)")
    ax.axhline(0.0, color="0.6", linewidth=0.6, linestyle="--", zorder=0)
    ax.margins(x=0.08)
    fig.tight_layout()

    out = OUT_DIR / "fig_slowdown_by_policy.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)

    # Report the medians/IQRs actually computed this run.
    stats = {pol: _iqr(per_seed[pol]) for pol, _ in POLICIES}
    return out, stats


def fig_settlement_curves() -> tuple[Path, tuple[float, float]]:
    """(b) Fraction settled vs year, one seed, slingshot_nearest: instant vs lightspeed."""
    seed = SEEDS[0]
    inst = simulate_swarm(
        SwarmParams(n_stars=N_STARS, policy="slingshot_nearest", coordination="instant"),
        seed=seed,
    )
    ls = simulate_swarm(
        SwarmParams(n_stars=N_STARS, policy="slingshot_nearest", coordination="lightspeed"),
        seed=seed,
    )

    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))

    for res, label, style in (
        (inst, "perfect information", {"color": "0.15", "linestyle": "-"}),
        (ls, "light-speed limited", {"color": "0.15", "linestyle": "--"}),
    ):
        years = [s.year for s in res.steps]
        frac = [s.fraction_settled * 100.0 for s in res.steps]
        ax.plot(years, frac, label=label, **style)

    ax.set_xlabel("year")
    ax.set_ylabel("fraction of field settled (%)")
    ax.set_ylim(0, 100)
    ax.set_xlim(left=0)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()

    out = OUT_DIR / "fig_settlement_curves.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)

    return out, (inst.t100_years, ls.t100_years)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing figures to {OUT_DIR}  (N={N_STARS} stars, {len(SEEDS)} seeds)\n")

    out_a, stats = fig_slowdown_by_policy()
    print(f"[a] {out_a.name}")
    for pol, _ in POLICIES:
        med, lo, hi = stats[pol]
        print(f"      {pol:<20} median {med:+6.1f}%  IQR [{lo:+.1f}, {hi:+.1f}]")

    out_b, (t100_inst, t100_ls) = fig_settlement_curves()
    print(f"[b] {out_b.name}")
    print(f"      slingshot_nearest, seed=SEEDS[0]={SEEDS[0]}")
    print(f"      t100 instant   = {t100_inst:,.0f} yr")
    print(f"      t100 lightspeed = {t100_ls:,.0f} yr")
    print(f"      shift = {(t100_ls - t100_inst) / t100_inst * 100:+.1f}%")


if __name__ == "__main__":
    main()

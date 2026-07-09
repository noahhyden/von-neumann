"""Generate the publication figures and headline statistics for papers/coordination-tax/.

Every number plotted or printed here is produced by the validated swarm fold (CLAUDE.md
1): we import the real experiments (`lightspeed_coordination`, `finite_size`) and the real
`simulate_swarm` fold - nothing is hardcoded or invented. The fold is a pure, seeded,
deterministic function of (params, seed), and the seed ensemble and star counts are fixed,
so every PDF and every printed statistic is bit-reproducible run to run.

Figures (vector PDF, IEEE single-column geometry, serif fonts):
  (a) fig_slowdown_by_policy.pdf  - box + strip of the 32 per-seed fill-100% penalties, per policy.
  (b) fig_settlement_curves.pdf   - fraction settled vs year, one seed, slingshot_nearest,
                                    perfect-info vs light-speed-limited.
  (c) fig_penalty_by_coverage.pdf - median penalty at t25..t100, per policy (the shift is
                                    present across the whole fill, not just the fragile tail).
  (d) fig_finite_size.pdf         - median fill-100% penalty vs system size N, per policy.

Printed to stdout: the medians, IQRs, bootstrap 95% CIs and sign-test p-values, the
per-coverage-fraction penalties, the effective speeds / Lambda / hop lengths, and the
finite-size table - i.e. every quantity the paper restates.

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
from swarm.models import C_PC_PER_YEAR, KM_S_TO_PC_YR

from experiments.finite_size import FS_N, FS_SEEDS, run_finite_size
from experiments.lightspeed_coordination import COVERAGE, N_STARS, SEEDS, Cell, run_cell
from experiments.stats_util import bootstrap_median_ci, sign_test_positive

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

# The three policies, in the paper's order, with readable labels and print-safe styling
# (grayscale + linestyle + marker, so the multi-line figures survive a monochrome print).
POLICIES = [
    ("powered", "powered", {"color": "0.6", "linestyle": ":", "marker": "o"}),
    ("slingshot_nearest", "slingshot\nnearest", {"color": "0.4", "linestyle": "--", "marker": "s"}),
    ("slingshot_maxboost", "slingshot\nmax-boost", {"color": "0.0", "linestyle": "-", "marker": "^"}),
]
# Nice single-line labels for the legend of the line figures.
LEGEND = {"powered": "powered", "slingshot_nearest": "slingshot nearest", "slingshot_maxboost": "slingshot max-boost"}


def _iqr(xs: list[float]) -> tuple[float, float, float]:
    """Median and quartiles matching lightspeed_coordination._iqr (32 seeds)."""
    xs = sorted(xs)
    med = statistics.median(xs)
    lo = xs[len(xs) // 4]
    hi = xs[(3 * len(xs)) // 4]
    return med, lo, hi


def fig_slowdown_by_policy(cells: dict[str, Cell]) -> Path:
    """(a) Distribution of per-seed % fill-100% penalty from light-speed lag, per policy."""
    data = [cells[pol].pen["t100"] for pol, _, _ in POLICIES]
    labels = [lab for _, lab, _ in POLICIES]

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
    # Overlay the 32 raw per-seed points (deterministic horizontal spread, no RNG).
    for pos, ys in zip(positions, data):
        n = len(ys)
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
    return out


def fig_penalty_by_coverage(cells: dict[str, Cell]) -> Path:
    """(c) Median penalty at each coverage fraction, per policy (not just the t100 tail)."""
    xfrac = [int(k[1:]) for k in COVERAGE]  # 25, 50, 75, 90, 99, 100

    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    for pol, _, style in POLICIES:
        ys = [statistics.median(cells[pol].pen[k]) for k in COVERAGE]
        ax.plot(xfrac, ys, label=LEGEND[pol], markersize=3.5, **style)
    ax.set_xlabel("coverage fraction settled (%)")
    ax.set_ylabel("median fill-time penalty (%)")
    ax.axhline(0.0, color="0.6", linewidth=0.6, linestyle="--", zorder=0)
    ax.set_ylim(bottom=-5)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()

    out = OUT_DIR / "fig_penalty_by_coverage.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out


def fig_settlement_curves() -> tuple[Path, tuple[float, float]]:
    """(b) Fraction settled vs year, one seed, slingshot_nearest: instant vs lightspeed."""
    seed = SEEDS[0]
    inst = simulate_swarm(SwarmParams(n_stars=N_STARS, policy="slingshot_nearest", coordination="instant"), seed=seed)
    ls = simulate_swarm(SwarmParams(n_stars=N_STARS, policy="slingshot_nearest", coordination="lightspeed"), seed=seed)

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


def fig_finite_size(fs_data: dict) -> Path:
    """(d) Median fill-100% penalty vs system size N, per policy (with IQR band)."""
    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    for pol, _, style in POLICIES:
        pts = fs_data[pol]
        ns = [p.n_stars for p in pts]
        med = [p.pen_median for p in pts]
        lo = [p.pen_lo for p in pts]
        hi = [p.pen_hi for p in pts]
        ax.fill_between(ns, lo, hi, color=style["color"], alpha=0.12, linewidth=0)
        ax.plot(ns, med, label=LEGEND[pol], markersize=3.5, **style)
    ax.set_xlabel("system size (number of stars)")
    ax.set_ylabel("median fill-100% penalty (%)")
    ax.axhline(0.0, color="0.6", linewidth=0.6, linestyle="--", zorder=0)
    ax.set_ylim(bottom=-5)
    ax.legend(loc="center left", frameon=False)
    fig.tight_layout()

    out = OUT_DIR / "fig_finite_size.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing figures to {OUT_DIR}  (N={N_STARS} stars, {len(SEEDS)} seeds)\n")

    # One 32-seed paired ensemble, reused by figures (a) and (c) and every printed statistic.
    cells = {pol: run_cell(pol) for pol, _, _ in POLICIES}

    out_a = fig_slowdown_by_policy(cells)
    out_c = fig_penalty_by_coverage(cells)
    out_b, (t100_inst, t100_ls) = fig_settlement_curves()

    # (d) finite-size sweep (its own, smaller seed set / larger N).
    fs_data = run_finite_size()
    out_d = fig_finite_size(fs_data)

    print(f"[a] {out_a.name}   [b] {out_b.name}   [c] {out_c.name}   [d] {out_d.name}\n")

    # ---- Headline: fill-100% penalty with spread, bootstrap CI, sign test ----
    print("Fill-100% penalty  (median, IQR, bootstrap 95% CI, seeds-positive/nonzero, sign-test p):")
    for pol, _, _ in POLICIES:
        xs = cells[pol].pen["t100"]
        med, lo, hi = _iqr(xs)
        _, blo, bhi = bootstrap_median_ci(xs)
        k, n, p = sign_test_positive(xs)
        print(f"  {pol:<20} {med:+5.1f}%  IQR [{lo:+.1f},{hi:+.1f}]  CI [{blo:+.1f},{bhi:+.1f}]  "
              f"{k}/{n} pos  p={p:.2e}")

    # ---- Penalty across coverage fractions ----
    print("\nMedian penalty by coverage fraction (%):")
    print(f"  {'policy':<20}" + "".join(f"{k:>8}" for k in COVERAGE))
    for pol, _, _ in POLICIES:
        row = "".join(f"{statistics.median(cells[pol].pen[k]):>+8.1f}" for k in COVERAGE)
        print(f"  {pol:<20}{row}")

    # ---- Mechanism: effective speed (Lambda) vs wasted-hop length (locality) ----
    print("\nMechanism (lightspeed, median over seeds):")
    print(f"  {'policy':<20}{'v_eff km/s':>12}{'Lambda_eff':>12}{'wasted hop pc':>15}{'settle hop pc':>15}")
    for pol, _, _ in POLICIES:
        c = cells[pol]
        v = statistics.median(c.v_eff_km_s)
        lam = v * KM_S_TO_PC_YR / C_PC_PER_YEAR
        print(f"  {pol:<20}{v:>12.0f}{lam:>12.2e}{statistics.median(c.wasted_hop_pc):>15.2f}"
              f"{statistics.median(c.settle_hop_pc):>15.2f}")

    # ---- Finite-size table ----
    print(f"\nFinite-size scaling (fill-100% penalty %, {len(FS_SEEDS)} seeds, N in {FS_N}):")
    print(f"  {'policy':<20}" + "".join(f"{f'N={n}':>18}" for n in FS_N))
    for pol, _, _ in POLICIES:
        row = "".join(f"{p.pen_median:+.1f} [{p.pen_lo:+.0f},{p.pen_hi:+.0f}]".rjust(18) for p in fs_data[pol])
        print(f"  {pol:<20}{row}")

    # ---- Settlement-curve figure anchor ----
    print(f"\nSettlement curve (slingshot_nearest, seed=SEEDS[0]={SEEDS[0]}):")
    print(f"  t100 instant   = {t100_inst:,.0f} yr")
    print(f"  t100 lightspeed = {t100_ls:,.0f} yr   shift = {(t100_ls - t100_inst) / t100_inst * 100:+.1f}%")


if __name__ == "__main__":
    main()

"""Generate the publication figures and headline statistics for papers/coordination-tax/.

Every number plotted or printed here is produced by the validated swarm fold (CLAUDE.md 1):
we import the real experiments and the real `simulate_swarm` fold - all at the resolved
`stepping="event"` timestep - and nothing is hardcoded. The fold is a pure, seeded,
deterministic function of (params, seed), and the seed ensemble and star counts are fixed, so
every PDF and every printed statistic is bit-reproducible run to run.

Figures (vector PDF, IEEE single-column geometry, serif fonts):
  (a) fig_fuel_tax_vs_lambda.pdf - the headline scaling law: redundant-travel (fuel) tax and
      fill-time tax vs Lambda = v/c, powered flight, event mode.
  (b) fig_time_tax_vs_dt.pdf     - the fill-time tax collapsing to ~0 as the timestep resolves
      (the coarse-dt "coordination tax" is a discretization artifact).
  (c) fig_fuel_tax_by_seed.pdf   - per-seed fuel tax at slingshot vs directed-energy speed
      (box + strip): robust and positive in every seed at high v/c.
  (d) fig_fuel_tax_vs_n.pdf      - the fuel tax is a scale-stable fraction (~18-19%) of effort.

Run (from the swarm/ package root):
    uv run --extra dev python -m experiments.paper_figures
"""

from __future__ import annotations

import statistics
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

from swarm.models import C_PC_PER_YEAR, KM_S_TO_PC_YR

from experiments.dt_artifact import DTS, _median_time_penalty
from experiments.finite_size import run_finite_size
from experiments.lightspeed_coordination import LAMBDAS, SEEDS, run_paired, summary

COLW = 3.5
GOLDEN = (5**0.5 - 1) / 2
mpl.rcParams.update({
    "font.family": "serif", "mathtext.fontset": "cm",
    "axes.labelsize": 9, "font.size": 9, "legend.fontsize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.titlesize": 9,
    "lines.linewidth": 1.0, "axes.linewidth": 0.6, "figure.dpi": 150,
})

OUT_DIR = Path(__file__).resolve().parents[2] / "papers" / "coordination-tax"


def fig_fuel_tax_vs_lambda(sweep: dict) -> tuple[Path, dict]:
    """(a) Fuel tax and time tax (median + 95% CI) vs Lambda = v/c."""
    lam = list(LAMBDAS)
    fuel = [summary(sweep[l].fuel_pct) for l in lam]
    time = [summary(sweep[l].time_pct) for l in lam]
    fmed = [s[0] for s in fuel]; ferr = [[s[0] - s[3] for s in fuel], [s[4] - s[0] for s in fuel]]
    tmed = [s[0] for s in time]; terr = [[s[0] - s[3] for s in time], [s[4] - s[0] for s in time]]

    fig, ax = plt.subplots(figsize=(COLW, COLW * 0.8))
    ax.errorbar(lam, fmed, yerr=ferr, marker="o", markersize=3.5, color="0.0",
                capsize=2, linewidth=1.0, label="fuel (wasted journeys)")
    ax.errorbar(lam, tmed, yerr=terr, marker="s", markersize=3.5, color="0.55",
                linestyle="--", capsize=2, linewidth=1.0, label="fill time")
    ax.set_xscale("log")
    ax.set_xlabel(r"probe speed $\Lambda = v/c$")
    ax.set_ylabel("coordination tax (% over perfect info)")
    ax.axhline(0.0, color="0.6", linewidth=0.6, linestyle=":", zorder=0)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    out = OUT_DIR / "fig_fuel_tax_vs_lambda.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out, {l: (summary(sweep[l].fuel_pct), summary(sweep[l].time_pct)) for l in lam}


def fig_time_tax_vs_dt() -> tuple[Path, list]:
    """(b) Fill-time tax vs timestep, collapsing to ~0 at the resolved limit."""
    rows = [(dt, _median_time_penalty(dt)) for dt in DTS]
    ev = _median_time_penalty(None)
    xs = [dt for dt, _ in rows]
    ys = [r[0] for _, r in rows]

    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    ax.plot(xs, ys, marker="o", markersize=3.5, color="0.0")
    ax.axhline(ev[0], color="0.5", linewidth=0.8, linestyle="--",
               label=f"event (dt$\\to$0): {ev[0]:+.1f}%")
    ax.set_xscale("log")
    ax.set_xlabel("fixed timestep dt (years)")
    ax.set_ylabel("fill-100% time tax (%)")
    ax.axhline(0.0, color="0.7", linewidth=0.6, linestyle=":", zorder=0)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    out = OUT_DIR / "fig_time_tax_vs_dt.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out, rows + [("event", ev)]


def fig_fuel_tax_by_seed(sweep: dict) -> Path:
    """(c) Per-seed fuel tax at slingshot (Lambda~0.01) vs directed-energy (Lambda=0.2)."""
    data = [sweep[0.01].fuel_pct, sweep[0.1].fuel_pct, sweep[0.2].fuel_pct]
    labels = [r"$\Lambda$=0.01" + "\n(slingshot)", r"$\Lambda$=0.1", r"$\Lambda$=0.2" + "\n(dir.-energy)"]
    fig, ax = plt.subplots(figsize=(COLW, COLW * 0.8))
    pos = list(range(1, len(data) + 1))
    ax.boxplot(data, positions=pos, widths=0.55, showfliers=False,
               medianprops={"color": "black", "linewidth": 1.2},
               boxprops={"linewidth": 0.8}, whiskerprops={"linewidth": 0.8},
               capprops={"linewidth": 0.8})
    for p, ys in zip(pos, data):
        n = len(ys)
        offs = [(-0.18 + 0.36 * i / (n - 1)) if n > 1 else 0.0 for i in range(n)]
        ax.plot([p + o for o in offs], ys, linestyle="none", marker="o", markersize=2.0,
                markerfacecolor="0.35", markeredgecolor="none", alpha=0.55)
    ax.set_xticks(pos); ax.set_xticklabels(labels)
    ax.set_ylabel("fuel tax: extra wasted journeys (%)")
    ax.axhline(0.0, color="0.6", linewidth=0.6, linestyle="--", zorder=0)
    fig.tight_layout()
    out = OUT_DIR / "fig_fuel_tax_by_seed.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out


def fig_fuel_tax_vs_n() -> tuple[Path, list]:
    """(d) Fuel tax (% of waste) vs system size at Lambda=0.2 - a scale-stable fraction."""
    pts = list(run_finite_size())
    ns = [p.n_stars for p in pts]
    med = [p.fuel_pct_median for p in pts]
    lo = [p.fuel_pct_lo for p in pts]
    hi = [p.fuel_pct_hi for p in pts]
    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    ax.fill_between(ns, lo, hi, color="0.0", alpha=0.12, linewidth=0)
    ax.plot(ns, med, marker="o", markersize=3.5, color="0.0")
    ax.set_xlabel("system size (number of stars)")
    ax.set_ylabel("fuel tax (% of perfect-info waste)")
    ax.set_ylim(0, max(hi) * 1.3)
    fig.tight_layout()
    out = OUT_DIR / "fig_fuel_tax_vs_n.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out, pts


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing figures to {OUT_DIR}  ({len(SEEDS)} seeds, event timestep)\n")

    sweep = {l: run_paired("powered", probe_speed_c=l) for l in LAMBDAS}  # reused by (a) and (c)
    print("  [sweep done]", flush=True)

    out_a, stats_a = fig_fuel_tax_vs_lambda(sweep)
    out_c = fig_fuel_tax_by_seed(sweep)
    print("  [figs a, c done]", flush=True)
    out_b, rows_b = fig_time_tax_vs_dt()
    print("  [fig b done]", flush=True)
    out_d, pts_d = fig_fuel_tax_vs_n()
    print("  [fig d done]", flush=True)

    print(f"[a] {out_a.name}   [b] {out_b.name}   [c] {out_c.name}   [d] {out_d.name}\n")

    print("Fuel + time tax vs Lambda (median, 95% CI, sign-test p):")
    for l in LAMBDAS:
        (fm, _, _, flo, fhi, fp), (tm, _, _, tlo, thi, tp) = stats_a[l]
        print(f"  Lambda={l:<5} fuel {fm:+5.1f}% CI[{flo:+.1f},{fhi:+.1f}] p={fp:.1e}   "
              f"time {tm:+5.1f}% CI[{tlo:+.1f},{thi:+.1f}] p={tp:.1e}")

    print("\nFill-time tax vs timestep (median %):")
    for tag, r in rows_b:
        label = f"dt={tag:.0f}" if isinstance(tag, float) else tag
        print(f"  {label:<12} {r[0]:+.1f}%  seeds+ {r[3]}/{r[4]}")

    print("\nFuel tax vs N at Lambda=0.2 (% of waste, and absolute):")
    for p in pts_d:
        print(f"  N={p.n_stars:<5} {p.fuel_pct_median:+.1f}% [{p.fuel_pct_lo:+.1f},{p.fuel_pct_hi:+.1f}]  "
              f"abs {p.fuel_abs_median:+.0f}  time {p.time_pct_median:+.1f}%  seeds+ {p.seeds_positive}/{p.seeds}")

    # Where the natural policies sit on the Lambda axis (connective text only; cheap subset -
    # maxboost is O(N^2) per run in event mode, so use a small field and few seeds here).
    print("\nNatural-policy anchors (event, N=200, 8 seeds):")
    for pol in ("powered", "slingshot_nearest", "slingshot_maxboost"):
        c = run_paired(pol, n_stars=200, seeds=SEEDS[:8])
        v = statistics.median(c.v_eff_km_s)
        lam = v * KM_S_TO_PC_YR / C_PC_PER_YEAR
        fm, _, _, _, _, fp = summary(c.fuel_pct)
        print(f"  {pol:<20} v_eff={v:>8.0f} km/s  Lambda={lam:.2e}  fuel {fm:+.1f}% p={fp:.1e}")


if __name__ == "__main__":
    main()

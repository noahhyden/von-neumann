"""Render the publication figures for papers/coordination-tax/ from committed JSON results.

This step is CHEAP and CI-safe: it reads the deterministic result artifacts written by the
heavy local run (``experiments/measure.py`` -> ``experiments/results/*.json``) and draws the
figures. It runs NO simulation. The heavy ensemble stays local (it would overwhelm the CI
runners); the paper and these figures restate only the committed numbers, and a drift-guard
test (``tests/test_measure_results.py``) re-runs a tiny slice to prove the JSON still matches
the fold. Regenerating the numbers is ``python -m experiments.measure`` (see that module).

Figures (vector PDF, IEEE single-column geometry, serif fonts):
  fig_fuel_tax_vs_lambda.pdf - headline: fuel + fill-time tax vs Lambda=v/c, with the derived
                               law tax=Lambda overlaid (the data sit on it)
  fig_fuel_tax_by_seed.pdf   - per-seed fuel tax at slingshot vs directed-energy speed (spread)
  fig_time_tax_vs_dt.pdf     - the fill-time tax collapsing to ~0 as the fixed timestep resolves
  fig_branching.pdf          - fuel tax vs the replication branching factor (offspring 2/3/4)
  fig_floor_bracket.pdf      - instant/inflight/lightspeed: how much survives in-flight relay
  fig_concurrency.pdf        - probes in flight vs coverage: why a loser is off the critical path
  fig_fuel_tax_vs_n.pdf      - fuel tax % over a 16x size span (scale-stable, tested range only)

Run (from the swarm/ package root):
    uv run --extra dev python -m experiments.paper_figures
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator

RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUT_DIR = Path(__file__).resolve().parents[2] / "papers" / "coordination-tax"

COLW = 3.5
GOLDEN = (5**0.5 - 1) / 2
mpl.rcParams.update({
    "font.family": "serif", "mathtext.fontset": "cm",
    "axes.labelsize": 9, "font.size": 9, "legend.fontsize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.titlesize": 9,
    "lines.linewidth": 1.0, "axes.linewidth": 0.6, "figure.dpi": 150,
})


def load(name: str) -> dict:
    path = RESULTS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path.name}; run `uv run --extra dev python -m experiments.measure {name}` first")
    return json.loads(path.read_text())


def _save(fig, name: str) -> Path:
    out = OUT_DIR / name
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out


def _pct(treat, base):
    return (treat - base) / base * 100.0 if base else None


def _err(summ: list[dict]) -> list[list[float]]:
    """Asymmetric error bars (median-to-CI) from a list of summary dicts."""
    med = [s["median"] for s in summ]
    return [[m - s["ci_lo"] for m, s in zip(med, summ)], [s["ci_hi"] - m for m, s in zip(med, summ)]]


def _clean_log_x(ax, xs) -> None:
    """Label a log x-axis at exactly the data points and drop the minor ticks.

    A log axis spanning only ~1 decade (our dt and size sweeps) otherwise auto-labels
    dense minor ticks (2,3,..,9 x 10^n) that collide and overprint. We instead place major
    ticks at the actual swept values with plain labels and remove the minor ticks entirely.
    """
    ax.set_xticks(list(xs))
    ax.set_xticklabels([f"{x:g}" for x in xs])
    ax.xaxis.set_minor_locator(NullLocator())


# --------------------------------------------------------------------------------------------

def fig_fuel_tax_vs_lambda() -> Path:
    d = load("lambda_sweep")
    lam = d["config"]["lambdas"]
    fuel = [d["data"][str(l)]["fuel_pct"] for l in lam]
    time = [d["data"][str(l)]["time_pct"] for l in lam]
    fmed = [s["median"] for s in fuel]
    tmed = [s["median"] for s in time]
    fig, ax = plt.subplots(figsize=(COLW, COLW * 0.8))
    # Derived law: the wasted-journey fraction equals Lambda (see the theory subsection), i.e.
    # tax% = 100*Lambda. Drawn on a fine log-spaced grid (NOT two points: a 2-point line renders
    # straight in pixel space on a log axis and misrepresents the curve) so the data sit on it.
    lo, hi = min(lam) * 0.8, max(lam) * 1.15
    grid = [lo * (hi / lo) ** (i / 60.0) for i in range(61)]
    ax.plot(grid, [100 * g for g in grid], color="0.5", linestyle="-", linewidth=0.9,
            zorder=1, label=r"derived: tax $=\Lambda$")
    ax.errorbar(lam, fmed, yerr=_err(fuel), marker="o", markersize=3.5, color="0.0",
                capsize=2, linewidth=0, elinewidth=1.0, zorder=3, label="fuel (wasted journeys)")
    ax.errorbar(lam, tmed, yerr=_err(time), marker="s", markersize=3.5, color="0.55",
                linestyle="--", capsize=2, linewidth=1.0, zorder=2, label="fill time")
    ax.set_xscale("log")
    _clean_log_x(ax, lam)
    ax.set_xlabel(r"probe speed $\Lambda = v/c$")
    ax.set_ylabel("coordination tax (%)")
    ax.axhline(0.0, color="0.6", linewidth=0.6, linestyle=":", zorder=0)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    return _save(fig, "fig_fuel_tax_vs_lambda.pdf")


def fig_fuel_tax_by_seed() -> Path:
    d = load("lambda_sweep")

    def per_seed_fuel(l):
        rows = d["data"][str(l)]["per_seed"]
        return [v for v in (_pct(r["treat"]["wasted_arrivals"], r["base"]["wasted_arrivals"]) for r in rows) if v is not None]

    picks = [l for l in (0.01, 0.1, 0.2) if str(l) in d["data"]]
    data = [per_seed_fuel(l) for l in picks]
    labels = {0.01: r"$\Lambda$=0.01" + "\n(slingshot)", 0.1: r"$\Lambda$=0.1", 0.2: r"$\Lambda$=0.2" + "\n(dir.-energy)"}
    fig, ax = plt.subplots(figsize=(COLW, COLW * 0.8))
    pos = list(range(1, len(data) + 1))
    ax.boxplot(data, positions=pos, widths=0.55, showfliers=False,
               medianprops={"color": "black", "linewidth": 1.2},
               boxprops={"linewidth": 0.8}, whiskerprops={"linewidth": 0.8}, capprops={"linewidth": 0.8})
    for p, ys in zip(pos, data):
        n = len(ys)
        offs = [(-0.18 + 0.36 * i / (n - 1)) if n > 1 else 0.0 for i in range(n)]
        ax.plot([p + o for o in offs], ys, linestyle="none", marker="o", markersize=2.0,
                markerfacecolor="0.35", markeredgecolor="none", alpha=0.55)
    ax.set_xticks(pos)
    ax.set_xticklabels([labels[l] for l in picks])
    ax.set_ylabel("fuel tax: extra wasted journeys (%)")
    ax.axhline(0.0, color="0.6", linewidth=0.6, linestyle="--", zorder=0)
    fig.tight_layout()
    return _save(fig, "fig_fuel_tax_by_seed.pdf")


def fig_time_tax_vs_dt() -> Path:
    d = load("dt_artifact")
    rows = [r for r in d["rows"] if r["dt"] is not None]
    ev = next(r for r in d["rows"] if r["dt"] is None)
    xs = [r["dt"] for r in rows]
    ys = [r["time_pct"]["median"] for r in rows]
    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    ax.plot(xs, ys, marker="o", markersize=3.5, color="0.0")
    ax.axhline(ev["time_pct"]["median"], color="0.5", linewidth=0.8, linestyle="--",
               label=f"event (dt$\\to$0): {ev['time_pct']['median']:+.1f}%")
    ax.set_xscale("log")
    _clean_log_x(ax, xs)
    ax.set_xlabel("fixed timestep dt (years)")
    ax.set_ylabel("fill-100% time tax (%)")
    ax.axhline(0.0, color="0.7", linewidth=0.6, linestyle=":", zorder=0)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    return _save(fig, "fig_time_tax_vs_dt.pdf")


def fig_branching() -> Path:
    d = load("branching")
    offs = d["config"]["offspring"]
    lambdas = d["config"]["lambdas"]
    fig, ax = plt.subplots(figsize=(COLW, COLW * 0.8))
    markers = ["o", "s", "^"]
    for lam, mk, col in zip(lambdas, markers, ["0.0", "0.4", "0.6"]):
        summ = [d["data"][f"lam{lam}_off{o}"]["fuel_pct"] for o in offs]
        med = [s["median"] for s in summ]
        ax.errorbar(offs, med, yerr=_err(summ), marker=mk, markersize=4, color=col,
                    capsize=2, linewidth=1.0, label=rf"$\Lambda$={lam}")
    ax.set_xlabel("branching factor (offspring per settlement)")
    ax.set_ylabel("fuel tax: extra wasted journeys (%)")
    ax.set_xticks(offs)
    ax.axhline(0.0, color="0.6", linewidth=0.6, linestyle=":", zorder=0)
    ax.legend(loc="best", frameon=False)
    fig.tight_layout()
    return _save(fig, "fig_branching.pdf")


def fig_floor_bracket() -> Path:
    d = load("floor_bracket")
    lambdas = d["config"]["lambdas"]
    modes = ["instant", "lightspeed", "inflight"]
    colors = {"instant": "0.75", "lightspeed": "0.15", "inflight": "0.45"}
    labels = {"instant": "perfect info", "lightspeed": "decision-site", "inflight": "in-flight relay"}
    fig, ax = plt.subplots(figsize=(COLW, COLW * 0.8))
    x = list(range(len(lambdas)))
    w = 0.26
    bar_max = 0.0
    for j, m in enumerate(modes):
        vals = [d["data"][str(l)]["wasted_travel_pc_median"][m] for l in lambdas]
        bar_max = max(bar_max, *vals)
        ax.bar([xi + (j - 1) * w for xi in x], vals, w, color=colors[m], label=labels[m])
    ax.set_xticks(x)
    ax.set_xticklabels([rf"$\Lambda$={l}" for l in lambdas])
    ax.set_ylabel("redundant travel (pc, median)")
    ax.set_ylim(0, bar_max * 1.06)
    # Every bar is tall, so there is no clear interior space: put the legend in one row ABOVE the axes.
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.00), ncol=3, frameon=False, fontsize=7,
              handlelength=1.1, columnspacing=1.2, handletextpad=0.4)
    fig.tight_layout()
    return _save(fig, "fig_floor_bracket.pdf")


def fig_concurrency() -> Path:
    d = load("concurrency")
    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    for mode, col, ls in (("instant", "0.55", "--"), ("lightspeed", "0.0", "-")):
        cov = d["data"][mode]["coverage"]
        inf = d["data"][mode]["in_flight_median"]
        pts = [(c, v) for c, v in zip(cov, inf) if v is not None]
        ax.plot([c for c, _ in pts], [v for _, v in pts], color=col, linestyle=ls,
                marker="o", markersize=2.5, label=mode)
    ax.set_xlabel("coverage fraction settled")
    ax.set_ylabel("probes in flight (median)")
    ax.legend(loc="best", frameon=False)
    fig.tight_layout()
    return _save(fig, "fig_concurrency.pdf")


def fig_fuel_tax_vs_n() -> Path:
    d = load("finite_size")
    ns = sorted(int(k) for k in d["data"])
    summ = [d["data"][str(n)]["fuel_pct"] for n in ns]
    med = [s["median"] for s in summ]
    lo = [s["ci_lo"] for s in summ]
    hi = [s["ci_hi"] for s in summ]
    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    ax.fill_between(ns, lo, hi, color="0.0", alpha=0.12, linewidth=0)
    ax.plot(ns, med, marker="o", markersize=3.5, color="0.0")
    ax.set_xscale("log")
    _clean_log_x(ax, ns)
    ax.set_xlabel("system size (number of stars)")
    ax.set_ylabel("fuel tax (%)")
    ax.set_ylim(0, max(hi) * 1.3)
    fig.tight_layout()
    return _save(fig, "fig_fuel_tax_vs_n.pdf")


def fig_fuel_tax_vs_clumpiness() -> Path:
    d = load("clumpiness")
    levels = d["config"]["levels"]
    R = [d["data"][lb]["clumpiness_R"] for lb in levels]
    a = [d["data"][lb]["slope_median"] for lb in levels]
    lo = [d["data"][lb]["slope_median"] - d["data"][lb]["slope_ci_lo"] for lb in levels]
    hi = [d["data"][lb]["slope_ci_hi"] - d["data"][lb]["slope_median"] for lb in levels]
    fig, ax = plt.subplots(figsize=(COLW, COLW * 0.8))
    # Derived law: tax = Lambda, i.e. slope a = 1. The data soften BELOW it (never above), so the
    # law is a conservative upper bound; only extreme substructure (low R) drops a resolvably.
    ax.axhline(1.0, color="0.5", linestyle="-", linewidth=0.9, zorder=1,
               label=r"derived: tax $=\Lambda$ ($a=1$)")
    ax.errorbar(R, a, yerr=[lo, hi], marker="o", markersize=3.5, color="0.0",
                capsize=2, linewidth=0, elinewidth=1.0, zorder=3)
    # Mark the uniform null (R ~ 1) - the generator's hard correctness check. Place it in the top
    # headroom with a thin leader to the point, clear of the error-bar cap it used to overlap.
    ax.annotate("uniform", xy=(R[0], a[0] + hi[0]), xytext=(R[0], 1.32),
                fontsize=7, ha="center", va="bottom",
                arrowprops=dict(arrowstyle="-", color="0.55", lw=0.6))
    ax.set_xlabel(r"clumpiness: Clark-Evans $R$ (clustered $\rightarrow$)")
    ax.set_ylabel(r"fitted slope $a$ of tax $= a\,\Lambda$")
    ax.invert_xaxis()  # R decreases with clustering; put uniform (R~1) at left, clumpy at right
    ax.set_ylim(0.0, 1.45)
    ax.legend(loc="lower left", frameon=False)
    fig.tight_layout()
    return _save(fig, "fig_fuel_tax_vs_clumpiness.pdf")


FIGURES = {
    "fig_fuel_tax_vs_clumpiness": fig_fuel_tax_vs_clumpiness,
    "fig_fuel_tax_vs_lambda": fig_fuel_tax_vs_lambda,
    "fig_fuel_tax_by_seed": fig_fuel_tax_by_seed,
    "fig_time_tax_vs_dt": fig_time_tax_vs_dt,
    "fig_branching": fig_branching,
    "fig_floor_bracket": fig_floor_bracket,
    "fig_concurrency": fig_concurrency,
    "fig_fuel_tax_vs_n": fig_fuel_tax_vs_n,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    made, missing = [], []
    for name, fn in FIGURES.items():
        try:
            out = fn()
            made.append(out.name)
            print(f"  [ok] {out.name}", flush=True)
        except FileNotFoundError as e:
            missing.append(name)
            print(f"  [--] {name}: {e}", flush=True)
    print(f"\nrendered {len(made)}/{len(FIGURES)} figures to {OUT_DIR}")
    if missing:
        print(f"missing results for: {', '.join(missing)} (run experiments.measure)")


if __name__ == "__main__":
    main()

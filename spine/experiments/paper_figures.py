"""Render the spine paper's figures from committed JSON (papers/spine/).

CHEAP and CI-safe: reads the deterministic artifacts written by `experiments/measure.py`
(`results/*.json`) and draws the figures. Runs NO simulation. The drift-guard test
(`tests/test_measure_results.py`) proves the JSON still matches the fold; regenerate the
numbers with `python -m experiments.measure --force`.

Figures (vector PDF, IEEE single-column geometry, serif fonts):
  fig_margin.pdf    - the decisive one: powered dwell fraction of the galactic fill vs a
                      x0.1..x1e5 copy-time sweep, with the 1% bar, the nominal copy time, and
                      the break-even. The whole robustness margin in one plot.
  fig_dwell_tax.pdf - the measured A/B dwell tax per seed for the two slingshot policies, with
                      the ensemble median and IQR. Shows nearest is small-and-resolved and
                      maxboost is within seed noise (the spread a single seed would have hidden).

Run (from the spine/ package root):
    uv run --extra dev python -m experiments.paper_figures
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUT_DIR = Path(__file__).resolve().parents[2] / "papers" / "spine"

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


def load(name: str) -> dict:
    path = RESULTS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path.name}; run `uv run --extra dev python -m experiments.measure {name}` first"
        )
    return json.loads(path.read_text())


def _save(fig, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / name
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out


def fig_margin() -> Path:
    """Powered dwell fraction vs copy time: the robustness margin (SCRUTINY.md C1)."""
    d = load("copy_time_robustness")
    sweep = d["sweep"]
    xs = [s["copy_time_days"] for s in sweep]
    ys = [s["dwell_fraction"] for s in sweep]
    nominal = d["nominal"]
    be = d["break_even"]
    bar = d["config"]["negligible_bar"]

    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    ax.loglog(xs, ys, "o-", color="#1f4e79", markersize=3.5, zorder=3)

    # the "no longer negligible" bar
    ax.axhline(bar, color="#b03a2e", linestyle="--", linewidth=0.9)
    ax.text(xs[0], bar * 1.4, "1% of the fill", color="#b03a2e", fontsize=7, va="bottom")

    # nominal copy time
    ax.axvline(nominal["copy_time_days"], color="#555555", linestyle=":", linewidth=0.9)
    ax.annotate(
        f"nominal\n{nominal['copy_time_days']:.0f} d",
        xy=(nominal["copy_time_days"], nominal["dwell_fraction"]),
        xytext=(nominal["copy_time_days"] * 1.6, nominal["dwell_fraction"] * 6),
        fontsize=7,
        color="#333333",
        arrowprops=dict(arrowstyle="-", color="#999999", lw=0.6),
    )

    # break-even marker
    ax.plot([be["copy_time_days"]], [be["fraction_at"]], "s", color="#b03a2e", markersize=4, zorder=4)
    ax.annotate(
        f"break-even\n{be['multiplier']:.0f}x nominal",
        xy=(be["copy_time_days"], be["fraction_at"]),
        xytext=(be["copy_time_days"] * 0.02, be["fraction_at"] * 0.18),
        fontsize=7,
        color="#b03a2e",
        arrowprops=dict(arrowstyle="-", color="#b03a2e", lw=0.6),
    )

    ax.set_xlabel("copy time (days, log scale)")
    ax.set_ylabel("dwell / galactic fill time")
    ax.set_ylim(min(ys) * 0.3, 0.1)
    ax.grid(True, which="major", linestyle="-", linewidth=0.3, alpha=0.4)
    return _save(fig, "fig_margin.pdf")


def fig_dwell_tax() -> Path:
    """Per-seed dwell tax with ensemble median and IQR, two slingshot policies (C6)."""
    d = load("dwell_tax")
    order = [
        ("slingshot_nearest", "nearest", "#1f4e79"),
        ("slingshot_maxboost", "max-boost", "#c07a00"),
    ]

    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    ax.axhline(0.0, color="#888888", linewidth=0.7, zorder=1)

    for i, (key, label, color) in enumerate(order):
        block = d["ensemble"][key]
        taxes = [r["tax_fraction"] * 100 for r in block["per_seed"] if r["tax_fraction"] is not None]
        stats = block["stats"]
        # jittered strip of per-seed points (deterministic jitter by index, no RNG)
        n = len(taxes)
        xj = [i + ((j % 7) - 3) * 0.02 for j in range(n)]
        ax.scatter(xj, taxes, s=9, color=color, alpha=0.55, zorder=3, edgecolors="none")
        # IQR band + median
        ax.add_patch(
            plt.Rectangle(
                (i - 0.28, stats["q25"] * 100),
                0.56,
                (stats["q75"] - stats["q25"]) * 100,
                facecolor=color,
                alpha=0.15,
                edgecolor="none",
                zorder=2,
            )
        )
        ax.plot([i - 0.28, i + 0.28], [stats["median"] * 100] * 2, color=color, linewidth=1.6, zorder=4)
        ax.text(
            i,
            stats["max"] * 100 + 0.6,
            f"median {stats['median'] * 100:.2f}%",
            ha="center",
            fontsize=7,
            color=color,
        )

    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([label for _, label, _ in order])
    ax.set_xlim(-0.6, len(order) - 0.4)
    ax.set_ylabel("dwell tax (% of fill time)")
    ax.set_xlabel(f"slingshot policy ({d['config']['n_seeds']} seeds each)")
    ax.grid(True, axis="y", linestyle="-", linewidth=0.3, alpha=0.4)
    return _save(fig, "fig_dwell_tax.pdf")


def main() -> int:
    for f in (fig_margin, fig_dwell_tax):
        out = f()
        print(f"wrote {out.relative_to(OUT_DIR.parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

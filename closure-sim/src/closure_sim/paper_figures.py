"""Generate the three publication figures for papers/electronics-wall/.

Every number plotted here is either produced by the validated closure-sim fold
(CLAUDE.md 1) or a pure-math derivation stated inline - nothing is hardcoded or
invented. closure-sim is a deterministic forward-Euler fold with no RNG, so all
three PDFs are bit-reproducible run to run.

Figures (vector PDF, IEEE single-column geometry, serif fonts):
  (a) fig_leverage.pdf       - launch-mass leverage 1/(1-C) vs closure C (pure math).
  (b) fig_embodied_energy.pdf - embodied energy (kWh/kg) per subsystem, read from the
      loaded scenario factory (not hardcoded), log scale, sorted ascending.
  (c) fig_chip_crossover.pdf - time-to-target (years) vs available power (kW), for
      importing chips vs making them locally, from the electronics_wall analysis.

Run (from the closure-sim/ package root):
    uv run --extra dev python -m closure_sim.paper_figures
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")  # deterministic, headless, file-only backend
import matplotlib.pyplot as plt

from closure_sim import compute_closure, electronics_wall, load_factory

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

DAYS_PER_YEAR = 365.25  # Julian year, used for every day -> year conversion below.

# Resolve paths from this file: .../closure-sim/src/closure_sim/paper_figures.py
#   parents[0]=closure_sim, [1]=src, [2]=closure-sim, [3]=repo root.
_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parents[3]
OUT_DIR = REPO_ROOT / "papers" / "electronics-wall"
SCENARIO = _HERE.parents[2] / "scenarios" / "lunar_regolith_seed.yaml"


def fig_leverage() -> tuple[Path, float, float]:
    """(a) Launch-mass leverage 1/(1-C) vs material closure C. Pure math derivation.

    Installed factory mass per unit launched mass is 1/(1-C): a factory that makes
    fraction C of its own mass locally amplifies each kilogram launched into
    1/(1-C) kilograms installed. This is an exact identity, not a simulation output.
    """
    n = 400
    cs = [i * 0.99 / (n - 1) for i in range(n)]  # C from 0 to 0.99
    ys = [1.0 / (1.0 - c) for c in cs]

    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    ax.plot(cs, ys, color="0.15")

    marks = [(0.67, 1.0 / (1.0 - 0.67)), (0.97, 1.0 / (1.0 - 0.97))]
    for c, y in marks:
        ax.plot([c], [y], marker="o", markersize=3.0, color="0.15", zorder=5)
        ax.annotate(
            f"C = {c:.2f}\n{y:.0f}x",
            xy=(c, y),
            xytext=(c - 0.18, y + 4.0),
            fontsize=8,
            ha="left",
            va="bottom",
            arrowprops={"arrowstyle": "-", "linewidth": 0.5, "color": "0.4"},
        )

    ax.set_xlabel("material closure C")
    ax.set_ylabel("installed mass per launched mass, $1/(1-C)$")
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 40)
    fig.tight_layout()

    out = OUT_DIR / "fig_leverage.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out, marks[0][1], marks[1][1]


def fig_embodied_energy(factory) -> tuple[Path, list[tuple[str, float]]]:
    """(b) Embodied energy (kWh/kg) per subsystem, read from the loaded factory."""
    # Short, readable labels keyed to the scenario subsystem names.
    label_map = {
        "Structure & supports (cast regolith/metal)": "structure",
        "Solar power arrays (Si refined from regolith)": "solar arrays",
        "Thermal radiators": "radiators",
        "Actuators & motors (cast + wound wire)": "actuators",
        "Robotic manipulators": "manipulators",
        "Refining / chemical plant": "refining plant",
        "Basic sensors (machined optics/housings)": "sensors",
        "Control electronics / compute (chips)": "chips (compute)",
        "Power electronics (inverters, driver ICs)": "power electronics",
        "Precision bearings & special alloys": "bearings & alloys",
    }
    # Read specific energy straight from the loaded factory (no hardcoded values).
    pairs = [
        (label_map.get(s.name, s.name), s.energy_to_produce_kwh_per_kg)
        for s in factory.subsystems
    ]
    pairs.sort(key=lambda p: p[1])  # ascending

    labels = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]
    # Colour the semiconductor tower (chips + power electronics) distinctly.
    colors = ["0.15" if v >= 1000 else "0.6" for v in vals]

    fig, ax = plt.subplots(figsize=(COLW, COLW * 1.05))  # taller: 10 horizontal bars
    ys = list(range(len(vals)))
    ax.barh(ys, vals, color=colors, edgecolor="none", height=0.7)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    ax.set_xscale("log")
    ax.set_xlim(1, 2e4)
    ax.set_xlabel("embodied energy (kWh/kg, log scale)")

    # Value labels at each bar end.
    for y, v in zip(ys, vals):
        ax.text(v * 1.25, y, f"{v:g}", va="center", ha="left", fontsize=7)

    fig.tight_layout()
    out = OUT_DIR / "fig_embodied_energy.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out, pairs


def fig_chip_crossover(factory) -> tuple[Path, dict[float, tuple[float | None, float | None]]]:
    """(c) Time-to-target (years) vs available power (kW): import vs make-locally."""
    # Sweep power over a sensible range; each point is a full electronics_wall run.
    powers = [500 + i * (5000 - 500) / 90 for i in range(91)]  # 500..5000 kW, 91 pts

    import_yr: list[tuple[float, float]] = []
    local_yr: list[tuple[float, float]] = []
    ref: dict[float, tuple[float | None, float | None]] = {}

    for p in powers:
        params = factory.replication.model_copy(update={"available_power_kw": p})
        report = electronics_wall(factory, params)
        b = report.before.time_to_target_days
        a = report.after.time_to_target_days
        if b is not None:
            import_yr.append((p, b / DAYS_PER_YEAR))
        if a is not None:  # None = never completes -> do NOT plot a fake value
            local_yr.append((p, a / DAYS_PER_YEAR))

    # Reference points at ~4 MW and ~1 MW, computed explicitly.
    for p_ref in (4000.0, 1000.0):
        rep = electronics_wall(
            factory, factory.replication.model_copy(update={"available_power_kw": p_ref})
        )
        b = rep.before.time_to_target_days
        a = rep.after.time_to_target_days
        ref[p_ref] = (
            None if b is None else b / DAYS_PER_YEAR,
            None if a is None else a / DAYS_PER_YEAR,
        )

    fig, ax = plt.subplots(figsize=(COLW, COLW * GOLDEN))
    ax.plot(
        [p for p, _ in import_yr],
        [y for _, y in import_yr],
        color="0.55",
        linestyle="--",
        label="import chips",
    )
    ax.plot(
        [p for p, _ in local_yr],
        [y for _, y in local_yr],
        color="0.15",
        linestyle="-",
        label="make chips locally",
    )

    # Cap the y-axis and annotate that the local line diverges (never completes) at low power.
    ax.set_ylim(0, 40)
    ax.set_xlim(500, 5000)
    lowest_local_p = min(p for p, _ in local_yr)
    ax.axvspan(500, lowest_local_p, color="0.9", zorder=0)
    ax.annotate(
        "local:\nnever\ncompletes",
        xy=((500 + lowest_local_p) / 2, 30),
        ha="center",
        va="center",
        fontsize=7,
        color="0.4",
    )

    # Mark the 4 MW and 1 MW reference verticals.
    for p_ref in (1000.0, 4000.0):
        ax.axvline(p_ref, color="0.7", linewidth=0.6, linestyle=":", zorder=0)
        ax.text(
            p_ref + 40,
            38,
            f"{p_ref / 1000:g} MW",
            fontsize=7,
            color="0.4",
            va="top",
            ha="left",
        )

    ax.set_xlabel("available power (kW)")
    ax.set_ylabel("time to target scale (years)")
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()

    out = OUT_DIR / "fig_chip_crossover.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    return out, ref


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    factory = load_factory(SCENARIO)
    closure = compute_closure(factory)
    print(f"Writing figures to {OUT_DIR}")
    print(f"scenario: {SCENARIO.name}  closure = {closure.closure_ratio * 100:.2f}%\n")

    out_a, lev67, lev97 = fig_leverage()
    print(f"[a] {out_a.name}")
    print(f"      1/(1-0.67) = {lev67:.2f}x ; 1/(1-0.97) = {lev97:.2f}x")

    out_b, pairs = fig_embodied_energy(factory)
    print(f"[b] {out_b.name}")
    for name, v in pairs:
        print(f"      {name:<20} {v:>8g} kWh/kg")

    out_c, ref = fig_chip_crossover(factory)
    print(f"[c] {out_c.name}")
    for p_ref in (4000.0, 1000.0):
        imp, loc = ref[p_ref]
        imp_s = "never" if imp is None else f"{imp:.1f} yr"
        loc_s = "never" if loc is None else f"{loc:.1f} yr"
        print(f"      {p_ref / 1000:g} MW: import {imp_s} ; local {loc_s}")


if __name__ == "__main__":
    main()

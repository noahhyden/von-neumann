"""argparse CLI: load a scenario and run closure / replication / electronics-wall."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from .analysis import ElectronicsWallReport, electronics_wall
from .closure import ClosureReport, compute_closure
from .models import Factory, ReplicationParams
from .replication import Regime, SimResult, simulate
from .scenarios import load_factory

# Plain-language explanation of each growth bottleneck, for non-technical readers.
REGIME_PLAIN = {
    Regime.MATERIAL: "growing fast - limited only by its own size (good)",
    Regime.ENERGY: "out of electricity to run its machines",
    Regime.RESUPPLY: "waiting on vitamins shipped from Earth",
}


def _table(title, headers, rows, right=()):
    """Print a plain ASCII table; columns listed in `right` are right-aligned."""
    cols = list(zip(headers, *rows))
    w = [max(len(c) for c in col) for col in cols]
    rule = "+" + "+".join("-" * (x + 2) for x in w) + "+"

    def line(cells):
        return "| " + " | ".join(
            c.rjust(w[i]) if i in right else c.ljust(w[i]) for i, c in enumerate(cells)
        ) + " |"

    if title:
        print(title)
    print(rule)
    print(line(headers))
    print(rule)
    for r in rows:
        print(line(r))
    print(rule)


def _fmt_days(days: float | None) -> str:
    if days is None:
        return "never"
    return f"{days:,.0f} d  ({days / 365.25:.1f} yr)"


def _fmt_rate(x: float) -> str:
    if math.isinf(x):
        return "unbounded"
    return f"{x:,.1f}"


def _overrides(
    target: float | None,
    power: float | None,
    resupply: float | None,
    cadence: float | None,
    duration: int | None,
) -> dict:
    """Collect non-None CLI overrides for the replication block."""
    out = {}
    if target is not None:
        out["target_output_kg_per_day"] = target
    if power is not None:
        out["available_power_kw"] = power
    if resupply is not None:
        out["vitamin_resupply_mass_kg"] = resupply
    if cadence is not None:
        out["resupply_cadence_days"] = cadence
    if duration is not None:
        out["duration_days"] = duration
    return out


def _resolve_params(factory: Factory, overrides: dict) -> ReplicationParams:
    if factory.replication is None:
        raise SystemExit("error: scenario has no `replication:` block; cannot simulate")
    if not overrides:
        return factory.replication
    return factory.replication.model_copy(update=overrides)


def _print_closure(report: ClosureReport) -> None:
    _table(
        f"Closure - {report.factory_name}",
        ["Metric", "Value"],
        [
            ["Total weight", f"{report.total_mass_kg:,.0f} kg"],
            ["Can make locally", f"{report.local_mass_kg:,.0f} kg"],
            ["Must ship from Earth (vitamins)", f"{report.vitamin_mass_kg:,.0f} kg"],
            ["Self-sufficiency (closure)", f"{report.closure_ratio * 100:.2f}%"],
            [
                "Electricity to build one copy",
                f"{report.total_build_energy_kwh:,.0f} kWh",
            ],
        ],
        right={1},
    )
    if report.vitamins:
        _table(
            "Vitamins - the parts it can't make (heaviest first)",
            ["Part", "Category", "Weight", "Share of factory", "Needs"],
            [
                [
                    v.name,
                    v.category,
                    f"{v.mass_kg:,.0f} kg",
                    f"{v.mass_share * 100:.2f}%",
                    ", ".join(v.processes) or "-",
                ]
                for v in report.vitamins
            ],
            right={2, 3},
        )


def _print_sim(result: SimResult) -> None:
    _table(
        f"Replication - {result.factory_name}",
        ["Metric", "Value"],
        [
            ["Self-sufficiency (closure)", f"{result.closure_ratio * 100:.2f}%"],
            [
                "Most growth from resupply can allow",
                f"{_fmt_rate(result.resupply_ceiling_kg_per_day)} kg/day",
            ],
            [
                "Most output power can allow",
                f"{_fmt_rate(result.energy_cap_kg_per_day)} kg/day",
            ],
            ["Doubling time (best case)", _fmt_days(result.analytic_doubling_time_days)],
            ["Doubling time (actual)", _fmt_days(result.empirical_doubling_time_days)],
            [
                f"Time to reach {result.target_output_kg_per_day:,.0f} kg/day",
                _fmt_days(result.time_to_target_days),
            ],
            ["Factory weight at the end", f"{result.final_factory_mass_kg:,.0f} kg"],
            ["Output at the end", f"{result.final_output_kg_per_day:,.1f} kg/day"],
        ],
        right={1},
    )
    _table(
        "What was holding growth back, over time",
        ["Bottleneck", "What it means", "Period"],
        [
            [
                span.regime.value,
                REGIME_PLAIN[span.regime],
                f"day {span.start_day:,.0f}-{span.end_day:,.0f}",
            ]
            for span in result.regime_timeline
        ],
        right={2},
    )


def _print_wall(report: ElectronicsWallReport) -> None:
    print(
        f"The electronics wall - {report.factory_name}\n"
        f"What if this factory could make its own electronics "
        f"({report.electronics_mass_kg:,.0f} kg, "
        f"{report.electronics_mass_share * 100:.2f}% of its weight)?"
    )
    b, a = report.before, report.after
    _table(
        None,
        ["", "Chips from Earth", "Chips made locally"],
        [
            [
                "Self-sufficiency (closure)",
                f"{b.closure_ratio * 100:.2f}%",
                f"{a.closure_ratio * 100:.2f}%",
            ],
            [
                "Most growth resupply can allow",
                f"{_fmt_rate(b.resupply_ceiling_kg_per_day)} kg/d",
                f"{_fmt_rate(a.resupply_ceiling_kg_per_day)} kg/d",
            ],
            [
                "Most output power can allow",
                f"{_fmt_rate(b.energy_cap_kg_per_day)} kg/d",
                f"{_fmt_rate(a.energy_cap_kg_per_day)} kg/d",
            ],
            [
                "Time to double in size",
                _fmt_days(b.empirical_doubling_time_days),
                _fmt_days(a.empirical_doubling_time_days),
            ],
            [
                "Time to reach the target",
                _fmt_days(b.time_to_target_days),
                _fmt_days(a.time_to_target_days),
            ],
            [
                "Output at the end",
                f"{b.final_output_kg_per_day:,.1f} kg/d",
                f"{a.final_output_kg_per_day:,.1f} kg/d",
            ],
        ],
        right={1, 2},
    )

    if report.time_to_target_delta_days is not None:
        d = report.time_to_target_delta_days
        print(
            f"\nMaking its own chips gets the factory to the target "
            f"{d:,.0f} days ({d / 365.25:.1f} years) sooner."
        )
    elif b.time_to_target_days is None and a.time_to_target_days is not None:
        print(
            "\nAs shipped it never reaches the target; making its own "
            "chips makes the target reachable."
        )
    elif b.time_to_target_days is not None and a.time_to_target_days is None:
        print(
            "\nBackfire: making its own chips makes things WORSE. Chips "
            "take thousands of times more electricity to manufacture than metal, so "
            "the factory now runs out of power long before it runs out of parts. "
            "More self-sufficient on paper, but stuck in practice - try a much higher "
            "--power to see when it would finally pay off."
        )


def _closure(args) -> None:
    _print_closure(compute_closure(load_factory(args.scenario)))


def _replicate(args) -> None:
    factory = load_factory(args.scenario)
    _print_sim(simulate(factory, _params(factory, args)))


def _wall(args) -> None:
    factory = load_factory(args.scenario)
    _print_wall(electronics_wall(factory, _params(factory, args)))


def _params(factory: Factory, a) -> ReplicationParams:
    o = _overrides(a.target, a.power, a.resupply, a.cadence, a.duration)
    return _resolve_params(factory, o)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="closure-sim",
        description="Could a factory in space build copies of itself? Explore "
        "self-sufficiency ('closure'), how fast a seed factory could multiply, and "
        "what changes if it could make its own chips.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, help, sim):
        c = sub.add_parser(name, help=help, description=help)
        c.add_argument("scenario", type=Path, help="Path to a YAML/JSON scenario file.")
        if sim:
            c.add_argument("--target", type=float, help="Target output kg/day.")
            c.add_argument("--power", type=float, help="Available power kW.")
            c.add_argument(
                "--resupply", type=float, help="Vitamin resupply mass kg per cadence."
            )
            c.add_argument("--cadence", type=float, help="Resupply cadence days.")
            c.add_argument("--duration", type=int, help="Simulation duration days.")
        c.set_defaults(fn=fn)

    cmd("closure", _closure, "How self-sufficient is it? Shows what it can make "
        "locally vs. ship from Earth.", False)
    cmd("replicate", _replicate, "How fast could it multiply? Simulates growth "
        "from one seed over time.", True)
    cmd("wall", _wall, "What if it made its own chips? Compares shipping "
        "electronics vs making them.", True)
    return p


def main(argv=None) -> None:
    args = _parser().parse_args(argv)
    try:
        args.fn(args)
    except FileNotFoundError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()

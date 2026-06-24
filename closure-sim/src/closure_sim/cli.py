"""Typer CLI: load a scenario and run closure / replication / electronics-wall."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .analysis import ElectronicsWallReport, electronics_wall
from .closure import ClosureReport, compute_closure
from .models import Factory, ReplicationParams
from .replication import Regime, SimResult, simulate
from .scenarios import load_factory

# Plain-language explanation of each growth bottleneck, for non-technical readers.
REGIME_PLAIN = {
    Regime.MATERIAL: "growing fast — limited only by its own size (good)",
    Regime.ENERGY: "out of electricity to run its machines",
    Regime.RESUPPLY: "waiting on vitamins shipped from Earth",
}

app = typer.Typer(
    add_completion=False,
    help="Could a factory in space build copies of itself? Explore self-sufficiency "
    "('closure'), how fast a seed factory could multiply, and what changes if it "
    "could make its own chips.",
)
console = Console()

ScenarioArg = typer.Argument(..., help="Path to a YAML/JSON scenario file.")


def _fmt_days(days: float | None) -> str:
    if days is None:
        return "[red]never[/red]"
    return f"{days:,.0f} d  ({days / 365.25:.1f} yr)"


def _fmt_rate(x: float) -> str:
    if math.isinf(x):
        return "unbounded"
    return f"{x:,.1f}"


def _overrides(
    target: Optional[float],
    power: Optional[float],
    resupply: Optional[float],
    cadence: Optional[float],
    duration: Optional[int],
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
        raise typer.BadParameter(
            "scenario has no `replication:` block; cannot simulate"
        )
    if not overrides:
        return factory.replication
    return factory.replication.model_copy(update=overrides)


def _print_closure(report: ClosureReport) -> None:
    table = Table(title=f"Closure — {report.factory_name}", title_style="bold cyan")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Total weight", f"{report.total_mass_kg:,.0f} kg")
    table.add_row("Can make locally", f"{report.local_mass_kg:,.0f} kg")
    table.add_row("Must ship from Earth (vitamins)", f"{report.vitamin_mass_kg:,.0f} kg")
    table.add_row(
        "[bold]Self-sufficiency (closure)[/bold]",
        f"[bold]{report.closure_ratio * 100:.2f}%[/bold]",
    )
    table.add_row(
        "Electricity to build one copy", f"{report.total_build_energy_kwh:,.0f} kWh"
    )
    console.print(table)

    if report.vitamins:
        vt = Table(
            title="Vitamins — the parts it can't make (heaviest first)",
            title_style="bold yellow",
        )
        vt.add_column("Part")
        vt.add_column("Category")
        vt.add_column("Weight", justify="right")
        vt.add_column("Share of factory", justify="right")
        vt.add_column("Needs")
        for v in report.vitamins:
            vt.add_row(
                v.name,
                v.category,
                f"{v.mass_kg:,.0f} kg",
                f"{v.mass_share * 100:.2f}%",
                ", ".join(v.processes) or "-",
            )
        console.print(vt)


def _print_sim(result: SimResult) -> None:
    table = Table(
        title=f"Replication — {result.factory_name}", title_style="bold cyan"
    )
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Self-sufficiency (closure)", f"{result.closure_ratio * 100:.2f}%")
    table.add_row(
        "Most growth from resupply can allow",
        f"{_fmt_rate(result.resupply_ceiling_kg_per_day)} kg/day",
    )
    table.add_row(
        "Most output power can allow",
        f"{_fmt_rate(result.energy_cap_kg_per_day)} kg/day",
    )
    table.add_row(
        "Doubling time (best case)", _fmt_days(result.analytic_doubling_time_days)
    )
    table.add_row(
        "Doubling time (actual)", _fmt_days(result.empirical_doubling_time_days)
    )
    table.add_row(
        f"Time to reach {result.target_output_kg_per_day:,.0f} kg/day",
        _fmt_days(result.time_to_target_days),
    )
    table.add_row("Factory weight at the end", f"{result.final_factory_mass_kg:,.0f} kg")
    table.add_row(
        "Output at the end", f"{result.final_output_kg_per_day:,.1f} kg/day"
    )
    console.print(table)

    tl = Table(title="What was holding growth back, over time", title_style="bold magenta")
    tl.add_column("Bottleneck")
    tl.add_column("What it means")
    tl.add_column("Period", justify="right")
    for span in result.regime_timeline:
        tl.add_row(
            span.regime.value,
            REGIME_PLAIN[span.regime],
            f"day {span.start_day:,.0f}–{span.end_day:,.0f}",
        )
    console.print(tl)


@app.command()
def closure(scenario: Path = ScenarioArg) -> None:
    """How self-sufficient is it? Shows what it can make locally vs. ship from Earth."""
    factory = load_factory(scenario)
    _print_closure(compute_closure(factory))


@app.command()
def replicate(
    scenario: Path = ScenarioArg,
    target: Optional[float] = typer.Option(None, help="Target output kg/day."),
    power: Optional[float] = typer.Option(None, help="Available power kW."),
    resupply: Optional[float] = typer.Option(
        None, help="Vitamin resupply mass kg per cadence."
    ),
    cadence: Optional[float] = typer.Option(None, help="Resupply cadence days."),
    duration: Optional[int] = typer.Option(None, help="Simulation duration days."),
) -> None:
    """How fast could it multiply? Simulates growth from one seed over time."""
    factory = load_factory(scenario)
    params = _resolve_params(
        factory, _overrides(target, power, resupply, cadence, duration)
    )
    _print_sim(simulate(factory, params))


@app.command()
def wall(
    scenario: Path = ScenarioArg,
    target: Optional[float] = typer.Option(None, help="Target output kg/day."),
    power: Optional[float] = typer.Option(None, help="Available power kW."),
    resupply: Optional[float] = typer.Option(
        None, help="Vitamin resupply mass kg per cadence."
    ),
    cadence: Optional[float] = typer.Option(None, help="Resupply cadence days."),
    duration: Optional[int] = typer.Option(None, help="Simulation duration days."),
) -> None:
    """What if it made its own chips? Compares shipping electronics vs making them."""
    factory = load_factory(scenario)
    params = _resolve_params(
        factory, _overrides(target, power, resupply, cadence, duration)
    )
    report = electronics_wall(factory, params)
    _print_wall(report)


def _print_wall(report: ElectronicsWallReport) -> None:
    console.print(
        f"[bold cyan]The electronics wall — {report.factory_name}[/bold cyan]\n"
        f"What if this factory could make its own electronics "
        f"({report.electronics_mass_kg:,.0f} kg, "
        f"{report.electronics_mass_share * 100:.2f}% of its weight)?"
    )
    table = Table(title_style="bold")
    table.add_column("")
    table.add_column("Chips from Earth", justify="right")
    table.add_column("Chips made locally", justify="right")
    b, a = report.before, report.after
    table.add_row(
        "Self-sufficiency (closure)",
        f"{b.closure_ratio * 100:.2f}%",
        f"{a.closure_ratio * 100:.2f}%",
    )
    table.add_row(
        "Most growth resupply can allow",
        f"{_fmt_rate(b.resupply_ceiling_kg_per_day)} kg/d",
        f"{_fmt_rate(a.resupply_ceiling_kg_per_day)} kg/d",
    )
    table.add_row(
        "Most output power can allow",
        f"{_fmt_rate(b.energy_cap_kg_per_day)} kg/d",
        f"{_fmt_rate(a.energy_cap_kg_per_day)} kg/d",
    )
    table.add_row(
        "Time to double in size",
        _fmt_days(b.empirical_doubling_time_days),
        _fmt_days(a.empirical_doubling_time_days),
    )
    table.add_row(
        "Time to reach the target",
        _fmt_days(b.time_to_target_days),
        _fmt_days(a.time_to_target_days),
    )
    table.add_row(
        "Output at the end",
        f"{b.final_output_kg_per_day:,.1f} kg/d",
        f"{a.final_output_kg_per_day:,.1f} kg/d",
    )
    console.print(table)

    if report.time_to_target_delta_days is not None:
        d = report.time_to_target_delta_days
        console.print(
            f"\n[bold green]✓ Making its own chips gets the factory to the target "
            f"{d:,.0f} days ({d / 365.25:.1f} years) sooner.[/bold green]"
        )
    elif report.before.time_to_target_days is None and report.after.time_to_target_days is not None:
        console.print(
            "\n[bold green]✓ As shipped it never reaches the target; making its own "
            "chips makes the target reachable.[/bold green]"
        )
    elif report.before.time_to_target_days is not None and report.after.time_to_target_days is None:
        console.print(
            "\n[bold red]✗ Backfire: making its own chips makes things WORSE. Chips "
            "take thousands of times more electricity to manufacture than metal, so "
            "the factory now runs out of power long before it runs out of parts. "
            "More self-sufficient on paper, but stuck in practice — try a much higher "
            "--power to see when it would finally pay off.[/bold red]"
        )


if __name__ == "__main__":
    app()

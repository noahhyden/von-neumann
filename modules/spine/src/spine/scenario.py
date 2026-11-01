"""Inputs to one cross-scale run - a single factory plus the knobs each scale needs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import closure_sim
from closure_sim.models import Factory
from closure_sim.scenarios import load_factory
from swarm.models import Policy

# The default factory is closure-sim's sourced lunar-regolith seed scenario, resolved relative to the installed closure_sim package (editable install -> repo tree): closure-sim/src/closure_sim/__init__.py -> parents[2] == closure-sim/.
_CLOSURE_ROOT = Path(closure_sim.__file__).resolve().parents[2]
DEFAULT_FACTORY_YAML = _CLOSURE_ROOT / "scenarios" / "lunar_regolith_seed.yaml"


def default_factory() -> Factory:
    """The sourced lunar-regolith seed factory, shared with mission and multi-probe."""
    return load_factory(DEFAULT_FACTORY_YAML)


@dataclass
class SpineScenario:
    """Everything one cross-scale run needs."""

    factory: Factory
    # scale 3 (galaxy) knobs
    n_stars: int = 1200
    offspring_per_settlement: int = 2
    policy: Policy = "powered"
    swarm_dt_years: float = 5000.0
    # the finer timestep used only to *measure* the dwell tax on a small field
    tax_n_stars: int = 400
    tax_dt_years: float = 1.0
    seed: int = 0x9E3779B9

    @classmethod
    def default(cls, **overrides: object) -> "SpineScenario":
        """A ready-to-run scenario on the shared sourced factory; override any field."""
        base: dict[str, object] = {"factory": default_factory()}
        base.update(overrides)
        return cls(**base)  # type: ignore[arg-type]

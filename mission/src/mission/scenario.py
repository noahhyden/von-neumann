"""The inputs to one end-to-end probe mission — every scalar sourced or a flagged choice.

A `MissionScenario` gathers exactly what the driver in `run.py` needs and nothing it
can derive itself. It holds:

- a closure-sim `Factory` (the bill of materials) — we default to the sourced
  `lunar_regolith_seed.yaml` scenario, so the masses/energies all trace to
  closure-sim/REFERENCES.md. There is no probe-specific BOM yet — the Borgue & Hein
  per-module masses are an open `[GAP]` in probe-sim — so we honestly reuse the
  lunar seed factory as the stand-in and say so.
- launch scalars (Δv, Isp, $/kg) — representative sourced values from
  launch-economics/REFERENCES.md; the caller may override per scenario.
- the solar array + power split + compute efficiency — sourced or `[ESTIMATE]`,
  documented in mission/REFERENCES.md.

Pure, deterministic, plain data; zero pimas imports (CLAUDE.md §7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import closure_sim
from closure_sim.models import Factory
from closure_sim.scenarios import load_factory
from probe_sim.environment import SOLAR_CONSTANT_1AU_W_M2, SolarArray

# The default factory is closure-sim's sourced lunar-regolith seed scenario. Resolve
# its path relative to the installed closure_sim package (editable install → repo tree):
# closure-sim/src/closure_sim/__init__.py -> parents[2] == closure-sim/.
_CLOSURE_ROOT = Path(closure_sim.__file__).resolve().parents[2]
DEFAULT_FACTORY_YAML = _CLOSURE_ROOT / "scenarios" / "lunar_regolith_seed.yaml"

# Array efficiency: sunlight->electric, [ESTIMATE] 0.30 (see probe-sim/REFERENCES.md).
DEFAULT_ARRAY_EFFICIENCY: float = 0.30

# Array area sized so the array delivers the closure scenario's ~4 MW at 1 AU with the
# efficiency above: area = P / (S0 * eff) = 4e6 / (1360.8 * 0.30) ≈ 9800 m^2. This keeps
# the mission consistent with lunar_regolith_seed.yaml's available_power_kw = 4000, while
# making that power *distance-dependent* (the scenario treated it as a fixed given).
DEFAULT_ARRAY_POWER_AT_1AU_W: float = 4_000_000.0
DEFAULT_ARRAY_AREA_M2: float = round(
    DEFAULT_ARRAY_POWER_AT_1AU_W / (SOLAR_CONSTANT_1AU_W_M2 * DEFAULT_ARRAY_EFFICIENCY)
)

# Compute hardware efficiency, FLOPS/W: [ESTIMATE] 1e11 (~100 GFLOP/W) — see
# power-budget/REFERENCES.md. Affects the compute-headroom leg only.
DEFAULT_COMPUTE_EFFICIENCY_FLOPS_PER_W: float = 1e11

# --- Launch scalars (launch-economics/REFERENCES.md) ---
# Δv Earth surface -> LEO, ~9400 m/s incl. gravity+drag losses (standard Δv tables).
DEFAULT_DELTA_V_M_S: float = 9400.0
# Isp LOX/RP-1, ~311 s vacuum (Merlin 1D). Sourced input, not a constant.
DEFAULT_SPECIFIC_IMPULSE_S: float = 311.0
# Falcon 9 (reusable) specific launch cost, ~$3000/kg to LEO (SpaceX list price).
DEFAULT_COST_PER_KG_USD: float = 3000.0

# Target installed factory mass — a scenario *design choice* (not a physical fact):
# grow a ~12 t seed into a 1000 t installation (leverage ~80x). Flagged as a choice.
DEFAULT_TARGET_INSTALLED_MASS_KG: float = 1_000_000.0

# Power split — scenario design choices (fractions of delivered power), not physics.
# Manufacturing gets the lion's share; compute is the autonomy budget; the rest is
# housekeeping (thermal/comms/attitude). Must not sum to > 1 (PowerBudget enforces).
DEFAULT_FRACTION_MANUFACTURING: float = 0.70
DEFAULT_FRACTION_COMPUTE: float = 0.20
DEFAULT_FRACTION_HOUSEKEEPING: float = 0.10


@dataclass
class MissionScenario:
    """Everything one end-to-end mission run needs; sensible sourced defaults."""

    factory: Factory
    distance_au: float = 1.0
    array_area_m2: float = DEFAULT_ARRAY_AREA_M2
    array_efficiency: float = DEFAULT_ARRAY_EFFICIENCY
    fraction_manufacturing: float = DEFAULT_FRACTION_MANUFACTURING
    fraction_compute: float = DEFAULT_FRACTION_COMPUTE
    fraction_housekeeping: float = DEFAULT_FRACTION_HOUSEKEEPING
    compute_efficiency_flops_per_w: float = DEFAULT_COMPUTE_EFFICIENCY_FLOPS_PER_W
    delta_v_m_s: float = DEFAULT_DELTA_V_M_S
    specific_impulse_s: float = DEFAULT_SPECIFIC_IMPULSE_S
    cost_per_kg_usd: float = DEFAULT_COST_PER_KG_USD
    target_installed_mass_kg: float = DEFAULT_TARGET_INSTALLED_MASS_KG

    @property
    def array(self) -> SolarArray:
        return SolarArray(area_m2=self.array_area_m2, efficiency=self.array_efficiency)

    @property
    def seed_mass_kg(self) -> float:
        """The launched seed mass, taken from the factory's own replication params.

        This closes the seam the modules left open: launch-economics'
        `comparison_from_closure` takes `seed_mass_kg` independently, so we feed it the
        factory's `replication.seed_mass_kg` rather than a second, unlinked number.
        """
        if self.factory.replication is None:
            raise ValueError("factory has no replication params (need seed_mass_kg)")
        return self.factory.replication.seed_mass_kg


def default_mission_scenario(**overrides: float) -> MissionScenario:
    """The default sourced mission: lunar-regolith seed factory, Falcon 9, 1 AU.

    Any scalar field may be overridden by keyword (e.g. ``distance_au=5.2``).
    """
    factory = load_factory(DEFAULT_FACTORY_YAML)
    return MissionScenario(factory=factory, **overrides)

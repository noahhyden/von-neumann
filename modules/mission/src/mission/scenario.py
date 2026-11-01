"""The inputs to one end-to-end probe mission - every scalar sourced or a flagged choice."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import closure_sim
from closure_sim.models import Factory
from closure_sim.scenarios import load_factory
from probe_sim.environment import SOLAR_CONSTANT_1AU_W_M2, SolarArray

# The default factory is closure-sim's sourced lunar-regolith seed scenario, resolved relative to the installed closure_sim package (parents[2] is closure-sim/).
_CLOSURE_ROOT = Path(closure_sim.__file__).resolve().parents[2]
DEFAULT_FACTORY_YAML = _CLOSURE_ROOT / "scenarios" / "lunar_regolith_seed.yaml"

# Array efficiency: sunlight->electric, [ESTIMATE] 0.30 (see probe-sim/REFERENCES.md).
DEFAULT_ARRAY_EFFICIENCY: float = 0.30

# Array power at 1 AU: area = P / (S0 * eff) = 4e6 / (1360.8 * 0.30) ~ 9800 m^2, matching lunar_regolith_seed.yaml available_power_kw = 4000 but now distance-dependent.
DEFAULT_ARRAY_POWER_AT_1AU_W: float = 4_000_000.0
DEFAULT_ARRAY_AREA_M2: float = round(
    DEFAULT_ARRAY_POWER_AT_1AU_W / (SOLAR_CONSTANT_1AU_W_M2 * DEFAULT_ARRAY_EFFICIENCY)
)

# Compute hardware efficiency, FLOPS/W: [ESTIMATE] 1e11 (~100 GFLOP/W), see power-budget/REFERENCES.md; affects the compute-headroom leg only.
DEFAULT_COMPUTE_EFFICIENCY_FLOPS_PER_W: float = 1e11

# --- Launch scalars (launch-economics/REFERENCES.md); delta-v Earth surface to LEO ~9400 m/s incl. gravity and drag losses (standard delta-v tables). ---
DEFAULT_DELTA_V_M_S: float = 9400.0
# Isp LOX/RP-1, ~311 s vacuum (Merlin 1D). Sourced input, not a constant.
DEFAULT_SPECIFIC_IMPULSE_S: float = 311.0
# Falcon 9 (reusable) specific launch cost, ~$3000/kg to LEO (SpaceX list price).
DEFAULT_COST_PER_KG_USD: float = 3000.0

# Target installed factory mass is a scenario design choice (not a physical fact): a ~12 t seed grown to 1000 t (naive ~83x, effective leverage ~24.5x with vitamins; REFERENCES.md).
DEFAULT_TARGET_INSTALLED_MASS_KG: float = 1_000_000.0

# Power split is a scenario design choice (fractions of delivered power, not physics): manufacturing the lion share, compute the autonomy budget, rest housekeeping; must not sum above 1.
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
        """The launched seed mass, taken from the factory's own replication params."""
        if self.factory.replication is None:
            raise ValueError("factory has no replication params (need seed_mass_kg)")
        return self.factory.replication.seed_mass_kg


def default_mission_scenario(**overrides: float) -> MissionScenario:
    """The default sourced mission: lunar-regolith seed factory, Falcon 9, 1 AU."""
    factory = load_factory(DEFAULT_FACTORY_YAML)
    return MissionScenario(factory=factory, **overrides)

"""Heat rejection and radiator sizing."""

from __future__ import annotations

from dataclasses import dataclass

from probe_sim.environment import solar_irradiance_w_m2

# Stefan-Boltzmann constant, W/m^2/K^4: CODATA value, fixed by the SI defined constants (h, k_B, c); see REFERENCES.md.
STEFAN_BOLTZMANN_W_M2_K4: float = 5.670374419e-8

# Default radiator emissivity (high-emissivity coating). Representative flight value.
DEFAULT_EMISSIVITY: float = 0.8

# Radiator areal density, kg/m^2: NASA lightweight target <=3.0 (achieved 3.08 at 500-600 K), heavy deployable radiators up to ~12; see REFERENCES.md.
RADIATOR_SPECIFIC_MASS_KG_M2: float = 3.0
RADIATOR_SPECIFIC_MASS_BAND_KG_M2: tuple[float, float] = (3.0, 12.0)

# --- ISS External Active Thermal Control System flight anchor. See REFERENCES.md. ---
ISS_HEAT_REJECTION_TOTAL_KW: float = 70.0
ISS_HEAT_REJECTION_PER_LOOP_KW: float = 35.0
ISS_RADIATOR_TEMP_K: float = 275.0  # single-phase ammonia coolant ~2-6 C
ISS_PANELS_PER_ASSEMBLY: int = 8
ISS_PANEL_LENGTH_M: float = 3.33
ISS_PANEL_WIDTH_M: float = 2.64
ISS_RADIATOR_ASSEMBLY_AREA_M2: float = (
    ISS_PANELS_PER_ASSEMBLY * ISS_PANEL_LENGTH_M * ISS_PANEL_WIDTH_M
)


@dataclass(frozen=True)
class RadiatorResult:
    """A sized radiator: the flux it achieves, its area, and its mass."""

    flux_w_m2: float
    area_m2: float
    mass_kg: float

    def __post_init__(self) -> None:
        # [inv:th-radiator] a radiator has positive flux and non-negative area/mass; a zero-heat-load call is legal (area = mass = 0) and negative anywhere is a bug.
        if self.flux_w_m2 <= 0:
            raise ValueError(f"[inv:th-radiator] flux_w_m2={self.flux_w_m2} must be > 0")
        if self.area_m2 < 0:
            raise ValueError(f"[inv:th-radiator] area_m2={self.area_m2} must be >= 0")
        if self.mass_kg < 0:
            raise ValueError(f"[inv:th-radiator] mass_kg={self.mass_kg} must be >= 0")


def radiated_flux_w_m2(
    temp_k: float,
    emissivity: float = DEFAULT_EMISSIVITY,
    sink_temp_k: float = 0.0,
    sides: int = 2,
) -> float:
    """Stefan-Boltzmann heat flux (W/m^2): sides * eps * sigma * (T^4 - T_sink^4)."""
    if temp_k <= 0:
        raise ValueError("temp_k must be positive")
    if not 0.0 < emissivity <= 1.0:
        raise ValueError("emissivity must be in (0, 1]")
    if sink_temp_k < 0:
        raise ValueError("sink_temp_k must be non-negative")
    if sides not in (1, 2):
        raise ValueError("sides must be 1 or 2")
    if sink_temp_k >= temp_k:
        raise ValueError("sink_temp_k must be below temp_k (radiator cannot reject heat)")
    return sides * emissivity * STEFAN_BOLTZMANN_W_M2_K4 * (temp_k**4 - sink_temp_k**4)


def radiator_area_m2(
    heat_w: float,
    temp_k: float,
    emissivity: float = DEFAULT_EMISSIVITY,
    sink_temp_k: float = 0.0,
    sides: int = 2,
) -> float:
    """Radiator area (m^2) to reject a heat load at a temperature: heat / flux."""
    if heat_w < 0:
        raise ValueError("heat_w must be non-negative")
    flux = radiated_flux_w_m2(temp_k, emissivity, sink_temp_k, sides)
    return heat_w / flux


def radiator_mass_kg(
    area_m2: float, specific_mass_kg_m2: float = RADIATOR_SPECIFIC_MASS_KG_M2
) -> float:
    """Radiator mass (kg) = area x areal density. This is the closure-sim BOM line."""
    if area_m2 < 0:
        raise ValueError("area_m2 must be non-negative")
    if specific_mass_kg_m2 <= 0:
        raise ValueError("specific_mass_kg_m2 must be positive")
    return area_m2 * specific_mass_kg_m2


def size_radiator(
    heat_w: float,
    temp_k: float,
    emissivity: float = DEFAULT_EMISSIVITY,
    sink_temp_k: float = 0.0,
    sides: int = 2,
    specific_mass_kg_m2: float = RADIATOR_SPECIFIC_MASS_KG_M2,
) -> RadiatorResult:
    """Full sizing: flux, area, and mass for a heat load at a radiator temperature."""
    flux = radiated_flux_w_m2(temp_k, emissivity, sink_temp_k, sides)
    area = heat_w / flux if heat_w >= 0 else 0.0
    return RadiatorResult(
        flux_w_m2=flux,
        area_m2=area,
        mass_kg=radiator_mass_kg(area, specific_mass_kg_m2),
    )


def mass_per_kw_kg(
    temp_k: float,
    emissivity: float = DEFAULT_EMISSIVITY,
    sink_temp_k: float = 0.0,
    sides: int = 2,
    specific_mass_kg_m2: float = RADIATOR_SPECIFIC_MASS_KG_M2,
) -> float:
    """Radiator mass per kilowatt rejected (kg/kW) - the T^4 leverage metric."""
    flux_kw_m2 = radiated_flux_w_m2(temp_k, emissivity, sink_temp_k, sides) / 1000.0
    return specific_mass_kg_m2 / flux_kw_m2


def net_flux_with_solar_load_w_m2(
    temp_k: float,
    distance_au: float,
    absorptivity: float = 0.2,
    emissivity: float = DEFAULT_EMISSIVITY,
    sides: int = 2,
) -> float:
    """Net rejection flux (W/m^2) after subtracting absorbed sunlight on one face."""
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    if not 0.0 <= absorptivity <= 1.0:
        raise ValueError("absorptivity must be in [0, 1]")
    gross = sides * emissivity * STEFAN_BOLTZMANN_W_M2_K4 * temp_k**4
    parasitic = absorptivity * solar_irradiance_w_m2(distance_au)
    net = gross - parasitic
    if net <= 0:
        raise ValueError(
            "radiator cannot reject heat here: absorbed sunlight exceeds T^4 emission"
        )
    return net

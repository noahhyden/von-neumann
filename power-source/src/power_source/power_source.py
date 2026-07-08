"""Choosing a power source: solar, fission, or radioisotope.

A self-replicating probe needs power, and which source is lightest is not a matter of
taste - it is set by two crossovers and gated by a scarce isotope.

**The distance crossover.** Solar specific power falls as 1/d^2; a nuclear source's
does not depend on distance at all. Setting them equal gives a crossover that is
independent of the power level (the power P cancels, because both masses scale with P):

    d_cross = sqrt(sp_solar_1AU / sp_nuclear)

With a conservative flight solar array (~100 W/kg system-level) and a fission reactor
(~6.7 W/kg) this is ~3.9 AU; against an RTG (~5.2 W/kg) it is ~4.4 AU. That ~4-5 AU
band matches reality: Juno runs solar right at Jupiter's 5.2 AU (with enormous arrays,
the exception at the boundary), and everything beyond switches to radioisotope power.

**The power-level crossover.** Below ~1 kWe an RTG is lighter (it scales down
gracefully); above it a fission reactor wins (its fixed reactor/shield/radiator
overhead only amortises at higher power).

**The Pu-238 vitamin wall.** A radioisotope source is not buildable in place at all: one
GPHS-RTG needs ~8.1 kg of plutonium-238, and the entire US produces only ~0.5-1.5 kg per
year. A fleet that relies on RTGs is throttled by an isotope no factory can smelt - the
sharpest "vitamin" in the project.

Pure algebra over sourced numbers - no reactor neutronics or array-degradation model
(over-nesting, CLAUDE.md 3), no pimas, no RNG (7). It reuses `probe-sim`'s 1/d^2 law and
calls `thermal` to size a reactor's radiator. Every number is in REFERENCES.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from probe_sim.environment import solar_irradiance_w_m2
from thermal.thermal import size_radiator

# --- Specific power, W/kg (flight system-level). See REFERENCES.md. ---
# Conservative flight solar array at 1 AU (Redwire ROSA ~100-120 W/kg system-level;
# wing-level runs 4x higher - basis pinned to system-level, CLAUDE.md 1).
SOLAR_SPECIFIC_POWER_1AU_W_PER_KG: float = 100.0
# Fission reactor (Kilopower 10 kWe class, ~1500 kg -> 6.7 W/kg; 800 We ~2 W/kg).
FISSION_SPECIFIC_POWER_W_PER_KG: float = 6.7
# GPHS-RTG (Cassini/New Horizons: ~300 We, ~57 kg) and MMRTG (Curiosity: ~110 We, 45 kg).
GPHS_RTG_SPECIFIC_POWER_W_PER_KG: float = 5.2
MMRTG_SPECIFIC_POWER_W_PER_KG: float = 2.4

# Power level below which an RTG beats a fission reactor, We. See REFERENCES.md.
RTG_FISSION_CROSSOVER_WE: float = 1000.0

# --- Pu-238 vitamin wall. See REFERENCES.md. ---
PU238_PER_GPHS_RTG_KG: float = 8.1
PU238_ANNUAL_PRODUCTION_KG: tuple[float, float] = (0.5, 1.5)  # US, now -> 2026 goal

# Fission thermal-to-electric conversion efficiency (Kilopower Stirling ~0.30).
FISSION_CONVERSION_EFFICIENCY: float = 0.30
# Fission radiator temperature, K (Stirling cold-side; a hot radiator is light, per
# thermal's T^4 leverage). Representative Kilopower value.
FISSION_RADIATOR_TEMP_K: float = 500.0


def solar_specific_power_at(
    distance_au: float, sp_1au_w_per_kg: float = SOLAR_SPECIFIC_POWER_1AU_W_PER_KG
) -> float:
    """Solar array specific power (W/kg) at a heliocentric distance, by the 1/d^2 law.

    Reuses `probe-sim`'s irradiance ratio so the solar constant lives in one place.
    """
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    ratio = solar_irradiance_w_m2(distance_au) / solar_irradiance_w_m2(1.0)
    return sp_1au_w_per_kg * ratio


def crossover_distance_au(
    sp_solar_1au_w_per_kg: float = SOLAR_SPECIFIC_POWER_1AU_W_PER_KG,
    sp_nuclear_w_per_kg: float = FISSION_SPECIFIC_POWER_W_PER_KG,
) -> float:
    """Solar/nuclear crossover distance: d = sqrt(sp_solar_1AU / sp_nuclear).

    Independent of power level (P cancels). Inside it solar is lighter; beyond it nuclear
    is.
    """
    if sp_solar_1au_w_per_kg <= 0 or sp_nuclear_w_per_kg <= 0:
        raise ValueError("specific powers must be positive")
    return (sp_solar_1au_w_per_kg / sp_nuclear_w_per_kg) ** 0.5


def source_mass_kg(power_we: float, specific_power_w_per_kg: float) -> float:
    """Mass (kg) of a source delivering a power at a given specific power: P / (W/kg)."""
    if power_we < 0:
        raise ValueError("power_we must be non-negative")
    if specific_power_w_per_kg <= 0:
        raise ValueError("specific_power_w_per_kg must be positive")
    return power_we / specific_power_w_per_kg


def choose_source(
    distance_au: float,
    power_we: float,
    sp_solar_1au_w_per_kg: float = SOLAR_SPECIFIC_POWER_1AU_W_PER_KG,
    sp_fission_w_per_kg: float = FISSION_SPECIFIC_POWER_W_PER_KG,
) -> str:
    """Lightest power source at a distance and power level: "solar", "fission", or "rtg".

    Distance crossover picks solar vs nuclear; within nuclear, the power-level crossover
    picks RTG (below ~1 kWe) vs fission (above).
    """
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    if power_we <= 0:
        raise ValueError("power_we must be positive")
    sp_solar = solar_specific_power_at(distance_au, sp_solar_1au_w_per_kg)
    if sp_solar >= sp_fission_w_per_kg:
        return "solar"
    return "rtg" if power_we < RTG_FISSION_CROSSOVER_WE else "fission"


def pu238_required_kg(n_rtgs: float, pu_per_rtg_kg: float = PU238_PER_GPHS_RTG_KG) -> float:
    """Plutonium-238 mass (kg) for a number of GPHS-RTGs."""
    if n_rtgs < 0:
        raise ValueError("n_rtgs must be non-negative")
    return n_rtgs * pu_per_rtg_kg


def years_of_pu238_production(
    pu238_kg: float, annual_production_kg: float = PU238_ANNUAL_PRODUCTION_KG[1]
) -> float:
    """Years of US Pu-238 output a given mass represents - the vitamin-wall clock."""
    if pu238_kg < 0:
        raise ValueError("pu238_kg must be non-negative")
    if annual_production_kg <= 0:
        raise ValueError("annual_production_kg must be positive")
    return pu238_kg / annual_production_kg


@dataclass(frozen=True)
class ReactorRadiator:
    """A fission reactor's waste heat and the radiator (from thermal) that rejects it."""

    waste_heat_w: float
    radiator_area_m2: float
    radiator_mass_kg: float


def fission_reactor_radiator(
    electric_power_we: float,
    conversion_efficiency: float = FISSION_CONVERSION_EFFICIENCY,
    radiator_temp_k: float = FISSION_RADIATOR_TEMP_K,
) -> ReactorRadiator:
    """Size a fission reactor's radiator by delegating to `thermal`.

    Waste heat = P_e (1 - eff)/eff (thermal power not converted to electricity). The
    radiator area and mass come from `thermal.size_radiator` - the clean seam that keeps
    the Stefan-Boltzmann model in one place.
    """
    if electric_power_we <= 0:
        raise ValueError("electric_power_we must be positive")
    if not 0.0 < conversion_efficiency < 1.0:
        raise ValueError("conversion_efficiency must be in (0, 1)")
    waste_heat_w = electric_power_we * (1.0 - conversion_efficiency) / conversion_efficiency
    r = size_radiator(waste_heat_w, radiator_temp_k)
    return ReactorRadiator(
        waste_heat_w=waste_heat_w,
        radiator_area_m2=r.area_m2,
        radiator_mass_kg=r.mass_kg,
    )

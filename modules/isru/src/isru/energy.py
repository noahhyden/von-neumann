"""The electrical energy it costs to make feedstock in place."""

from __future__ import annotations

from dataclasses import dataclass

# --- Oxygen: 2025 PNAS full-chain model (H2 reduction of ilmenite, 10 wt%), 24.3 +/- 5.8 kWh per kg LOX end to end; see REFERENCES.md. ---
OXYGEN_FULL_CHAIN_KWH_PER_KG: float = 24.3
OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG: float = 5.8

# Share of the oxygen chain's energy by step (PNAS): reduction dominates.
OXYGEN_ENERGY_SHARES: dict[str, float] = {
    "hydrogen_reduction": 0.55,
    "electrolysis": 0.38,
    "liquefaction": 0.048,
}

# Water-ice route cross-check (Kornuta et al.), a *different* feedstock at ~11.3 kWh/kg LOX; links to the propellant module and is not the regolith route above.
WATER_ICE_LOX_KWH_PER_KG: float = 11.3

# --- Metal: MOE of Fe2O3 -> Fe + O2; ~2.6 kWh/kg floor at ~1600 C (2600 kWh/tonne), ~3.7 practical, ~4.0 global-scale; see REFERENCES.md. ---
METAL_MOE_THEORETICAL_MIN_KWH_PER_KG: float = 2.6
METAL_MOE_PRACTICAL_KWH_PER_KG: float = 3.7
METAL_MOE_GLOBAL_SCALE_KWH_PER_KG: float = 4.0

# The closure-sim lunar-scenario value this module derives/retires.
CLOSURE_SIM_IRON_KWH_PER_KG: float = 5.0


@dataclass(frozen=True)
class EnergyBand:
    """A specific-energy estimate (kWh/kg) with an explicit uncertainty band."""

    central_kwh_per_kg: float
    low_kwh_per_kg: float
    high_kwh_per_kg: float


def oxygen_energy_kwh_per_kg(include_liquefaction: bool = True) -> EnergyBand:
    """Full-chain LOX specific energy (kWh/kg), 24.3 +/- 5.8 (PNAS 2025); include_liquefaction=False drops the ~4.8% liquefaction share (gaseous basis)."""
    central = OXYGEN_FULL_CHAIN_KWH_PER_KG
    if not include_liquefaction:
        central = central * (1.0 - OXYGEN_ENERGY_SHARES["liquefaction"])
    u = OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG
    return EnergyBand(
        central_kwh_per_kg=central,
        low_kwh_per_kg=central - u,
        high_kwh_per_kg=central + u,
    )


def metal_energy_kwh_per_kg(basis: str = "practical") -> float:
    """Iron specific energy (kWh/kg) via MOE; basis is theoretical (2.6), practical (3.7, retires closure-sim 5.0) or global_scale (4.0)."""
    table = {
        "theoretical": METAL_MOE_THEORETICAL_MIN_KWH_PER_KG,
        "practical": METAL_MOE_PRACTICAL_KWH_PER_KG,
        "global_scale": METAL_MOE_GLOBAL_SCALE_KWH_PER_KG,
    }
    if basis not in table:
        raise ValueError(f"basis must be one of {sorted(table)}, got {basis!r}")
    return table[basis]

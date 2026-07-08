"""The electrical energy it costs to make feedstock in place.

`closure-sim` takes a per-material `energy_to_produce_kwh_per_kg` as an input - in the
lunar scenario, ~5 kWh/kg for "in-situ iron from regolith". This module derives those
numbers from the process physics instead of assuming them, for the two feedstocks that
dominate a factory's mass: **oxygen** (the majority of regolith by weight, and the
propellant oxidiser) and **metal** (structural iron).

Two grounded results:

- **Oxygen, full production chain: 24.3 +/- 5.8 kWh/kg LOX** for hydrogen reduction of
  ilmenite (10 wt% ilmenite regolith), from a 2025 PNAS end-to-end model. The chain is
  dominated by the hydrogen-reduction (~55%) and electrolysis (~38%) steps; liquefaction
  is ~4.8%. This is exceptionally well-sourced: an entire chain, not a single reactor.
- **Metal, molten oxide electrolysis: ~2.6 kWh/kg thermodynamic minimum, ~3.7-4.0
  kWh/kg practical.** Electrolysing molten iron oxide to iron + O2. The practical figure
  grounds (and slightly undercuts) closure-sim's hand-set 5.0 - the number this module
  retires.

Metal beyond iron and asteroid feedstock are `[ESTIMATE]` (terrestrial molten-oxide-
electrolysis as a proxy); the lunar-oxygen tier is solid. No reactor or electrochemistry
simulation (over-nesting, CLAUDE.md 3) - these are sourced specific energies with their
uncertainty bands. Every number traces to REFERENCES.md.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Oxygen: 2025 PNAS full-chain model (H2 reduction of ilmenite, 10 wt%). ---
# 24.3 +/- 5.8 kWh per kg of liquid oxygen, end to end from dry regolith. See REFERENCES.
OXYGEN_FULL_CHAIN_KWH_PER_KG: float = 24.3
OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG: float = 5.8

# Share of the oxygen chain's energy by step (PNAS): reduction dominates.
OXYGEN_ENERGY_SHARES: dict[str, float] = {
    "hydrogen_reduction": 0.55,
    "electrolysis": 0.38,
    "liquefaction": 0.048,
}

# Water-ice route cross-check (Kornuta et al.), a *different* feedstock: ~11.3 kWh/kg
# LOX. Links to the propellant module; not the regolith route above.
WATER_ICE_LOX_KWH_PER_KG: float = 11.3

# --- Metal: molten oxide electrolysis of iron oxide (Fe2O3 -> Fe + O2). ---
# Thermodynamic minimum from hematite decomposition at ~1600 C (~2.6 kWh/kg = 2600
# kWh/tonne); practical optimized industrial ~3.7 kWh/kg; global-scale estimate ~4.0.
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
    """Full-chain LOX specific energy (kWh/kg), 24.3 +/- 5.8 (PNAS 2025).

    If include_liquefaction is False, drop the ~4.8% liquefaction share to report
    gaseous-oxygen energy instead of liquid (the basis a scenario needs may differ;
    pin it per CLAUDE.md 1).
    """
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
    """Iron specific energy (kWh/kg) via molten oxide electrolysis.

    basis: "theoretical" (2.6, thermodynamic floor), "practical" (3.7, optimized
    industrial), or "global_scale" (4.0). The practical value is what retires
    closure-sim's hand-set 5.0 for in-situ iron.
    """
    table = {
        "theoretical": METAL_MOE_THEORETICAL_MIN_KWH_PER_KG,
        "practical": METAL_MOE_PRACTICAL_KWH_PER_KG,
        "global_scale": METAL_MOE_GLOBAL_SCALE_KWH_PER_KG,
    }
    if basis not in table:
        raise ValueError(f"basis must be one of {sorted(table)}, got {basis!r}")
    return table[basis]

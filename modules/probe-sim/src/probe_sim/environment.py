"""The solar environment a probe operates in."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

# Total Solar Irradiance at 1 AU, W/m^2 (Kopp & Lean 2011; Borgue & Hein quote an older 1374 - see REFERENCES.md).
SOLAR_CONSTANT_1AU_W_M2: float = 1360.8

# The same quantity as a distribution for UQ (issue #35 / Depth track Tier 1).
SOLAR_CONSTANT_1AU_W_M2_STD: float = 0.5

# Mean heliocentric distances, AU (NASA planetary fact sheets). See REFERENCES.md.
AU_DISTANCE: dict[str, float] = {
    "earth": 1.000,
    "mars": 1.524,
    "jupiter": 5.203,
}


def solar_irradiance_w_m2(
    distance_au: float,
    solar_constant: float = SOLAR_CONSTANT_1AU_W_M2,
) -> float:
    """Solar irradiance (W/m^2) at a heliocentric distance, by the inverse-square law."""
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    return solar_constant / (distance_au**2)


class SolarArray(BaseModel):
    """A solar-electric power source, sized by collector area and conversion efficiency."""

    area_m2: float = Field(gt=0, description="collector area, m^2")
    efficiency: float = Field(
        gt=0, le=1, description="sunlight->electric conversion efficiency, 0-1"
    )

    def power_w(
        self,
        distance_au: float,
        solar_constant: float = SOLAR_CONSTANT_1AU_W_M2,
    ) -> float:
        """Electrical power (W) delivered at a heliocentric distance (AU)."""
        return solar_irradiance_w_m2(distance_au, solar_constant) * self.area_m2 * self.efficiency

    def max_distance_au(
        self,
        required_power_w: float,
        solar_constant: float = SOLAR_CONSTANT_1AU_W_M2,
    ) -> float:
        """Farthest heliocentric distance (AU) at which the array still meets a demand."""
        if required_power_w <= 0:
            raise ValueError("required_power_w must be positive")
        return math.sqrt(
            solar_constant * self.area_m2 * self.efficiency / required_power_w
        )

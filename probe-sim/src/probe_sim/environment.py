"""The solar environment a probe operates in.

The probe is solar-electric, so how far from the Sun it can work is set by how much
power sunlight delivers there. Irradiance falls off as the inverse square of
heliocentric distance - that is the physical fact that gates a solar probe's range
(Borgue & Hein 2020): ~1361 W/m^2 near Earth down to ~50 W/m^2 near Jupiter, beyond
which a solar-electric design becomes impractical and the mission is constrained to
the inner/mid solar system.

All figures are sourced - see REFERENCES.md.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

# Total Solar Irradiance at 1 AU, W/m^2. Kopp & Lean (2011) measured value: 1360.8.
# (Borgue & Hein quote 1374 near Earth, an older/AM0-style figure; we use the
# accepted TSI and note the difference in REFERENCES.md.)
SOLAR_CONSTANT_1AU_W_M2: float = 1360.8

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
    """Solar irradiance (W/m^2) at a heliocentric distance, by the inverse-square law.

    S(d) = S0 / d^2, with S0 the irradiance at 1 AU.
    """
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    return solar_constant / (distance_au**2)


class SolarArray(BaseModel):
    """A solar-electric power source, sized by collector area and conversion efficiency.

    Electrical power delivered is P = S(d) * area * efficiency, where S(d) is the
    inverse-square irradiance above.
    """

    area_m2: float = Field(gt=0, description="collector area, m^2")
    efficiency: float = Field(
        gt=0, le=1, description="sunlight->electric conversion efficiency, 0-1"
    )

    def power_w(self, distance_au: float) -> float:
        """Electrical power (W) delivered at a heliocentric distance (AU)."""
        return solar_irradiance_w_m2(distance_au) * self.area_m2 * self.efficiency

    def max_distance_au(self, required_power_w: float) -> float:
        """Farthest heliocentric distance (AU) at which the array still meets a demand.

        Solving required = S0/d^2 * area * eff for d gives
        d = sqrt(S0 * area * eff / required).
        """
        if required_power_w <= 0:
            raise ValueError("required_power_w must be positive")
        return math.sqrt(
            SOLAR_CONSTANT_1AU_W_M2 * self.area_m2 * self.efficiency / required_power_w
        )

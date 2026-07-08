"""transfer - interplanetary Δv and trip time.

Turns "how far" into "how much Δv, and how long" for a self-replicating probe. Two
regimes, both closed-form and framework-agnostic:

- **Impulsive (Hohmann):** two-burn heliocentric Δv and transfer time between circular
  coplanar orbits, plus the synodic launch-window cadence. Textbook-exact from GM_sun
  and the orbital radii.
- **Low-thrust (solar-electric):** rocket-equation propellant (reused from
  `launch-economics`), a 1/d^2 available-power model (reused from `probe-sim`), the
  resulting thrust and acceleration, and Edelbaum's closed-form spiral trip time.

This retires `multi-probe`'s hand-set transit time and makes the expansion wall a
derived output. Deterministic, plain data, zero pimas imports (CLAUDE.md §7). Every
number traces to a source; see REFERENCES.md.
"""

from transfer.orbits import (
    AU_M,
    BODY_SEMI_MAJOR_AXIS_AU,
    BODY_SIDEREAL_PERIOD_DAYS,
    GM_SUN_M3_S2,
    SECONDS_PER_DAY,
    HohmannResult,
    circular_orbital_speed_m_s,
    hohmann_transfer,
    synodic_period_days,
)
from transfer.low_thrust import (
    SepResult,
    available_power_w,
    edelbaum_delta_v_m_s,
    sep_thrust_n,
    sep_transfer,
)

__all__ = [
    "AU_M",
    "GM_SUN_M3_S2",
    "SECONDS_PER_DAY",
    "BODY_SEMI_MAJOR_AXIS_AU",
    "BODY_SIDEREAL_PERIOD_DAYS",
    "HohmannResult",
    "circular_orbital_speed_m_s",
    "hohmann_transfer",
    "synodic_period_days",
    "SepResult",
    "available_power_w",
    "edelbaum_delta_v_m_s",
    "sep_thrust_n",
    "sep_transfer",
]

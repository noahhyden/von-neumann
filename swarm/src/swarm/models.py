"""Plain-data types for the deterministic swarm fold (slice 1: the settlement front).

The star field is held struct-of-arrays style (parallel lists of coordinates + a
per-star settlement year), which is the shape the future TypeScript SoA/typed-array
port will use at scale. Probes are ephemeral in-flight hops. A seeded RNG is carried in
the state (CLAUDE.md §7), so a run is a pure function of (params, seed).

Nothing here imports pimas, the DOM, or a clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

# Speed of light in parsecs per year (c = 299792.458 km/s). Exact given the SI second
# and the parsec definition: 1 pc = 3.0856775814913673e13 km, 1 yr = 3.15576e7 s
# (Julian year). c = 299792.458 * 3.15576e7 / 3.0856775814913673e13 pc/yr.
C_PC_PER_YEAR: float = 299792.458 * 3.15576e7 / 3.0856775814913673e13
# 1 km/s expressed in pc/yr (derived from the same constants).
KM_S_TO_PC_YR: float = 3.15576e7 / 3.0856775814913673e13

# Target-selection / travel policies (Nicholson & Forgan 2013, their three scenarios).
Policy = Literal["powered", "slingshot_nearest", "slingshot_maxboost"]

# Coordination regime (FRONTIER #1). "instant" = the paper's assumption of perfect global
# knowledge (bit-identical to slices 1-3). "lightspeed" = a probe deciding at a star only
# knows a distant star is settled once the news-light has arrived (settled_year + dist/c ≤
# now), so probes race for the same star from stale views. "inflight" = the optimistic floor:
# a probe also listens WHILE flying, so when a beacon from its now-claimed target overtakes it
# mid-hop it redirects early (avoiding the wasted arrival and its brake), wasting only the
# partial travel already flown. instant <= inflight <= lightspeed. See REFERENCES.md.
Coordination = Literal["instant", "lightspeed", "inflight"]

# Time-stepping scheme. "fixed" advances by a constant dt_years (the original slice-1
# behaviour; keep dt <= mean hop time or it quantizes the timescale). "event" jumps to the
# next probe arrival - exact and dt-independent, the continuum (dt -> 0) limit. "event" is
# required whenever hops can be short relative to any fixed dt (the boosted/slingshot
# regime), where "fixed" over-synchronizes launches and inflates the coordination tax.
Stepping = Literal["fixed", "event"]


class SwarmParams(BaseModel):
    """Inputs to one settlement-front run. Physical numbers sourced in REFERENCES.md."""

    n_stars: int = Field(gt=1, default=500)
    density_stars_per_pc3: float = Field(
        gt=0, default=1.0, description="uniform stellar density (Nicholson & Forgan use 1 star/pc^3)"
    )
    probe_speed_c: float = Field(
        gt=0, le=1, default=3e-5, description="powered cruise speed, fraction of c (N&F: 3e-5 c ≈ 9 km/s)"
    )
    offspring_per_settlement: int = Field(
        ge=0, default=2, description="probes launched from each newly settled star"
    )
    settle_time_years: float = Field(
        ge=0, default=0.0, description="dwell to build offspring before they depart [ESTIMATE]"
    )
    dt_years: float = Field(
        gt=0, default=5000.0, description="fixed timestep (stepping='fixed'); keep ≲ mean hop time (~1e5 yr at defaults)"
    )
    stepping: Stepping = Field(
        default="fixed", description="time-stepping: fixed (constant dt) | event (jump to next arrival, dt-independent)"
    )
    max_years: float = Field(gt=0, default=50_000_000.0, description="safety cap; the run ends when the front does")

    # --- slingshot dynamics (ROADMAP §4; N&F 2013). Default 'powered' = no slingshots. ---
    policy: Policy = Field(default="powered", description="target/travel policy: powered | slingshot_nearest | slingshot_maxboost")
    star_speed_km_s: float = Field(
        gt=0, default=220.0, description="[ESTIMATE] mean stellar speed (galactic rotation ~220 km/s; paper defers to Forgan+2012)"
    )
    star_speed_dispersion_km_s: float = Field(
        ge=0, default=40.0, description="[ESTIMATE] spread in stellar speeds (thin-disc dispersion ~30-40 km/s)"
    )
    escape_velocity_km_s: float = Field(
        gt=0, default=617.5, description="stellar escape velocity for the slingshot cap; solar sqrt(2GM/R) (derived, see REFERENCES.md)"
    )
    max_boost_candidates: int = Field(
        ge=1, default=30, description="[ESTIMATE] max-boost policy scans this many nearest unsettled stars"
    )
    speed_cap_c: float = Field(
        gt=0, le=1, default=0.05, description="[ESTIMATE] sanity ceiling on accumulated probe speed"
    )

    # --- light-speed-limited coordination (FRONTIER #1). Default 'instant' = perfect info. ---
    coordination: Coordination = Field(
        default="instant", description="knowledge regime: instant (perfect global info) | lightspeed (news travels at c)"
    )
    max_retargets: int = Field(
        ge=0, default=8, description="[ESTIMATE] cap on re-target hops before a probe is retired as wasted (bounds stale-view bounce chains)"
    )

    @property
    def probe_speed_pc_per_year(self) -> float:
        return self.probe_speed_c * C_PC_PER_YEAR

    @property
    def box_side_pc(self) -> float:
        """Side of the cube holding ``n_stars`` at the given density: (N/ρ)^(1/3)."""
        return (self.n_stars / self.density_stars_per_pc3) ** (1.0 / 3.0)


@dataclass
class Probe:
    """One in-flight hop: heading to ``target`` star, arriving at ``arrive_year``.

    ``speed_pc_yr`` is the probe's current galactic-frame speed - constant (= powered
    cruise) under the powered policy, but accumulated across slingshots otherwise.
    """

    id: int
    target: int
    arrive_year: float
    speed_pc_yr: float
    retargets: int = 0  # how many times this probe has lost a race and re-aimed (capped by max_retargets)
    hop_len_pc: float = 0.0  # length of the hop this probe is currently flying (its launch/re-aim distance)
    # Launch position + year of the current hop. Used only by coordination="inflight" to
    # interpolate the probe's mid-flight position when a beacon overtakes it; unread (and left
    # at defaults) in "instant"/"lightspeed", so those folds stay bit-identical.
    from_x: float = 0.0
    from_y: float = 0.0
    from_z: float = 0.0
    launch_year: float = 0.0


@dataclass
class SwarmState:
    """Full state carried by the fold. SoA star field + seeded RNG (pure data)."""

    rng: int
    year: float
    xs: list[float]
    ys: list[float]
    zs: list[float]
    star_speed_pc_yr: list[float]  # per-star speed magnitude (drives the slingshot boost)
    settled_year: list[float]  # -1.0 while unsettled, else the year it was settled
    origin: int  # index of the homeworld star (front radius is measured from here)
    probes: list[Probe]
    next_probe_id: int
    total_launched: int
    max_speed_pc_yr: float  # fastest probe launched so far (shows accumulated boost)
    # --- coordination observability (the cost of no-coordination; 0 unless probes race) ---
    total_arrivals: int = 0  # every probe arrival processed
    wasted_arrivals: int = 0  # arrivals landing on an already-(truly-)settled star (redundant trips)
    retarget_count: int = 0  # total re-target events (a lost race that re-aimed)
    # Redundant travel distance (pc): the common currency across coordination modes. A lost
    # full arrival contributes its whole hop; an "inflight" mid-flight abort contributes only
    # the partial distance flown before it redirected. midflight_aborts counts the latter.
    wasted_travel_pc: float = 0.0
    midflight_aborts: int = 0
    # --- effective-speed + hop-length observability (read-only accumulators; touch no RNG) ---
    launch_speed_sum_pc_yr: float = 0.0  # sum of departing speeds over every probe launched
    launch_count: int = 0  # number of probes launched (for the mean effective speed)
    settle_hop_sum_pc: float = 0.0  # sum of hop lengths of arrivals that WON (settled a star)
    settle_hop_count: int = 0
    wasted_hop_sum_pc: float = 0.0  # sum of hop lengths of arrivals that LOST (wasted trips)
    wasted_hop_count: int = 0
    # --- energy-weighted-tax observability (read-only; Newtonian (1/2)v^2 per journey) -------
    # Summed over completed journeys at arrival (when the win/waste is known), using the speed
    # the probe actually flew. Lets the tax be weighted by the kinetic energy its launch speed
    # cost, not counted flat. No RNG, no decision - cannot perturb the pinned fold.
    settle_v_sum_pc_yr: float = 0.0  # sum of flight speeds over winning journeys
    settle_v2_sum: float = 0.0  # sum of speed^2 [(pc/yr)^2] over winning journeys
    wasted_v_sum_pc_yr: float = 0.0  # sum of flight speeds over wasted journeys
    wasted_v2_sum: float = 0.0  # sum of speed^2 [(pc/yr)^2] over wasted journeys

    def n_settled(self) -> int:
        return sum(1 for y in self.settled_year if y >= 0.0)


@dataclass
class SwarmStep:
    year: float
    n_settled: int
    fraction_settled: float
    in_flight: int
    front_radius_pc: float


@dataclass
class SwarmResult:
    n_stars: int
    final_settled: int
    total_probes_launched: int
    t50_years: float | None  # years to settle 50% / 90% / 100% of the field
    t90_years: float | None
    t100_years: float | None
    front_radius_pc: float
    max_probe_speed_km_s: float  # peak accumulated probe speed (powered = the cruise speed)
    policy: str
    # Coverage-fraction timescales beyond the original 50/90/100 (t100 is a tail statistic
    # dominated by the last few stars, so we also report earlier, more robust fractions).
    t25_years: float | None = None
    t75_years: float | None = None
    t99_years: float | None = None
    coordination: str = "instant"  # knowledge regime this run used
    total_arrivals: int = 0  # every probe arrival (settlements + wasted trips)
    wasted_arrivals: int = 0  # arrivals at an already-settled star - the cost of stale info
    retarget_count: int = 0  # total re-target events
    # Redundant travel distance (pc) and, for "inflight", the count of mid-flight aborts. This
    # is the mode-comparable fuel currency: full doomed hops (instant/lightspeed) plus partial
    # aborted hops (inflight). The floor bracket (instant/inflight/lightspeed) is read from it.
    wasted_travel_pc: float = 0.0
    midflight_aborts: int = 0
    # Effective speed actually achieved (not just the powered-cruise input): the mean speed at
    # which probes were launched, in km/s, so Lambda_eff = v/c can be checked per policy.
    mean_launch_speed_km_s: float = 0.0
    # Mean hop length of winning vs wasted trips (pc): the wasted-trip length is the direct
    # measure of "how non-local a lost race is" - the quantity that actually governs the tax.
    mean_settle_hop_pc: float = 0.0
    mean_wasted_hop_pc: float = 0.0
    # Energy-weighted-tax observables. Newtonian specific kinetic energy (1/2)(v/c)^2 summed
    # over journeys (dimensionless, in units of c^2), split winning vs wasted, so the paper can
    # weight redundant travel by the energy its launch speed cost. The relativistic form
    # (gamma-1)c^2 exceeds this by < 3.1% up to 0.2c, so Newtonian is the safe primary metric.
    settle_energy_c2: float = 0.0  # sum over winning journeys of (1/2)(v/c)^2
    wasted_energy_c2: float = 0.0  # sum over wasted journeys of (1/2)(v/c)^2
    mean_settle_speed_km_s: float = 0.0  # mean flight speed of winning journeys
    mean_wasted_speed_km_s: float = 0.0  # mean flight speed of wasted journeys
    steps: list[SwarmStep] = field(default_factory=list)

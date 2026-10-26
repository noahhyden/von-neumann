"""Plain-data types for the deterministic swarm fold (slice 1: the settlement front)."""

from __future__ import annotations

import numpy as np

import math
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

# Speed of light in pc/yr: c = 299792.458 km/s (SI exact) x 3.15576e7 s/yr (Julian year) / 3.0856775814913673e13 km/pc (IAU parsec).
C_PC_PER_YEAR: float = 299792.458 * 3.15576e7 / 3.0856775814913673e13
# 1 km/s expressed in pc/yr (derived from the same constants).
KM_S_TO_PC_YR: float = 3.15576e7 / 3.0856775814913673e13

# Fixed log-spaced hop-length bin edges, 0.1 to 30 pc in 12 steps (sub-nearest-neighbour to cross-box at the densities used), for the clumpy-field d-cancellation check.
HOP_BIN_EDGES: tuple[float, ...] = tuple(round(0.1 * (300.0 ** (k / 12.0)), 6) for k in range(13))
N_HOP_BINS: int = len(HOP_BIN_EDGES) + 1  # + one underflow (< first edge) and one overflow slot

# Wall-distance bin edges for the finite-size EDGE test (referee finding M1), in units of the mean NN distance E[NN] = 0.55396 rho^(-1/3) (Clark and Evans 1954).
WALL_BIN_EDGES_NN: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)  # in units of mean NN distance
N_WALL_BINS: int = len(WALL_BIN_EDGES_NN) + 1  # bins: [0,.5) [.5,1) [1,1.5) [1.5,2) [2,inf)

# Target-selection / travel policies (Nicholson & Forgan 2013, their three scenarios).
Policy = Literal["powered", "slingshot_nearest", "slingshot_maxboost"]

# Coordination regime (FRONTIER #1). "instant" = the paper's assumption of perfect global
Coordination = Literal["instant", "lightspeed", "inflight"]

# Time-stepping scheme. "fixed" advances by a constant dt_years (the original slice-1
Stepping = Literal["fixed", "event"]


class SwarmParams(BaseModel):
    """Inputs to one settlement-front run. Physical numbers sourced in REFERENCES.md."""

    n_stars: int = Field(gt=1, default=500)
    density_stars_per_pc3: float = Field(
        gt=0, default=1.0, description="uniform stellar density (Nicholson & Forgan use 1 star/pc^3)"
    )
    periodic: bool = Field(
        default=False,
        description="periodic (toroidal, minimum-image) box instead of a hard wall; the finite-size "
        "edge control (M1) - removes boundary stars so the with-N tax trend has no edge artifact",
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

    # --- clumpy (non-uniform) star field (FRONTIER #1 robustness: does tax = Lambda survive a non-uniform field, where hop length and local claim rate correlate?).
    n_clumps: int | None = Field(
        default=None, description="clumpy field: number of Thomas cluster centres (None = uniform cube, the default and all prior behaviour)"
    )
    clump_sigma_frac: float = Field(
        gt=0, default=0.15, description="[ESTIMATE] cluster scatter radius as a fraction of box side; read only when n_clumps is set (large -> uniform limit)"
    )

    @property
    def probe_speed_pc_per_year(self) -> float:
        return self.probe_speed_c * C_PC_PER_YEAR

    @property
    def box_side_pc(self) -> float:
        """Side of the cube holding ``n_stars`` at the given density: (N/ρ)^(1/3)."""
        return (self.n_stars / self.density_stars_per_pc3) ** (1.0 / 3.0)


@dataclass(slots=True)
class Probe:
    """One in-flight hop: heading to ``target`` star, arriving at ``arrive_year``."""

    id: int
    target: int
    arrive_year: float
    speed_pc_yr: float
    retargets: int = 0  # how many times this probe has lost a race and re-aimed (capped by max_retargets)
    hop_len_pc: float = 0.0  # length of the hop this probe is currently flying (its launch/re-aim distance)
    # Launch position and year of the current hop, read only by coordination="inflight" to interpolate the probe's mid-flight position.
    from_x: float = 0.0
    from_y: float = 0.0
    from_z: float = 0.0
    launch_year: float = 0.0


@dataclass(slots=True)
class SwarmState:
    """Full state carried by the fold."""

    rng: int
    year: float
    # Fixed star field, stored as tuples of Python floats so per-element access in the per-arrival hot loop is native Python (~40% faster than numpy scalar boxing).
    xs: tuple[float, ...]
    ys: tuple[float, ...]
    zs: tuple[float, ...]
    star_speed_pc_yr: tuple[float, ...]
    # settled_year is numpy (mutated per settle, and read by njit); Python reads convert to `float()` at hot access sites.
    settled_year: np.ndarray
    origin: int  # index of the homeworld star (front radius is measured from here)
    # In-flight probes keyed by id, insertion-ordered (issue #27).
    probes: dict[int, Probe]
    next_probe_id: int
    total_launched: int
    max_speed_pc_yr: float  # fastest probe launched so far (shows accumulated boost)
    box_side_pc: float = 0.0  # side of the cube (for the periodic minimum-image metric)
    periodic: bool = False  # torus (minimum-image distances) instead of a hard wall
    # Running settled-count and front radius, maintained incrementally at the settle site so the
    settled_count: int = 0
    front_radius: float = 0.0
    # Balanced k-d tree over the (fixed) star positions, replacing the flat cell list (issue #30).
    xs_np: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    ys_np: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    zs_np: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    kd_root: int = -1
    kd_axis: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int8))
    kd_split: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    kd_lo: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int32))
    kd_hi: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int32))
    kd_parent: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int32))
    kd_bucket_flat: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int32))
    kd_bucket_offsets: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int32))
    kd_bxmin: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    kd_bxmax: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    kd_bymin: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    kd_bymax: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    kd_bzmin: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    kd_bzmax: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    kd_nuns: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int32))
    kd_tsmax: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    star_leaf: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int32))
    # Prebuilt tuple of (xs_np, ys_np, zs_np, settled_year, kd_root, kd_axis, kd_split, kd_lo,
    _njit_args: tuple = field(default_factory=tuple)
    # Event queue (issue #27): a lazy min-heap of (actionable_year, probe_id), so the next event is
    ev_heap: list[tuple[float, int]] = field(default_factory=list)
    by_target: dict[int, list[int]] = field(default_factory=dict)
    # --- coordination observability (the cost of no-coordination; 0 unless probes race) ---
    total_arrivals: int = 0  # every probe arrival processed
    wasted_arrivals: int = 0  # arrivals landing on an already-(truly-)settled star (redundant trips)
    retarget_count: int = 0  # total re-target events (a lost race that re-aimed)
    # Redundant travel distance (pc): the common currency across coordination modes.
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
    settle_v_sum_pc_yr: float = 0.0  # sum of flight speeds over winning journeys
    settle_v2_sum: float = 0.0  # sum of speed^2 [(pc/yr)^2] over winning journeys
    wasted_v_sum_pc_yr: float = 0.0  # sum of flight speeds over wasted journeys
    wasted_v2_sum: float = 0.0  # sum of speed^2 [(pc/yr)^2] over wasted journeys
    # --- hop-length-stratified arrival counts (read-only; the clumpy-field d-cancellation test) ---
    settle_hop_hist: list[int] = field(default_factory=lambda: [0] * N_HOP_BINS)
    wasted_hop_hist: list[int] = field(default_factory=lambda: [0] * N_HOP_BINS)
    # --- wall-distance-stratified arrival counts (read-only; the finite-size EDGE test, M1) ---
    settle_wall_hist: list[int] = field(default_factory=lambda: [0] * N_WALL_BINS)
    wasted_wall_hist: list[int] = field(default_factory=lambda: [0] * N_WALL_BINS)
    # Scratchpad: normalized claim-margin histogram for wasted arrivals in the instant run.
    wasted_s_hist: list[int] = field(default_factory=lambda: [0] * 32)

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
    t25_years: float | None = None
    t75_years: float | None = None
    t99_years: float | None = None
    coordination: str = "instant"  # knowledge regime this run used
    total_arrivals: int = 0  # every probe arrival (settlements + wasted trips)
    wasted_arrivals: int = 0  # arrivals at an already-settled star - the cost of stale info
    retarget_count: int = 0  # total re-target events
    # Redundant travel distance (pc) and, for "inflight", the count of mid-flight aborts.
    wasted_travel_pc: float = 0.0
    midflight_aborts: int = 0
    # Effective speed actually achieved (not just the powered-cruise input): the mean speed at
    mean_launch_speed_km_s: float = 0.0
    # Mean hop length of winning vs wasted trips (pc): the wasted-trip length is the direct
    mean_settle_hop_pc: float = 0.0
    mean_wasted_hop_pc: float = 0.0
    # Energy-weighted-tax observables: Newtonian (1/2)(v/c)^2 per journey, within 3.1% of the relativistic (gamma-1) up to 0.2c.
    settle_energy_c2: float = 0.0  # sum over winning journeys of (1/2)(v/c)^2
    wasted_energy_c2: float = 0.0  # sum over wasted journeys of (1/2)(v/c)^2
    mean_settle_speed_km_s: float = 0.0  # mean flight speed of winning journeys
    mean_wasted_speed_km_s: float = 0.0  # mean flight speed of wasted journeys
    # Won/wasted arrivals binned by hop length (HOP_BIN_EDGES) - the clumpy-field d-cancellation
    settle_hop_hist: list[int] = field(default_factory=list)
    wasted_hop_hist: list[int] = field(default_factory=list)
    # Won/wasted arrivals binned by target-star distance to nearest wall (WALL_BIN_EDGES_NN, in
    settle_wall_hist: list[int] = field(default_factory=list)
    wasted_wall_hist: list[int] = field(default_factory=list)
    wasted_s_hist: list[int] = field(default_factory=list)
    steps: list[SwarmStep] = field(default_factory=list)

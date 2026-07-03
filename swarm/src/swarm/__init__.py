"""swarm - a deterministic interstellar settlement front (ROADMAP §4, slice 1).

The paradigm step beyond the small deterministic fleet: probes spread star-to-star
through a seeded field, settling and re-launching, and we ask how fast the reachable
galaxy fills (the exploration-timescale question of Nicholson & Forgan 2013). This
first slice is the pure, seeded, fixed-step algorithm core - straight-line travel,
nearest-unsettled policy - validated in Python. Slingshots, the 200k-star SoA
performance engine + spatial hashing, WebGL rendering, and the novel
light-speed-limited-coordination extension are later slices (see README/ROADMAP).
"""

from swarm.models import (
    C_PC_PER_YEAR,
    Probe,
    SwarmParams,
    SwarmResult,
    SwarmState,
    SwarmStep,
)
from swarm.sim import initial_state, simulate_swarm, step

__all__ = [
    "simulate_swarm",
    "step",
    "initial_state",
    "SwarmParams",
    "SwarmState",
    "SwarmStep",
    "SwarmResult",
    "Probe",
    "C_PC_PER_YEAR",
]

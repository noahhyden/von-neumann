"""closure-sim: closure & self-replication analysis for in-situ space factories."""

from .analysis import ElectronicsWallReport, electronics_wall
from .closure import ClosureReport, compute_closure
from .models import (
    ELECTRONICS_CATEGORIES,
    Factory,
    ReplicationParams,
    Subsystem,
)
from .replication import Regime, SimResult, reaches_target, simulate
from .scenarios import load_factory
from .structures import (
    SINTERED_REGOLITH_STRENGTH_BAND_MPA,
    SINTERED_REGOLITH_STRENGTH_MPA,
    closure_with_structural_penalty,
    is_producible_locally,
    mass_penalty_k,
)

__all__ = [
    "ELECTRONICS_CATEGORIES",
    "ClosureReport",
    "ElectronicsWallReport",
    "Factory",
    "Regime",
    "ReplicationParams",
    "SimResult",
    "Subsystem",
    "compute_closure",
    "electronics_wall",
    "load_factory",
    "simulate",
    "reaches_target",
    "SINTERED_REGOLITH_STRENGTH_BAND_MPA",
    "SINTERED_REGOLITH_STRENGTH_MPA",
    "closure_with_structural_penalty",
    "is_producible_locally",
    "mass_penalty_k",
]

"""closure-sim: closure & self-replication analysis for in-situ space factories."""

from .analysis import ElectronicsWallReport, electronics_wall
from .closure import ClosureReport, compute_closure
from .models import (
    ELECTRONICS_CATEGORIES,
    Factory,
    ReplicationParams,
    Subsystem,
)
from .replication import Regime, SimResult, simulate
from .scenarios import load_factory

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
]

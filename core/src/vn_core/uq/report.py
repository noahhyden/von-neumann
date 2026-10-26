"""Paper-ready one-liner: the "X, +/- Y, driven by Z" line the issue asks for."""

from __future__ import annotations

from vn_core.uq.sample import MCResult
from vn_core.uq.sobol import SobolResult


def one_line_finding(
    name: str,
    unit: str,
    mc: MCResult,
    sobol: SobolResult,
    *,
    ci_pct: int = 90,
) -> str:
    """Format one finding as "X = m +/- s <unit> (<ci_pct>% CI [lo, hi]), driven by <input> (S_T=v)"."""
    ranked = sobol.ranked()
    top_name, top_val = ranked[0]
    driver_clause: str
    if len(ranked) >= 2 and (top_val - ranked[1][1]) < 0.1:
        # No clear dominant driver; the second is within 0.1 of the top.
        second_name, second_val = ranked[1]
        driver_clause = (
            f"shared between {top_name} (S_T={top_val:.2f}) "
            f"and {second_name} (S_T={second_val:.2f})"
        )
    else:
        driver_clause = f"driven by {top_name} (S_T={top_val:.2f})"

    return (
        f"{name} = {mc.mean:.4g} +/- {mc.std:.4g} {unit} "
        f"({ci_pct}% CI [{mc.q05:.4g}, {mc.q95:.4g}]), "
        f"{driver_clause}"
    )

"""Simulation verification: MC, randomized QMC and PCE must agree on a finding's mean."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from vn_core.uq.distributions import Distribution, Fixed
from vn_core.uq.pce import pce_fit
from vn_core.uq.qmc import qmc_mean
from vn_core.uq.sample import monte_carlo
from vn_core.uq.sobol import sobol_total_order


@dataclass(frozen=True)
class VerifyResult:
    """Three independent mean estimates, their pairwise gaps, and the Sobol cross-check."""

    mc_mean: float
    qmc_mean: float
    pce_mean: float
    gap_mc_qmc: float  # relative gaps: |a-b| / max(|a|, |b|)
    gap_mc_pce: float
    gap_qmc_pce: float
    sobol_sampled: tuple[tuple[str, float], ...]
    sobol_pce: tuple[tuple[str, float], ...]
    sobol_max_gap: float  # largest absolute total-order difference over active inputs
    sobol_rank_agrees: bool
    pce_trustworthy: bool
    rtol: float
    agree: bool  # every pairwise mean gap <= rtol


def _gap(a: float, b: float) -> float:
    scale = max(abs(a), abs(b))
    return 0.0 if scale == 0.0 else abs(a - b) / scale


def verify_finding(
    inputs: Mapping[str, Distribution],
    f: Callable[[Mapping[str, float]], float],
    *,
    seed: int,
    n_mc: int = 2048,
    n_qmc: int = 256,
    qmc_replicates: int = 16,
    pce_degree: int = 3,
    rtol: float = 0.05,
) -> VerifyResult:
    """Cross-check a finding's mean three ways and its Sobol indices two ways."""
    active = [k for k, d in inputs.items() if not isinstance(d, Fixed)]
    mc = monte_carlo(inputs, f, n=n_mc, seed=seed).mean
    qm = qmc_mean(inputs, f, n=n_qmc, seed=seed + 1, replicates=qmc_replicates).mean
    pce = pce_fit(inputs, f, degree=pce_degree, seed=seed + 2)
    n_sobol = max(16, n_mc // (len(active) + 2))
    samp = sobol_total_order(inputs, f, n=n_sobol, seed=seed + 3).total_order if active else {}
    s_samp = tuple(sorted(((k, samp[k]) for k in active), key=lambda kv: (-kv[1], kv[0])))
    s_pce = tuple(sorted(((k, pce.total_order[k]) for k in active), key=lambda kv: (-kv[1], kv[0])))
    gaps = (_gap(mc, qm), _gap(mc, pce.mean), _gap(qm, pce.mean))
    return VerifyResult(
        mc_mean=mc, qmc_mean=qm, pce_mean=pce.mean,
        gap_mc_qmc=gaps[0], gap_mc_pce=gaps[1], gap_qmc_pce=gaps[2],
        sobol_sampled=s_samp, sobol_pce=s_pce,
        sobol_max_gap=max((abs(samp[k] - pce.total_order[k]) for k in active), default=0.0),
        sobol_rank_agrees=[k for k, _ in s_samp] == [k for k, _ in s_pce],
        pce_trustworthy=pce.is_trustworthy(), rtol=rtol,
        agree=all(g <= rtol for g in gaps),
    )

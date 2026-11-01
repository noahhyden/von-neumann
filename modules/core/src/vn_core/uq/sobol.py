"""Global sensitivity: Sobol total-order indices via Saltelli-style sampling."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from vn_core.uq.distributions import Distribution
from vn_core.uq.sample import MCResult, summarize
from vn_core.uq.sequences import MAX_SOBOL_DIM, sobol_points


@dataclass(frozen=True)
class SobolResult:
    """Sobol indices per input, with confidence intervals to sanity-check them."""

    total_order: dict[str, float]
    first_order: dict[str, float]
    total_order_ci: dict[str, tuple[float, float]]
    first_order_ci: dict[str, tuple[float, float]]
    variance: float
    mean: float
    n: int
    n_evaluations: int
    ci_method: str
    second_order: dict[tuple[str, str], float] | None = None
    second_order_ci: dict[tuple[str, str], tuple[float, float]] | None = None

    def ranked(self) -> list[tuple[str, float]]:
        """Inputs sorted by decreasing total-order index."""
        return sorted(self.total_order.items(), key=lambda kv: -kv[1])


@dataclass(frozen=True)
class _SaltelliEvals:
    """The finding evaluations of one Saltelli design - the shared substrate."""

    names: tuple[str, ...]
    y_a: list[float]
    y_b: list[float]
    y_ab: dict[str, list[float]]
    n: int
    # y_ba[name] is the finding on B with column name replaced by A's column; None unless second_order was requested (it raises the model calls to N*(2K+2)).
    y_ba: dict[str, list[float]] | None = None


def _ab_matrices(
    sampler: str, n: int, k: int, seed: int
) -> tuple[list[list[float]], list[list[float]]]:
    """The two base uniform matrices A, B in [0, 1)^{n x k} for the Saltelli design."""
    if sampler == "random":
        rng = random.Random(seed)
        a_u = [[rng.random() for _ in range(k)] for _ in range(n)]
        b_u = [[rng.random() for _ in range(k)] for _ in range(n)]
        return a_u, b_u
    if sampler == "sobol":
        if 2 * k > MAX_SOBOL_DIM:
            raise ValueError(
                f"sampler='sobol' needs 2*K <= {MAX_SOBOL_DIM} tabulated Sobol' dimensions "
                f"(A and B are independent column blocks of one sequence); K={k} gives "
                f"2K={2 * k}. Use sampler='random' for more inputs."
            )
        pts = sobol_points(n, 2 * k, skip=1)
        a_u = [list(p[:k]) for p in pts]
        b_u = [list(p[k:]) for p in pts]
        return a_u, b_u
    raise ValueError(f"unknown sampler {sampler!r}; choose 'random' or 'sobol'")


def _saltelli_evaluate(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
    sampler: str = "random",
    second_order: bool = False,
) -> _SaltelliEvals:
    """Run one Saltelli design and return all its finding evaluations."""
    if n < 2:
        raise ValueError(f"n must be >= 2, got {n}")
    names = tuple(inputs.keys())
    k = len(names)
    if k < 1:
        raise ValueError("a Saltelli design requires at least one input")

    a_u, b_u = _ab_matrices(sampler, n, k, seed)

    def push(u_row: list[float]) -> dict[str, float]:
        return {name: inputs[name].quantile(u) for name, u in zip(names, u_row)}

    y_a = [finding(push(row)) for row in a_u]
    y_b = [finding(push(row)) for row in b_u]

    y_ab: dict[str, list[float]] = {}
    for i, name in enumerate(names):
        # AB^(i): copy A, replace column i with B's column i.
        ab_rows = [row.copy() for row in a_u]
        for j in range(n):
            ab_rows[j][i] = b_u[j][i]
        y_ab[name] = [finding(push(row)) for row in ab_rows]

    y_ba: dict[str, list[float]] | None = None
    if second_order:
        y_ba = {}
        for i, name in enumerate(names):
            # BA^(i): copy B, replace column i with A's column i (the mirror of AB).
            ba_rows = [row.copy() for row in b_u]
            for j in range(n):
                ba_rows[j][i] = a_u[j][i]
            y_ba[name] = [finding(push(row)) for row in ba_rows]

    return _SaltelliEvals(names=names, y_a=y_a, y_b=y_b, y_ab=y_ab, n=n, y_ba=y_ba)


# 90% two-sided normal quantile (z_0.95), for the asymptotic CI half-width.
_Z90 = 1.6448536269514722


def _asymptotic_ci(
    rows_by_name: dict[str, list[float]], center: dict[str, float], n: int
) -> dict[str, tuple[float, float]]:
    """90% CI from the estimator's own standard error (each index is a mean of rows)."""
    out: dict[str, tuple[float, float]] = {}
    for name, rows in rows_by_name.items():
        se = statistics.pstdev(rows) / math.sqrt(n) if n >= 2 else 0.0
        half = _Z90 * se
        out[name] = (center[name] - half, center[name] + half)
    return out


def _bootstrap_ci(
    ev: _SaltelliEvals, mean: float, n_boot: int, seed: int
) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    """90% percentile CIs by resampling the N design rows with replacement."""
    rng = random.Random(seed)
    n = ev.n
    t_num = {nm: [(ev.y_a[j] - ev.y_ab[nm][j]) ** 2 for j in range(n)] for nm in ev.names}
    fb = {nm: [ev.y_b[j] * (ev.y_ab[nm][j] - ev.y_a[j]) for j in range(n)] for nm in ev.names}
    diff = {nm: [ev.y_ab[nm][j] - ev.y_a[j] for j in range(n)] for nm in ev.names}
    boot_total = {nm: [] for nm in ev.names}
    boot_first = {nm: [] for nm in ev.names}
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        comb = [ev.y_a[j] for j in idx] + [ev.y_b[j] for j in idx]
        var_b = statistics.pvariance(comb)
        if var_b == 0.0:
            continue
        mean_b = statistics.fmean(comb)
        for nm in ev.names:
            boot_total[nm].append(sum(t_num[nm][j] for j in idx) / (2.0 * n * var_b))
            # Centered first-order: sum (y_b - mean_b)(y_ab - y_a) = sum fb - mean_b sum diff.
            first_num = sum(fb[nm][j] for j in idx) - mean_b * sum(diff[nm][j] for j in idx)
            boot_first[nm].append(first_num / (n * var_b))

    def ci(vals: list[float]) -> tuple[float, float]:
        if not vals:  # pragma: no cover - vals is empty only if every bootstrap resample
            # vals is empty only if every bootstrap resample had zero variance, which needs a (near-)constant finding, but a constant finding is caught by the var == 0 early return before bootstrap runs.
            return (0.0, 0.0)
        s = sorted(vals)
        lo = s[int(0.05 * (len(s) - 1))]
        hi = s[int(math.ceil(0.95 * (len(s) - 1)))]
        return (lo, hi)

    return (
        {nm: ci(boot_total[nm]) for nm in ev.names},
        {nm: ci(boot_first[nm]) for nm in ev.names},
    )


def _second_order_indices(
    ev: _SaltelliEvals,
    var: float,
    first_rows: dict[str, list[float]],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], tuple[float, float]]]:
    """Pairwise interaction indices S_ij (with asymptotic CIs) from the BA matrices."""
    assert ev.y_ba is not None  # only called when second-order was evaluated
    n = ev.n
    names = ev.names
    second: dict[tuple[str, str], float] = {}
    second_ci: dict[tuple[str, str], tuple[float, float]] = {}
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            ni, nj = names[a], names[b]
            ab_i, ba_j = ev.y_ab[ni], ev.y_ba[nj]
            # Per-row pure-interaction term: closed second-order minus the two mains.
            rows = [
                (ab_i[j] * ba_j[j] - ev.y_a[j] * ev.y_b[j]) / var
                - first_rows[ni][j]
                - first_rows[nj][j]
                for j in range(n)
            ]
            sij = statistics.fmean(rows)
            se = statistics.pstdev(rows) / math.sqrt(n) if n >= 2 else 0.0
            half = _Z90 * se
            second[(ni, nj)] = sij
            second_ci[(ni, nj)] = (sij - half, sij + half)
    return second, second_ci


def _sobol_from_evals(
    ev: _SaltelliEvals, *, bootstrap: int = 0, seed: int = 0
) -> SobolResult:
    """First- and total-order Sobol indices (with CIs) from a Saltelli design."""
    k = len(ev.names)
    # Union variance from A and B evaluations - 2N samples, tighter than either alone; a degenerate constant finding (var == 0) is handled just below.
    combined = ev.y_a + ev.y_b
    var = statistics.pvariance(combined)
    # Total finding calls: N*(K+2) for first+total order; the BA matrices add N*K more, giving N*(2K+2).
    n_eval = ev.n * (2 * k + 2) if ev.y_ba is not None else ev.n * (k + 2)
    mean = statistics.fmean(combined)
    if var == 0.0:
        # No variance in the output means no input contributes any, so report zeros rather than dividing 0/0 (a deterministic finding is honestly labelled as such).
        zeros = {name: 0.0 for name in ev.names}
        zero_ci = {name: (0.0, 0.0) for name in ev.names}
        pairs = (
            [(ev.names[a], ev.names[b]) for a in range(k) for b in range(a + 1, k)]
            if ev.y_ba is not None
            else None
        )
        second_zero = {p: 0.0 for p in pairs} if pairs is not None else None
        second_zero_ci = {p: (0.0, 0.0) for p in pairs} if pairs is not None else None
        return SobolResult(
            total_order=dict(zeros), first_order=dict(zeros),
            total_order_ci=dict(zero_ci), first_order_ci=dict(zero_ci),
            variance=0.0, mean=mean, n=ev.n, n_evaluations=n_eval, ci_method="none",
            second_order=second_zero, second_order_ci=second_zero_ci,
        )

    n = ev.n
    total_order: dict[str, float] = {}
    first_order: dict[str, float] = {}
    total_rows: dict[str, list[float]] = {}
    first_rows: dict[str, list[float]] = {}
    for name in ev.names:
        y_ab = ev.y_ab[name]
        # Jansen total-order estimator (arithmetic kept exactly as before so the point estimate stays byte-identical to the pre-CI implementation).
        s = sum((ev.y_a[j] - y_ab[j]) ** 2 for j in range(n))
        total_order[name] = s / (2.0 * n * var)
        # Saltelli-2010 first-order estimator, CENTERED: subtract the output mean, else a low-coefficient-of-variation finding suffers catastrophic cancellation (REFERENCES.md); total-order is immune because it uses differences.
        s_f = sum((ev.y_b[j] - mean) * (y_ab[j] - ev.y_a[j]) for j in range(n))
        first_order[name] = s_f / (n * var)
        total_rows[name] = [(ev.y_a[j] - y_ab[j]) ** 2 / (2.0 * var) for j in range(n)]
        first_rows[name] = [(ev.y_b[j] - mean) * (y_ab[j] - ev.y_a[j]) / var for j in range(n)]

    if bootstrap > 0:
        total_ci, first_ci = _bootstrap_ci(ev, mean, bootstrap, seed)
        ci_method = "bootstrap"
    else:
        total_ci = _asymptotic_ci(total_rows, total_order, n)
        first_ci = _asymptotic_ci(first_rows, first_order, n)
        ci_method = "asymptotic"

    second_order = None
    second_order_ci = None
    if ev.y_ba is not None:
        # Second-order CIs are always asymptotic (from the per-row spread); the bootstrap path above covers first- and total-order only.
        second_order, second_order_ci = _second_order_indices(ev, var, first_rows)

    return SobolResult(
        total_order=total_order,
        first_order=first_order,
        total_order_ci=total_ci,
        first_order_ci=first_ci,
        variance=var,
        mean=mean,
        n=ev.n,
        n_evaluations=n_eval,
        ci_method=ci_method,
        second_order=second_order,
        second_order_ci=second_order_ci,
    )


def sobol_total_order(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
    bootstrap: int = 0,
    sampler: str = "random",
    second_order: bool = False,
) -> SobolResult:
    """First- and total-order Sobol indices, each with a 90% confidence interval."""
    ev = _saltelli_evaluate(
        inputs, finding, n=n, seed=seed, sampler=sampler, second_order=second_order
    )
    return _sobol_from_evals(ev, bootstrap=bootstrap, seed=seed)


@dataclass(frozen=True)
class Analysis:
    """Both readouts of one Saltelli design: UQ (spread) and GSA (attribution)."""

    uq: MCResult
    gsa: SobolResult


def uq_and_gsa(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
    bootstrap: int = 0,
    sampler: str = "random",
    second_order: bool = False,
) -> Analysis:
    """Propagate uncertainty AND rank drivers from one Saltelli design."""
    ev = _saltelli_evaluate(
        inputs, finding, n=n, seed=seed, sampler=sampler, second_order=second_order
    )
    uq = summarize(ev.y_a + ev.y_b, ev.names)
    gsa = _sobol_from_evals(ev, bootstrap=bootstrap, seed=seed)
    return Analysis(uq=uq, gsa=gsa)

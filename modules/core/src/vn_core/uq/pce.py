"""Polynomial chaos expansion (PCE): the spectral surrogate for smooth findings."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import product

from vn_core.linalg import solve_lstsq
from vn_core.uq.distributions import (
    Distribution,
    Fixed,
    LogNormal,
    LogUniform,
    Normal,
    Uniform,
)

# Polynomial families keyed by the distribution they are orthogonal to.
_LEGENDRE = "legendre"  # Uniform
_HERMITE = "hermite"  # Normal (probabilists' He_n, standard-normal weight)
_ARBITRARY = "arbitrary"  # any distribution: basis built from its moments (aPCE)

# Points used to discretize an arbitrary distribution for the Stieltjes procedure.
_STIELTJES_DISC = 4000


# --- Gauss quadrature: Golub-Welsch nodes/weights on the reference domain ------


def _recurrence_beta(family: str, k: int) -> float:
    """Monic three-term recurrence coefficient b_k for the reference measure."""
    if k == 0:
        return 1.0
    if family == _LEGENDRE:
        return (k * k) / (4.0 * k * k - 1.0)  # k^2 / (4k^2 - 1)
    if family == _HERMITE:
        return float(k)
    raise ValueError(f"unknown polynomial family {family!r}")


def _jacobi_eigen(a: list[list[float]]) -> tuple[list[float], list[list[float]]]:
    """Eigenvalues + eigenvectors of a small dense symmetric matrix (Jacobi rotations)."""
    n = len(a)
    m = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    if n == 1:
        return [m[0][0]], v
    for _ in range(100):  # pragma: no cover - the 100-sweep cap is never exhausted:
        # Jacobi converges quadratically on these small symmetric matrices and breaks on off < 1e-300 first, so the 100-sweep cap is a floor, not a normal exit.
        off = math.sqrt(sum(m[p][q] ** 2 for p in range(n) for q in range(p + 1, n)))
        if off < 1e-300:
            break
        for p in range(n):
            for q in range(p + 1, n):
                apq = m[p][q]
                if abs(apq) < 1e-300:
                    continue
                app, aqq = m[p][p], m[q][q]
                theta = (aqq - app) / (2.0 * apq)
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                # Update the pivot 2x2 block explicitly, then only the off-pivot rows and cols: updating all rows and all cols would touch the pivot block twice and corrupt the rotation.
                m[p][p] = app - t * apq
                m[q][q] = aqq + t * apq
                m[p][q] = 0.0
                m[q][p] = 0.0
                for r in range(n):
                    if r == p or r == q:
                        continue
                    mrp, mrq = m[r][p], m[r][q]
                    m[r][p] = m[p][r] = c * mrp - s * mrq
                    m[r][q] = m[q][r] = s * mrp + c * mrq
                for r in range(n):
                    vrp, vrq = v[r][p], v[r][q]
                    v[r][p] = c * vrp - s * vrq
                    v[r][q] = s * vrp + c * vrq
    eigenvalues = [m[i][i] for i in range(n)]
    return eigenvalues, v


def _gauss_nodes_weights(family: str, m: int) -> tuple[list[float], list[float]]:
    """m-point Gauss nodes and weights for the family's reference measure."""
    jac = [[0.0] * m for _ in range(m)]
    for k in range(1, m):
        beta = math.sqrt(_recurrence_beta(family, k))
        jac[k - 1][k] = beta
        jac[k][k - 1] = beta
    eigenvalues, v = _jacobi_eigen(jac)
    order = sorted(range(m), key=lambda i: eigenvalues[i])
    nodes = [eigenvalues[i] for i in order]
    weights = [v[0][i] ** 2 for i in order]
    return nodes, weights


# --- Orthonormal basis on the reference domain (E[phi_n^2] = 1) -----------------


def _basis_values(family: str, max_degree: int, xi: float) -> list[float]:
    """[phi_0(xi), ..., phi_{max_degree}(xi)] for the orthonormal family basis."""
    if family == _LEGENDRE:
        # Standard Legendre recurrence, then normalize: E[P_n^2] = 1/(2n+1).
        p = [0.0] * (max_degree + 1)
        p[0] = 1.0
        if max_degree >= 1:
            p[1] = xi
        for n in range(1, max_degree):
            p[n + 1] = ((2 * n + 1) * xi * p[n] - n * p[n - 1]) / (n + 1)
        return [p[n] * math.sqrt(2 * n + 1) for n in range(max_degree + 1)]
    if family == _HERMITE:
        # Probabilists' Hermite He_n, then normalize: E[He_n^2] = n!.
        he = [0.0] * (max_degree + 1)
        he[0] = 1.0
        if max_degree >= 1:
            he[1] = xi
        for n in range(1, max_degree):
            he[n + 1] = xi * he[n] - n * he[n - 1]
        fact = 1.0
        out = [he[0]]
        for n in range(1, max_degree + 1):
            fact *= n
            out.append(he[n] / math.sqrt(fact))
        return out
    raise ValueError(f"unknown polynomial family {family!r}")


# --- Input adapters: family + physical<->reference map per distribution ---------


@dataclass(frozen=True)
class _Adapter:
    """How one input maps to its orthonormal-polynomial reference variable."""

    kind: str
    p0: float
    p1: float
    alpha: tuple[float, ...] = ()
    beta: tuple[float, ...] = ()


def _stieltjes(
    dist: Distribution, max_degree: int, n_disc: int = _STIELTJES_DISC
) -> tuple[float, float, tuple[float, ...], tuple[float, ...]]:
    """Recurrence (alpha_k, beta_k) of the polynomials orthonormal to ``dist``."""
    us = [(i + 0.5) / n_disc for i in range(n_disc)]
    xs = [dist.quantile(u) for u in us]
    mu = statistics.fmean(xs)
    sigma = statistics.pstdev(xs)
    if sigma <= 0:
        raise ValueError("arbitrary-PCE input has zero spread; model it as Fixed")
    z = [(x - mu) / sigma for x in xs]
    w = 1.0 / n_disc
    alpha: list[float] = []
    beta: list[float] = [1.0]
    p_prev = [0.0] * n_disc
    p_cur = [1.0] * n_disc
    inner_prev = 1.0
    inner_cur = sum(w * p_cur[i] ** 2 for i in range(n_disc))  # = 1
    for k in range(max_degree + 1):  # pragma: no cover - the range never exhausts: the
        # The k == max_degree branch below always breaks on the final index, so the loop's natural-exit edge is unreachable (the recurrence needs one alpha per degree).
        num = sum(w * z[i] * p_cur[i] ** 2 for i in range(n_disc))
        alpha.append(num / inner_cur)
        if k == max_degree:
            break
        b_recur = (inner_cur / inner_prev) if k >= 1 else 0.0
        p_next = [(z[i] - alpha[k]) * p_cur[i] - b_recur * p_prev[i] for i in range(n_disc)]
        inner_next = sum(w * p_next[i] ** 2 for i in range(n_disc))
        beta.append(inner_next / inner_cur)
        p_prev, p_cur = p_cur, p_next
        inner_prev, inner_cur = inner_cur, inner_next
    return mu, sigma, tuple(alpha), tuple(beta)


def _basis_from_recurrence(
    alpha: tuple[float, ...], beta: tuple[float, ...], max_degree: int, z: float
) -> list[float]:
    """[phi_0..phi_max_degree](z) for the arbitrary family's orthonormal basis."""
    p = [0.0] * (max_degree + 1)
    p[0] = 1.0
    if max_degree >= 1:
        p[1] = z - alpha[0]
    for k in range(1, max_degree):
        p[k + 1] = (z - alpha[k]) * p[k] - beta[k] * p[k - 1]
    out: list[float] = []
    norm2 = 1.0
    for k in range(max_degree + 1):
        if k > 0:
            norm2 *= beta[k]  # <p_k,p_k> = prod_{j<=k} beta_j (beta_0 = 1)
        out.append(p[k] / math.sqrt(norm2))
    return out


def _gauss_from_recurrence(
    alpha: tuple[float, ...], beta: tuple[float, ...], m: int
) -> tuple[list[float], list[float]]:
    """m-point Gauss nodes/weights for the arbitrary family (Golub-Welsch)."""
    jac = [[0.0] * m for _ in range(m)]
    for k in range(m):
        jac[k][k] = alpha[k]
    for k in range(1, m):
        b = math.sqrt(beta[k])
        jac[k - 1][k] = b
        jac[k][k - 1] = b
    eigenvalues, v = _jacobi_eigen(jac)
    order = sorted(range(m), key=lambda i: eigenvalues[i])
    return [eigenvalues[i] for i in order], [v[0][i] ** 2 for i in order]


def _adapt(dist: Distribution, max_degree: int) -> _Adapter:
    """Build the reference-variable adapter for one input distribution."""
    if isinstance(dist, Uniform):
        return _Adapter(_LEGENDRE, dist.low, dist.high)
    if isinstance(dist, Normal):
        if dist.std <= 0:
            raise ValueError("PCE needs a Normal with std > 0 (a zero-std Normal is Fixed)")
        return _Adapter(_HERMITE, dist.mean, dist.std)
    if isinstance(dist, (LogNormal, LogUniform)):
        mu, sigma, alpha, beta = _stieltjes(dist, max_degree)
        return _Adapter(_ARBITRARY, mu, sigma, alpha, beta)
    raise NotImplementedError(
        f"PCE does not support {type(dist).__name__} inputs; use monte_carlo / "
        "uq_and_gsa, or add a distribution with a quantile() for the arbitrary path."
    )


def _to_reference(ad: _Adapter, x: float) -> float:
    if ad.kind == _LEGENDRE:
        return 2.0 * (x - ad.p0) / (ad.p1 - ad.p0) - 1.0
    return (x - ad.p0) / ad.p1  # Hermite (mean,std) / arbitrary (mu,sigma)


def _to_physical(ad: _Adapter, ref: float) -> float:
    if ad.kind == _LEGENDRE:
        return ad.p0 + (ad.p1 - ad.p0) * (ref + 1.0) / 2.0
    return ad.p0 + ad.p1 * ref


def _basis_at(ad: _Adapter, max_degree: int, ref: float) -> list[float]:
    if ad.kind == _ARBITRARY:
        return _basis_from_recurrence(ad.alpha, ad.beta, max_degree, ref)
    return _basis_values(ad.kind, max_degree, ref)


def _gauss_for(ad: _Adapter, m: int) -> tuple[list[float], list[float]]:
    if ad.kind == _ARBITRARY:
        return _gauss_from_recurrence(ad.alpha, ad.beta, m)
    return _gauss_nodes_weights(ad.kind, m)


# --- Result --------------------------------------------------------------------


@dataclass(frozen=True)
class PCEResult:
    """A fitted polynomial chaos expansion and everything read off its coefficients."""

    mean: float
    variance: float
    std: float
    first_order: dict[str, float]
    total_order: dict[str, float]
    degree: int
    n_evaluations: int  # model calls for the fit
    n_validation: int  # model calls for the fit-quality check
    fit_residual: float  # relative RMS surrogate error on the validation sample
    input_names: tuple[str, ...]  # active (non-Fixed) inputs, in order
    method: str  # "quadrature" (tensor Gauss) or "regression" (least squares)

    # Private surrogate state for predict(); underscored to signal "not the API".
    coefficients: dict[tuple[int, ...], float]
    _adapters: tuple["_Adapter", ...]
    _fixed: tuple[tuple[str, float], ...]

    def is_trustworthy(self, tol: float = 1e-2) -> bool:
        """True when the surrogate reproduces the finding well (fit_residual < tol)."""
        return self.fit_residual < tol

    def predict(self, sample: Mapping[str, float]) -> float:
        """Evaluate the surrogate polynomial at a physical input sample."""
        xis = [
            _to_reference(ad, sample[name])
            for name, ad in zip(self.input_names, self._adapters)
        ]
        max_deg = self.degree
        tables = [_basis_at(ad, max_deg, xi) for ad, xi in zip(self._adapters, xis)]
        total = 0.0
        for alpha, c in self.coefficients.items():
            term = c
            for d, a in enumerate(alpha):
                term *= tables[d][a]
            total += term
        return total


# --- Fit -----------------------------------------------------------------------


def _check_finite(y: float) -> None:
    if math.isnan(y) or math.isinf(y):
        raise ValueError("finding returned nan/inf - a nonfinite draw is not honest UQ")


def _split_inputs(
    inputs: Mapping[str, Distribution], max_degree: int
) -> tuple[list[str], list[_Adapter], list[tuple[str, float]]]:
    """Partition inputs into active and Fixed; adapt the active for ``max_degree``."""
    active: list[str] = []
    adapters: list[_Adapter] = []
    fixed: list[tuple[str, float]] = []
    for name in inputs:
        dist = inputs[name]
        if isinstance(dist, Fixed):
            fixed.append((name, dist.value))
        else:
            active.append(name)
            adapters.append(_adapt(dist, max_degree))
    return active, adapters, fixed


def _total_degree_alphas(degree: int, d: int) -> list[tuple[int, ...]]:
    """All multi-indices with total degree <= ``degree`` over ``d`` inputs."""
    return [a for a in product(range(degree + 1), repeat=d) if sum(a) <= degree]


def _statistics(
    coeffs: dict[tuple[int, ...], float], active: list[str], d: int
) -> tuple[float, float, dict[str, float], dict[str, float]]:
    """Mean, variance, and first-/total-order Sobol indices from PCE coefficients."""
    zero = tuple([0] * d)
    mean = coeffs[zero]
    variance = sum(c * c for a, c in coeffs.items() if a != zero)
    first_order: dict[str, float] = {}
    total_order: dict[str, float] = {}
    for i, name in enumerate(active):
        if variance == 0.0:
            first_order[name] = 0.0
            total_order[name] = 0.0
            continue
        # First-order: only input i active in the multi-index.
        s1 = sum(
            c * c
            for a, c in coeffs.items()
            if a[i] > 0 and all(a[j] == 0 for j in range(d) if j != i)
        )
        # Total-order: input i active at all (direct effect + interactions).
        st = sum(c * c for a, c in coeffs.items() if a[i] > 0)
        first_order[name] = s1 / variance
        total_order[name] = st / variance
    return mean, variance, first_order, total_order


def _fit_quadrature(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    active: list[str],
    adapters: list[_Adapter],
    fixed_sample: dict[str, float],
    degree: int,
    d: int,
    alphas: list[tuple[int, ...]],
) -> tuple[dict[tuple[int, ...], float], int]:
    """Coefficients by tensor Gauss-quadrature pseudospectral projection."""
    m = degree + 1
    per_dim_nodes: list[list[float]] = []
    per_dim_weights: list[list[float]] = []
    per_dim_basis: list[list[list[float]]] = []
    for ad in adapters:
        nodes, weights = _gauss_for(ad, m)
        per_dim_nodes.append(nodes)
        per_dim_weights.append(weights)
        per_dim_basis.append([_basis_at(ad, degree, xi) for xi in nodes])

    idx_grid = list(product(*[range(m) for _ in range(d)]))
    ys: list[float] = []
    tensor_w: list[float] = []
    for idx in idx_grid:
        sample = dict(fixed_sample)
        for dim, node_i in enumerate(idx):
            sample[active[dim]] = _to_physical(adapters[dim], per_dim_nodes[dim][node_i])
        y = finding(sample)
        _check_finite(y)
        ys.append(y)
        w = 1.0
        for dim, node_i in enumerate(idx):
            w *= per_dim_weights[dim][node_i]
        tensor_w.append(w)

    coeffs: dict[tuple[int, ...], float] = {}
    for alpha in alphas:
        acc = 0.0
        for q, idx in enumerate(idx_grid):
            psi = 1.0
            for dim, node_i in enumerate(idx):
                psi *= per_dim_basis[dim][node_i][alpha[dim]]
            acc += tensor_w[q] * ys[q] * psi
        coeffs[alpha] = acc
    return coeffs, len(idx_grid)


def _smolyak_combinations(d: int, level: int) -> list[tuple[tuple[int, ...], int]]:
    """Smolyak combination multi-indices and coefficients (Gerstner-Griebel 1998)."""
    q = d + level
    combos: list[tuple[tuple[int, ...], int]] = []
    for lvec in product(range(1, level + 2), repeat=d):
        s = sum(lvec)
        if s < q - d + 1 or s > q:
            continue
        # q - s ranges over [0, d-1], so C(d-1, q-s) >= 1 and the coefficient is always nonzero: every retained multi-index contributes.
        coef = ((-1) ** (q - s)) * math.comb(d - 1, q - s)
        combos.append((lvec, coef))
    return combos


def _fit_sparse(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    active: list[str],
    adapters: list[_Adapter],
    fixed_sample: dict[str, float],
    degree: int,
    d: int,
    alphas: list[tuple[int, ...]],
) -> tuple[dict[tuple[int, ...], float], int]:
    """Coefficients by Smolyak sparse-grid pseudospectral projection."""
    # Aggregate signed weights by reference-node coordinate, rounding the key so the symmetric zero node shared by odd-point rules merges to one evaluation (first-seen unrounded coordinates are kept).
    node_weight: dict[tuple[float, ...], float] = {}
    node_coords: dict[tuple[float, ...], tuple[float, ...]] = {}
    rule_cache: dict[tuple[int, int], tuple[list[float], list[float]]] = {}
    for lvec, coef in _smolyak_combinations(d, degree):
        per_dim: list[tuple[list[float], list[float]]] = []
        for dim in range(d):
            m = lvec[dim]
            cached = rule_cache.get((dim, m))
            if cached is None:
                cached = _gauss_for(adapters[dim], m)
                rule_cache[(dim, m)] = cached
            per_dim.append(cached)
        for idx in product(*[range(lvec[dim]) for dim in range(d)]):
            coords = tuple(per_dim[dim][0][idx[dim]] for dim in range(d))
            key = tuple(round(c, 12) for c in coords)
            w = float(coef)
            for dim in range(d):
                w *= per_dim[dim][1][idx[dim]]
            if key in node_weight:
                node_weight[key] += w
            else:
                node_weight[key] = w
                node_coords[key] = coords

    coeffs: dict[tuple[int, ...], float] = {alpha: 0.0 for alpha in alphas}
    n_eval = 0
    for key, w in node_weight.items():
        coords = node_coords[key]
        sample = dict(fixed_sample)
        for dim in range(d):
            sample[active[dim]] = _to_physical(adapters[dim], coords[dim])
        y = finding(sample)
        _check_finite(y)
        n_eval += 1
        tables = [_basis_at(adapters[dim], degree, coords[dim]) for dim in range(d)]
        for alpha in alphas:
            psi = 1.0
            for dim in range(d):
                psi *= tables[dim][alpha[dim]]
            coeffs[alpha] += w * y * psi
    return coeffs, n_eval


def _fit_regression(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    active: list[str],
    adapters: list[_Adapter],
    fixed_sample: dict[str, float],
    degree: int,
    d: int,
    alphas: list[tuple[int, ...]],
    oversampling: float,
    n_samples: int | None,
    seed: int,
) -> tuple[dict[tuple[int, ...], float], int]:
    """Coefficients by least-squares regression over N sampled points."""
    p = len(alphas)
    n = n_samples if n_samples is not None else max(p + 1, math.ceil(oversampling * p))
    if n <= p:
        raise ValueError(
            f"regression needs more samples than basis terms: n={n} <= n_terms={p}. "
            "Raise oversampling or n_samples (or lower the degree)."
        )
    rng = random.Random(seed)
    design: list[list[float]] = []
    rhs: list[float] = []
    for _ in range(n):
        sample = dict(fixed_sample)
        tables: list[list[float]] = []
        for dim in range(d):
            ad = adapters[dim]
            x = inputs[active[dim]].quantile(rng.random())
            sample[active[dim]] = x
            tables.append(_basis_at(ad, degree, _to_reference(ad, x)))
        design.append([math.prod(tables[dim][a[dim]] for dim in range(d)) for a in alphas])
        y = finding(sample)
        _check_finite(y)
        rhs.append(y)

    # Solve M c ~= y directly by Householder QR: the normal equations (M^T M) c = M^T y would square the condition number of the design and throw away half the digits, QR keeps them.
    try:
        coeffs = dict(zip(alphas, solve_lstsq(design, rhs)))
    except ValueError as exc:  # pragma: no cover - unreachable via the public API:
        # The n<=p too-few-samples case is guarded above and n>p continuous draws give a full-rank design almost surely; kept to rewrap rank-deficiency into a PCE-context message.
        raise ValueError(
            "regression design is rank-deficient (too few / degenerate samples)"
        ) from exc
    return coeffs, n


def pce_fit(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    degree: int,
    method: str = "quadrature",
    oversampling: float = 2.0,
    n_samples: int | None = None,
    seed: int = 0,
    validation: int = 256,
) -> PCEResult:
    """Fit a polynomial chaos expansion of ``finding`` over ``inputs``."""
    if degree < 1:
        raise ValueError(f"degree must be >= 1, got {degree}")
    if method not in ("quadrature", "sparse", "regression"):
        raise ValueError(
            f"method must be 'quadrature', 'sparse', or 'regression', got {method!r}"
        )

    active, adapters, fixed = _split_inputs(inputs, degree)
    fixed_sample = {name: value for name, value in fixed}

    if not active:
        # Every input is Fixed: the finding is a constant, no expansion to fit.
        y0 = finding(dict(fixed_sample))
        _check_finite(y0)
        return PCEResult(
            mean=y0, variance=0.0, std=0.0, first_order={}, total_order={},
            degree=degree, n_evaluations=1, n_validation=0, fit_residual=0.0,
            input_names=(), method=method, coefficients={(): y0}, _adapters=(),
            _fixed=tuple(fixed),
        )

    d = len(active)
    alphas = _total_degree_alphas(degree, d)
    if method == "quadrature":
        coeffs, n_eval = _fit_quadrature(
            inputs, finding, active, adapters, fixed_sample, degree, d, alphas
        )
    elif method == "sparse":
        coeffs, n_eval = _fit_sparse(
            inputs, finding, active, adapters, fixed_sample, degree, d, alphas
        )
    else:
        coeffs, n_eval = _fit_regression(
            inputs, finding, active, adapters, fixed_sample, degree, d, alphas,
            oversampling, n_samples, seed,
        )

    mean, variance, first_order, total_order = _statistics(coeffs, active, d)
    result = PCEResult(
        mean=mean,
        variance=variance,
        std=math.sqrt(variance) if variance > 0 else 0.0,
        first_order=first_order,
        total_order=total_order,
        degree=degree,
        n_evaluations=n_eval,
        n_validation=0,
        fit_residual=0.0,
        input_names=tuple(active),
        method=method,
        coefficients=coeffs,
        _adapters=tuple(adapters),
        _fixed=tuple(fixed),
    )
    if validation <= 0:
        return result

    # Fit-quality: relative RMS of (surrogate - truth) on an independent sample (seed + 1, so an in-sample residual does not flatter the fit).
    rng = random.Random(seed + 1)
    truth: list[float] = []
    pred: list[float] = []
    for _ in range(validation):
        sample = dict(fixed_sample)
        for name in active:
            sample[name] = inputs[name].quantile(rng.random())
        y = finding(sample)
        _check_finite(y)
        truth.append(y)
        pred.append(result.predict(sample))
    resid = math.sqrt(statistics.fmean([(p - t) ** 2 for p, t in zip(pred, truth)]))
    spread = statistics.pstdev(truth) if len(truth) >= 2 else 0.0
    fit_residual = resid / spread if spread > 0 else (0.0 if resid == 0 else math.inf)

    return PCEResult(
        mean=result.mean, variance=result.variance, std=result.std,
        first_order=result.first_order, total_order=result.total_order,
        degree=degree, n_evaluations=result.n_evaluations, n_validation=validation,
        fit_residual=fit_residual, input_names=result.input_names, method=method,
        coefficients=coeffs, _adapters=tuple(adapters), _fixed=tuple(fixed),
    )


@dataclass(frozen=True)
class CVResult:
    """A PCE control-variate estimate of a finding's mean."""

    mean: float
    stderr: float
    ci: tuple[float, float]
    variance_reduction: float  # Var(f) / Var(f - g); >1 means the CV helped
    n_evaluations: int  # PCE fit + validation + the residual MC samples
    input_names: tuple[str, ...]


def pce_control_variate(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    degree: int,
    n: int,
    seed: int,
) -> CVResult:
    """Estimate the mean of ``finding`` with a PCE control variate."""
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    # validation=0: the CV does not need the fit-quality probe (the residual MC is itself the honest check), and it keeps the PCE fit purely deterministic.
    pce = pce_fit(inputs, finding, degree=degree, seed=seed, validation=0)

    rng = random.Random(seed)
    raw: list[float] = []
    resid: list[float] = []
    for _ in range(n):
        sample = {name: inputs[name].quantile(rng.random()) for name in inputs}
        f = finding(sample)
        if math.isnan(f) or math.isinf(f):
            raise ValueError("finding returned nan/inf - a nonfinite draw is not honest UQ")
        raw.append(f)
        resid.append(f - pce.predict(sample))

    mean = statistics.fmean(resid) + pce.mean
    stderr = statistics.pstdev(resid) / math.sqrt(n) if n >= 2 else 0.0
    half = 1.6448536269514722 * stderr
    var_raw = statistics.pvariance(raw) if n >= 2 else 0.0
    var_resid = statistics.pvariance(resid) if n >= 2 else 0.0
    if var_resid > 0:
        vr = var_raw / var_resid
    else:
        vr = math.inf if var_raw > 0 else 1.0
    n_eval = pce.n_evaluations + pce.n_validation + n
    return CVResult(
        mean=mean,
        stderr=stderr,
        ci=(mean - half, mean + half),
        variance_reduction=vr,
        n_evaluations=n_eval,
        input_names=tuple(inputs.keys()),
    )

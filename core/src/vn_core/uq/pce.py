"""Polynomial chaos expansion (PCE): the spectral surrogate for smooth findings.

Where Monte Carlo (`sample`) and Saltelli Sobol (`sobol`) sample the model
randomly, PCE fits the finding as a sum of orthogonal polynomials in the uncertain
inputs, Y(xi) ~ sum_a c_a * Psi_a(xi), with the polynomial family chosen per input
distribution (Wiener-Askey: Uniform -> Legendre, Normal -> Hermite). From the
coefficients you read, in closed form and for free:

- **UQ**: mean = c_0, variance = sum_{a != 0} c_a^2 (Parseval; the basis is
  orthonormal), hence std / error scale.
- **GSA**: Sobol indices are just grouped coefficient energy - first-order S_i
  sums c_a^2 over multi-indices touching only input i; total-order S_Ti sums over
  every multi-index where i appears. No extra sampling.
- **A cheap surrogate**: `PCEResult.predict` evaluates the polynomial, so broad
  input sweeps cost polynomial arithmetic, not model runs.

Why this and not more Monte Carlo: for a **smooth, low-dimensional** finding PCE
converges spectrally - on the Ishigami benchmark degree 8 (729 evals) matches the
analytic variance and every Sobol index, where plain MC is still ~0.5% off on the
variance alone at 100k evals. That is the regime this repo's findings mostly live
in (2-5 sourced inputs).

The catch, and the honesty guard: PCE assumes smoothness. On a kink (a `min()`
regime switch, a threshold) the spectral convergence collapses to slow algebraic
(Gibbs), and a naive PCE would hand back confident-but-wrong moments. So every fit
carries a **`fit_residual`**: the relative RMS error of the surrogate against the
true finding on an independent validation sample. Near 0 means trust the numbers;
elevated (the kink case measured ~0.04-0.11) means this finding is not smooth
enough for PCE - use `monte_carlo` / `uq_and_gsa` instead. PCE never silently
lies; it reports how well it fit (CLAUDE.md §1).

Coefficients are computed by tensor Gauss quadrature (Golub-Welsch nodes from the
recurrence, a classical Jacobi eigensolver - pure Python, zero deps), so they are
*derived* numbers, not fitted black-box weights. Deterministic (§7): fixed nodes,
and the validation sample uses a threaded seed, no wall clock.

Scope (kept small per §2/§3): Uniform and Normal inputs; total-degree truncation;
tensor quadrature (cost (degree+1)^d - fine for the low d here, sparse grids are
the follow-up for higher d). LogNormal/LogUniform raise until a documented
transformation lands.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import product

from vn_core.uq.distributions import Distribution, Fixed, Normal, Uniform

# Polynomial families keyed by the distribution they are orthogonal to.
_LEGENDRE = "legendre"  # Uniform
_HERMITE = "hermite"  # Normal (probabilists' He_n, standard-normal weight)


# --- Gauss quadrature: Golub-Welsch nodes/weights on the reference domain ------


def _recurrence_beta(family: str, k: int) -> float:
    """Monic three-term recurrence coefficient b_k for the reference measure.

    pi_{k+1} = (x - a_k) pi_k - b_k pi_{k-1}, with a_k = 0 for both (symmetric)
    families. Legendre on [-1, 1] with the uniform probability weight; Hermite
    with the standard-normal weight. b_0 = total mass = 1 (probability measures).
    """
    if k == 0:
        return 1.0
    if family == _LEGENDRE:
        return (k * k) / (4.0 * k * k - 1.0)  # k^2 / (4k^2 - 1)
    if family == _HERMITE:
        return float(k)
    raise ValueError(f"unknown polynomial family {family!r}")


def _jacobi_eigen(a: list[list[float]]) -> tuple[list[float], list[list[float]]]:
    """Eigenvalues + eigenvectors of a small dense symmetric matrix (Jacobi rotations).

    Returns (eigenvalues, V) where V[i][j] is component i of eigenvector j. Robust
    and simple - the matrices here are (degree+1) x (degree+1), tens at most.
    """
    n = len(a)
    m = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    if n == 1:
        return [m[0][0]], v
    for _ in range(100):
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
                # Update the pivot 2x2 block explicitly (it is zeroed off-diagonal),
                # then the off-pivot rows/cols only - updating all rows *and* all
                # cols would touch the pivot block twice and corrupt the rotation.
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
    """m-point Gauss nodes and weights for the family's reference measure.

    Golub-Welsch: nodes are the eigenvalues of the symmetric tridiagonal Jacobi
    matrix (diagonal 0, off-diagonal sqrt(b_k)); weight_i = (first component of the
    i-th normalized eigenvector)^2, since the total mass b_0 = 1.
    """
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


def _adapt(dist: Distribution) -> tuple[str, float, float]:
    """Return (family, p0, p1) so a physical x maps to the reference variable xi.

    Legendre (Uniform[low, high]): xi = 2 (x - low)/(high - low) - 1, x in [-1, 1].
    Hermite  (Normal[mean, std]):  xi = (x - mean)/std, standard normal.
    """
    if isinstance(dist, Uniform):
        return (_LEGENDRE, dist.low, dist.high)
    if isinstance(dist, Normal):
        if dist.std <= 0:
            raise ValueError("PCE needs a Normal with std > 0 (a zero-std Normal is Fixed)")
        return (_HERMITE, dist.mean, dist.std)
    raise NotImplementedError(
        f"PCE supports Uniform and Normal inputs; got {type(dist).__name__}. "
        "LogNormal/LogUniform need a documented transformation (follow-up); use "
        "monte_carlo / uq_and_gsa for those."
    )


def _to_reference(family: str, p0: float, p1: float, x: float) -> float:
    if family == _LEGENDRE:
        return 2.0 * (x - p0) / (p1 - p0) - 1.0
    return (x - p0) / p1  # Hermite: (x - mean)/std


def _to_physical(family: str, p0: float, p1: float, xi: float) -> float:
    if family == _LEGENDRE:
        return p0 + (p1 - p0) * (xi + 1.0) / 2.0
    return p0 + p1 * xi  # Hermite: mean + std*xi


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
    _adapters: tuple[tuple[str, float, float], ...]
    _fixed: tuple[tuple[str, float], ...]

    def is_trustworthy(self, tol: float = 1e-2) -> bool:
        """True when the surrogate reproduces the finding well (fit_residual < tol).

        A False here is the honest-null signal: the finding is not smooth enough
        for PCE (a kink/threshold), so its moments and Sobol indices should not be
        reported - fall back to monte_carlo / uq_and_gsa.
        """
        return self.fit_residual < tol

    def predict(self, sample: Mapping[str, float]) -> float:
        """Evaluate the surrogate polynomial at a physical input sample.

        Cheap (polynomial arithmetic, no model run) - this is the "sweep inputs
        broadly" surface. Fixed inputs in ``sample`` are ignored (they carry no
        variance); missing active inputs raise via the mapping lookup.
        """
        xis = [
            _to_reference(fam, p0, p1, sample[name])
            for name, (fam, p0, p1) in zip(self.input_names, self._adapters)
        ]
        max_deg = self.degree
        tables = [
            _basis_values(fam, max_deg, xi)
            for (fam, _p0, _p1), xi in zip(self._adapters, xis)
        ]
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
    inputs: Mapping[str, Distribution],
) -> tuple[list[str], list[tuple[str, float, float]], list[tuple[str, float]]]:
    """Partition inputs into active (Uniform/Normal) and Fixed; adapt the active."""
    active: list[str] = []
    adapters: list[tuple[str, float, float]] = []
    fixed: list[tuple[str, float]] = []
    for name in inputs:
        dist = inputs[name]
        if isinstance(dist, Fixed):
            fixed.append((name, dist.value))
        else:
            active.append(name)
            adapters.append(_adapt(dist))
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


def _solve_spd(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve a small dense system ``a x = b`` by Gaussian elimination w/ pivoting."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-300:
            raise ValueError("regression design is rank-deficient (too few / degenerate samples)")
        if piv != col:
            m[col], m[piv] = m[piv], m[col]
        inv = 1.0 / m[col][col]
        for r in range(col + 1, n):
            f = m[r][col] * inv
            if f == 0.0:
                continue
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for row in range(n - 1, -1, -1):
        acc = m[row][n]
        for c in range(row + 1, n):
            acc -= m[row][c] * x[c]
        x[row] = acc / m[row][row]
    return x


def _fit_quadrature(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    active: list[str],
    adapters: list[tuple[str, float, float]],
    fixed_sample: dict[str, float],
    degree: int,
    d: int,
    alphas: list[tuple[int, ...]],
) -> tuple[dict[tuple[int, ...], float], int]:
    """Coefficients by tensor Gauss-quadrature pseudospectral projection.

    Exact for a degree-``degree`` finding, but costs (degree+1)^d model calls -
    exponential in dimension. For higher d use the "regression" method.
    """
    m = degree + 1
    per_dim_nodes: list[list[float]] = []
    per_dim_weights: list[list[float]] = []
    per_dim_basis: list[list[list[float]]] = []
    for fam, _p0, _p1 in adapters:
        nodes, weights = _gauss_nodes_weights(fam, m)
        per_dim_nodes.append(nodes)
        per_dim_weights.append(weights)
        per_dim_basis.append([_basis_values(fam, degree, xi) for xi in nodes])

    idx_grid = list(product(*[range(m) for _ in range(d)]))
    ys: list[float] = []
    tensor_w: list[float] = []
    for idx in idx_grid:
        sample = dict(fixed_sample)
        for dim, node_i in enumerate(idx):
            fam, p0, p1 = adapters[dim]
            sample[active[dim]] = _to_physical(fam, p0, p1, per_dim_nodes[dim][node_i])
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


def _fit_regression(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    active: list[str],
    adapters: list[tuple[str, float, float]],
    fixed_sample: dict[str, float],
    degree: int,
    d: int,
    alphas: list[tuple[int, ...]],
    oversampling: float,
    n_samples: int | None,
    seed: int,
) -> tuple[dict[tuple[int, ...], float], int]:
    """Coefficients by least-squares regression over N sampled points.

    N = ``n_samples`` or ceil(``oversampling`` * n_terms), where n_terms grows
    only *polynomially* in dimension (C(degree+d, d)) - so this scales where the
    (degree+1)^d tensor quadrature explodes. On the orthonormal basis with samples
    drawn from the input distribution, the normal-equations Gram matrix tends to
    N * identity, so it is well-conditioned by construction.
    """
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
            fam, p0, p1 = adapters[dim]
            x = inputs[active[dim]].quantile(rng.random())
            sample[active[dim]] = x
            tables.append(_basis_values(fam, degree, _to_reference(fam, p0, p1, x)))
        design.append([math.prod(tables[dim][a[dim]] for dim in range(d)) for a in alphas])
        y = finding(sample)
        _check_finite(y)
        rhs.append(y)

    # Normal equations (M^T M) c = M^T y.
    gram = [[sum(design[r][i] * design[r][j] for r in range(n)) for j in range(p)] for i in range(p)]
    proj = [sum(design[r][i] * rhs[r] for r in range(n)) for i in range(p)]
    coeffs = dict(zip(alphas, _solve_spd(gram, proj)))
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
    """Fit a polynomial chaos expansion of ``finding`` over ``inputs``.

    ``degree`` is the total-degree truncation. ``method`` chooses how the
    coefficients are computed:

    - ``"quadrature"`` (default): tensor Gauss quadrature, exact for a
      degree-``degree`` finding but (degree+1)^d model calls - best in low
      dimension.
    - ``"regression"``: least-squares over ~``oversampling`` * n_terms sampled
      points (n_terms = C(degree+d, d), polynomial in d) - the scalable choice in
      higher dimension. Override the sample count with ``n_samples``.

    ``validation`` extra evaluations estimate ``fit_residual`` on an independent
    sample (set 0 to skip). Deterministic given ``seed``. Always check
    ``result.is_trustworthy()`` before quoting the moments/indices: on a
    non-smooth finding they are not reliable.
    """
    if degree < 1:
        raise ValueError(f"degree must be >= 1, got {degree}")
    if method not in ("quadrature", "regression"):
        raise ValueError(f"method must be 'quadrature' or 'regression', got {method!r}")

    active, adapters, fixed = _split_inputs(inputs)
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

    # Fit-quality: relative RMS of (surrogate - truth) on an independent sample.
    # seed + 1 so the validation points are independent of the regression fit
    # sample (which uses seed) - an in-sample residual would flatter the fit.
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
    """A PCE control-variate estimate of a finding's mean.

    Unbiased (it is Monte Carlo on the residual f - g plus the *exact* E[g] = the
    PCE's constant coefficient), with an honest iid error bar, and a variance far
    below plain MC when the PCE surrogate correlates with the finding.
    """

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
    """Estimate the mean of ``finding`` with a PCE control variate.

    Fits a PCE surrogate ``g`` (whose mean E[g] is known exactly from its constant
    coefficient), then Monte-Carlos the residual ``f - g`` over ``n`` fresh iid
    samples: ``E[f] = E[f - g] + E[g]``. Because g correlates with f, Var(f - g) is
    much smaller than Var(f), so the estimate is far tighter than plain MC at the
    same MC sample count - yet it stays **unbiased** and keeps a real iid error
    bar, even on findings where the PCE alone is not trustworthy (a kink): the MC
    on the residual carries the part PCE cannot fit. ``variance_reduction`` reports
    how much the control variate actually bought (~1 means the finding did not
    correlate with a low-degree polynomial - honest, and no worse than MC).

    Deterministic (§7): the PCE quadrature is fixed; the residual MC uses ``seed``.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    # validation=0: the CV does not need the fit-quality probe (the residual MC is
    # itself the honest check), and it keeps the PCE fit purely deterministic.
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

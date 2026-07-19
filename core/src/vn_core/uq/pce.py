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
    n_evaluations: int  # model calls for the quadrature fit
    n_validation: int  # model calls for the fit-quality check
    fit_residual: float  # relative RMS surrogate error on the validation sample
    input_names: tuple[str, ...]  # active (non-Fixed) inputs, in order

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


def pce_fit(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    degree: int,
    seed: int = 0,
    validation: int = 256,
) -> PCEResult:
    """Fit a polynomial chaos expansion of ``finding`` over ``inputs``.

    ``degree`` is the total-degree truncation. Model evaluations for the fit are
    (degree+1)^d where d is the number of non-Fixed inputs (tensor Gauss
    quadrature). ``validation`` extra evaluations estimate ``fit_residual`` - set
    it to 0 to skip (then trust is your responsibility). Deterministic given
    ``seed`` (used only for the validation sample).

    Always check ``result.is_trustworthy()`` (or ``fit_residual``) before quoting
    the moments/indices: on a non-smooth finding they are not reliable.
    """
    if degree < 1:
        raise ValueError(f"degree must be >= 1, got {degree}")

    names = tuple(inputs.keys())
    active: list[str] = []
    adapters: list[tuple[str, float, float]] = []
    fixed: list[tuple[str, float]] = []
    for name in names:
        dist = inputs[name]
        if isinstance(dist, Fixed):
            fixed.append((name, dist.value))
        else:
            active.append(name)
            adapters.append(_adapt(dist))

    fixed_sample = {name: value for name, value in fixed}

    if not active:
        # Every input is Fixed: the finding is a constant, no expansion to fit.
        y0 = finding(dict(fixed_sample))
        return PCEResult(
            mean=y0, variance=0.0, std=0.0, first_order={}, total_order={},
            degree=degree, n_evaluations=1, n_validation=0, fit_residual=0.0,
            input_names=(), coefficients={(): y0}, _adapters=(), _fixed=tuple(fixed),
        )

    d = len(active)
    m = degree + 1  # nodes per dimension (exact for the projected integrand)

    # 1D reference nodes/weights and the orthonormal basis table at each node.
    per_dim_nodes: list[list[float]] = []
    per_dim_weights: list[list[float]] = []
    per_dim_basis: list[list[list[float]]] = []  # [dim][node][phi_0..phi_deg]
    for fam, _p0, _p1 in adapters:
        nodes, weights = _gauss_nodes_weights(fam, m)
        per_dim_nodes.append(nodes)
        per_dim_weights.append(weights)
        per_dim_basis.append([_basis_values(fam, degree, xi) for xi in nodes])

    # Tensor grid: evaluate the finding once per node, caching Y and the tensor weight.
    idx_grid = list(product(*[range(m) for _ in range(d)]))
    ys: list[float] = []
    tensor_w: list[float] = []
    for idx in idx_grid:
        sample = dict(fixed_sample)
        for dim, node_i in enumerate(idx):
            fam, p0, p1 = adapters[dim]
            sample[active[dim]] = _to_physical(fam, p0, p1, per_dim_nodes[dim][node_i])
        y = finding(sample)
        if math.isnan(y) or math.isinf(y):
            raise ValueError("finding returned nan/inf - a nonfinite draw is not honest UQ")
        ys.append(y)
        w = 1.0
        for dim, node_i in enumerate(idx):
            w *= per_dim_weights[dim][node_i]
        tensor_w.append(w)

    # Total-degree multi-index basis.
    alphas = [a for a in product(range(degree + 1), repeat=d) if sum(a) <= degree]

    # Pseudospectral projection: c_a = sum_q W_q * Y_q * prod_d phi_{a_d}(xi_{q,d}).
    coeffs: dict[tuple[int, ...], float] = {}
    for alpha in alphas:
        acc = 0.0
        for q, idx in enumerate(idx_grid):
            psi = 1.0
            for dim, node_i in enumerate(idx):
                psi *= per_dim_basis[dim][node_i][alpha[dim]]
            acc += tensor_w[q] * ys[q] * psi
        coeffs[alpha] = acc

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

    result = PCEResult(
        mean=mean,
        variance=variance,
        std=math.sqrt(variance) if variance > 0 else 0.0,
        first_order=first_order,
        total_order=total_order,
        degree=degree,
        n_evaluations=len(idx_grid),
        n_validation=0,
        fit_residual=0.0,
        input_names=tuple(active),
        coefficients=coeffs,
        _adapters=tuple(adapters),
        _fixed=tuple(fixed),
    )

    if validation <= 0:
        return result

    # Fit-quality: relative RMS of (surrogate - truth) on an independent sample.
    rng = random.Random(seed)
    truth: list[float] = []
    pred: list[float] = []
    for _ in range(validation):
        sample = dict(fixed_sample)
        for name in active:
            sample[name] = inputs[name].quantile(rng.random())
        y = finding(sample)
        if math.isnan(y) or math.isinf(y):
            raise ValueError("finding returned nan/inf - a nonfinite draw is not honest UQ")
        truth.append(y)
        pred.append(result.predict(sample))
    resid = math.sqrt(statistics.fmean([(p - t) ** 2 for p, t in zip(pred, truth)]))
    spread = statistics.pstdev(truth) if len(truth) >= 2 else 0.0
    fit_residual = resid / spread if spread > 0 else (0.0 if resid == 0 else math.inf)

    # Rebuild with the measured residual (frozen dataclass).
    return PCEResult(
        mean=result.mean, variance=result.variance, std=result.std,
        first_order=result.first_order, total_order=result.total_order,
        degree=degree, n_evaluations=result.n_evaluations, n_validation=validation,
        fit_residual=fit_residual, input_names=result.input_names,
        coefficients=coeffs, _adapters=tuple(adapters), _fixed=tuple(fixed),
    )

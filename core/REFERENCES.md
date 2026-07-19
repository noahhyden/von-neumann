# Where the numbers come from

`core/` (the `vn-core` package) is shared infrastructure, not a physics model, so
most of it has no physical constants. The one place numbers appear is the ODE
solver (`vn_core.ode`), where every coefficient is a published numerical-methods
constant, not a physical quantity. They are transcribed here so each can be
checked against its source.

## ODE solver (`vn_core.ode`, issue #38)

### Dormand-Prince RK45 tableau (`rk45.py`)

The Butcher tableau (the `A*`, `C*`, `B*` coefficients and the embedded
error-estimate weights `E*`) is the standard explicit RK5(4) pair.

- **Dormand, J. R. and Prince, P. J. (1980), "A family of embedded Runge-Kutta
  formulae", Journal of Computational and Applied Mathematics 6(1), 19-26.** The
  original RK5(4) 7-stage FSAL pair. Coefficients are stored as exact rationals so
  they can be read straight off the paper.
  - https://doi.org/10.1016/0771-050X(80)90013-3
- Cross-check: the same tableau is what `scipy.integrate.solve_ivp(method="RK45")`
  uses, which is the test-only oracle the validation gate compares against
  (`tests/test_ode_validation.py`). Verdict: reasonable - two independent
  implementations of the identical published pair agree to 1e-6 on the repo's own
  ODEs.

### Adaptive step-size control constants (`rk45.py`, `implicit.py`)

- **safety = 0.9, min shrink factor = 0.2, max growth factor = 10.0 (explicit) /
  5.0 (implicit).** Standard PI-free step controller factors.
  - **Hairer, E., Norsett, S. P., Wanner, G. (1993), "Solving Ordinary
    Differential Equations I: Nonstiff Problems", 2nd ed., Springer**, Section
    II.4 ("Automatic Step Size Control"). These are the textbook default factors,
    and match scipy's `RK45` implementation. Verdict: reasonable - conventional
    values, not tuned to any one problem.
- **Error-estimate exponent = -1/(order+1):** -1/5 for RK45 (estimator order 4),
  -1/2 for backward Euler (order 1). Same source (Hairer/Wanner II.4). This is the
  order the local error scales at, so it is derived, not chosen.
- **Automatic first-step heuristic (`common.select_initial_step`).** The
  balance-of-scales starting-step formula is Hairer/Wanner I, "Starting Step Size"
  (the routine `hinit`). Verdict: reasonable - a start value only; the controller
  corrects it within a step or two.

### Scaled RMS error norm (`common.rms_error_norm`)

- Per-component scale `atol + rtol * max(|y0|, |y1|)`, combined as root-mean-square.
  This is the mixed absolute/relative weighting from Hairer/Wanner II.4, and again
  matches scipy. A step is accepted when the norm is <= 1.

### Backward Euler + finite-difference Jacobian (`implicit.py`, `linalg.py`)

- **Backward (implicit) Euler**, the order-1 L-stable method, is textbook
  (Hairer & Wanner, "Solving ODEs II: Stiff and Differential-Algebraic Problems",
  Section IV). Chosen for L-stability + simplicity to meet the stiff validation
  gate; a higher-order L-stable method (Radau IIA-5, BDF2) is the flagged Phase-3+
  follow-up in issue #38.
- **Finite-difference Jacobian perturbation `h = sqrt(eps_machine) * max(|y_j|,
  1)`** with `eps_machine ~ 2.22e-16`. The `sqrt(eps)` forward-difference step is
  the standard optimum trading truncation against round-off.
  - **Nocedal, J. and Wright, S. (2006), "Numerical Optimization", 2nd ed.,
    Springer**, Section 8.1 (finite-difference derivatives). Verdict: reasonable -
    standard choice; the resulting Jacobian is only used to drive Newton, which
    self-corrects.
- **Newton convergence tolerance 1e-3 (scaled correction norm).** Not a physical
  number: it only needs to be comfortably below the step's own error budget so the
  nonlinear solve is not the accuracy bottleneck. Verdict: reasonable - loose by
  design, tightening it would only cost iterations.

## UQ: variance-reduction mean estimators (`vn_core.uq.qmc`, `vn_core.uq.pce`)

- **Halton low-discrepancy sequence (`qmc.py`).** Per-dimension radical inverse in
  the first primes as bases - a quasi-random sequence that fills the cube evenly,
  giving ~1/N mean convergence vs Monte Carlo's 1/sqrt(N) for smooth low-dim
  findings.
  - **Halton, J. H. (1964), "Algorithm 247: Radical-inverse quasi-random point
    sequence", Comm. ACM 7(12), 701-702.**
    - https://doi.org/10.1145/355588.365104
- **Randomization (Cranley-Patterson rotation).** A seeded uniform shift per
  dimension, applied mod 1, per replicate - makes each replicate an unbiased QMC
  estimate so the spread between replicate means is an honest error bar (plain
  QMC's iid stderr is invalid).
  - **Cranley, R. and Patterson, T. N. L. (1976), "Randomization of number
    theoretic methods for multiple integration", SIAM J. Numer. Anal. 13(6),
    904-914.**
    - https://doi.org/10.1137/0713071
- **PCE control variate (`pce.py`).** Standard control-variate variance reduction
  with the polynomial-chaos surrogate as the control (its mean is known exactly),
  so the estimate is unbiased MC on the residual with much lower variance.
  - **Owen, A. B. (2013), "Monte Carlo theory, methods and examples", Ch. 8-9
    (control variates).** https://artowen.su.domains/mc/ ; and Sudret (2008) above
    for using PCE as the surrogate.

## UQ: Sobol sensitivity estimators (`vn_core.uq.sobol`)

Method choices, not physical numbers - each is a published variance-based
sensitivity estimator computed from the shared Saltelli design.

- **Total-order index (Jansen 1999).** `S_Ti = (1/2N) sum_j (f(A)_j - f(AB^i)_j)^2
  / Var`.
  - **Jansen, M. J. W. (1999), "Analysis of variance designs for model output",
    Computer Physics Communications 117, 35-43.**
    - https://doi.org/10.1016/S0010-4655(98)00154-4
- **First-order index (Saltelli et al. 2010).** `S_i = (1/N) sum_j f(B)_j (f(AB^i)_j
  - f(A)_j) / Var`. Free: it reuses the exact A, B, AB^i evaluations the total-order
  estimator already needs.
  - **Saltelli, A. et al. (2010), "Variance based sensitivity analysis of model
    output. Design and estimator for the total sensitivity index", Computer Physics
    Communications 181, 259-270.**
    - https://doi.org/10.1016/j.cpc.2009.09.018
- **Confidence intervals.** Default is asymptotic: each index is a sample mean of
  per-row terms, so `stderr = pstdev(terms)/sqrt(N)` and the 90% CI is `estimate +-
  z * stderr` with `z = 1.6448536269514722` (the 0.95 standard-normal quantile, a
  derived math constant). Opt-in bootstrap uses percentile CIs over resampled rows.
  Verdict: on the Ishigami benchmark the two agree to 2-3 decimals; asymptotic is
  the free default, bootstrap the costlier robustness check.

## UQ: polynomial chaos (`vn_core.uq.pce`)

Like the ODE solver, PCE carries no physical constants - only numerical-method
constants, each a mathematical identity, not an assumption.

- **Wiener-Askey basis choice (Uniform -> Legendre, Normal -> Hermite).**
  - **Xiu, D. and Karniadakis, G. E. (2002), "The Wiener-Askey polynomial chaos
    for stochastic differential equations", SIAM J. Sci. Comput. 24(2), 619-644.**
    The correspondence between input distribution and the orthogonal polynomial
    family that makes the expansion converge optimally.
    - https://doi.org/10.1137/S1064827501387826
- **Recurrence coefficients b_k (used to build the Gauss quadrature).** Monic
  three-term recurrence, symmetric families (a_k = 0):
  - Legendre (uniform on [-1,1]): `b_k = k^2 / (4k^2 - 1)`.
  - Probabilists' Hermite (standard normal): `b_k = k`.
  These are standard tabulated values (Gautschi, "Orthogonal Polynomials:
  Computation and Approximation", 2004). Verdict: exact identities; the tests
  confirm the resulting nodes integrate polynomials to degree 2m-1 exactly.
- **Golub-Welsch quadrature (nodes = Jacobi-matrix eigenvalues, weights = squared
  first eigenvector components).**
  - **Golub, G. H. and Welsch, J. H. (1969), "Calculation of Gauss quadrature
    rules", Math. Comp. 23, 221-230.** The eigenvalue algorithm for Gauss nodes;
    implemented here on a pure-Python classical Jacobi symmetric eigensolver.
    - https://doi.org/10.1090/S0025-5718-69-99647-1
- **Coefficient fitting: quadrature or regression.** Two non-intrusive methods
  build the same orthonormal expansion. Tensor Gauss quadrature (pseudospectral
  projection) is exact but costs (degree+1)^d runs. Least-squares **regression**
  (point collocation) fits from ~2 * n_terms sampled runs, where n_terms =
  C(degree+d, d) is polynomial in dimension - the scalable choice in higher d.
  - **Hosder, S., Walters, R. W., Balch, M. (2007), "Efficient sampling for
    non-intrusive polynomial chaos expansions with high number of random
    variables", AIAA 2007-1939.** Source of the ~2x oversampling ratio (runs vs.
    basis terms). Verdict: reasonable - with the orthonormal basis and samples
    drawn from the input distribution, the normal-equations Gram matrix tends to
    N * identity, so it is well-conditioned; tests confirm machine-precision
    recovery of a degree-2 polynomial in 8 inputs from ~90 runs.
- **Sobol indices from PCE coefficients (grouped coefficient energy).**
  - **Sudret, B. (2008), "Global sensitivity analysis using polynomial chaos
    expansions", Reliability Engineering & System Safety 93(7), 964-979.** First-
    and total-order indices as sums of squared coefficients over the multi-indices
    that involve each input - the closed form used here.
    - https://doi.org/10.1016/j.ress.2007.04.002
- **Ishigami test function (validation benchmark, not shipped).** Used only in
  tests, with its analytic variance and Sobol indices, to validate the estimator.
  - **Ishigami, T. and Homma, T. (1990), "An importance quantification technique
    in uncertainty analysis for computer models", ISUMA '90.** Verdict: standard
    GSA benchmark; PCE degree 10 reproduces its analytic indices to ~1e-3.

## Everything else in `vn-core`

`vn_core.uq` (distributions, Monte Carlo, Sobol, the unified UQ+GSA surface, and
polynomial chaos) carries no physical constants of its own - it propagates numbers
that live in each consuming module's own `REFERENCES.md`. See those modules for the
physics.

# Where the numbers come from

`core/` (the `vn-core` package) is shared infrastructure, not a physics model, so
most of it has no physical constants. The two places numbers appear are the RNG
(`vn_core.rng`), where the constants are the mulberry32 algorithm's own tabulated
values, and the ODE solver (`vn_core.ode`), where every coefficient is a
published numerical-methods constant. They are transcribed here so each can be
checked against its source.

## Seeded RNG (`vn_core.rng`, issue #29)

Mulberry32, a 32-bit-state PRNG in the "small fast RNG" family. Deterministic,
threaded through the fold, byte-identical across Python and JavaScript so a
Python fold and its TypeScript port replay bit-for-bit.

- **mulberry32 (Tommy Ettinger, 2017, public domain).** The reference version is a
  15-line JavaScript snippet. The Python impl here mirrors it exactly, with a
  32-bit mask on every intermediate to reproduce JS's `Math.imul` / `| 0` /
  `>>>` semantics under Python's unbounded ints.
  - https://github.com/bryc/code/blob/master/jshash/PRNGs.md#mulberry32
  - Verdict: reasonable - a small, well-tested PRNG appropriate for scientific
    reproducibility. It is not cryptographic and is not for that. Statistical
    quality is enough for the paper-scale ensembles the repo runs (verified
    downstream in the drift-guard tests, which pin exact result JSONs).
- **Constants (`0x6D2B79F5`, shift widths 15/7/14, `1 | s`, `61 | t`).** These
  are the mulberry32 algorithm's own tabulated values from the reference above,
  not tuning parameters. Changing any of them yields a different PRNG.
- **Parity is a test contract, not a hope.** `tests/rng_js_fixture/fixture.json`
  is regenerated from `tests/rng_js_fixture/gen.mjs`, and Python's u32 and
  float streams are asserted equal to the JS values in `tests/test_rng.py`. If
  the Python or JS implementation ever drifts, that test fails.

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

### Dense-output interpolation matrix (`rk45.py`, `_P`)

Requested output times (`t_eval`) are served by the Dormand-Prince quartic dense
output: on an accepted step [t, t+h] the solution at t + theta*h is a degree-4
polynomial in theta built from the step's seven stage derivatives.

- **The 7x4 interpolation matrix `_P`** holds the coefficients of that polynomial. It
  is the standard Dormand-Prince dense-output (Hairer & Wanner, "Solving ODEs I", 2nd
  ed., Section II.6, "Dense Output"), stored as exact rationals - identical to the `P`
  matrix in `scipy.integrate` `RK45` (BSD-3), from which the values were transcribed.
  - Cross-check: the interpolant is validated *bit-for-bit* against scipy's
    `dense_output()` in `tests/test_ode_dense_output.py` (agreement to ~1e-14), and
    the endpoints are checked (theta=0 returns the step start, theta=1 the step end).
    Verdict: reasonable - a transcribed, reference-verified standard interpolant, no
    tuned constants.

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

## UQ: low-discrepancy sequences (`vn_core.uq.sequences`)

The shared quasi-random point sources for the QMC mean estimator and the Saltelli
sensitivity design. Method choices, not physical numbers; the Sobol' direction
integers are tabulated data whose provenance is pinned below.

- **Halton low-discrepancy sequence.** Per-dimension radical inverse (van der
  Corput) in the first primes as bases - a quasi-random sequence that fills the cube
  evenly, giving ~1/N mean convergence vs Monte Carlo's 1/sqrt(N) for smooth low-dim
  findings.
  - **Halton, J. H. (1964), "Algorithm 247: Radical-inverse quasi-random point
    sequence", Comm. ACM 7(12), 701-702.**
    - https://doi.org/10.1145/355588.365104
- **Sobol' sequence (direction numbers).** A digital (t, s)-sequence with far better
  high-dimensional equidistribution than Halton, generated by the standard gray-code
  recurrence over per-dimension direction integers. Better than Halton because the
  high-prime Halton bases correlate as dimension grows; Sobol' does not.
  - **Sobol', I. M. (1967), "On the distribution of points in a cube and the
    approximate evaluation of integrals", USSR Comp. Math. and Math. Phys. 7(4),
    86-112.** The original sequence.
    - https://doi.org/10.1016/0041-5553(67)90144-9
  - **Joe, S. and Kuo, F. Y. (2008), "Constructing Sobol sequences with better
    two-dimensional projections", SIAM J. Sci. Comput. 30(5), 2635-2654.** The source
    of the specific direction numbers used here.
    - https://doi.org/10.1137/070709359
    - Direction-number data: https://web.maths.unsw.edu.au/~fkuo/sobol/ (BSD-style
      licence, free use with attribution).
  - **Provenance of the embedded table (CLAUDE.md §1).** The direction integers in
    `sequences.py` (`_SOBOL_V`) are the Joe-Kuo values as distributed with SciPy
    (BSD-3), transcribed so the runtime needs no SciPy. They are not tunable and not
    guessed. `tests/test_sequences.py` regenerates them from `scipy.stats.qmc.Sobol`
    and asserts (a) the embedded table equals scipy's computed direction matrix and
    (b) this module's points are bit-identical to scipy's - so a drift is a red test,
    the same discipline the RNG's JS-parity fixture holds. Verdict: reasonable -
    verified bit-for-bit against the reference implementation.
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
- **First-order index (Saltelli et al. 2010), centered.** `S_i = (1/N) sum_j
  (f(B)_j - f0) (f(AB^i)_j - f(A)_j) / Var`, with `f0` the sample mean. Free: it
  reuses the exact A, B, AB^i evaluations the total-order estimator already needs.
  The `- f0` centering is essential, not cosmetic: without it the estimator carries
  the full output mean and, for a low-coefficient-of-variation finding (mean large
  vs. spread), catastrophic cancellation makes it wildly noisy - it read 2.459 (and
  0.384 at N=6000) on a real finding with mean/std ~ 52 where the true value is ~1.
  Total-order (Jansen) is immune because it uses differences.
  - **Saltelli, A. et al. (2010), "Variance based sensitivity analysis of model
    output. Design and estimator for the total sensitivity index", Computer Physics
    Communications 181, 259-270.**
    - https://doi.org/10.1016/j.cpc.2009.09.018
- **Second-order (pairwise interaction) index S_ij (Saltelli 2002/2010), opt-in.**
  The closed second-order effect `V^c_ij` (main effects of i and j plus their
  interaction) is estimated from the AB and BA matrices as `mean_j(f(AB^i)_j f(BA^j)_j
  - f(A)_j f(B)_j)/Var`, and the *pure* interaction is `S_ij = V^c_ij/Var - S_i - S_j`.
  The `- f(A)f(B)` term is a correlated control (it estimates the same f0^2 the product
  would otherwise carry), which keeps the estimator numerically well behaved - the same
  centering discipline the first-order estimator uses. This needs the extra "BA"
  matrices (B with one column from A), so it doubles the design to `N*(2K+2)` model
  calls and is therefore off by default. Validated on Ishigami, whose only nonzero
  interaction is x1-x3: the estimator recovers `S_13 ~ 0.244` (which equals x3's
  total-order, since x3 has no main effect) and reads x1-x2, x2-x3 as ~0 with CIs
  straddling zero.
  - **Saltelli, A. (2002), "Making best use of model evaluations to compute
    sensitivity indices", Computer Physics Communications 145, 280-297.** The
    second-order estimator and the AB/BA radial-sampling design.
    - https://doi.org/10.1016/S0010-4655(02)00280-1
- **Confidence intervals.** Default is asymptotic: each index is a sample mean of
  per-row terms, so `stderr = pstdev(terms)/sqrt(N)` and the 90% CI is `estimate +-
  z * stderr` with `z = 1.6448536269514722` (the 0.95 standard-normal quantile, a
  derived math constant). Opt-in bootstrap uses percentile CIs over resampled rows.
  Verdict: on the Ishigami benchmark the two agree to 2-3 decimals; asymptotic is
  the free default, bootstrap the costlier robustness check.

## UQ: polynomial chaos (`vn_core.uq.pce`)

Like the ODE solver, PCE carries no physical constants - only numerical-method
constants, each a mathematical identity, not an assumption.

- **Arbitrary distributions (aPCE via the Stieltjes recurrence).** For inputs
  outside the Askey scheme (LogNormal, LogUniform), the orthonormal basis is built
  from the distribution's own moments instead of a fixed family, by the
  *discretized Stieltjes* procedure (a stable route via the distribution's
  quantile). Caveat: the finding must still be low-degree-polynomial in the
  physical variable - the fit_residual flags cases (e.g. 1/x over decades) where it
  is not.
  - **Oladyshkin, S. and Nowak, W. (2012), "Data-driven uncertainty quantification
    using the arbitrary polynomial chaos expansion", Reliability Engineering &
    System Safety 106, 179-190.** The moment-based (arbitrary) PCE.
    - https://doi.org/10.1016/j.ress.2012.05.002
  - **Gautschi, W. (1994), "Algorithm 726: ORTHPOL", ACM TOMS 20(1), 21-62.** The
    discretized Stieltjes procedure for recurrence coefficients. Verdict:
    reasonable - reproduces the analytic Legendre nodes on a Uniform to ~1e-4 and
    recovers LogUniform's closed-form mean/variance to ~1e-6.
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
    drawn from the input distribution, the design's Gram matrix tends to
    N * identity, so it is well-conditioned; tests confirm machine-precision
    recovery of a degree-2 polynomial in 8 inputs from ~90 runs.
  - **Least-squares solve: Householder QR (`vn_core.linalg.solve_lstsq`).** The
    regression fit solves the design system M c ~= y by Householder QR rather than
    the normal equations (M^T M) c = M^T y. The normal equations square the
    condition number of M, discarding up to half the significant digits on a mildly
    ill-conditioned design; QR on M keeps them (a test shows QR ~8 orders of
    magnitude more accurate than the normal equations on a near-collinear design).
    - **Golub, G. H. and Van Loan, C. F. (2013), "Matrix Computations", 4th ed.,
      Johns Hopkins**, Section 5.2 (Householder QR least squares). Verdict:
      reasonable - the textbook stable LS method; validated bit-for-bit against
      numpy.linalg.lstsq in the tests (numpy is a dev-only oracle).
  - **Smolyak sparse-grid quadrature (`method="sparse"`).** The same pseudospectral
    projection as tensor quadrature, but over a Smolyak sparse grid (level = degree)
    that combines the 1-D Gauss rules by the signed combination technique. The node
    count grows polynomially rather than as (degree+1)^d, so a degree>=2 PCE stays
    feasible into moderate dimension (measured ~4x fewer model calls at d=5, ~100x at
    d=8; for d <= ~3 the tensor grid is comparable or cheaper). The rule integrates
    total-degree polynomials to 2*level+1 exactly, so level = degree is exact for the
    degree-`degree` projection - verified in tests by exact recovery of polynomials
    and agreement with tensor quadrature on Ishigami.
    - **Smolyak, S. A. (1963), "Quadrature and interpolation formulas for tensor
      products of certain classes of functions", Soviet Math. Dokl. 4, 240-243.** The
      original sparse-grid construction.
    - **Gerstner, T. and Griebel, M. (1998), "Numerical integration using sparse
      grids", Numerical Algorithms 18(3-4), 209-232.** The combination-technique form
      (signed sum of tensor rules) implemented here.
      - https://doi.org/10.1023/A:1019129717644
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

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

## Everything else in `vn-core`

`vn_core.uq` (distributions, Monte Carlo, Sobol) carries no physical constants of
its own - it propagates numbers that live in each consuming module's own
`REFERENCES.md`. See those modules for the physics.

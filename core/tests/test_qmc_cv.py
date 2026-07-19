"""Red-hat + validation for the two variance-reduction mean estimators.

`qmc_mean` (randomized quasi-Monte Carlo) and `pce_control_variate` both estimate
a finding's mean more efficiently than plain Monte Carlo. The claims under attack:

- **They actually converge better.** QMC must beat MC on the mean of a known-mean
  smooth integrand; PCE-CV must report a real variance reduction.
- **They stay honest.** QMC's error bar comes from replicate spread (not the
  invalid iid stderr) and must bracket the truth; PCE-CV must be *unbiased* even on
  a finding where the PCE alone is untrustworthy (a kink) - that is the whole point
  of a control variate vs. using the surrogate directly.
- **They are deterministic** (§7) and reject nonfinite returns.
- **QMC refuses high dimension** rather than silently returning a bad Halton
  estimate.
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq import (
    Normal,
    Uniform,
    monte_carlo,
    pce_control_variate,
    qmc_mean,
)

PI = math.pi
_A, _B = 7.0, 0.1
_ISH = {n: Uniform(-PI, PI) for n in ("x1", "x2", "x3")}


def _ishigami(s):
    return math.sin(s["x1"]) + _A * math.sin(s["x2"]) ** 2 + _B * s["x3"] ** 4 * math.sin(s["x1"])


_ISH_MEAN = _A / 2.0  # E[Ishigami] = 3.5 exactly


# --- QMC ----------------------------------------------------------------------


def test_qmc_mean_beats_monte_carlo_on_a_known_mean():
    """On a smooth integrand with known mean, RQMC's estimate must be at least as
    accurate as plain MC at the same evaluation budget - usually much better."""
    q = qmc_mean(_ISH, _ishigami, n=512, seed=1, replicates=16)
    mc = monte_carlo(_ISH, _ishigami, n=512 * 16, seed=1)
    assert abs(q.mean - _ISH_MEAN) <= abs(mc.mean - _ISH_MEAN)
    assert abs(q.mean - _ISH_MEAN) < 0.02


def test_qmc_error_bar_brackets_the_truth():
    """The replicate-spread CI is the honest error bar - it should contain the true
    mean (a ~90% CI, checked on a comfortable case)."""
    q = qmc_mean(_ISH, _ishigami, n=512, seed=1, replicates=24)
    lo, hi = q.ci
    assert lo <= _ISH_MEAN <= hi
    assert q.stderr > 0.0


def test_qmc_reports_the_right_evaluation_count():
    calls = {"n": 0}

    def counted(s):
        calls["n"] += 1
        return _ishigami(s)

    q = qmc_mean(_ISH, counted, n=200, seed=1, replicates=8)
    assert q.n_evaluations == 200 * 8 == calls["n"]


def test_qmc_is_deterministic():
    a = qmc_mean(_ISH, _ishigami, n=256, seed=5, replicates=8)
    b = qmc_mean(_ISH, _ishigami, n=256, seed=5, replicates=8)
    assert (a.mean, a.stderr, a.ci) == (b.mean, b.stderr, b.ci)


def test_qmc_refuses_too_many_dimensions():
    many = {f"x{i}": Uniform(0.0, 1.0) for i in range(25)}  # > prime table
    with pytest.raises(ValueError, match="low-dimensional"):
        qmc_mean(many, lambda s: sum(s.values()), n=64, seed=1, replicates=4)


def test_qmc_needs_at_least_two_replicates():
    with pytest.raises(ValueError, match="replicates"):
        qmc_mean(_ISH, _ishigami, n=64, seed=1, replicates=1)


def test_qmc_rejects_nonfinite():
    with pytest.raises(ValueError, match="nan/inf"):
        qmc_mean({"a": Uniform(0, 1)}, lambda s: float("inf"), n=16, seed=1, replicates=4)


# --- PCE control variate ------------------------------------------------------


def _borderline(s):
    # smooth bulk + a kink the PCE cannot fully capture
    return math.exp(0.3 * s["a"]) + 2.0 * s["b"] ** 2 + 0.5 * max(0.0, s["a"] - 1.0)


_BL_INPUTS = {"a": Normal(mean=0.0, std=1.0), "b": Uniform(-1.0, 1.0)}


def _big_mc_truth(finding, inputs, n=200000):
    return monte_carlo(inputs, finding, n=n, seed=98765).mean


def test_control_variate_is_unbiased_even_when_pce_is_untrustworthy():
    """The finding has a kink, so PCE alone is not trustworthy - but the control
    variate must still land on the true mean (it is MC on the residual)."""
    from vn_core.uq import pce_fit

    assert not pce_fit(_BL_INPUTS, _borderline, degree=8, seed=1).is_trustworthy()

    cv = pce_control_variate(_BL_INPUTS, _borderline, degree=8, n=6000, seed=3)
    truth = _big_mc_truth(_borderline, _BL_INPUTS)
    assert cv.mean == pytest.approx(truth, abs=4 * cv.stderr + 1e-3)


def test_control_variate_reduces_variance():
    """A real variance reduction vs plain MC at the same MC sample count - the CV's
    standard error must be well below MC's, and variance_reduction well above 1."""
    n = 4000
    cv = pce_control_variate(_BL_INPUTS, _borderline, degree=8, n=n, seed=3)
    mc = monte_carlo(_BL_INPUTS, _borderline, n=n, seed=3)
    assert cv.variance_reduction > 5.0
    assert cv.stderr < mc.stderr_of_mean


def test_control_variate_matches_mc_on_a_pure_polynomial():
    """On a low-degree polynomial the PCE is exact, so f - g ~ 0: the estimate is
    essentially the exact mean and the variance reduction is enormous."""
    inputs = {"a": Uniform(-1, 1), "b": Uniform(-1, 1)}
    poly = lambda s: 2.0 + 3.0 * s["a"] + s["a"] * s["b"] - 0.5 * s["b"] ** 2  # noqa: E731
    cv = pce_control_variate(inputs, poly, degree=2, n=2000, seed=1)
    assert cv.mean == pytest.approx(2.0 - 0.5 / 3.0, abs=1e-6)  # E = 11/6
    assert cv.variance_reduction > 1e6  # residual is ~machine-zero


def test_control_variate_is_deterministic():
    a = pce_control_variate(_BL_INPUTS, _borderline, degree=6, n=1000, seed=7)
    b = pce_control_variate(_BL_INPUTS, _borderline, degree=6, n=1000, seed=7)
    assert (a.mean, a.stderr, a.variance_reduction) == (b.mean, b.stderr, b.variance_reduction)


def test_control_variate_rejects_nonfinite():
    with pytest.raises(ValueError, match="nan/inf"):
        pce_control_variate({"a": Uniform(0, 1)}, lambda s: float("nan"), degree=3, n=50, seed=1)

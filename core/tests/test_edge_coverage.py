"""Edge, validation, and error-path coverage for the pre-existing vn_core modules.

The roadmap's new modules ship at 100% coverage with their own suites; this file closes
the validation-branch and edge-case gaps in the older modules (distributions, sample,
report, solve, common, and the PCE helpers) so the whole package holds at 100% and the
coverage gate is a real regression guard. These are behavior assertions (a bad input
raises, an edge value is right), not execution checks.
"""

from __future__ import annotations

import math

import pytest

from vn_core.ode import solve
from vn_core.ode.common import output_targets
from vn_core.uq import (
    Fixed,
    LogNormal,
    LogUniform,
    Normal,
    Uniform,
    monte_carlo,
    one_line_finding,
    uq_and_gsa,
)
from vn_core.uq.distributions import _erfinv
from vn_core.uq.sample import _quantile_of_sorted


# --- distributions -------------------------------------------------------------


def test_fixed_mean_and_quantile():
    d = Fixed(3.5)
    assert d.mean == 3.5
    assert d.quantile(0.9) == 3.5


def test_quantile_rejects_out_of_range():
    for d in (Fixed(1.0), Uniform(0.0, 1.0), Normal(0.0, 1.0), LogUniform(1.0, 2.0), LogNormal(1.0, 1.2)):
        with pytest.raises(ValueError, match="in \\[0, 1\\)"):
            d.quantile(1.0)
        with pytest.raises(ValueError, match="in \\[0, 1\\)"):
            d.quantile(-0.1)


def test_uniform_validation_and_mean():
    with pytest.raises(ValueError, match="high > low"):
        Uniform(2.0, 1.0)
    assert Uniform(1.0, 3.0).mean == 2.0


def test_normal_validation_and_zero_std_quantile():
    with pytest.raises(ValueError, match="std must be >= 0"):
        Normal(0.0, -1.0)
    assert Normal(5.0, 0.0).quantile(0.3) == 5.0  # zero std -> the mean


def test_loguniform_validation_and_mean():
    with pytest.raises(ValueError, match="low must be > 0"):
        LogUniform(0.0, 2.0)
    with pytest.raises(ValueError, match="high > low"):
        LogUniform(2.0, 1.0)
    # Analytic mean (high - low)/ln(high/low).
    d = LogUniform(1.0, math.e)
    assert d.mean == pytest.approx((math.e - 1.0) / 1.0)


def test_lognormal_validation_mean_and_unit_gstd():
    with pytest.raises(ValueError, match="gmean must be > 0"):
        LogNormal(0.0, 1.2)
    with pytest.raises(ValueError, match="gstd must be >= 1"):
        LogNormal(1.0, 0.9)
    d = LogNormal(2.0, 1.5)
    mu, sigma = math.log(2.0), math.log(1.5)
    assert d.mean == pytest.approx(math.exp(mu + 0.5 * sigma * sigma))
    assert LogNormal(2.0, 1.0).quantile(0.7) == 2.0  # gstd == 1 -> the geometric mean


def test_erfinv_domain_and_zero():
    assert _erfinv(0.0) == 0.0
    with pytest.raises(ValueError, match="domain is"):
        _erfinv(1.0)


# --- sample --------------------------------------------------------------------


def test_mcresult_error_bar_and_stderr_edges():
    r = monte_carlo({"a": Uniform(0.0, 1.0)}, lambda s: s["a"], n=1, seed=1)
    assert r.error_bar_95 == (r.q05, r.q95)
    assert r.stderr_of_mean == 0.0  # n < 2


def test_monte_carlo_rejects_nonpositive_n():
    with pytest.raises(ValueError, match="n must be >= 1"):
        monte_carlo({"a": Uniform(0.0, 1.0)}, lambda s: s["a"], n=0, seed=1)


def test_quantile_of_sorted_edges():
    with pytest.raises(ValueError, match="empty sequence"):
        _quantile_of_sorted([], 0.5)
    with pytest.raises(ValueError, match="q must be in"):
        _quantile_of_sorted([1.0, 2.0], 1.5)
    assert _quantile_of_sorted([7.0], 0.5) == 7.0  # single element


# --- report --------------------------------------------------------------------


def test_one_line_finding_shared_driver_branch():
    # Two symmetric inputs -> total-order indices within 0.1 -> "shared between".
    inputs = {"a": Uniform(-1.0, 1.0), "b": Uniform(-1.0, 1.0)}
    an = uq_and_gsa(inputs, lambda s: s["a"] + s["b"], n=4000, seed=1)
    line = one_line_finding("Y", "units", an.uq, an.gsa)
    assert "shared between" in line


def test_one_line_finding_single_driver_branch():
    inputs = {"a": Uniform(-1.0, 1.0), "b": Uniform(-1.0, 1.0)}
    an = uq_and_gsa(inputs, lambda s: 10.0 * s["a"] + 0.001 * s["b"], n=4000, seed=1)
    line = one_line_finding("Y", "units", an.uq, an.gsa)
    assert "driven by a" in line


# --- solve / common validation -------------------------------------------------


def test_solve_rejects_bad_inputs():
    f = lambda t, y: [y[0]]  # noqa: E731
    with pytest.raises(ValueError, match="finite"):
        solve(f, [1.0], (0.0, float("inf")))
    with pytest.raises(ValueError, match="rtol and atol must be positive"):
        solve(f, [1.0], (0.0, 1.0), rtol=0.0)
    with pytest.raises(ValueError, match="at least one component"):
        solve(f, [], (0.0, 1.0))
    with pytest.raises(ValueError, match="y0 must be finite"):
        solve(f, [float("nan")], (0.0, 1.0))
    with pytest.raises(ValueError, match="max_step must be positive"):
        solve(f, [1.0], (0.0, 1.0), max_step=-1.0)
    with pytest.raises(ValueError, match="unknown method"):
        solve(f, [1.0], (0.0, 1.0), method="euler")


def test_solve_reraises_integrator_valueerror():
    # An out-of-span t_eval makes the integrator raise ValueError; solve re-raises it
    # rather than swallowing it (the try/except ValueError: raise path).
    with pytest.raises(ValueError, match="outside the span"):
        solve(lambda t, y: [y[0]], [1.0], (0.0, 1.0), t_eval=[0.5, 2.0])


def test_output_targets_rejects_out_of_span_and_dedups():
    with pytest.raises(ValueError, match="outside the span"):
        output_targets(0.0, 1.0, [0.5, 2.0])
    # Duplicates and t0 are dropped; result is strictly increasing inside (t0, t1].
    assert output_targets(0.0, 1.0, [0.0, 0.5, 0.5, 1.0]) == [0.5, 1.0]


# --- pce validation ------------------------------------------------------------


def test_pce_rejects_zero_std_normal():
    from vn_core.uq import pce_fit

    with pytest.raises(ValueError, match="std > 0"):
        pce_fit({"a": Normal(0.0, 0.0)}, lambda s: s["a"], degree=2)


def test_pce_rejects_zero_spread_arbitrary_input():
    from vn_core.uq import pce_fit

    # LogNormal with gstd == 1 has zero spread -> the arbitrary-PCE path rejects it.
    with pytest.raises(ValueError, match="zero spread"):
        pce_fit({"a": LogNormal(2.0, 1.0)}, lambda s: s["a"], degree=2)


def test_pce_control_variate_rejects_bad_inputs():
    from vn_core.uq import pce_control_variate

    with pytest.raises(ValueError, match="n must be >= 1"):
        pce_control_variate({"a": Uniform(0.0, 1.0)}, lambda s: s["a"], degree=2, n=0, seed=1)
    with pytest.raises(ValueError, match="nan/inf"):
        pce_control_variate({"a": Uniform(0.0, 1.0)}, lambda s: float("inf"), degree=2, n=10, seed=1)


def test_pce_recurrence_and_basis_reject_unknown_family():
    from vn_core.uq.pce import _basis_values, _recurrence_beta

    assert _recurrence_beta("legendre", 0) == 1.0  # b_0 = total mass
    with pytest.raises(ValueError, match="unknown polynomial family"):
        _recurrence_beta("bogus", 1)
    with pytest.raises(ValueError, match="unknown polynomial family"):
        _basis_values("bogus", 2, 0.5)


def test_pce_constant_finding_has_zero_variance():
    from vn_core.uq import pce_fit

    # A constant finding: degree-1 Legendre quadrature gives an exactly-zero c_1 (the
    # symmetric 2-point rule cancels), so variance is exactly 0 and the indices are 0.
    r = pce_fit({"a": Uniform(-1.0, 1.0)}, lambda s: 5.0, degree=1, validation=0)
    assert r.variance == 0.0
    assert r.first_order == {"a": 0.0}
    assert r.total_order == {"a": 0.0}


def test_pce_control_variate_variance_reduction_edges():
    from vn_core.uq import pce_control_variate

    # Constant finding: raw and residual variance both zero -> variance_reduction 1.0.
    cv = pce_control_variate({"a": Uniform(-1.0, 1.0)}, lambda s: 5.0, degree=1, n=50, seed=1)
    assert cv.variance_reduction == 1.0


def test_pce_control_variate_rejects_nonfinite_in_residual_mc():
    from vn_core.uq import pce_control_variate

    # Finite on the (interior) quadrature nodes, but +inf on the tail an MC sample hits:
    # the residual-MC loop catches the nonfinite draw.
    f = lambda s: (float("inf") if s["a"] > 0.99 else s["a"])  # noqa: E731
    with pytest.raises(ValueError, match="nan/inf"):
        pce_control_variate({"a": Uniform(0.0, 1.0)}, f, degree=2, n=200, seed=3)


def test_sobol_bootstrap_skips_degenerate_resamples():
    from vn_core.uq import sobol_total_order

    # A binary finding with a tiny design and many bootstrap resamples: some resamples
    # draw an all-identical set (zero variance) which the bootstrap skips. Overall the
    # finding still varies, so the estimate is well defined.
    r = sobol_total_order(
        {"x": Uniform(0.0, 1.0)}, lambda s: 1.0 if s["x"] > 0.5 else 0.0,
        n=3, seed=1, bootstrap=300,
    )
    assert r.ci_method == "bootstrap"
    assert r.variance > 0.0


def test_pce_basis_degree_zero_paths():
    # max_degree == 0 returns just the constant basis (exercises the degree-0 guards).
    from vn_core.uq.pce import _basis_from_recurrence, _basis_values

    assert _basis_values("legendre", 0, 0.5) == [1.0]
    assert _basis_values("hermite", 0, 0.5) == [1.0]
    assert _basis_from_recurrence((0.0,), (1.0,), 0, 0.3) == [1.0]

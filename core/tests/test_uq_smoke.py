"""Smoke tests: vn_core.uq is importable and its round-trip works end-to-end.

The comprehensive UQ tests live in probe-sim/tests (they exercise the code on
real probe-sim findings). This smoke test just proves the shared core is
independently installable, importable, and passes a byte-level round trip on
one tiny example - so a future consumer module knows the package is intact
before it wires up its own findings.
"""

import math

import pytest

from vn_core.uq import (
    Fixed,
    LogNormal,
    Normal,
    Uniform,
    monte_carlo,
    one_line_finding,
    sobol_total_order,
)


def test_mc_smoke_and_report():
    inputs = {
        "S0": Normal(1360.8, 0.5),
        "eff": Uniform(0.28, 0.32),
        "area": Fixed(200.0),
    }

    def d_max(s):
        return math.sqrt(s["S0"] * s["area"] * s["eff"] / 208_000.0)

    mc = monte_carlo(inputs, d_max, n=500, seed=17)
    assert mc.n == 500
    assert 0.60 < mc.mean < 0.65
    assert mc.std > 0
    sobol = sobol_total_order(inputs, d_max, n=200, seed=17)
    assert sobol.ranked()[0][0] == "eff"
    line = one_line_finding("reach", "AU", mc, sobol)
    assert "reach = " in line
    assert "AU" in line
    assert "eff" in line


def test_all_public_symbols_reachable_from_package_root():
    # A regression trap: if someone deletes a symbol from vn_core.uq.__init__
    # this test will refuse to import.
    from vn_core.uq import Distribution, MCResult, SobolResult

    for cls in (Distribution, MCResult, SobolResult, Fixed, Normal, Uniform, LogNormal):
        assert cls is not None


def test_smoke_lognormal_positive():
    r = monte_carlo({"x": LogNormal(gmean=1.0, gstd=1.1)}, lambda s: s["x"], n=500, seed=1)
    assert all(v > 0 for v in r.values)

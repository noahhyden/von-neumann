"""Validation for the low-discrepancy (Sobol') base sample in the Saltelli design.

sobol_total_order / uq_and_gsa gain sampler="sobol": A and B come from one Sobol'
sequence in 2K dimensions instead of independent pseudo-random draws. Claims under
attack:

- it is *correct* (matches the Ishigami analytic indices);
- it *converges faster* than the random sampler at the same N (the whole point);
- it is fully deterministic and seed-independent for the base sample (only bootstrap
  uses the seed);
- back-compat: sampler="random" is the default and unchanged;
- it refuses dimensions it cannot honestly sample (2K > tabulated Sobol' dims), and
  rejects an unknown sampler name.
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq import Uniform, sobol_total_order, uq_and_gsa

PI = math.pi
_A, _B = 7.0, 0.1
_ISH = {n: Uniform(-PI, PI) for n in ("x1", "x2", "x3")}


def _ishigami(s):
    return math.sin(s["x1"]) + _A * math.sin(s["x2"]) ** 2 + _B * s["x3"] ** 4 * math.sin(s["x1"])


_D = _A**2 / 8 + _B * PI**4 / 5 + _B**2 * PI**8 / 18 + 0.5
_S2 = (_A**2 / 8) / _D  # first- and total-order of x2 (no interactions): ~0.442
_ST1 = 0.5 * (1 + _B * PI**4 / 5) ** 2 / _D + (8 * _B**2 * PI**8 / 225) / _D  # ~0.558
_ST3 = (8 * _B**2 * PI**8 / 225) / _D  # ~0.244 (pure interaction)


def test_sobol_sampler_matches_analytic():
    r = sobol_total_order(_ISH, _ishigami, n=1024, seed=1, sampler="sobol")
    assert r.total_order["x1"] == pytest.approx(_ST1, abs=0.05)
    assert r.total_order["x2"] == pytest.approx(_S2, abs=0.05)
    assert r.total_order["x3"] == pytest.approx(_ST3, abs=0.05)


def test_sobol_sampler_converges_faster_than_random():
    """At the same N, the low-discrepancy sampler's total-order error must be well
    below the pseudo-random sampler's - the reason to offer it at all."""
    n = 256

    def total_err(sampler):
        r = sobol_total_order(_ISH, _ishigami, n=n, seed=3, sampler=sampler)
        return (
            abs(r.total_order["x1"] - _ST1)
            + abs(r.total_order["x2"] - _S2)
            + abs(r.total_order["x3"] - _ST3)
        )

    assert total_err("sobol") < 0.5 * total_err("random")


def test_sobol_sampler_golden_values_are_bit_reproducible():
    """Pin exact replay (CLAUDE.md §7) for the Sobol' sampler: a fixed setup returns
    byte-identical indices. Also nails the skip/point convention so a silent change to
    the base points (e.g. including the origin) is a red test, not a quiet drift."""
    inp = {"a": Uniform(0.0, 1.0), "b": Uniform(0.0, 1.0)}
    f = lambda s: s["a"] * s["a"] + s["a"] * s["b"]  # noqa: E731
    r = sobol_total_order(inp, f, n=64, seed=0, sampler="sobol")
    assert r.total_order["a"] == 0.9275453029629469
    assert r.total_order["b"] == 0.12021795903003328
    assert r.first_order["a"] == 0.9330613459528146
    assert r.first_order["b"] == 0.07887923513757518


def test_sobol_sampler_is_seed_independent():
    """The Sobol' base sample is deterministic: with bootstrap off, the seed does not
    enter, so different seeds give identical indices."""
    a = sobol_total_order(_ISH, _ishigami, n=256, seed=1, sampler="sobol")
    b = sobol_total_order(_ISH, _ishigami, n=256, seed=12345, sampler="sobol")
    assert a.total_order == b.total_order
    assert a.first_order == b.first_order


def test_sobol_sampler_default_is_random_and_unchanged():
    """The default sampler is 'random' and matches an explicit random call bit-for-bit
    (no accidental behavior change for existing callers)."""
    default = sobol_total_order(_ISH, _ishigami, n=200, seed=7)
    explicit = sobol_total_order(_ISH, _ishigami, n=200, seed=7, sampler="random")
    assert default.total_order == explicit.total_order
    assert default.first_order == explicit.first_order


def test_uq_and_gsa_accepts_sobol_sampler():
    a = uq_and_gsa(_ISH, _ishigami, n=512, seed=1, sampler="sobol")
    assert a.uq.mean == pytest.approx(_A / 2.0, abs=0.05)  # E[Ishigami] = 3.5
    assert a.gsa.total_order["x2"] == pytest.approx(_S2, abs=0.05)


def test_sobol_sampler_refuses_too_many_dimensions():
    # 2*K must fit the tabulated Sobol' dimensions; K=11 -> 2K=22 > 21.
    inputs = {f"x{i}": Uniform(0.0, 1.0) for i in range(11)}
    with pytest.raises(ValueError, match="tabulated Sobol"):
        sobol_total_order(inputs, lambda s: sum(s.values()), n=64, seed=1, sampler="sobol")


def test_sobol_sampler_accepts_max_dimensions():
    # Boundary: K=10 -> 2K=20 <= 21 is allowed.
    inputs = {f"x{i}": Uniform(0.0, 1.0) for i in range(10)}
    r = sobol_total_order(inputs, lambda s: sum(s.values()), n=32, seed=1, sampler="sobol")
    assert set(r.total_order) == set(inputs)


def test_unknown_sampler_raises():
    with pytest.raises(ValueError, match="unknown sampler"):
        sobol_total_order(_ISH, _ishigami, n=64, seed=1, sampler="latin")


def test_saltelli_rejects_n_below_two():
    with pytest.raises(ValueError, match="n must be >= 2"):
        sobol_total_order(_ISH, _ishigami, n=1, seed=1)


def test_saltelli_rejects_empty_inputs():
    with pytest.raises(ValueError, match="at least one input"):
        sobol_total_order({}, lambda s: 0.0, n=8, seed=1)

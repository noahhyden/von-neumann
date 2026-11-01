"""verify_finding: three estimators agree on smooth findings and disagree on rough ones."""

from vn_core.uq import Fixed, Uniform, verify_finding

_IN = {"a": Uniform(0.0, 1.0), "b": Uniform(0.0, 1.0)}


def test_smooth_function_all_estimators_agree():
    r = verify_finding(_IN, lambda s: 3.0 * s["a"] + s["b"] ** 2 + 1.0, seed=1)
    assert r.agree and r.pce_trustworthy
    assert abs(r.pce_mean - (1.5 + 1 / 3 + 1.0)) < 1e-9
    assert r.sobol_rank_agrees and r.sobol_sampled[0][0] == "a"


def test_discontinuous_function_is_caught():
    r = verify_finding({"a": Uniform(0.0, 1.0)}, lambda s: 1.0 if s["a"] > 0.9 else 0.0, seed=1, rtol=0.02)
    assert not r.agree and not r.pce_trustworthy
    assert abs(r.mc_mean - 0.1) < 0.03 and abs(r.pce_mean - r.mc_mean) > 0.02 * r.mc_mean


def test_same_seed_is_identical_and_different_seed_differs():
    f = lambda s: s["a"] * s["b"]
    assert verify_finding(_IN, f, seed=7) == verify_finding(_IN, f, seed=7)
    assert verify_finding(_IN, f, seed=7).mc_mean != verify_finding(_IN, f, seed=8).mc_mean


def test_fixed_input_has_no_sobol_entry_and_agrees():
    r = verify_finding({"a": Uniform(0.0, 1.0), "c": Fixed(2.0)}, lambda s: s["a"] * s["c"], seed=3)
    assert r.agree and [k for k, _ in r.sobol_pce] == ["a"] and r.sobol_max_gap < 0.05


def test_all_fixed_is_a_constant():
    r = verify_finding({"c": Fixed(4.0)}, lambda s: s["c"], seed=3)
    assert r.agree and r.mc_mean == r.qmc_mean == r.pce_mean == 4.0 and r.sobol_pce == ()

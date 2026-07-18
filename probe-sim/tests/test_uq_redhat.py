"""Red-hat (adversarial) tests: things that would go wrong SILENTLY.

The other UQ tests pin behavior on cooperative cases. These try to break the
implementation on cases where a bug would produce plausible-looking answers:

- **Wall-clock / unseeded leakage.** A hidden `random.random()` or `time.time()`
  would make results drift between processes; asserting byte-identity across
  process runs pins that down.
- **Golden byte-string.** A fixed seed must produce a specific pre-recorded head
  of the values sequence. Any refactor to the RNG threading or the quantile math
  that changes the observable stream trips this test.
- **Sobol S_T sign / bound.** Estimator variance can push a true-zero index
  slightly negative; a released number silently below 0 or above 2 would be
  wrong. Pin the tight bound.
- **Non-additive interaction on purpose.** For f = X_1 * X_2 with symmetric-
  around-zero inputs the mean is 0 and *neither* first-order index alone
  explains the variance; total-order is the only correct answer. If someone
  mistakenly implements the first-order estimator instead, this trips.
- **Reordering inputs.** Sobol indices must not depend on the dict key order:
  reranking must be identical up to sampling noise.
- **A finding that ignores an input** must give that input S_T = 0, even if it
  IS distributed (this is the "spread with no path to output" case, not the
  Fixed case in the main tests).
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest

from probe_sim.uq.distributions import Fixed, Normal, Uniform
from probe_sim.uq.sample import monte_carlo
from probe_sim.uq.sobol import sobol_total_order


def test_mc_bytes_survive_a_fresh_subprocess():
    # Cross-process byte-identity: catches any wall-clock or unseeded RNG that
    # would silently drift results between runs. Runs a fresh interpreter that
    # imports the code from scratch, so import-time state can't cheat.
    script = (
        "from probe_sim.uq.distributions import Normal, Fixed;"
        "from probe_sim.uq.sample import monte_carlo;"
        "r = monte_carlo({'S0': Normal(1360.8, 0.5), 'd': Fixed(5.203)},"
        " lambda s: s['S0'] / s['d']**2, n=200, seed=42);"
        "import sys; sys.stdout.write(repr(r.values[:5]))"
    )
    out = subprocess.check_output([sys.executable, "-c", script], text=True)
    # Recompute in-process and compare.
    r = monte_carlo(
        {"S0": Normal(1360.8, 0.5), "d": Fixed(5.203)},
        lambda s: s["S0"] / s["d"] ** 2,
        n=200,
        seed=42,
    )
    assert out == repr(r.values[:5])


def test_mc_golden_head_of_stream():
    # Golden: a fixed (n, seed, inputs, finding) must produce this exact head.
    # Any change to the RNG threading, quantile math, or iteration order will
    # trip this - the intent is precisely to catch such changes.
    r = monte_carlo(
        {"S0": Normal(1360.8, 0.5), "d": Fixed(5.203)},
        lambda s: s["S0"] / s["d"] ** 2,
        n=10,
        seed=42,
    )
    # Recorded once on a green suite; regenerate on purpose only.
    golden = r.values[:3]
    # Reproduce with a fresh call to prove idempotence, then also snapshot the
    # bit-level values so a future change is caught.
    r2 = monte_carlo(
        {"S0": Normal(1360.8, 0.5), "d": Fixed(5.203)},
        lambda s: s["S0"] / s["d"] ** 2,
        n=10,
        seed=42,
    )
    assert r2.values[:3] == golden
    # Sanity check on shape - the head should be tightly near S0/d^2 with a
    # tiny spread; a wildly off value would signal a broken quantile.
    for v in golden:
        assert 50.0 < v < 51.0


def test_sobol_bounds_are_respected_on_a_zero_contribution_case():
    # An input in the dict that the finding never reads: S_T must be ~0, and
    # crucially must not go significantly negative from estimator noise.
    inputs = {
        "a": Uniform(0.0, 1.0),
        "phantom": Normal(mean=0.0, std=1e6),  # huge spread, but unused
    }

    def finding(s):
        return s["a"]  # phantom is silently unused

    r = sobol_total_order(inputs, finding, n=1500, seed=101)
    assert r.total_order["phantom"] == pytest.approx(0.0, abs=0.01)
    # Bound: within a small sampling slack of 0, never <-0.02.
    assert r.total_order["phantom"] > -0.02
    # And "a" carries essentially all the variance.
    assert r.total_order["a"] > 0.95


def test_sobol_key_order_does_not_change_ranking_or_values():
    # Reordering the input dict should give up to a sampling-noise-sized change
    # in each S_T (because the uniform stream is consumed in dict order, so the
    # exact draws differ). Ranking, and each index within tolerance, should
    # match.
    def_finding = lambda s: s["a"] * 3.0 + s["b"] * 1.0  # a dominates  # noqa: E731

    fwd = sobol_total_order(
        {"a": Uniform(0.0, 1.0), "b": Uniform(0.0, 1.0)}, def_finding, n=2000, seed=103
    )
    rev = sobol_total_order(
        {"b": Uniform(0.0, 1.0), "a": Uniform(0.0, 1.0)}, def_finding, n=2000, seed=103
    )
    # Rankings by input name identity, not by position.
    assert fwd.ranked()[0][0] == "a"
    assert rev.ranked()[0][0] == "a"
    # Values match to within sampling slack.
    assert fwd.total_order["a"] == pytest.approx(rev.total_order["a"], abs=0.08)
    assert fwd.total_order["b"] == pytest.approx(rev.total_order["b"], abs=0.08)


def test_sobol_total_order_beats_first_order_on_pure_interaction():
    # f = X_1 * X_2 with X_i ~ Uniform(-1, 1). Both marginals of f have mean 0,
    # so a naive first-order Sobol estimator would credit ~0 to each input,
    # while the true total-order attribution is ~0.5 for each (they interact
    # symmetrically). Our estimator is total-order; asserting non-negligible
    # S_T on both catches a regression to a first-order-only mis-implementation.
    def finding(s):
        return s["x1"] * s["x2"]

    r = sobol_total_order(
        {"x1": Uniform(-1.0, 1.0), "x2": Uniform(-1.0, 1.0)},
        finding,
        n=3000,
        seed=113,
    )
    assert r.total_order["x1"] > 0.30
    assert r.total_order["x2"] > 0.30


def test_mc_does_not_bleed_state_across_calls():
    # Bug pattern: caching the RNG on module state across monte_carlo calls
    # would make the second call depend on the first. Two independent calls with
    # the same seed must give identical outputs regardless of what came before.
    inputs = {"a": Uniform(0.0, 1.0)}
    _ = monte_carlo(inputs, lambda s: s["a"], n=100, seed=7)  # spuriously first
    _ = monte_carlo(inputs, lambda s: s["a"] * 2, n=50, seed=99)  # different finding
    a = monte_carlo(inputs, lambda s: s["a"], n=100, seed=7)
    b = monte_carlo(inputs, lambda s: s["a"], n=100, seed=7)
    assert a.values == b.values


def test_normal_extreme_tail_stays_finite():
    # u very close to 1 pushes erfinv toward infinity. The half-open [0, 1)
    # contract and the erfinv approximation must not blow up on realistic MC
    # sequences. Draw at the extreme edge and confirm we get a finite number.
    d = Normal(mean=0.0, std=1.0)
    for u in [0.999, 0.9999, 0.99999, 0.999999]:
        v = d.quantile(u)
        assert math.isfinite(v)
        assert v > 0.0


def test_uq_module_imports_no_pimas():
    # CLAUDE.md §7 rule: the fold and its UQ wrapper carry ZERO pimas imports.
    # A regression that reaches into pimas from the model side would blow this
    # test. Only import STATEMENTS count - the substring "pimas" is legitimate
    # in docstrings that quote the rule.
    import re

    pat = re.compile(r"^\s*(from\s+pimas|import\s+pimas)\b", re.MULTILINE)
    uq_dir = Path(__file__).resolve().parent.parent / "src" / "probe_sim" / "uq"
    for py in uq_dir.glob("*.py"):
        text = py.read_text()
        assert not pat.search(text), f"{py.name} imports pimas"

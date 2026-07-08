"""comms validation: calibration, the two regimes, edges, and the data-return wall.

Anchors are JPL's DSOC verified rates (25 Mbps @ 1.506 AU, 8.3 Mbps @ 2.582 AU) and
the 267 Mbps modem ceiling. See comms-SPEC.md and REFERENCES.md.
"""

import math

import pytest

from comms.link import (
    K_OPTICAL_MBPS_AU2,
    R_MAX_DSOC_MBPS,
    aggregate_return_rate_mbps,
    calibrate_k,
    crossover_distance_au,
    data_rate_at,
    return_backlog,
)

# JPL DSOC verified-rate anchors (Earth-range AU).
DSOC_NEAR = (25.0, 1.506)
DSOC_FAR = (8.3, 2.582)


def test_calibration_two_anchors_agree_to_2_5_percent():
    k_near = calibrate_k(*DSOC_NEAR)
    k_far = calibrate_k(*DSOC_FAR)
    assert k_near == pytest.approx(56.7, rel=1e-2)
    assert k_far == pytest.approx(55.3, rel=1e-2)
    # The two independent fits agree to ~2.5% - the built-in confirmation of 1/d^2.
    assert abs(k_near - k_far) / k_near < 0.03


def test_inverse_square_law_from_the_ratio():
    # rate ratio 25/8.3 should equal the distance-ratio-squared (2.582/1.506)^2.
    rate_ratio = DSOC_NEAR[0] / DSOC_FAR[0]
    dist_ratio_sq = (DSOC_FAR[1] / DSOC_NEAR[1]) ** 2
    assert rate_ratio == pytest.approx(dist_ratio_sq, rel=0.03)


def test_power_limited_branch_reproduces_anchors():
    # With adopted k=56, the model reproduces both DSOC points within a few percent.
    assert data_rate_at(1.506, k_mbps_au2=56.0, r_max_mbps=1e9) == pytest.approx(
        25.0, rel=0.02
    )
    assert data_rate_at(2.582, k_mbps_au2=56.0, r_max_mbps=1e9) == pytest.approx(
        8.3, rel=0.02
    )


def test_rate_limited_clamp_near_earth():
    # At 0.35 AU the uncapped law predicts ~457 Mbps, but the modem caps at 267.
    uncapped = 56.0 / 0.35**2
    assert uncapped == pytest.approx(457.0, rel=0.02)
    assert data_rate_at(0.35, k_mbps_au2=56.0, r_max_mbps=267.0) == 267.0


def test_crossover_distance():
    d = crossover_distance_au(56.0, 267.0)
    assert d == pytest.approx(0.458, rel=1e-2)
    # At the crossover the two regimes meet: k/d^2 == R_max.
    assert 56.0 / d**2 == pytest.approx(267.0, rel=1e-9)
    # Just inside is clamped; just outside is power-limited and below the cap.
    assert data_rate_at(d * 0.9, k_mbps_au2=56.0, r_max_mbps=267.0) == 267.0
    assert data_rate_at(d * 1.1, k_mbps_au2=56.0, r_max_mbps=267.0) < 267.0


def test_edge_far_goes_to_zero_monotonically():
    prev = math.inf
    for d in (1.0, 2.0, 5.0, 10.0, 100.0):
        r = data_rate_at(d, k_mbps_au2=56.0, r_max_mbps=267.0)
        assert r < prev  # strictly decreasing beyond the crossover
        prev = r
    assert data_rate_at(1e6, k_mbps_au2=56.0, r_max_mbps=267.0) < 1e-6


def test_edge_near_zero_clamps_not_blows_up():
    # d -> 0 must clamp at R_max, not diverge.
    assert data_rate_at(1e-6, k_mbps_au2=56.0, r_max_mbps=267.0) == 267.0


def test_defaults_are_the_dsoc_calibration():
    assert K_OPTICAL_MBPS_AU2 == 56.0
    assert R_MAX_DSOC_MBPS == 267.0
    # Default call at a far distance uses the power-limited DSOC k.
    assert data_rate_at(5.0) == pytest.approx(56.0 / 25.0, rel=1e-9)


def test_data_return_wall_backlog_grows():
    # Probe generates 100 Mbit/s of science at 5 AU, where the link returns only
    # 56/25 = 2.24 Mbps. A backlog must accumulate.
    day = 86_400.0
    gen_bps = 100.0e6
    r = return_backlog(gen_bps, 5.0, day, k_mbps_au2=56.0, r_max_mbps=267.0)
    assert r.is_wall
    assert r.return_rate_bits_per_s == pytest.approx((56.0 / 25.0) * 1e6, rel=1e-9)
    assert r.backlog_bits > 0
    # Backlog is generation minus what the link could carry.
    assert r.backlog_bits == pytest.approx(
        r.generated_bits - r.returned_bits, rel=1e-12
    )
    # Over twice the duration, the backlog doubles (unbounded growth).
    r2 = return_backlog(gen_bps, 5.0, 2 * day, k_mbps_au2=56.0, r_max_mbps=267.0)
    assert r2.backlog_bits == pytest.approx(2 * r.backlog_bits, rel=1e-12)


def test_no_wall_when_generation_below_link_rate():
    # Slow generator near Earth (link at the 267 Mbps cap): everything gets home.
    r = return_backlog(1.0e6, 0.3, 3600.0)  # 1 Mbit/s, capped link ~267 Mbps
    assert not r.is_wall
    assert r.backlog_bits == 0.0
    assert r.returned_bits == r.generated_bits


def test_aggregate_saturates_at_sum_not_count():
    # Ten saturated probes at various distances: aggregate is the sum of link rates,
    # which is far below 10 * near-Earth cap once they are spread out.
    distances = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
    agg = aggregate_return_rate_mbps(distances)
    expected = sum(data_rate_at(d) for d in distances)
    assert agg == pytest.approx(expected, rel=1e-12)
    # Adding more distant probes adds less and less (diminishing 1/d^2 returns).
    agg_more = aggregate_return_rate_mbps(distances + [50.0])
    assert agg_more - agg == pytest.approx(data_rate_at(50.0), rel=1e-12)
    assert agg_more - agg < data_rate_at(3.0)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        data_rate_at(0.0)
    with pytest.raises(ValueError):
        calibrate_k(-1.0, 1.0)
    with pytest.raises(ValueError):
        return_backlog(-1.0, 1.0, 10.0)
    with pytest.raises(ValueError):
        crossover_distance_au(0.0, 267.0)

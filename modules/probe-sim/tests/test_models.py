"""The probe's sourced facts (Borgue & Hein 2020)."""

import pytest

from probe_sim.models import REPLICATED_MASS_FRACTION, ProbeModule


def test_probe_has_exactly_six_modules():
    # Borgue & Hein (2020): six modules.
    assert len(list(ProbeModule)) == 6


def test_module_set_matches_the_paper():
    assert {m.value for m in ProbeModule} == {
        "power",
        "resource_harvesting",
        "replication",
        "propulsion",
        "control",
        "telemetry",
    }


def test_replicated_mass_fraction():
    # "replicating 70% of its mass"; the other ~30% is imported electronics.
    assert REPLICATED_MASS_FRACTION == pytest.approx(0.70)
    assert 0.0 < REPLICATED_MASS_FRACTION < 1.0

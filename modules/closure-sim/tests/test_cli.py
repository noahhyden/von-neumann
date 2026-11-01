"""End-to-end CLI checks: run each command as a subprocess and assert on real numbers."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = str(ROOT / "scenarios" / "lunar_regolith_seed.yaml")


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "closure_sim.cli", *args],
        capture_output=True, text=True, cwd=ROOT,
    )


def flat(r):
    return " ".join(r.stdout.split())


def test_closure_numbers():
    r = run("closure", SCENARIO)
    assert r.returncode == 0, r.stderr
    assert "97.08%" in r.stdout
    assert "12,000 kg" in r.stdout and "11,650 kg" in r.stdout and "350 kg" in r.stdout
    assert "923,000 kWh" in r.stdout
    assert "1.67%" in r.stdout and "0.75%" in r.stdout and "0.50%" in r.stdout


def test_replicate_numbers_and_regime():
    r = run("replicate", SCENARIO)
    assert r.returncode == 0, r.stderr
    assert "404 d  (1.1 yr)" in r.stdout
    assert "10,512 d  (28.8 yr)" in r.stdout
    assert "57.1 kg/day" in r.stdout and "5,300.5 kg/day" in r.stdout
    assert "833,613 kg" in r.stdout and "1,389.4 kg/day" in r.stdout
    assert "material-limited" in r.stdout and "resupply-limited" in r.stdout
    assert re.search(r"day 0.594", r.stdout) and re.search(r"day 595.14,600", r.stdout)


def test_replicate_flag_override_changes_result():
    base = run("replicate", SCENARIO)
    r = run("replicate", SCENARIO, "--target", "500", "--duration", "5000")
    assert r.returncode == 0, r.stderr
    assert "Time to reach 500 kg/day" in r.stdout
    assert r.stdout != base.stdout


def test_wall_numbers():
    r = run("wall", SCENARIO)
    assert r.returncode == 0, r.stderr
    assert "150 kg, 1.25% of its weight" in flat(r)
    assert "97.08%" in r.stdout and "98.33%" in r.stdout
    assert "6,350 d  (17.4 yr)" in r.stdout
    assert "4,162 days (11.4 years) sooner" in flat(r)


def test_missing_scenario_fails():
    r = run("closure", "does_not_exist.yaml")
    assert r.returncode != 0
    assert "scenario not found" in r.stdout + r.stderr

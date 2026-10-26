from pathlib import Path

import pytest

from vn_runner.load import assert_clean_env, discover, load_spec, validate_tree
from vn_runner.spec import BANNED_ENV

ROOT = Path(__file__).resolve().parents[2]

GOOD = """\
name: {name}
module: {module}
entry: pkg.mod:fn
description: a run
runtime:
  workers: 2
params:
  n: 5
"""


def write(root: Path, module: str, name: str, text: str | None = None, stem: str | None = None) -> Path:
    d = root / module / "runs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem or name}.yaml"
    p.write_text(text if text is not None else GOOD.format(name=name, module=module))
    return p


def test_good_spec_round_trips(tmp_path):
    s = load_spec(write(tmp_path, "swarm", "a-run"))
    assert (s.name, s.module, s.runtime.workers, s.params) == ("a-run", "swarm", 2, {"n": 5})
    assert s.runtime.optimize is True and s.runtime.backends.rust is True


def test_typo_key_rejected(tmp_path):
    p = write(tmp_path, "swarm", "a-run", GOOD.format(name="a-run", module="swarm").replace("workers", "worker"))
    with pytest.raises(ValueError, match="a-run.yaml") as e:
        load_spec(p)
    assert "worker" in str(e.value)


def test_malformed_yaml_names_file(tmp_path):
    p = write(tmp_path, "swarm", "a-run", "name: [unclosed\n")
    with pytest.raises(ValueError, match="a-run.yaml"):
        load_spec(p)


def test_name_stem_mismatch_fails(tmp_path):
    p = write(tmp_path, "swarm", "a-run", stem="other")
    with pytest.raises(ValueError, match="other.yaml.*a-run"):
        load_spec(p)


def test_duplicate_names_across_modules(tmp_path):
    a = write(tmp_path, "swarm", "same")
    b = write(tmp_path, "spine", "same")
    problems = validate_tree(tmp_path)
    assert len(problems) == 1 and "duplicate" in problems[0]
    assert str(a) in problems[0] and str(b) in problems[0]


def test_module_dir_mismatch(tmp_path):
    p = write(tmp_path, "swarm", "a-run", GOOD.format(name="a-run", module="spine"))
    (problem,) = validate_tree(tmp_path)
    assert str(p) in problem and "spine" in problem


def test_clean_tree_and_bad_spec_reported(tmp_path):
    write(tmp_path, "swarm", "ok")
    assert validate_tree(tmp_path) == []
    bad = write(tmp_path, "swarm", "bad", "nope: 1\n")
    (problem,) = validate_tree(tmp_path)
    assert str(bad) in problem


def test_discover_sorted_and_skips_junk(tmp_path):
    write(tmp_path, "swarm", "a")
    write(tmp_path, "spine", "b")
    write(tmp_path, ".venv", "junk", "not: valid\n")
    write(tmp_path, "node_modules", "junk2", "not: valid\n")
    assert [s.name for _, s in discover(tmp_path)] == ["b", "a"]


def test_clean_env_raises_naming_offender(monkeypatch):
    for k in BANNED_ENV:
        monkeypatch.delenv(k, raising=False)
    assert_clean_env()
    monkeypatch.setenv("SWARM_WORKERS", "2")
    with pytest.raises(RuntimeError, match="SWARM_WORKERS") as e:
        assert_clean_env()
    assert "run.yaml" in str(e.value) and "SWARM_NO_RUST" not in str(e.value)


def test_committed_reference_specs_load():
    names = {s.name for _, s in discover(ROOT)}
    assert {"branching-scale", "dwell-tax"} <= names
    assert validate_tree(ROOT) == []

"""Repo-wide red-hat: every module with a REFERENCES.md must carry a."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Module directories are those that (a) sit at repo root, (b) have a REFERENCES.md, and (c) have a src/ tree; the names below are skipped.
_SKIP = {"core", "frontend", "papers", "scripts", ".git", ".github", "docs"}


def _module_dirs() -> list[Path]:
    dirs: list[Path] = []
    for child in REPO_ROOT.iterdir():
        if not child.is_dir() or child.name in _SKIP:
            continue
        if not (child / "REFERENCES.md").exists():
            continue
        if not (child / "src").exists():
            continue
        dirs.append(child)
    return sorted(dirs)


def _pkg_name(module_dir: Path) -> str:
    # src/<pkg>/ - the single subdirectory of src that isn't egg-info.
    for entry in (module_dir / "src").iterdir():
        if entry.is_dir() and not entry.name.endswith(".egg-info"):
            return entry.name
    raise FileNotFoundError(f"no python package under {module_dir}/src")


@pytest.mark.parametrize("module_dir", _module_dirs(), ids=lambda p: p.name)
def test_module_has_a_distributions_file(module_dir: Path) -> None:
    pkg = _pkg_name(module_dir)
    dist_py = module_dir / "src" / pkg / "distributions.py"
    assert dist_py.exists(), (
        f"module {module_dir.name!r} has REFERENCES.md but no distributions.py; "
        f"add {dist_py.relative_to(REPO_ROOT)} to carry the sourced spreads "
        f"for the numbers in that REFERENCES.md (issue #35)"
    )


@pytest.mark.parametrize("module_dir", _module_dirs(), ids=lambda p: p.name)
def test_module_reaches_uq_only_through_vn_core_public_api(module_dir: Path) -> None:
    # A future regression: someone imports a private (underscore) symbol from a vn_core submodule instead of the public API.
    pkg = _pkg_name(module_dir)
    src = module_dir / "src" / pkg
    bad = re.compile(r"from\s+vn_core\.[a-z_]+\.[a-z_]+\s+import\s+_")
    for py in src.rglob("*.py"):
        text = py.read_text()
        assert not bad.search(text), (
            f"{py.relative_to(REPO_ROOT)} imports a private symbol from vn_core; "
            f"go through the package's public API (vn_core.uq)"
        )


@pytest.mark.parametrize("module_dir", _module_dirs(), ids=lambda p: p.name)
def test_distributions_file_is_not_a_stub(module_dir: Path) -> None:
    # Guard against the trivial case: an empty distributions.py that would satisfy the other checks vacuously.
    pkg = _pkg_name(module_dir)
    dist_py = module_dir / "src" / pkg / "distributions.py"
    text = dist_py.read_text()
    assert re.search(r"from\s+vn_core\.uq(\.[a-z_]+)?\s+import", text), (
        f"{dist_py.relative_to(REPO_ROOT)} does not import from vn_core.uq; "
        f"a stub distributions.py that carries no bands defeats the purpose "
        f"of the repo-wide UQ rollout (issue #35)."
    )

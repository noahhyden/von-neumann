"""Tests for depgraph.py - the monorepo dependency graph.

Two layers:
  - synthetic mini-repos (tmp_path) drive every branch of the graph logic with
    controlled inputs, so a mutation to that logic has somewhere to fail;
  - live-repo integration asserts the correctness contract (selftest) and the
    real edges, so the tool cannot silently diverge from the actual repo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import depgraph as dg

REPO = dg.repo_root()


# --------------------------------------------------------------------------- #
# synthetic mini-repo fixture
# --------------------------------------------------------------------------- #
def _mk_module(root: Path, mod: str, pkg: str, imports=()) -> Path:
    d = root / mod / "src" / pkg
    d.mkdir(parents=True)
    (d / "__init__.py").write_text("")
    body = "".join(
        (f"from {i} import x\n" if "." in i else f"import {i}\n") for i in imports
    )
    (d / "mod.py").write_text(body or "x = 1\n")
    return d


@pytest.fixture
def mini(tmp_path: Path) -> Path:
    """aa -> {bb, cc}; cc -> {bb}; bb, dd leaves. cc owns a result; aa emits a figure;
    paper p1 includes that figure. Plus edge cases: third-party import, self-import,
    a pruned .venv file, a src dir with a non-package child, a non-module top dir."""
    _mk_module(tmp_path, "aa", "aa", imports=["bb", "cc.sub", "third_party", "aa"])
    _mk_module(tmp_path, "bb", "bb")
    _mk_module(tmp_path, "cc", "cc", imports=["bb"])
    _mk_module(tmp_path, "dd", "dd")

    # cc owns a committed result
    res = tmp_path / "cc" / "experiments" / "results"
    res.mkdir(parents=True)
    (res / "out.json").write_text("{}")

    # aa emits a figure (one .pdf string, one non-pdf string, one non-str constant)
    exp = tmp_path / "aa" / "experiments"
    exp.mkdir(parents=True)
    (exp / "paper_figures.py").write_text('name = "fig_x.pdf"\nother = "not_a_pdf"\nn = 1\n')

    # a paper that includes aa's figure, plus the excluded "scripts" slug
    p1 = tmp_path / "papers" / "p1"
    p1.mkdir(parents=True)
    (p1 / "main.tex").write_text(r"\includegraphics[width=0.5\linewidth]{fig_x.pdf}")
    (tmp_path / "papers" / "scripts").mkdir()

    # a pruned dir: without the skip, aa would gain a spurious edge to dd and a
    # spurious figure fig_junk.pdf; _skip must prune both.
    venv = tmp_path / "aa" / ".venv"
    venv.mkdir()
    (venv / "junk.py").write_text("import dd\n")
    (venv / "paper_figures.py").write_text('x = "fig_junk.pdf"\n')

    # a top-level dir with src/ but a child that is NOT a package (no __init__)
    notpkg = tmp_path / "ee" / "src" / "ee"
    notpkg.mkdir(parents=True)  # no __init__.py -> not discovered

    # a non-module top-level dir with NO src/ (hits the "no src" continue)
    (tmp_path / "toolsdir").mkdir()

    # a non-module top-level dir named in _NON_MODULE
    (tmp_path / "docs").mkdir()

    # frontend TS ports: aa-model.ts matches module aa; reactive-model.ts does not.
    fsrc = tmp_path / "frontend" / "src"
    fsrc.mkdir(parents=True)
    (fsrc / "aa-model.ts").write_text("// port of aa\n")
    (fsrc / "reactive-model.ts").write_text("// generic base, not a module\n")

    return tmp_path


# --------------------------------------------------------------------------- #
# discover / imports
# --------------------------------------------------------------------------- #
def test_discover_modules(mini: Path):
    assert dg.discover_modules(mini) == {"aa": "aa", "bb": "bb", "cc": "cc", "dd": "dd"}


def test_import_edges(mini: Path):
    edges = dg.build_import_edges(mini, dg.discover_modules(mini))
    assert edges["aa"] == {"bb", "cc"}      # third_party dropped, self-edge dropped
    assert edges["cc"] == {"bb"}
    assert edges["bb"] == set()             # leaf
    assert "dd" not in edges["aa"]          # .venv import was pruned by _skip


def test_top_level_imports(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text("import a.b\nfrom c.d import e\nfrom . import f\nfrom .g import h\n")
    # a.b -> 'a'; c.d -> 'c'; relative imports (level>0) ignored
    assert dg._top_level_imports(good) == {"a", "c"}

    bad = tmp_path / "bad.py"
    bad.write_text("def (:\n")             # syntax error -> {}
    assert dg._top_level_imports(bad) == set()

    nonutf = tmp_path / "nonutf.py"
    nonutf.write_bytes(b"\xff\xfe import x")  # invalid utf-8 -> {}
    assert dg._top_level_imports(nonutf) == set()


def test_skip_outside_repo_uses_path_parts():
    # A path not under `repo` triggers the ValueError branch and falls back to its own parts.
    assert dg._skip(Path("/somewhere/node_modules/x.py"), Path("/other/repo")) is True
    assert dg._skip(Path("/somewhere/src/x.py"), Path("/other/repo")) is False


# --------------------------------------------------------------------------- #
# results / figures / papers
# --------------------------------------------------------------------------- #
def test_results(mini: Path):
    mods = sorted(set(dg.discover_modules(mini).values()))
    assert dg.build_results(mini, mods) == {"cc": ["cc/experiments/results/out.json"]}


def test_figures(mini: Path):
    mods = sorted(set(dg.discover_modules(mini).values()))
    assert dg.build_figures(mini, mods) == {"aa": {"fig_x.pdf"}}  # non-pdf/non-str excluded


def test_paper_edges(mini: Path):
    figs = dg.build_figures(mini, sorted(set(dg.discover_modules(mini).values())))
    assert dg.build_paper_edges(mini, figs) == {"p1": {"aa"}}     # 'scripts' slug excluded


def test_paper_edges_no_papers_dir(tmp_path: Path):
    assert dg.build_paper_edges(tmp_path, {}) == {}               # papers/ absent


def test_frontend_ports(mini: Path):
    mods = sorted(set(dg.discover_modules(mini).values()))
    # aa-model.ts maps to module aa; reactive-model.ts (no module) is ignored.
    assert dg.build_frontend_ports(mini, mods) == {"aa": "frontend/src/aa-model.ts"}


def test_frontend_ports_no_frontend_dir(tmp_path: Path):
    assert dg.build_frontend_ports(tmp_path, ["aa"]) == {}        # frontend/src absent


# --------------------------------------------------------------------------- #
# reachability / impact
# --------------------------------------------------------------------------- #
def test_reverse_reachable(mini: Path):
    edges = dg.build_import_edges(mini, dg.discover_modules(mini))
    assert dg.reverse_reachable(edges, {"bb"}) == {"aa", "bb", "cc"}  # bb's importers, transitively
    assert dg.reverse_reachable(edges, {"aa"}) == {"aa"}              # nothing imports aa


def test_graph_impact(mini: Path):
    g = dg.Graph(mini)
    imp = g.impact({"bb"})
    assert imp["test_impact"] == ["aa", "bb", "cc"]
    assert imp["stale_results"] == ["cc/experiments/results/out.json"]  # cc reached
    assert imp["stale_papers"] == ["p1"]                               # aa reached
    assert imp["stale_frontend"] == ["frontend/src/aa-model.ts"]       # aa's port reached
    # a change with no downstream results/papers/ports
    imp2 = g.impact({"dd"})
    assert imp2["stale_results"] == [] and imp2["stale_papers"] == []
    assert imp2["stale_frontend"] == []


# --------------------------------------------------------------------------- #
# resolve_changed
# --------------------------------------------------------------------------- #
def test_resolve_changed(mini: Path, capsys):
    mods = set(dg.discover_modules(mini).values())
    assert dg.resolve_changed(mini, ["aa"], mods) == {"aa"}            # module name
    assert dg.resolve_changed(mini, ["cc"], mods) == {"cc"}            # package name == module name here
    assert dg.resolve_changed(mini, ["aa/src/aa/mod.py"], mods) == {"aa"}  # path
    assert dg.resolve_changed(mini, ["  "], mods) == set()             # empty token skipped
    assert dg.resolve_changed(mini, ["nope"], mods) == set()           # unmatched
    assert "could not map 'nope'" in capsys.readouterr().err


def test_resolve_changed_package_name_distinct_from_dir(tmp_path: Path):
    # dir uses a hyphen, package uses underscore: token = package name must map to the dir.
    _mk_module(tmp_path, "my-mod", "my_mod")
    mods = set(dg.discover_modules(tmp_path).values())
    assert dg.resolve_changed(tmp_path, ["my_mod"], mods) == {"my-mod"}


# --------------------------------------------------------------------------- #
# selftest: pass on real repo, fail on a synthetic one
# --------------------------------------------------------------------------- #
def test_selftest_passes_on_real_repo(capsys):
    assert dg.selftest(REPO) == 0
    assert "selftest OK" in capsys.readouterr().out


def test_selftest_fails_on_mini(mini: Path, capsys):
    assert dg.selftest(mini) == 1
    assert "SELFTEST FAILED" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# live-repo edges (the tool must match reality, not just be internally consistent)
# --------------------------------------------------------------------------- #
def test_live_core_is_universal_substrate():
    g = dg.Graph(REPO)
    assert all("core" in g.edges[m] for m in g.modules if m != "core")
    assert dg.reverse_reachable(g.edges, {"core"}) == set(g.modules)


def test_live_paper_edges_match_ci_filter():
    g = dg.Graph(REPO)
    assert g.papers["coordination-tax"] == {"swarm"}
    assert g.papers["electronics-wall"] == {"closure-sim"}
    assert g.papers["spine"] == {"spine"}


def test_live_swarm_reaches_spine():
    g = dg.Graph(REPO)
    imp = g.impact({"swarm"})
    assert "spine" in imp["test_impact"]
    assert any("spine/experiments/results" in j for j in imp["stale_results"])


def test_live_frontend_ports():
    g = dg.Graph(REPO)
    assert g.frontend["swarm"] == "frontend/src/swarm-model.ts"
    assert "reactive" not in g.frontend            # generic base is not a module
    # a swarm change marks its TS port stale
    assert "frontend/src/swarm-model.ts" in g.impact({"swarm"})["stale_frontend"]


# --------------------------------------------------------------------------- #
# main() CLI dispatch (driven over the real repo)
# --------------------------------------------------------------------------- #
def test_main_default(capsys):
    assert dg.main([]) == 0
    assert "import DAG" in capsys.readouterr().out


def test_main_json(capsys):
    assert dg.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "imports" in payload and "papers" in payload


def test_main_dot(capsys):
    assert dg.main(["--dot"]) == 0
    assert capsys.readouterr().out.startswith("digraph deps {")


def test_main_selftest(capsys):
    assert dg.main(["--selftest"]) == 0
    assert "selftest OK" in capsys.readouterr().out


def test_main_changed_text(capsys):
    assert dg.main(["--changed", "swarm"]) == 0
    out = capsys.readouterr().out
    assert "test impact" in out and "spine" in out


def test_main_changed_json(capsys):
    assert dg.main(["--changed", "core", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["test_impact"]) == set(dg.Graph(REPO).modules)


def test_main_changed_list(capsys):
    # --list emits just the test-impact module names, one per line, sorted (for `make affected`).
    assert dg.main(["--changed", "swarm", "--list"]) == 0
    lines = capsys.readouterr().out.split()
    assert lines == ["spine", "swarm"]


def test_main_changed_none_stale(capsys):
    # comms owns no results and nothing imports it -> the "(none)" formatting branches.
    assert dg.main(["--changed", "comms"]) == 0
    out = capsys.readouterr().out
    assert "(none)" in out


def test_main_changed_invalid(capsys):
    assert dg.main(["--changed", "does_not_exist_xyz"]) == 1
    assert "no valid modules" in capsys.readouterr().err

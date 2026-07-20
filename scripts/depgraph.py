#!/usr/bin/env python3
"""Monorepo dependency graph: which modules, results, and papers a change reaches.

This is the repo-scale analog of swarm's frozen-JSON oracle. It answers two
questions that stop being answerable by memory once more than one module is
swarm-sized:

  1. TEST IMPACT   - if module X changes, whose tests can that break?
  2. ARTIFACT DRIFT - if module X changes, which committed results/*.json are now
                      stale, and which papers were built from them?

Both fall out of ONE relation: reverse-reachability over the import DAG. If A
imports B (directly or transitively) then a change to B affects A - so A's tests
must re-run and A's results/papers may have drifted.

=== SCOPE (what this covers) ===
  - imports  module -> module : AST-parsed absolute `import`/`from` of an
                                intra-repo package (src-layout: dir/src/<pkg>/).
  - results  module -> *.json : committed `results/*.json` a module owns.
  - figures  paper  -> module : a paper's \\includegraphics{X.pdf} matched to the
                                module whose paper_figures.py emits the string
                                "X.pdf". Derived from CONTENT, so it cannot drift
                                from the code the way a hand-kept list would.
  - frontend module -> port   : a module's TS re-implementation, by the convention
                                frontend/src/<module>-model.ts. A fold change makes
                                the parity-tested port stale (a forward edge).

=== NON-GOALS (deliberately out of scope; do not assume these are covered) ===
  - The frontend edge is CONVENTION-based (the -model.ts name), not import-based: it
    flags the port for re-verification against the parity fixtures, it does not parse
    the TS. A port that breaks the naming convention is invisible here.
  - Dynamic/`importlib`/conditional imports are not seen (AST of literal imports only).
  - Third-party and stdlib imports are ignored (only intra-repo packages are edges).
  - Runtime/data dependencies that are not Python imports (e.g. a module reading
    another's JSON at runtime) are not edges. Today none exist; revisit if they do.

=== CORRECTNESS CONTRACT (how we know it is right; asserted by --selftest and tests) ===
  - `core` (vn_core) is the shared substrate: imported by every other module.
  - `spine` threads the cross-scale set {closure-sim, multi-probe, swarm, core}.
  - A change to `swarm` reaches `spine` (the derived-dwell coupling).
  - A change to `core` reaches every module.
  - Result owners are exactly the modules with committed ensembles (swarm, spine).
  - paper->module edges equal the CI paths-filter: coordination-tax->swarm,
    electronics-wall->closure-sim, spine->spine.
  - swarm's frontend port is frontend/src/swarm-model.ts.

Pure stdlib, deterministic (everything sorted). Wall-clock only; it reads the tree,
it never runs a fold - so it can never change a number (CLAUDE.md 7).

Usage:
    python scripts/depgraph.py                     # print the whole graph + stats
    python scripts/depgraph.py --changed vn_core   # impact of a module change
    python scripts/depgraph.py --changed swarm/src/swarm/sim.py   # ...or a path
    python scripts/depgraph.py --changed core,closure-sim --json  # machine output
    python scripts/depgraph.py --dot | dot -Tsvg -o deps.svg      # visualize
    python scripts/depgraph.py --selftest          # assert the correctness contract
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Directories that are not Python modules (JS packages, docs, tooling, worktrees).
_NON_MODULE = {"frontend", "papers", "docs", "scripts", ".git", ".github", ".claude"}
# A path component under REPO named any of these prunes the file (venvs, caches, builds).
_SKIP_PARTS = {".venv", "node_modules", "__pycache__", "build", "target", ".claude", ".git"}

_INCLUDEGRAPHICS = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")


def repo_root() -> Path:
    """The monorepo root, inferred from this file's location (scripts/ is one level down)."""
    return Path(__file__).resolve().parent.parent


def _skip(path: Path, repo: Path) -> bool:
    """True if `path` sits under a pruned directory, judged RELATIVE to `repo`.

    The relative check matters: an absolute check trips on ancestor dirs (a worktree
    living under .claude/worktrees/ would skip the entire tree).
    """
    try:
        rel = path.relative_to(repo)
    except ValueError:
        rel = path
    return any(part in _SKIP_PARTS for part in rel.parts)


def discover_modules(repo: Path) -> dict[str, str]:
    """Return {package_name: module_dir}. A module is a top-level dir with src/<pkg>/__init__.py."""
    pkg_to_module: dict[str, str] = {}
    for d in sorted(repo.iterdir()):
        if not d.is_dir() or d.name in _NON_MODULE:
            continue
        src = d / "src"
        if not src.is_dir():
            continue
        for pkg in sorted(src.iterdir()):
            if (pkg / "__init__.py").is_file():
                pkg_to_module[pkg.name] = d.name
    return pkg_to_module


def _top_level_imports(pyfile: Path) -> set[str]:
    """Top-level package names imported by a .py file (best-effort; unparseable -> {})."""
    try:
        tree = ast.parse(pyfile.read_text(encoding="utf-8"), filename=str(pyfile))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:  # absolute import only
                out.add(node.module.split(".")[0])
    return out


def build_import_edges(repo: Path, pkg_to_module: dict[str, str]) -> dict[str, set[str]]:
    """{module: set of modules it depends on}, from every .py under each module dir."""
    edges: dict[str, set[str]] = {}
    for module in sorted(set(pkg_to_module.values())):
        deps: set[str] = set()
        for pyfile in sorted((repo / module).rglob("*.py")):
            if _skip(pyfile, repo):
                continue
            for pkg in _top_level_imports(pyfile):
                dep = pkg_to_module.get(pkg)
                if dep and dep != module:
                    deps.add(dep)
        edges[module] = deps
    return edges


def build_results(repo: Path, modules: list[str]) -> dict[str, list[str]]:
    """{module: [repo-relative result json paths]} for committed experiment outputs."""
    out: dict[str, list[str]] = {}
    for module in modules:
        jsons = sorted(
            str(p.relative_to(repo))
            for p in (repo / module).rglob("results/*.json")
            if not _skip(p, repo)
        )
        if jsons:
            out[module] = jsons
    return out


def build_figures(repo: Path, modules: list[str]) -> dict[str, set[str]]:
    """{module: set of figure basenames its paper_figures.py emits as .pdf string literals}."""
    out: dict[str, set[str]] = {}
    for module in modules:
        figs: set[str] = set()
        for gen in sorted((repo / module).rglob("paper_figures.py")):
            if _skip(gen, repo):
                continue
            for node in ast.walk(ast.parse(gen.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value.endswith(".pdf"):
                        figs.add(Path(node.value).name)
        if figs:
            out[module] = figs
    return out


def build_paper_edges(repo: Path, module_figures: dict[str, set[str]]) -> dict[str, set[str]]:
    """{paper_slug: set of source modules}, by matching \\includegraphics to figure emitters."""
    edges: dict[str, set[str]] = {}
    papers_dir = repo / "papers"
    if not papers_dir.is_dir():
        return edges
    for slug in sorted(papers_dir.iterdir()):
        if not slug.is_dir() or slug.name in {"scripts", "node_modules"}:
            continue
        wanted: set[str] = set()
        for tex in sorted(slug.rglob("*.tex")):
            for m in _INCLUDEGRAPHICS.finditer(tex.read_text(encoding="utf-8")):
                wanted.add(Path(m.group(1)).name)
        edges[slug.name] = {mod for mod, figs in module_figures.items() if wanted & figs}
    return edges


def build_frontend_ports(repo: Path, modules: list[str]) -> dict[str, str]:
    """{module: frontend TS model-port path}. Convention: frontend/src/<module>-model.ts.

    A convention-based edge, not an import edge: the TS port re-implements the module's
    fold and must stay bit-identical to it (the parity fixtures), so a fold change makes
    the port stale even though no Python import connects them. `reactive-model.ts` and
    any other `*-model.ts` not named after a module are ignored.
    """
    out: dict[str, str] = {}
    src = repo / "frontend" / "src"
    if not src.is_dir():
        return out
    modset = set(modules)
    suffix = "-model.ts"
    for f in sorted(src.glob("*" + suffix)):
        mod = f.name[: -len(suffix)]
        if mod in modset:
            out[mod] = str(f.relative_to(repo))
    return out


def expected_ci_filter(g: "Graph") -> dict[str, set[str]]:
    """{filter_key: source modules} the CI paths-filter should list, per depgraph.

    The dorny/paths-filter keys in ci.yml use the paper slug with hyphens replaced by
    underscores (`coordination-tax` -> `coordination_tax`), so we mirror that here.
    """
    return {slug.replace("-", "_"): set(srcs) for slug, srcs in g.papers.items() if srcs}


def parse_ci_filter(repo: Path, modules: set[str]) -> dict[str, set[str]]:
    """Parse the per-paper module globs from the dorny/paths-filter block in ci.yml.

    Returns {filter_key: set of module dirs it lists as '<mod>/**'}. Hand-parses the
    YAML literal block (stdlib only, no pyyaml): finds `filters: |`, then reads its
    more-indented body, treating `word:` lines as filter groups and `- '<glob>'` lines
    as patterns. The `shared` anchor group and non-module globs (papers/**, frontend/**,
    .github/**) are ignored - only globs whose first path component is a known module
    count. Returns {} if ci.yml is absent.
    """
    ci = repo / ".github" / "workflows" / "ci.yml"
    out: dict[str, set[str]] = {}
    if not ci.is_file():
        return out
    in_block = False
    base_indent = 0
    key: str | None = None
    for line in ci.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not in_block:
            if re.match(r"filters:\s*\|", stripped):
                in_block = True
                base_indent = len(line) - len(line.lstrip())
            continue
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent:  # dedent back out of the block scalar -> done
            break
        km = re.match(r"^(\w+):", stripped)
        if km:
            key = km.group(1)
            if key != "shared":
                out.setdefault(key, set())
            continue
        pm = re.match(r"^- '([^']+)'$", stripped)
        if pm and key and key != "shared":
            first = pm.group(1).split("/")[0]
            if first in modules:
                out[key].add(first)
    return out


def check_ci_filter(repo: Path) -> int:
    """Assert the committed ci.yml paths-filter matches depgraph's paper edges.

    Catches the drift that hand-maintaining the filter invites: a paper gaining a
    figure from a module nobody added to its filter (so CI would stop rebuilding it).
    """
    g = Graph(repo)
    want = expected_ci_filter(g)
    got = parse_ci_filter(repo, set(g.modules))
    failures = [
        f"filter '{key}': ci.yml lists {sorted(got.get(key, set()))}, depgraph expects {sorted(mods)}"
        for key, mods in sorted(want.items())
        if got.get(key) != mods
    ]
    if failures:
        print("CI FILTER DRIFT:")
        for f in failures:
            print(f"  - {f}")
        print("\nregenerate the paper groups with: python scripts/depgraph.py --ci-filter")
        return 1
    print(f"ci filter OK: {len(want)} paper filters match depgraph")
    return 0


def reverse_reachable(edges: dict[str, set[str]], changed: set[str]) -> set[str]:
    """All modules affected by a change to `changed`: the set plus every transitive importer."""
    importers: dict[str, set[str]] = defaultdict(set)
    for a, deps in edges.items():
        for b in deps:
            importers[b].add(a)
    affected = set(changed)
    stack = list(changed)
    while stack:
        node = stack.pop()
        for imp in sorted(importers.get(node, ())):
            if imp not in affected:
                affected.add(imp)
                stack.append(imp)
    return affected


def resolve_changed(repo: Path, tokens: list[str], modules: set[str]) -> set[str]:
    """Map CLI tokens (module names, package names, or file paths) to module dirs."""
    pkg_to_module = discover_modules(repo)
    out: set[str] = set()
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if tok in modules:
            out.add(tok)
        elif tok in pkg_to_module:
            out.add(pkg_to_module[tok])
        else:  # treat as a path; the first component that is a module wins
            hit = next((p for p in Path(tok).parts if p in modules), None)
            if hit:
                out.add(hit)
            else:
                print(f"warning: could not map '{tok}' to a module", file=sys.stderr)
    return out


class Graph:
    """The whole graph, built once from a repo root. Cheap; holds no simulation state."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.pkg_to_module = discover_modules(repo)
        self.modules = sorted(set(self.pkg_to_module.values()))
        self.edges = build_import_edges(repo, self.pkg_to_module)
        self.results = build_results(repo, self.modules)
        self.figures = build_figures(repo, self.modules)
        self.papers = build_paper_edges(repo, self.figures)
        self.frontend = build_frontend_ports(repo, self.modules)

    def impact(self, changed: set[str]) -> dict[str, list[str]]:
        affected = reverse_reachable(self.edges, changed)
        return {
            "changed": sorted(changed),
            "test_impact": sorted(affected),
            "stale_results": sorted(j for m in affected for j in self.results.get(m, [])),
            "stale_papers": sorted(s for s, srcs in self.papers.items() if srcs & affected),
            "stale_frontend": sorted(self.frontend[m] for m in affected if m in self.frontend),
        }


def selftest(repo: Path) -> int:
    """Assert the correctness contract against the repo (CLAUDE.md 2). Real edges, not "it ran"."""
    g = Graph(repo)
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    fanin = sum(1 for m in g.modules if "core" in g.edges[m])
    check(fanin == len(g.modules) - 1, f"core fan-in {fanin}, expected {len(g.modules) - 1} (all others)")
    check("core" not in g.edges.get("core", set()), "core must not import itself")
    spine_deps = g.edges.get("spine", set())
    check(spine_deps >= {"closure-sim", "multi-probe", "swarm", "core"},
          f"spine deps {sorted(spine_deps)} missing the cross-scale set")
    check("spine" in reverse_reachable(g.edges, {"swarm"}), "swarm change should reach spine")
    check(reverse_reachable(g.edges, {"core"}) == set(g.modules), "core change should reach all modules")
    check(set(g.results) == {"swarm", "spine"}, f"result owners {sorted(g.results)}, expected swarm+spine")
    expected = {"coordination-tax": {"swarm"}, "electronics-wall": {"closure-sim"}, "spine": {"spine"}}
    for slug, want in expected.items():
        check(g.papers.get(slug) == want, f"paper {slug} -> {sorted(g.papers.get(slug, set()))}, expected {sorted(want)}")
    check(g.frontend.get("swarm") == "frontend/src/swarm-model.ts",
          f"swarm frontend port -> {g.frontend.get('swarm')}, expected frontend/src/swarm-model.ts")

    if failures:
        print("SELFTEST FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"selftest OK: {len(g.modules)} modules, core fan-in {fanin}, "
          f"{sum(len(v) for v in g.results.values())} result json, {len(g.papers)} papers")
    return 0


def _fmt_impact(payload: dict[str, list[str]], changed: set[str]) -> str:
    lines = [f"changed:       {', '.join(payload['changed'])}",
             f"\ntest impact ({len(payload['test_impact'])} modules to re-test):"]
    for m in payload["test_impact"]:
        lines.append(f"  {'*' if m in changed else ' '} {m}")
    lines.append(f"\nstale results ({len(payload['stale_results'])} to regenerate):")
    lines += [f"    {j}" for j in payload["stale_results"]] or ["    (none)"]
    lines.append(f"\nstale papers ({len(payload['stale_papers'])} to rebuild):")
    lines += [f"    {s}" for s in payload["stale_papers"]] or ["    (none)"]
    lines.append(f"\nstale frontend ports ({len(payload['stale_frontend'])} to re-verify vs parity):")
    lines += [f"    {p}" for p in payload["stale_frontend"]] or ["    (none)"]
    return "\n".join(lines)


def _fmt_graph(g: Graph) -> str:
    lines = [f"modules ({len(g.modules)}):  {', '.join(g.modules)}\n",
             "import DAG (module -> depends on):"]
    for m in g.modules:
        deps = sorted(g.edges[m])
        lines.append(f"  {m:18s} -> {', '.join(deps) if deps else '(leaf)'}")
    fanin: dict[str, int] = defaultdict(int)
    for m in g.modules:
        for b in g.edges[m]:
            fanin[b] += 1
    lines.append("\nblast radius (direct importers, high = change carefully):")
    for m in sorted(g.modules, key=lambda x: (-fanin[x], x)):
        if fanin[m]:
            lines.append(f"  {m:18s} <- {fanin[m]} importer(s)")
    lines.append("\nresults owners:")
    for m, js in sorted(g.results.items()):
        lines.append(f"  {m:18s} : {len(js)} json")
    lines.append("\npaper -> source module(s):")
    for s, srcs in sorted(g.papers.items()):
        lines.append(f"  {s:18s} -> {', '.join(sorted(srcs)) if srcs else '(no matched figures)'}")
    lines.append("\nfrontend TS port -> source module:")
    for m, port in sorted(g.frontend.items()):
        lines.append(f"  {port:32s} <- {m}")
    return "\n".join(lines)


def _fmt_ci_filter(g: Graph) -> str:
    """The dorny/paths-filter paper groups, derived from depgraph - copy into ci.yml.

    Emits each paper group with its `*shared` ref, its own dir, and one `<mod>/**` per
    source module. The `shared: &shared` anchor definition is hand-kept in ci.yml.
    """
    lines: list[str] = []
    for key, mods in sorted(expected_ci_filter(g).items()):
        slug = key.replace("_", "-")
        lines.append(f"{key}:")
        lines.append("  - *shared")
        lines.append(f"  - 'papers/{slug}/**'")
        for m in sorted(mods):
            lines.append(f"  - '{m}/**'")
    return "\n".join(lines)


def _fmt_dot(g: Graph) -> str:
    lines = ["digraph deps {", '  rankdir=LR; node [shape=box, fontname="monospace"];']
    for a in g.modules:
        for b in sorted(g.edges[a]):
            lines.append(f'  "{a}" -> "{b}";')
    lines.append("}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="monorepo dependency graph", formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--changed", help="comma-separated module names / package names / file paths")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--list", action="store_true", help="with --changed: print only the test-impact module names, one per line (for `make affected`)")
    ap.add_argument("--dot", action="store_true", help="emit Graphviz DOT of the import DAG")
    ap.add_argument("--ci-filter", action="store_true", help="emit the dorny paths-filter paper groups (for ci.yml)")
    ap.add_argument("--check-ci-filter", action="store_true", help="assert ci.yml's paths-filter matches depgraph, exit nonzero on drift")
    ap.add_argument("--selftest", action="store_true", help="assert the correctness contract, exit nonzero on drift")
    args = ap.parse_args(argv)
    repo = repo_root()

    if args.selftest:
        return selftest(repo)
    if args.check_ci_filter:
        return check_ci_filter(repo)

    g = Graph(repo)

    if args.ci_filter:
        print(_fmt_ci_filter(g))
        return 0

    if args.dot:
        print(_fmt_dot(g))
        return 0

    if args.changed:
        changed = resolve_changed(repo, args.changed.split(","), set(g.modules))
        if not changed:
            print("no valid modules in --changed", file=sys.stderr)
            return 1
        payload = g.impact(changed)
        if args.list:
            print("\n".join(payload["test_impact"]))
        elif args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(_fmt_impact(payload, changed))
        return 0

    if args.json:
        print(json.dumps({
            "modules": g.modules,
            "imports": {m: sorted(g.edges[m]) for m in g.modules},
            "results": g.results,
            "papers": {s: sorted(v) for s, v in g.papers.items()},
            "frontend": g.frontend,
        }, indent=2))
        return 0

    print(_fmt_graph(g))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-07

The first public release.

### Added
- Eight physics modules, each a pure, seeded, deterministic fold with its own tests and
  `REFERENCES.md`: `closure-sim`, `probe-sim`, `power-budget`, `launch-economics`,
  `mission`, `multi-probe`, `swarm`, and `spine` (the cross-scale integrator).
- A pimas-only interactive frontend hosting one live surface per model, plus an
  overview, a stated-findings section, and a full bibliography with inline citations.
- Deep-linkable per-surface URLs, social-card metadata, a favicon, and a GitHub Pages
  deploy pipeline for <https://vn.noahhyden.com>.
- Light-speed-limited coordination in the swarm (FRONTIER #1).
- `FINDINGS.md`, a synthesis of the project's sourced results.
- Public-release licensing: PolyForm Strict 1.0.0 for code and data, CC BY-NC-ND 4.0
  for the written research, third-party notices for the bundled MIT-licensed pimas, and
  a `CITATION.cff`.

[Unreleased]: https://github.com/noahhyden/von-neumann/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/noahhyden/von-neumann/releases/tag/v0.1.0

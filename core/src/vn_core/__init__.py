"""Shared core primitives for the von-neumann monorepo.

Every module reaches for the same UQ, seeded RNG discipline, and (in the
future) fold utilities. They live here so no module re-implements them and
the invariants (deterministic, seeded, no wall clock) hold across the repo.
"""

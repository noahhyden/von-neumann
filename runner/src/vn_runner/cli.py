"""`vn-run` entry point. SLICE B owns the body; the subcommand surface is fixed."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """vn-run <spec.yaml> | vn-run ls | vn-run ps | vn-run validate"""
    raise NotImplementedError

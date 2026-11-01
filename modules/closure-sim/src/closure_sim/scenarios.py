"""Load a :class:`Factory` from a YAML or JSON scenario file."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .models import Factory


def load_factory(path: str | Path) -> Factory:
    """Load a factory scenario from a ``.yaml``/``.yml`` or ``.json`` file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"scenario not found: {p}")
    text = p.read_text()
    if p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    return Factory.model_validate(data)

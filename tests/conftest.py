"""Pytest configuration for loading Morganic as a package from repository root."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _ensure_morganic_package() -> None:
    if "morganic" in sys.modules:
        return

    spec = importlib.util.spec_from_file_location(
        "morganic",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load morganic package for tests")

    module = importlib.util.module_from_spec(spec)
    sys.modules["morganic"] = module
    spec.loader.exec_module(module)


_ensure_morganic_package()

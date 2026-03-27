"""Interpreter state containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MorganicState:
    """Runtime state for Morganic program execution."""

    env: dict[str, Any] = field(default_factory=dict)
    types: dict[str, str] = field(default_factory=dict)
    functions: dict[str, Any] = field(default_factory=dict)
    classes: dict[str, Any] = field(default_factory=dict)

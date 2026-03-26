from __future__ import annotations

from typing import Any, Dict

class MorganicState:
    def __init__(self) -> None:
        self.env: Dict[str, Any] = {}
        self.types: Dict[str, str] = {}
        self.functions: Dict[str, Any] = {}

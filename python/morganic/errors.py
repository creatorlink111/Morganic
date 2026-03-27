"""Error types for Morganic."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MorganicError(Exception):
    """Structured language/runtime error.

    Attributes:
        message: Human readable error message.
        line: Optional 1-indexed source line number.
        token: Optional offending token/value.
        hint: Optional suggestion to fix common mistakes.
    """

    message: str
    line: int | None = None
    token: str | None = None
    hint: str | None = None

    def __str__(self) -> str:
        """Render a concise but descriptive error string for CLI/REPL output."""
        parts: list[str] = [self.message]
        if self.line is not None:
            parts.append(f"line={self.line}")
        if self.token is not None:
            parts.append(f"token={self.token!r}")
        if self.hint is not None:
            parts.append(f"hint={self.hint}")
        return " | ".join(parts)

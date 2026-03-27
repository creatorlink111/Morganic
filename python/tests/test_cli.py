from __future__ import annotations

from morganic.cli import _needs_more_input


def test_trailing_colon_does_not_force_multiline_repl() -> None:
    assert _needs_more_input("[a]=^1^:") is False

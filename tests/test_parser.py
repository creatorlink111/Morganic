from __future__ import annotations

import pytest

from morganic.errors import MorganicError
from morganic.parser import execute_program
from morganic.state import MorganicState


def test_assignment_and_arithmetic() -> None:
    state = MorganicState()
    execute_program("[a]=^3^:[b]=^4^:[c]=|`a+`b|", state)
    assert state.env["c"] == 7
    assert state.types["c"] == "i"


def test_invalid_statement_has_line_number() -> None:
    state = MorganicState()
    with pytest.raises(MorganicError) as exc:
        execute_program("[a]=^1^:\n??bad", state)
    assert "line=2" in str(exc.value)


def test_invalid_numeric_literal_hint() -> None:
    state = MorganicState()
    with pytest.raises(MorganicError) as exc:
        execute_program("[x]=3", state)
    assert "^ ^" in str(exc.value)

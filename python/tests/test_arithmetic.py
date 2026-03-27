from __future__ import annotations

import pytest

from morganic.arithmetic import eval_arithmetic
from morganic.errors import MorganicError
from morganic.state import MorganicState


def test_eval_arithmetic_with_variables() -> None:
    state = MorganicState(env={"a": 3, "b": 4}, types={"a": "i", "b": "i"})
    assert eval_arithmetic("`a + `b * 2", state) == 11


def test_division_by_zero_has_hint() -> None:
    state = MorganicState()
    with pytest.raises(MorganicError) as exc:
        eval_arithmetic("1/0", state)
    assert "Division by zero" in str(exc.value)
    assert "hint=" in str(exc.value)

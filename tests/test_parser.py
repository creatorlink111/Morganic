from __future__ import annotations

from pathlib import Path

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


def test_typed_list_supports_non_boolean_elements() -> None:
    state = MorganicState()
    execute_program("[nums]=l(i4)<i4^1^,i4^2^>:[nums]~i4^3^", state)
    assert state.env["nums"] == [1, 2, 3]
    assert state.types["nums"] == "l(i4)"


def test_type_query_expression_returns_canonical_name() -> None:
    state = MorganicState()
    execute_program("[v]=b/:[t]=\"[v]", state)
    assert state.env["t"] == "Boolean"
    assert state.types["t"] == "£"


def test_print_list_index_expression(capsys: pytest.CaptureFixture[str]) -> None:
    state = MorganicState()
    execute_program("[items]=l(i)<i^10^,i^20^,i^30^>:1([items]@2)", state)
    out = capsys.readouterr().out.strip()
    assert out == "30"


def test_file_write_statement_writes_content(tmp_path: Path) -> None:
    state = MorganicState()
    out_file = tmp_path / "result.txt"
    execute_program(f"[!{out_file}!/w](£hello world)", state)
    assert out_file.read_text(encoding="utf-8") == "hello world"

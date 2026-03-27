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


def test_class_definition_supports_fields_and_methods() -> None:
    state = MorganicState()
    execute_program("*Point{[x]=^1^:[y]=^2^:#sum'a.i'#{1(&a)}}", state)
    assert "Point" in state.classes
    assert state.classes["Point"]["fields"]["x"] == (1, "i")
    assert state.classes["Point"]["methods"]["sum"]["params"] == [("a", "i")]


def test_constructor_expression_creates_typed_instance_with_overrides() -> None:
    state = MorganicState()
    execute_program("*Point{[x]=^1^:[y]=^2^}:[p]=*Point{x=^5^}", state)
    assert state.types["p"] == ".Point."
    assert state.env["p"]["__class__"] == "Point"
    assert state.env["p"]["x"] == 5
    assert state.env["p"]["y"] == 2


def test_constructor_period_syntax_with_colon_fields() -> None:
    state = MorganicState()
    execute_program("*doctor{[name]=£none:[age]=i16^0^}:[mrgreen]=.doctor.name:£morgan,age:i16^32^", state)
    assert state.types["mrgreen"] == ".doctor."
    assert state.env["mrgreen"]["name"] == "morgan"
    assert state.env["mrgreen"]["age"] == 32


def test_console_graph_statement_renders_points_and_axes(capsys: pytest.CaptureFixture[str]) -> None:
    state = MorganicState()
    execute_program("0(-2&2,-1&1){(-2,-1)(0,0)(2,1)}", state)
    out = capsys.readouterr().out.strip()
    lines = out.splitlines()
    assert len(lines) == 3
    assert any("│" in line or "─" in line for line in lines)
    assert out.count("●") == 3


def test_console_graph_rejects_points_outside_range() -> None:
    state = MorganicState()
    with pytest.raises(MorganicError) as exc:
        execute_program("0(-1&1,-1&1){(2,0)}", state)
    assert "outside graph range" in str(exc.value)

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


def test_append_and_index_can_be_nested_inside_value_expression() -> None:
    state = MorganicState()
    execute_program("[mylist]=l(i)<^1^,^2^,^3^>:[mylist]~[mylist]@^2^", state)
    assert state.env["mylist"] == [1, 2, 3, 3]


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
    assert "·" not in out
    assert "x" in out
    assert "y" in out


def test_console_graph_uses_uniform_unit_scale_on_axes() -> None:
    from morganic.parser import render_console_graph

    graph = render_console_graph(-1, 1, -1, 1, [(0, 0), (1, 0), (0, 1)])
    lines = graph.splitlines()
    origin_row = lines[1]
    assert origin_row.count("─") >= 2


def test_console_graph_rejects_points_outside_range() -> None:
    state = MorganicState()
    with pytest.raises(MorganicError) as exc:
        execute_program("0(-1&1,-1&1){(2,0)}", state)
    assert "outside graph range" in str(exc.value)


def test_console_graph_label_modes_show_numeric_axis_labels(capsys: pytest.CaptureFixture[str]) -> None:
    state = MorganicState()
    execute_program("0.1(-2&2,-2&2){(-2,-2)(0,0)(2,2)}", state)
    out = capsys.readouterr().out.strip()
    assert "-2" in out
    assert "2" in out
    assert "0" in out


def test_matrix_coord_literal_parses_into_points() -> None:
    state = MorganicState()
    execute_program("[mycoords]=m<0,1,2><0,1,2>", state)
    assert state.types["mycoords"] == "m"
    assert state.env["mycoords"] == [(0, 0), (1, 1), (2, 2)]


def test_console_graph_allows_matrix_payload_expression(capsys: pytest.CaptureFixture[str]) -> None:
    state = MorganicState()
    execute_program("[pairs]=m<0,1,2><0,1,2>:0(-2&2,-2&2){[pairs]}", state)
    out = capsys.readouterr().out
    assert out.count("●") == 3


def test_console_graph_allows_coord_list_payload_expression(capsys: pytest.CaptureFixture[str]) -> None:
    state = MorganicState()
    execute_program("[pairs]=l(c)<(0,0),(1,1),(2,2)>:0(-2&2,-2&2){[pairs]}", state)
    out = capsys.readouterr().out
    assert out.count("●") == 3


def test_console_graph_uses_default_range_when_omitted(capsys: pytest.CaptureFixture[str]) -> None:
    state = MorganicState()
    execute_program("0.1{(0,0)(1,1)}", state)
    out = capsys.readouterr().out
    assert "-10" in out
    assert "10" in out


def test_coord_list_literal_and_conversion_to_matrix() -> None:
    state = MorganicState()
    execute_program("[data]=l(c)<(0,0),(1,1),(2,2)>:[data]£m", state)
    assert state.types["data"] == "m"
    assert state.env["data"] == [(0, 0), (1, 1), (2, 2)]


def test_enum_declaration_and_assignment_with_quote_syntax() -> None:
    state = MorganicState()
    execute_program('"direction"=north¬south¬east¬west:[mydir]="direction"north', state)
    assert state.env["mydir"] == "north"
    assert state.types["mydir"] == '"direction"'


def test_enum_assignment_rejects_unknown_member() -> None:
    state = MorganicState()
    with pytest.raises(MorganicError) as exc:
        execute_program('"direction"=north¬south:[mydir]="direction"west', state)
    assert "Unknown enum member" in str(exc.value)

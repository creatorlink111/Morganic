from __future__ import annotations

from morganic.splitter import split_statement_chunks, strip_comments


def test_splitter_tracks_line_numbers() -> None:
    chunks = split_statement_chunks("[a]=^1^:\n[b]=^2^")
    assert len(chunks) == 2
    assert chunks[0].line == 1
    assert chunks[1].line == 2


def test_splitter_keeps_constructor_field_colons_inside_statement() -> None:
    chunks = split_statement_chunks("[mrgreen]=.doctor.name:£morgan,age:i16^32^:[x]=^1^")
    assert len(chunks) == 2
    assert chunks[0].text == "[mrgreen]=.doctor.name:£morgan,age:i16^32^"


def test_splitter_keeps_modulo_inside_arithmetic() -> None:
    src = "[a]=^7^:[b]=^3^:[m]=|`a%`b|"
    assert strip_comments(src) == src

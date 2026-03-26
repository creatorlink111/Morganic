from __future__ import annotations

from morganic.splitter import split_statement_chunks


def test_splitter_tracks_line_numbers() -> None:
    chunks = split_statement_chunks("[a]=^1^:\n[b]=^2^")
    assert len(chunks) == 2
    assert chunks[0].line == 1
    assert chunks[1].line == 2

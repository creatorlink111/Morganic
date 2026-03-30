"""Source pre-processing and statement splitting utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class StatementChunk:
    """A top-level statement and the line where it begins."""

    text: str
    line: int


def _starts_special_string(source: str, index: int) -> bool:
    return source.startswith('\u00A3\u00A3', index)


def strip_comments(source: str) -> str:
    """Remove single-line (`%`) and block (`%%...%`) comments from source text."""
    out: list[str] = []
    i = 0
    n = len(source)
    in_arithmetic = False
    in_sstring = False
    while i < n:
        if _starts_special_string(source, i):
            out.append(source[i:i + 2])
            in_sstring = not in_sstring
            i += 2
            continue

        ch = source[i]

        if not in_sstring and ch == '|':
            in_arithmetic = not in_arithmetic
            out.append(ch)
            i += 1
            continue

        if ch == '%' and not in_arithmetic and not in_sstring:
            nxt = source[i + 1] if i + 1 < n else ''
            if nxt == '%':
                i += 2
                while i < n and source[i] != '%':
                    i += 1
                if i < n and source[i] == '%':
                    i += 1
                continue

            i += 1
            while i < n and source[i] != '\n':
                i += 1
            continue

        out.append(ch)
        i += 1
    return ''.join(out)


def strip_repl_prompts(source: str) -> str:
    """Remove pasted REPL prompts (`>>>` / `...`) at line starts."""
    cleaned_lines: list[str] = []
    for line in source.splitlines():
        working = line
        while True:
            trimmed = working.lstrip()
            if trimmed.startswith('>>>'):
                trimmed = trimmed[3:]
                if trimmed.startswith(' '):
                    trimmed = trimmed[1:]
                working = trimmed
                continue
            if trimmed.startswith('...'):
                trimmed = trimmed[3:]
                if trimmed.startswith(' '):
                    trimmed = trimmed[1:]
                working = trimmed
                continue
            break
        cleaned_lines.append(working)
    return '\n'.join(cleaned_lines)


def split_statement_chunks(source: str) -> list[StatementChunk]:
    """Split source into top-level statements by `:` while tracking start lines."""
    source = strip_repl_prompts(source)
    source = strip_comments(source)
    out: list[StatementChunk] = []
    buf: list[str] = []
    depth = {'(': 0, '[': 0, '{': 0, '<': 0}
    pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}
    in_sstring = False

    line = 1
    current_stmt_line = 1

    i = 0
    while i < len(source):
        if _starts_special_string(source, i):
            if not buf:
                current_stmt_line = line
            buf.append(source[i:i + 2])
            in_sstring = not in_sstring
            i += 2
            continue

        ch = source[i]
        if ch == '\n':
            line += 1

        if in_sstring:
            if not buf:
                current_stmt_line = line
            buf.append(ch)
            i += 1
            continue

        if ch in '([{<':
            depth[ch] += 1
            if not buf:
                current_stmt_line = line
            buf.append(ch)
        elif ch in ')]}>':
            if not buf:
                current_stmt_line = line
            for k, v in pairs.items():
                if v == ch:
                    depth[k] = max(0, depth[k] - 1)
                    break
            buf.append(ch)
        elif ch == ':' and all(d == 0 for d in depth.values()):
            current = ''.join(buf)
            ctor_match = re.search(r"\[[A-Za-z_][A-Za-z0-9_]*\]\s*=\s*\.[A-Za-z_][A-Za-z0-9_]*\.(.*)$", current)
            if ctor_match:
                tail = ctor_match.group(1).split(',')[-1].strip()
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tail):
                    buf.append(ch)
                    i += 1
                    continue
            part = ''.join(buf).strip()
            if part:
                out.append(StatementChunk(part, current_stmt_line))
            buf = []
            current_stmt_line = line
        else:
            if not buf:
                current_stmt_line = line
            buf.append(ch)
        i += 1

    tail = ''.join(buf).strip()
    if tail:
        out.append(StatementChunk(tail, current_stmt_line))
    return out


def split_statements(source: str) -> list[str]:
    """Compatibility helper that returns statement text only."""
    return [chunk.text for chunk in split_statement_chunks(source)]

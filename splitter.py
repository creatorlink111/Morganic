from __future__ import annotations

from typing import List

def strip_comments(source: str) -> str:
    out: List[str] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]

        if ch == '%':
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

def split_statements(source: str) -> List[str]:
    """
    Split source into top-level statements by ':'.
    Ignores ':' inside (), [], {}, <>.
    Supports nested { } for if-blocks.
    """
    source = strip_comments(source)
    out: List[str] = []
    buf: List[str] = []
    depth = {'(': 0, '[': 0, '{': 0, '<': 0}
    pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}

    for ch in source:
        if ch in '([{<':
            depth[ch] += 1
            buf.append(ch)
        elif ch in ')]}>':
            for k, v in pairs.items():
                if v == ch:
                    depth[k] = max(0, depth[k] - 1)
                    break
            buf.append(ch)
        elif ch == ':' and all(d == 0 for d in depth.values()):
            part = ''.join(buf).strip()
            if part:
                out.append(part)
            buf = []
        else:
            buf.append(ch)
    tail = ''.join(buf).strip()
    if tail:
        out.append(tail)
    return out

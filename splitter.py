from __future__ import annotations

from typing import List

def split_statements(source: str) -> List[str]:
    """
    Split source into top-level statements by ':'.
    Ignores ':' inside (), [], {}, <>.
    Supports nested { } for if-blocks.
    """
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

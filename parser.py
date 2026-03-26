from __future__ import annotations

import re
from typing import Any, List

from .arithmetic import eval_arithmetic
from .errors import MorganicError
from .splitter import split_statements
from .state import MorganicState

def get_var(state: MorganicState, name: str) -> Any:
    if name not in state.env:
        raise MorganicError(f"Undefined: {name}")
    return state.env[name]

def store_value(state: MorganicState, name: str, value: Any, type_code: str | None = None) -> None:
    state.env[name] = value
    if type_code:
        state.types[name] = type_code
    else:
        state.types[name] = type(value).__name__[0].lower()

def execute_statement(stmt: str, state: MorganicState) -> None:
    stmt = stmt.strip()
    if not stmt:
        return

    # Function definition
    m = re.fullmatch(r"#(\w+)((?:'\w+\.[bifsl£]+')*)#\{(.*)\}", stmt, re.DOTALL)
    if m:
        name = m.group(1)
        params_str = m.group(2)
        body = m.group(3)
        params = re.findall(r"'(\w+)\.([bifsl£]+)'", params_str)
        state.functions[name] = {'params': params, 'body': body.strip()}
        return

    # Function call #print_num ^4^ or #grey /
    # Inline spaces are only supported for function-call arguments.
    if stmt.startswith('#'):
        m = re.fullmatch(r"#(\w+)(?:\s+(.+))?", stmt)
        if m:
            name, args_part = m.groups()
            args = re.split(r'\s+', args_part.strip()) if args_part else []
            func = state.functions.get(name)
            if func:
                ps = func['params']
                if len(args) == len(ps):
                    saved = {}
                    for i, (pn, pt) in enumerate(ps):
                        arg = args[i].strip()
                        if arg.startswith('^') and arg.endswith('^'):
                            lit = arg[1:-1]
                            v = int(lit) if pt == 'i' else float(lit) if pt == 'f' else lit
                        elif pt == 'b':
                            v = arg == '/'
                        else:
                            v = arg
                        k = '&' + pn
                        saved[k] = state.env.get(k)
                        state.env[k] = v
                    execute_program(func['body'], state)
                    for k in saved:
                        state.env[k] = saved[k] if saved[k] is not None else state.env.pop(k, None)
                    return

    # [a]=i^42^
    m = re.fullmatch(r"\[(\w+)\]=i\^([0-9]+)\^", stmt)
    if m:
        store_value(state, m.group(1), int(m.group(2)), 'i')
        return

    # [b]=b/
    m = re.fullmatch(r"\[(\w+)\]=b([/\\])", stmt)
    if m:
        store_value(state, m.group(1), m.group(2) == '/', 'b')
        return

    # 1([a]) or 1({expr})
    m = re.fullmatch(r"1\(\[(\w+)\]\)", stmt)
    if m:
        print(get_var(state, m.group(1)))
        return

    m = re.fullmatch(r"1\(\{(.+)\}\)", stmt)
    if m:
        print(eval_arithmetic(m.group(1), state))
        return

    m = re.fullmatch(r"1\(&(\w+)\)", stmt)
    if m:
        print(state.env.get('&' + m.group(1), 'undef'))
        return

    raise MorganicError(f"Unrecognized: {stmt}")

def execute_program(program: str, state: MorganicState) -> None:
    for stmt in split_statements(program):
        execute_statement(stmt, state)


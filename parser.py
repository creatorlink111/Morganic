from __future__ import annotations

import re
from typing import Any

from .arithmetic import eval_arithmetic
from .errors import MorganicError
from .splitter import split_statements
from .state import MorganicState

TYPE_ALIASES = {
    'b': 'b',
    'bool': 'b',
    'boolean': 'b',
    'i': 'i',
    'int': 'i',
    'integer': 'i',
    'f': 'f',
    'float': 'f',
    's': '£',
    'str': '£',
    'string': '£',
    'l': 'l',
    'list': 'l',
    '£': '£',
}


def is_numeric_literal(expr: str) -> bool:
    return bool(re.fullmatch(r"[+-]?(?:\d+\.\d+|\d+)", expr))


def get_var(state: MorganicState, name: str) -> Any:
    if name not in state.env:
        raise MorganicError(f"Undefined: {name}")
    return state.env[name]


def infer_type_code(value: Any) -> str:
    if isinstance(value, bool):
        return 'b'
    if isinstance(value, int):
        return 'i'
    if isinstance(value, float):
        return 'f'
    if isinstance(value, str):
        return '£'
    if isinstance(value, list):
        return 'l(?)'
    return type(value).__name__[0].lower()


def store_value(state: MorganicState, name: str, value: Any, type_code: str | None = None) -> None:
    resolved_type = type_code or infer_type_code(value)
    existing_type = state.types.get(name)
    if existing_type is not None and existing_type != resolved_type:
        raise MorganicError(
            f"Type safety violation: variable '{name}' is {existing_type}, cannot assign {resolved_type}."
        )
    state.env[name] = value
    state.types[name] = resolved_type


def parse_bool_token(token: str) -> bool:
    if token == '/':
        return True
    if token == '\\':
        return False
    raise MorganicError(f"Expected boolean token '/' or '\\', got: {token}")


def parse_value_expr(expr: str, state: MorganicState) -> tuple[Any, str | None]:
    expr = expr.strip()

    m = re.fullmatch(r"\^(.+)\^", expr, re.DOTALL)
    if m:
        literal = m.group(1)
        if re.fullmatch(r"[+-]?\d+", literal):
            return int(literal), 'i'
        if re.fullmatch(r"[+-]?(?:\d+\.\d+|\d+)", literal):
            return float(literal), 'f'
        return literal, '£'

    m = re.fullmatch(r"\[(\w+)\]", expr)
    if m:
        name = m.group(1)
        return get_var(state, name), state.types.get(name)

    m = re.fullmatch(r"\|(.+)\|", expr, re.DOTALL)
    if m:
        value = eval_arithmetic(m.group(1).strip(), state)
        return value, infer_type_code(value)

    m = re.fullmatch(r"`([A-Za-z_][A-Za-z0-9_]*)", expr)
    if m:
        name = m.group(1)
        return get_var(state, name), state.types.get(name)

    m = re.fullmatch(r"l\(b\)<(.*)>", expr)
    if m:
        inside = m.group(1).strip()
        if not inside:
            return [], 'l(b)'
        raw_tokens = [tok.strip() for tok in inside.split(',')]
        values = [parse_bool_token(tok) for tok in raw_tokens]
        return values, 'l(b)'

    if expr in {'/', '\\'}:
        return parse_bool_token(expr), 'b'

    if expr.startswith('£'):
        return expr[1:], '£'

    if is_numeric_literal(expr):
        raise MorganicError(
            "Numeric literals must be wrapped with ^ ^ (example: ^3^)."
        )

    raise MorganicError(f"Unrecognized value expression: {expr}")


def eval_condition(condition_expr: str, state: MorganicState) -> bool:
    if '..' not in condition_expr:
        raise MorganicError("Condition must use equality operator '..'.")
    left_raw, right_raw = condition_expr.split('..', 1)
    left, _ = parse_value_expr(left_raw, state)
    right, _ = parse_value_expr(right_raw, state)
    return left == right


def convert_value(value: Any, src_type: str, target_type: str) -> tuple[Any, str]:
    if target_type == src_type:
        return value, src_type

    if target_type == 'i':
        if src_type == 'f':
            if int(value) != value:
                raise MorganicError("Cannot convert non-whole float to integer.")
            return int(value), 'i'
        if src_type == '£' and re.fullmatch(r"[+-]?\d+", value):
            return int(value), 'i'
        raise MorganicError(f"Incompatible conversion: {src_type} -> i")

    if target_type == 'f':
        if src_type == 'i':
            return float(value), 'f'
        if src_type == '£' and re.fullmatch(r"[+-]?(?:\d+\.\d+|\d+)", value):
            return float(value), 'f'
        raise MorganicError(f"Incompatible conversion: {src_type} -> f")

    if target_type == 'b':
        if src_type == '£' and value in {'/', '\\'}:
            return (value == '/'), 'b'
        raise MorganicError(f"Incompatible conversion: {src_type} -> b")

    if target_type == '£':
        if src_type in {'i', 'f', 'b', '£'}:
            if src_type == 'b':
                return ('/' if value else '\\'), '£'
            return str(value), '£'
        raise MorganicError(f"Incompatible conversion: {src_type} -> £")

    raise MorganicError(f"Unsupported target conversion type: {target_type}")


def parse_loop_range_operand(expr: str, state: MorganicState) -> int:
    value, _ = parse_value_expr(expr, state)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MorganicError("For loop range bounds must be integers.")
    return value


def execute_statement(stmt: str, state: MorganicState) -> None:
    stmt = stmt.strip()
    if not stmt:
        return

    m = re.fullmatch(r"#(\w+)((?:'[\w£]+\.[\w£]+')*)#\{(.*)\}", stmt, re.DOTALL)
    if m:
        name = m.group(1)
        params_str = m.group(2)
        body = m.group(3)
        raw_params = re.findall(r"'([\w£]+)\.([\w£]+)'", params_str)
        params = []
        for left, right in raw_params:
            left_type = TYPE_ALIASES.get(left.lower(), left if left == '£' else None)
            right_type = TYPE_ALIASES.get(right.lower(), right if right == '£' else None)

            if left_type and right_type and len(left) > 1 and len(right) == 1:
                params.append((right, left_type))
                continue
            if right_type:
                params.append((left, right_type))
                continue
            if left_type:
                params.append((right, left_type))
                continue

            raise MorganicError(f"Bad parameter declaration: '{left}.{right}'")
        state.functions[name] = {'params': params, 'body': body.strip()}
        return

    if stmt.startswith('#'):
        m = re.fullmatch(r"#(\w+)(?:\s+(.+))?", stmt)
        if m:
            name, args_part = m.groups()
            args = re.split(r'\s+', args_part.strip()) if args_part else []
            func = state.functions.get(name)
            if func:
                ps = func['params']
                if len(args) == len(ps):
                    sentinel = object()
                    saved_env = {}
                    saved_types = {}
                    for i, (pn, pt) in enumerate(ps):
                        arg = args[i].strip()
                        value, actual_type = parse_value_expr(arg, state)
                        if actual_type is None:
                            actual_type = infer_type_code(value)
                        if pt in {'i', 'f'} and not re.fullmatch(r"\^.+\^", arg, re.DOTALL):
                            raise MorganicError(
                                f"Numeric argument for '{pn}' must use ^ ^ (example: ^3^)."
                            )
                        if actual_type != pt:
                            raise MorganicError(
                                f"Type mismatch for '{pn}': expected {pt}, got {actual_type}."
                            )
                        v = value
                        k = '&' + pn
                        saved_env[k] = state.env.get(k, sentinel)
                        saved_types[k] = state.types.get(k, sentinel)
                        state.env[k] = v
                        state.types[k] = pt
                    execute_program(func['body'], state)
                    for k in saved_env:
                        if saved_env[k] is sentinel:
                            state.env.pop(k, None)
                        else:
                            state.env[k] = saved_env[k]
                        if saved_types[k] is sentinel:
                            state.types.pop(k, None)
                        else:
                            state.types[k] = saved_types[k]
                    return

    m = re.fullmatch(r"2\((.+)\)\{(.*)\}", stmt, re.DOTALL)
    if m:
        cond = m.group(1).strip()
        body = m.group(2)
        if eval_condition(cond, state):
            execute_program(body, state)
        return

    m = re.fullmatch(r"3\((.+)\)\{(.*)\}", stmt, re.DOTALL)
    if m:
        cond = m.group(1).strip()
        body = m.group(2)
        loop_guard = 0
        while eval_condition(cond, state):
            execute_program(body, state)
            loop_guard += 1
            if loop_guard > 100000:
                raise MorganicError("While loop guard triggered (possible infinite loop).")
        return

    m = re.fullmatch(r"4\((.+?),(.+?)\)\{(.*)\}", stmt, re.DOTALL)
    if m:
        first = m.group(1).strip()
        second = m.group(2).strip()
        body = m.group(3)

        iterable_ref = re.fullmatch(r"_\[(\w+)\]", second)
        if iterable_ref:
            var_name = first
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var_name):
                raise MorganicError("Invalid loop variable name.")
            seq_name = iterable_ref.group(1)
            seq = get_var(state, seq_name)
            if not isinstance(seq, list):
                raise MorganicError("List iteration requires a list variable.")

            key = '&' + var_name
            had_old = key in state.env
            old_value = state.env.get(key)
            old_type = state.types.get(key)
            for item in seq:
                store_value(state, key, item)
                execute_program(body, state)
            if had_old:
                state.env[key] = old_value
                if old_type is not None:
                    state.types[key] = old_type
            else:
                state.env.pop(key, None)
                state.types.pop(key, None)
            return

        str_ref = re.fullmatch(r"\[(\w+)\]", second)
        if str_ref and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", first):
            var_name = first
            value = get_var(state, str_ref.group(1))
            if not isinstance(value, str):
                raise MorganicError("Character iteration requires a string variable.")

            key = '&' + var_name
            had_old = key in state.env
            old_value = state.env.get(key)
            old_type = state.types.get(key)
            for ch in value:
                store_value(state, key, ch, '£')
                execute_program(body, state)
            if had_old:
                state.env[key] = old_value
                if old_type is not None:
                    state.types[key] = old_type
            else:
                state.env.pop(key, None)
                state.types.pop(key, None)
            return

        start = parse_loop_range_operand(first, state)
        end = parse_loop_range_operand(second, state)
        for _ in range(start, end):
            execute_program(body, state)
        return

    m = re.fullmatch(r"\[(\w+)\]=;\((.*)\)", stmt, re.DOTALL)
    if m:
        name = m.group(1)
        prompt = m.group(2)
        if prompt.startswith('£'):
            prompt = prompt[1:]
        value = input(prompt)
        store_value(state, name, value, '£')
        return

    m = re.fullmatch(r"\[(\w+)\]\$([A-Za-z£]+)", stmt)
    if m:
        name = m.group(1)
        raw_target = m.group(2).lower()
        target_type = TYPE_ALIASES.get(raw_target, m.group(2))
        if target_type not in {'i', 'f', 'b', '£'}:
            raise MorganicError(f"Unsupported conversion target: {m.group(2)}")
        value = get_var(state, name)
        src_type = state.types.get(name, infer_type_code(value))
        new_value, new_type = convert_value(value, src_type, target_type)
        store_value(state, name, new_value, new_type)
        return

    m = re.fullmatch(r"\[(\w+)\]~([/\\])", stmt)
    if m:
        name = m.group(1)
        token = m.group(2)
        if name not in state.env:
            raise MorganicError(f"Undefined: {name}")
        list_type = state.types.get(name)
        if list_type != 'l(b)':
            raise MorganicError("Type safety violation: append type does not match list type.")
        state.env[name].append(parse_bool_token(token))
        return

    m = re.fullmatch(r"\[(\w+)\]=(.*)", stmt, re.DOTALL)
    if m:
        name = m.group(1)
        expr = m.group(2)
        value, type_code = parse_value_expr(expr, state)
        store_value(state, name, value, type_code)
        return

    m = re.fullmatch(r"1\(\[(\w+)\]\)", stmt)
    if m:
        print(get_var(state, m.group(1)))
        return

    m = re.fullmatch(r"1\(\|(.+)\|\)", stmt, re.DOTALL)
    if m:
        print(eval_arithmetic(m.group(1), state))
        return

    m = re.fullmatch(r"1\(\{(.+)\}\)", stmt, re.DOTALL)
    if m:
        print(eval_arithmetic(m.group(1), state))
        return

    m = re.fullmatch(r"1\(\^(.+)\^\)", stmt)
    if m:
        literal = m.group(1)
        if re.fullmatch(r"[+-]?[0-9]+", literal):
            print(int(literal))
        elif re.fullmatch(r"[+-]?(?:[0-9]+\.[0-9]+|[0-9]+)", literal):
            print(float(literal))
        else:
            print(literal)
        return

    m = re.fullmatch(r"1\(&(\w+)\)", stmt)
    if m:
        print(state.env.get('&' + m.group(1), 'undef'))
        return

    m = re.fullmatch(r"1\((£.*)\)", stmt, re.DOTALL)
    if m:
        print(m.group(1)[1:])
        return

    raise MorganicError(f"Unrecognized: {stmt}")


def execute_program(program: str, state: MorganicState) -> None:
    for stmt in split_statements(program):
        execute_statement(stmt, state)

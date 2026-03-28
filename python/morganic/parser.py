from __future__ import annotations

import re
from typing import Any

from .arithmetic import eval_arithmetic
from .errors import MorganicError
from .splitter import split_statement_chunks, split_statements
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
    'm': 'm',
    'matrix': 'm',
    '£': '£',
}
for bits in (2, 4, 8, 16, 32, 64, 128, 256, 512):
    TYPE_ALIASES[f'i{bits}'] = f'i{bits}'


def is_integer_type(type_code: str | None) -> bool:
    """Return True when type code is `i` or one of the sized integer forms."""
    return bool(type_code) and bool(re.fullmatch(r"i(?:2|4|8|16|32|64|128|256|512)?", type_code))


def integer_bounds(type_code: str) -> tuple[int, int] | None:
    """Return signed integer bounds for sized integer types, otherwise None."""
    if type_code == 'i':
        return None
    m = re.fullmatch(r"i(2|4|8|16|32|64|128|256|512)", type_code)
    if not m:
        return None
    bits = int(m.group(1))
    return -(2 ** (bits - 1)), (2 ** (bits - 1)) - 1


def validate_integer_range(value: int, type_code: str) -> None:
    """Validate integer fits in target integer type, raising on overflow."""
    bounds = integer_bounds(type_code)
    if bounds is None:
        return
    low, high = bounds
    if not (low <= value <= high):
        raise MorganicError(f"Integer overflow for {type_code}: {value} out of range [{low}, {high}].")


def is_numeric_literal(expr: str) -> bool:
    """Return True when expression text is a plain numeric literal."""
    return bool(re.fullmatch(r"[+-]?(?:\d+\.\d+|\d+)", expr))


def get_var(state: MorganicState, name: str) -> Any:
    if name not in state.env:
        raise MorganicError("Undefined variable", token=name, hint="Define it before use with [name]=...")
    return state.env[name]


def infer_type_code(value: Any) -> str:
    """Infer Morganic type code from a Python runtime value."""
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


def canonical_type_name(type_code: str | None) -> str:
    """Return a human-friendly canonical type name for display."""
    if not type_code:
        return 'Unknown'
    if type_code == 'b':
        return 'Boolean'
    if type_code == 'f':
        return 'Float'
    if type_code == 'i':
        return 'Integer'
    if is_integer_type(type_code):
        return f'Integer{type_code[1:]}'
    if type_code == '£':
        return 'String'
    if type_code == 'm':
        return 'MatrixCoords'
    if type_code == 'l(c)':
        return 'List<Coord>'
    if type_code.startswith('l(') and type_code.endswith(')'):
        inner = type_code[2:-1]
        return f"List<{canonical_type_name(inner)}>"
    return type_code


def split_top_level_csv(raw: str) -> list[str]:
    """Split comma-separated text while respecting nested delimiters."""
    tokens: list[str] = []
    buf: list[str] = []
    depth = {'(': 0, '[': 0, '{': 0, '<': 0}
    pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}
    for ch in raw:
        if ch in depth:
            depth[ch] += 1
            buf.append(ch)
            continue
        if ch in pairs.values():
            for k, v in pairs.items():
                if v == ch:
                    depth[k] = max(0, depth[k] - 1)
                    break
            buf.append(ch)
            continue
        if ch == ',' and all(level == 0 for level in depth.values()):
            tokens.append(''.join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = ''.join(buf).strip()
    if tail:
        tokens.append(tail)
    return tokens


def split_top_level_operator(raw: str, operator: str) -> tuple[str, str] | None:
    """Split expression by top-level operator, ignoring nested delimiters."""
    depth = {'(': 0, '[': 0, '{': 0, '<': 0}
    pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}
    for idx, ch in enumerate(raw):
        if ch in depth:
            depth[ch] += 1
            continue
        if ch in pairs.values():
            for opener, closer in pairs.items():
                if closer == ch:
                    depth[opener] = max(0, depth[opener] - 1)
                    break
            continue
        if ch == operator and all(level == 0 for level in depth.values()):
            return raw[:idx].strip(), raw[idx + 1 :].strip()
    return None


def normalize_type_alias(raw_type: str) -> str:
    """Normalize primitive aliases while preserving composite types."""
    raw = raw_type.strip()
    alias = TYPE_ALIASES.get(raw.lower())
    return alias if alias is not None else raw


def is_list_element_type_allowed(type_code: str) -> bool:
    """Allow primitive, matrix, coord, and recursively-nested list element types."""
    normalized = normalize_type_alias(type_code)
    if normalized in {'b', 'f', '£', 'c', 'm'} or is_integer_type(normalized):
        return True
    if normalized.startswith('l(') and normalized.endswith(')'):
        inner = normalized[2:-1].strip()
        return bool(inner) and is_list_element_type_allowed(inner)
    return False


def parse_pointer_address(raw: str) -> int:
    """Parse decimal/hex pointer address."""
    token = raw.strip()
    if re.fullmatch(r"[+-]?\d+", token):
        return int(token)
    if re.fullmatch(r"0x[0-9A-Fa-f]+", token):
        return int(token, 16)
    raise MorganicError(f"Invalid pointer address: {raw}")


def parse_byte_literal(raw: str) -> int:
    """Parse one byte literal from decimal or hexadecimal text."""
    token = raw.strip()
    if re.fullmatch(r"0x[0-9A-Fa-f]{1,2}", token):
        value = int(token, 16)
    elif re.fullmatch(r"\d{1,3}", token):
        value = int(token)
    else:
        raise MorganicError(f"Invalid byte literal: {raw}")
    if value < 0 or value > 255:
        raise MorganicError(f"Byte literal out of range 0..255: {value}")
    return value


def store_value(state: MorganicState, name: str, value: Any, type_code: str | None = None) -> None:
    """Store a value in state while enforcing Morganic type safety rules."""
    resolved_type = type_code or infer_type_code(value)
    existing_type = state.types.get(name)
    if existing_type and is_integer_type(existing_type) and isinstance(value, int) and not isinstance(value, bool):
        if not is_integer_type(resolved_type):
            resolved_type = existing_type
        if resolved_type == 'i':
            resolved_type = existing_type
        validate_integer_range(value, existing_type)
        resolved_type = existing_type
    if existing_type is not None and existing_type != resolved_type:
        raise MorganicError(
            f"Type safety violation: variable '{name}' is {existing_type}, cannot assign {resolved_type}."
        )
    if is_integer_type(resolved_type) and isinstance(value, int) and not isinstance(value, bool):
        validate_integer_range(value, resolved_type)
    state.env[name] = value
    state.types[name] = resolved_type


def parse_function_signature(raw_decl: str) -> tuple[str, list[tuple[str, str]], str]:
    """Parse Morganic function-style declaration and return (name, params, body)."""
    m = re.fullmatch(r"#(\w+)((?:'[\w£]+\.[\w£]+')*)#\{(.*)\}", raw_decl, re.DOTALL)
    if not m:
        raise MorganicError("Invalid method declaration syntax.")
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
    return name, params, body.strip()


def build_instance(state: MorganicState, class_name: str, raw_ctor: str) -> tuple[dict[str, Any], str]:
    """Instantiate class by applying default fields and constructor overrides."""
    class_def = state.classes.get(class_name)
    if class_def is None:
        raise MorganicError(f"Undefined class: {class_name}")
    instance = {'__class__': class_name}
    field_types = {}
    for field_name, (field_value, field_type) in class_def['fields'].items():
        instance[field_name] = field_value
        if field_type is not None:
            field_types[field_name] = field_type

    payload = raw_ctor.strip()
    if payload:
        for token in split_top_level_csv(payload):
            m = re.fullmatch(r"(\w+)\s*(?:=|:)\s*(.+)", token, re.DOTALL)
            if not m:
                raise MorganicError(f"Bad constructor field assignment: {token}")
            field_name = m.group(1)
            expr = m.group(2)
            value, value_type = parse_value_expr(expr, state)
            expected = field_types.get(field_name)
            if expected is not None and value_type != expected:
                raise MorganicError(
                    f"Type safety violation: constructor field '{field_name}' expects {expected}, got {value_type}."
                )
            instance[field_name] = value
            if value_type is not None:
                field_types[field_name] = value_type

    return instance, f'.{class_name}.'


def parse_bool_token(token: str) -> bool:
    """Parse Morganic boolean token into Python bool."""
    if token == '/':
        return True
    if token == '\\':
        return False
    raise MorganicError(f"Expected boolean token '/' or '\\', got: {token}")


def _parse_graph_range(raw: str, axis_name: str) -> tuple[int, int]:
    """Parse `<min>&<max>` integer range used by console graph statements."""
    m = re.fullmatch(r"\s*([+-]?\d+)\s*&\s*([+-]?\d+)\s*", raw)
    if not m:
        raise MorganicError(f"Bad {axis_name}-axis range: {raw}")
    axis_min = int(m.group(1))
    axis_max = int(m.group(2))
    if axis_min >= axis_max:
        raise MorganicError(f"{axis_name}-axis min must be less than max: {axis_min}&{axis_max}")
    return axis_min, axis_max


def _coerce_graph_points(value: Any) -> list[tuple[int, int]]:
    """Validate/coerce a matrix or coord-list value into graph points."""
    if not isinstance(value, list):
        raise MorganicError("Graph points must be pairs, l(c), or m.")
    points: list[tuple[int, int]] = []
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise MorganicError("Graph points must be 2D coordinate pairs.")
        x, y = item
        if not isinstance(x, int) or isinstance(x, bool) or not isinstance(y, int) or isinstance(y, bool):
            raise MorganicError("Graph coordinates must be integer pairs.")
        points.append((x, y))
    if not points:
        raise MorganicError("Graph requires at least one point like {(0,0)}.")
    return points


def _parse_graph_points(raw_points: str, state: MorganicState) -> list[tuple[int, int]]:
    """Parse graph payload from pair literals or matrix/coord-list expressions."""
    literal_points = [
        (int(x_raw), int(y_raw))
        for x_raw, y_raw in re.findall(r"\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)", raw_points)
    ]
    normalized = ''.join(match.group(0) for match in re.finditer(r"\(\s*[+-]?\d+\s*,\s*[+-]?\d+\s*\)", raw_points))
    if literal_points and re.sub(r"\s+", "", raw_points) == re.sub(r"\s+", "", normalized):
        return literal_points
    if literal_points:
        raise MorganicError("Bad graph point payload; use consecutive pairs like {(0,0)(1,4)}.")

    value, value_type = parse_value_expr(raw_points.strip(), state)
    if value_type not in {'l(c)', 'm'}:
        raise MorganicError("Graph payload expression must evaluate to l(c) or m.")
    return _coerce_graph_points(value)


def _draw_graph_line(grid: list[list[str]], x0: int, y0: int, x1: int, y1: int) -> None:
    """Draw a line on `grid` using Bresenham integer line rasterization."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        if grid[y0][x0] in {' ', '│', '─', '┼'}:
            grid[y0][x0] = ' '
        if x0 == x1 and y0 == y1:
            break
        err2 = 2 * err
        if err2 > -dy:
            err -= dy
            x0 += sx
        if err2 < dx:
            err += dx
            y0 += sy


def render_console_graph(
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    points: list[tuple[int, int]],
    label_every_units: int | None = None,
) -> str:
    """Render points (with connecting lines) on an ASCII console grid."""
    # Console glyphs are usually taller than they are wide, so use two
    # columns per x-unit to keep one unit on each axis visually comparable.
    x_scale = 2
    left_margin = 5 if label_every_units else 0
    bottom_margin = 2 if label_every_units else 0
    plot_width = (x_max - x_min) * x_scale + 1
    plot_height = y_max - y_min + 1
    width = left_margin + plot_width
    height = plot_height + bottom_margin
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    def to_grid_coords(x: int, y: int) -> tuple[int, int]:
        return left_margin + (x - x_min) * x_scale, y_max - y

    if x_min <= 0 <= x_max:
        axis_x, _ = to_grid_coords(0, 0)
        for row in grid[:plot_height]:
            row[axis_x] = '│'
    if y_min <= 0 <= y_max:
        _, axis_y = to_grid_coords(0, 0)
        for col in range(width):
            grid[axis_y][col] = '─'
    if x_min <= 0 <= x_max and y_min <= 0 <= y_max:
        axis_x, axis_y = to_grid_coords(0, 0)
        grid[axis_y][axis_x] = '┼'

    for x, y in points:
        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            raise MorganicError(f"Point ({x},{y}) is outside graph range x[{x_min},{x_max}] y[{y_min},{y_max}].")

    mapped = [to_grid_coords(x, y) for x, y in points]

    for gx, gy in mapped:
        grid[gy][gx] = '●'

    if x_min <= 0 <= x_max and not label_every_units:
        axis_x, _ = to_grid_coords(0, 0)
        y_label_row = 0
        if grid[y_label_row][axis_x] == ' ':
            grid[y_label_row][axis_x] = 'y'
        elif axis_x + 1 < width and grid[y_label_row][axis_x + 1] == ' ':
            grid[y_label_row][axis_x + 1] = 'y'

    if y_min <= 0 <= y_max and not label_every_units:
        _, axis_y = to_grid_coords(0, 0)
        x_label_col = width - 1
        grid[axis_y][x_label_col] = 'x'

    if label_every_units:
        if label_every_units <= 0:
            raise MorganicError("Graph label interval must be positive.")
        if y_min <= 0 <= y_max:
            _, axis_y = to_grid_coords(0, 0)
            x_label_row = min(plot_height, height - 1)
            for x in range(x_min, x_max + 1):
                if x % label_every_units != 0:
                    continue
                gx, _ = to_grid_coords(x, 0)
                label = str(x)
                start = gx - (len(label) // 2)
                if 0 <= start and start + len(label) <= width:
                    for idx, ch in enumerate(label):
                        grid[x_label_row][start + idx] = ch
        if x_min <= 0 <= x_max:
            axis_x, _ = to_grid_coords(0, 0)
            for y in range(y_min, y_max + 1):
                if y % label_every_units != 0:
                    continue
                _, gy = to_grid_coords(0, y)
                label = str(y).rjust(left_margin - 1)
                for idx, ch in enumerate(label):
                    if idx < axis_x:
                        grid[gy][idx] = ch

    return '\n'.join(''.join(row).rstrip() for row in grid)


def parse_value_expr(expr: str, state: MorganicState) -> tuple[Any, str | None]:
    """Parse/resolve value expression and return `(value, type_code)`."""
    expr = expr.strip()

    m = re.fullmatch(r"--([A-Za-z_][A-Za-z0-9_]*)", expr)
    if m:
        pointer_name = m.group(1)
        pointer = state.pointers.get(pointer_name)
        if pointer is None:
            raise MorganicError(f"Undefined pointer: {pointer_name}")
        address = pointer.get('address')
        if address is None:
            raise MorganicError(f"Pointer '{pointer_name}' is free and cannot be dereferenced.")
        buffer = pointer.get('buffer', [])
        if address < 0 or address >= len(buffer):
            raise MorganicError(f"Pointer '{pointer_name}' address {address} is out of bounds.")
        return buffer[address], 'i8'

    m = re.fullmatch(r"\"([A-Za-z_][A-Za-z0-9_]*)\"([A-Za-z_][A-Za-z0-9_]*)", expr)
    if m:
        enum_name = m.group(1)
        enum_member = m.group(2)
        members = state.enums.get(enum_name)
        if not members:
            raise MorganicError(f"Undefined enum: {enum_name}")
        if enum_member not in members:
            raise MorganicError(f"Unknown enum member '{enum_member}' for \"{enum_name}\".")
        return enum_member, f"\"{enum_name}\""

    m = re.fullmatch(r"b([/\\])", expr)
    if m:
        return parse_bool_token(m.group(1)), 'b'

    m = re.fullmatch(r"(i(?:2|4|8|16|32|64|128|256|512)?)\^(.+)\^", expr, re.DOTALL)
    if m:
        target_type = m.group(1)
        literal = m.group(2).strip()
        if not re.fullmatch(r"[+-]?\d+", literal):
            raise MorganicError(f"{target_type} requires an integer literal inside ^ ^.")
        value = int(literal)
        validate_integer_range(value, target_type)
        return value, target_type

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

    m = re.fullmatch(r"\"\[(\w+)\]", expr)
    if m:
        name = m.group(1)
        if name not in state.env:
            raise MorganicError("Undefined variable", token=name, hint="Define it before reading type with \"[name].")
        return canonical_type_name(state.types.get(name)), '£'

    m = re.fullmatch(r"\|(.+)\|", expr, re.DOTALL)
    if m:
        value = eval_arithmetic(m.group(1).strip(), state)
        return value, infer_type_code(value)

    m = re.fullmatch(r"`([A-Za-z_][A-Za-z0-9_]*)", expr)
    if m:
        name = m.group(1)
        return get_var(state, name), state.types.get(name)

    m = re.fullmatch(r"\*([A-Za-z_][A-Za-z0-9_]*)\{(.*)\}", expr, re.DOTALL)
    if m:
        return build_instance(state, m.group(1), m.group(2))

    m = re.fullmatch(r"\.([A-Za-z_][A-Za-z0-9_]*)\.(.*)", expr, re.DOTALL)
    if m:
        return build_instance(state, m.group(1), m.group(2))

    m = re.fullmatch(r"l\((.+)\)<(.*)>", expr, re.DOTALL)
    if m:
        raw_inner_type = m.group(1).strip()
        normalized_inner = normalize_type_alias(raw_inner_type)
        raw_inner_type_lower = raw_inner_type.lower()
        if normalized_inner == 'c' or raw_inner_type_lower == 'coord':
            inside = m.group(2).strip()
            if not inside:
                return [], 'l(c)'
            raw_tokens = split_top_level_csv(inside)
            points: list[tuple[int, int]] = []
            for token in raw_tokens:
                pair = re.fullmatch(r"\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)", token)
                if not pair:
                    raise MorganicError(f"Bad coord token in l(c): {token}")
                points.append((int(pair.group(1)), int(pair.group(2))))
            return points, 'l(c)'
        element_type = normalized_inner
        if not is_list_element_type_allowed(element_type):
            raise MorganicError(f"Unsupported list element type: {m.group(1).strip()}")
        inside = m.group(2).strip()
        if not inside:
            return [], f'l({element_type})'
        raw_tokens = split_top_level_csv(inside)
        values = []
        for token in raw_tokens:
            value, value_type = parse_value_expr(token, state)
            if value_type != element_type:
                raise MorganicError(
                    f"Type safety violation: list expects {element_type}, got {value_type}."
                )
            values.append(value)
        return values, f'l({element_type})'

    m = re.fullmatch(r"m<([^>]*)><([^>]*)>", expr, re.DOTALL)
    if m:
        x_values = [part.strip() for part in m.group(1).split(',') if part.strip()]
        y_values = [part.strip() for part in m.group(2).split(',') if part.strip()]
        if len(x_values) != len(y_values):
            raise MorganicError("m<x...><y...> requires equal x and y counts.")
        points: list[tuple[int, int]] = []
        for x_raw, y_raw in zip(x_values, y_values):
            if not re.fullmatch(r"[+-]?\d+", x_raw) or not re.fullmatch(r"[+-]?\d+", y_raw):
                raise MorganicError("m coordinates must be integers.")
            points.append((int(x_raw), int(y_raw)))
        return points, 'm'

    if expr in {'/', '\\'}:
        return parse_bool_token(expr), 'b'

    if expr.startswith('£'):
        return expr[1:], '£'

    split_append = split_top_level_operator(expr, '~')
    if split_append is not None:
        left_raw, right_raw = split_append
        m = re.fullmatch(r"\[(\w+)\]", left_raw)
        if not m:
            raise MorganicError("Append expression requires a list variable target like [list]~value.")
        name = m.group(1)
        if name not in state.env:
            raise MorganicError(f"Undefined: {name}")
        list_type = state.types.get(name)
        typed_list = re.fullmatch(r"l\((.+)\)", list_type or "")
        if not typed_list:
            raise MorganicError("Append requires a typed list variable.")
        element_type = typed_list.group(1)
        value, value_type = parse_value_expr(right_raw, state)
        if value_type != element_type:
            raise MorganicError("Type safety violation: append type does not match list type.")
        state.env[name].append(value)
        return state.env[name], list_type

    split_index = split_top_level_operator(expr, '@')
    if split_index is not None:
        left_raw, right_raw = split_index
        seq_value, seq_type = parse_value_expr(left_raw, state)
        if not isinstance(seq_value, list):
            raise MorganicError("Index operator '@' requires a list value.")
        index_value, _ = parse_value_expr(right_raw, state)
        if not isinstance(index_value, int) or isinstance(index_value, bool):
            raise MorganicError("List index must be an integer expression.")
        idx = index_value
        if idx < 0 or idx >= len(seq_value):
            raise MorganicError(f"List index out of range: {idx}")
        value = seq_value[idx]
        result_type: str | None = None
        if seq_type and seq_type.startswith('l(') and seq_type.endswith(')'):
            result_type = seq_type[2:-1]
        return value, result_type or infer_type_code(value)

    if is_numeric_literal(expr):
        raise MorganicError(
            "Numeric literals must be wrapped with ^ ^ (example: ^3^)."
        )

    raise MorganicError(f"Unrecognized value expression: {expr}")


def eval_condition(condition_expr: str, state: MorganicState) -> bool:
    """Evaluate Morganic equality condition expression (`..`)."""
    if '..' not in condition_expr:
        raise MorganicError("Condition must use equality operator '..'.")
    left_raw, right_raw = condition_expr.split('..', 1)
    left, _ = parse_value_expr(left_raw, state)
    right, _ = parse_value_expr(right_raw, state)
    return left == right


def convert_value(value: Any, src_type: str, target_type: str) -> tuple[Any, str]:
    """Convert a runtime value to a target Morganic type."""
    if target_type == src_type:
        return value, src_type

    if target_type == 'm':
        if src_type == 'l(c)':
            return list(value), 'm'
        raise MorganicError(f"Incompatible conversion: {src_type} -> m")

    if is_integer_type(target_type):
        if src_type == 'f':
            if int(value) != value:
                raise MorganicError("Cannot convert non-whole float to integer.")
            out = int(value)
            validate_integer_range(out, target_type)
            return out, target_type
        if src_type == '£' and re.fullmatch(r"[+-]?\d+", value):
            out = int(value)
            validate_integer_range(out, target_type)
            return out, target_type
        if is_integer_type(src_type):
            out = int(value)
            validate_integer_range(out, target_type)
            return out, target_type
        raise MorganicError(f"Incompatible conversion: {src_type} -> {target_type}")

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
    """Parse range-loop bound operand as integer."""
    raw = expr.strip()
    if re.fullmatch(r"[+-]?\d+", raw):
        value = int(raw)
    else:
        value, _ = parse_value_expr(raw, state)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MorganicError("For loop range bounds must be integers.")
    return value


def parse_list_index(list_name: str, index_expr: str, state: MorganicState) -> Any:
    """Read one element from a list variable by integer index expression."""
    seq = get_var(state, list_name)
    if not isinstance(seq, list):
        raise MorganicError(f"Indexing requires a list variable, got: {list_name}")

    raw_index = index_expr.strip()
    if re.fullmatch(r"[+-]?\d+", raw_index):
        index = int(raw_index)
    else:
        value, _ = parse_value_expr(raw_index, state)
        if not isinstance(value, int) or isinstance(value, bool):
            raise MorganicError("List index must be an integer.")
        index = value

    if index < 0 or index >= len(seq):
        raise MorganicError(f"List index out of bounds: {index} (size={len(seq)}).")
    return seq[index]


def execute_statement(stmt: str, state: MorganicState) -> None:
    """Execute one top-level Morganic statement."""
    stmt = stmt.strip()
    if not stmt:
        return

    m = re.fullmatch(r"0(?:\.(\d+))?(?:\(([^,]+),([^)]+)\))?\{(.*)\}", stmt, re.DOTALL)
    if m:
        if m.group(2) is None or m.group(3) is None:
            x_min, x_max = -10, 10
            y_min, y_max = -10, 10
        else:
            x_min, x_max = _parse_graph_range(m.group(2), 'x')
            y_min, y_max = _parse_graph_range(m.group(3), 'y')
        points = _parse_graph_points(m.group(4), state)
        label_mode = m.group(1)
        interval = None
        if label_mode:
            interval = int(label_mode)
            if interval <= 0:
                raise MorganicError("Graph label mode must be 0.1, 0.2, ...")
        print(render_console_graph(x_min, x_max, y_min, y_max, points, label_every_units=interval))
        return

    m = re.fullmatch(r"\*([A-Za-z_][A-Za-z0-9_]*)\{(.*)\}", stmt, re.DOTALL)
    if m:
        class_name = m.group(1)
        body = m.group(2).strip()
        fields: dict[str, tuple[Any, str | None]] = {}
        methods: dict[str, Any] = {}
        if body:
            local_state = MorganicState(
                env=dict(state.env),
                types=dict(state.types),
                functions=dict(state.functions),
                classes=dict(state.classes),
                enums=dict(state.enums),
                pointers=dict(state.pointers),
            )
            for part in split_statements(body):
                item = part.strip()
                if not item:
                    continue
                if item.startswith('#'):
                    method_name, method_params, method_body = parse_function_signature(item)
                    methods[method_name] = {'params': method_params, 'body': method_body}
                    continue
                assign = re.fullmatch(r"\[(\w+)\]=(.*)", item, re.DOTALL)
                if not assign:
                    raise MorganicError("Class body only supports field assignments and #method declarations.")
                field_name = assign.group(1)
                field_expr = assign.group(2).strip()
                value, value_type = parse_value_expr(field_expr, local_state)
                fields[field_name] = (value, value_type)
                store_value(local_state, field_name, value, value_type)
        state.classes[class_name] = {'fields': fields, 'methods': methods}
        return

    m = re.fullmatch(r"#(\w+)((?:'[\w£]+\.[\w£]+')*)#\{(.*)\}", stmt, re.DOTALL)
    if m:
        name, params, body = parse_function_signature(stmt)
        state.functions[name] = {'params': params, 'body': body.strip()}
        return

    m = re.fullmatch(r"\"([A-Za-z_][A-Za-z0-9_]*)\"=([A-Za-z_][A-Za-z0-9_]*(?:¬[A-Za-z_][A-Za-z0-9_]*)*)", stmt)
    if m:
        enum_name = m.group(1)
        raw_members = m.group(2).split('¬')
        if len(set(raw_members)) != len(raw_members):
            raise MorganicError(f"Enum \"{enum_name}\" has duplicate members.")
        state.enums[enum_name] = set(raw_members)
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
                        if (pt == 'f' or is_integer_type(pt)) and not (
                            re.fullmatch(r"\^.+\^", arg, re.DOTALL)
                            or re.fullmatch(r"i(?:2|4|8|16|32|64|128|256|512)?\^.+\^", arg, re.DOTALL)
                        ):
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
        try:
            value = input(prompt)
        except EOFError:
            value = '0'
        store_value(state, name, value, '£')
        return

    m = re.fullmatch(r"\[(\w+)\]\$([A-Za-z£][A-Za-z0-9]*)", stmt)
    if m:
        name = m.group(1)
        raw_target = m.group(2).lower()
        target_type = TYPE_ALIASES.get(raw_target, m.group(2))
        if target_type not in {'f', 'b', '£'} and not is_integer_type(target_type):
            raise MorganicError(f"Unsupported conversion target: {m.group(2)}")
        value = get_var(state, name)
        src_type = state.types.get(name, infer_type_code(value))
        new_value, new_type = convert_value(value, src_type, target_type)
        state.env[name] = new_value
        state.types[name] = new_type
        return

    m = re.fullmatch(r"\[(\w+)\]£m", stmt)
    if m:
        name = m.group(1)
        value = get_var(state, name)
        src_type = state.types.get(name, infer_type_code(value))
        new_value, new_type = convert_value(value, src_type, 'm')
        state.env[name] = new_value
        state.types[name] = new_type
        return

    m = re.fullmatch(r"\[(\w+)\]~(.+)", stmt, re.DOTALL)
    if m:
        name = m.group(1)
        expr = m.group(2).strip()
        if name not in state.env:
            raise MorganicError(f"Undefined: {name}")
        list_type = state.types.get(name)
        if not list_type or not re.fullmatch(r"l\((.+)\)", list_type):
            raise MorganicError("Append requires a typed list variable.")
        element_type = re.fullmatch(r"l\((.+)\)", list_type).group(1)
        value, value_type = parse_value_expr(expr, state)
        if value_type != element_type:
            raise MorganicError("Type safety violation: append type does not match list type.")
        state.env[name].append(value)
        return

    m = re.fullmatch(r"\+\+([A-Za-z_][A-Za-z0-9_]*)==\[(.*)\]", stmt, re.DOTALL)
    if m:
        pointer_name = m.group(1)
        body = m.group(2).strip()
        buffer: list[int] = []
        if body:
            buffer = [parse_byte_literal(token) for token in body.split()]
        state.pointers[pointer_name] = {'buffer': buffer, 'address': 0 if buffer else None}
        return

    m = re.fullmatch(r"\+\+([A-Za-z_][A-Za-z0-9_]*)==", stmt)
    if m:
        state.pointers[m.group(1)] = {'buffer': [], 'address': None}
        return

    m = re.fullmatch(r"\+\+([A-Za-z_][A-Za-z0-9_]*)", stmt)
    if m:
        state.pointers.setdefault(m.group(1), {'buffer': [], 'address': None})
        return

    m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\+\-(.+)", stmt, re.DOTALL)
    if m:
        pointer_name = m.group(1)
        pointer = state.pointers.get(pointer_name)
        if pointer is None:
            raise MorganicError(f"Undefined pointer: {pointer_name}")
        pointer['address'] = parse_pointer_address(m.group(2))
        return

    m = re.fullmatch(r"\+([A-Za-z_][A-Za-z0-9_]*)([+-])(\d+)", stmt)
    if m:
        pointer_name = m.group(1)
        op = m.group(2)
        delta = int(m.group(3))
        pointer = state.pointers.get(pointer_name)
        if pointer is None:
            raise MorganicError(f"Undefined pointer: {pointer_name}")
        address = pointer.get('address')
        if address is None:
            raise MorganicError(f"Pointer '{pointer_name}' is free and cannot be shifted.")
        pointer['address'] = address + delta if op == '+' else address - delta
        return

    m = re.fullmatch(r"-([A-Za-z_][A-Za-z0-9_]*)>>(\d+)", stmt)
    if m:
        pointer_name = m.group(1)
        delta = int(m.group(2))
        pointer = state.pointers.get(pointer_name)
        if pointer is None:
            raise MorganicError(f"Undefined pointer: {pointer_name}")
        address = pointer.get('address')
        if address is None:
            raise MorganicError(f"Pointer '{pointer_name}' is free and cannot be shifted.")
        pointer['address'] = address + delta
        return

    m = re.fullmatch(r"\[!(.+)!/w\]\((.*)\)", stmt, re.DOTALL)
    if m:
        filename = m.group(1).strip()
        expr = m.group(2).strip()
        value, _ = parse_value_expr(expr, state)
        with open(filename, 'w', encoding='utf-8') as handle:
            handle.write(str(value))
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

    m = re.fullmatch(r"1\(\[(\w+)\]@(.+)\)", stmt, re.DOTALL)
    if m:
        print(parse_list_index(m.group(1), m.group(2), state))
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

    m = re.fullmatch(r"1\(\"(\[\w+\])\)", stmt)
    if m:
        value, _ = parse_value_expr(f"\"{m.group(1)}", state)
        print(value)
        return

    raise MorganicError(
        "Unrecognized statement",
        token=stmt,
        hint="Check delimiters and required forms like [x]=..., 1(...), 2(...){...}.",
    )


def try_eval_and_print_inline_expression(program: str, state: MorganicState) -> bool:
    """
    If the input is a single inline arithmetic expression (`|...|` or `{...}`),
    evaluate and print it directly.
    """
    statements = split_statements(program)
    if len(statements) != 1:
        return False
    stmt = statements[0].strip()

    m = re.fullmatch(r"\|(.+)\|", stmt, re.DOTALL)
    if m:
        print(eval_arithmetic(m.group(1).strip(), state))
        return True

    m = re.fullmatch(r"\{(.+)\}", stmt, re.DOTALL)
    if m:
        print(eval_arithmetic(m.group(1).strip(), state))
        return True

    return False


def execute_program(program: str, state: MorganicState) -> None:
    """Execute a Morganic program split by top-level `:` statements."""
    for chunk in split_statement_chunks(program):
        try:
            execute_statement(chunk.text, state)
        except MorganicError as exc:
            if exc.line is None:
                raise MorganicError(exc.message, line=chunk.line, token=exc.token, hint=exc.hint) from exc
            raise

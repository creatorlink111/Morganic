from __future__ import annotations

import re
from typing import Any, Callable

from .errors import MorganicError
from .state import MorganicState


def parse_graph_range(raw: str, axis_name: str) -> tuple[int, int]:
    """Parse `<min>&<max>` integer range used by console graph statements."""
    m = re.fullmatch(r"\s*([+-]?\d+)\s*&\s*([+-]?\d+)\s*", raw)
    if not m:
        raise MorganicError(f"Bad {axis_name}-axis range: {raw}")
    axis_min = int(m.group(1))
    axis_max = int(m.group(2))
    if axis_min >= axis_max:
        raise MorganicError(f"{axis_name}-axis min must be less than max: {axis_min}&{axis_max}")
    return axis_min, axis_max


def coerce_graph_points(value: Any) -> list[tuple[int, int]]:
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


def parse_graph_points(
    raw_points: str,
    state: MorganicState,
    value_expr_parser: Callable[[str, MorganicState], tuple[Any, str | None]],
) -> list[tuple[int, int]]:
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

    value, value_type = value_expr_parser(raw_points.strip(), state)
    if value_type not in {'l(c)', 'm'}:
        raise MorganicError("Graph payload expression must evaluate to l(c) or m.")
    return coerce_graph_points(value)


def render_console_graph(
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    points: list[tuple[int, int]],
    label_every_units: int | None = None,
) -> str:
    """Render points (with connecting lines) on an ASCII console grid."""
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

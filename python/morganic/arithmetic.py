"""Safe arithmetic evaluator for Morganic inline arithmetic blocks."""

from __future__ import annotations

import ast
import operator
import re
from typing import Any, Callable

from .errors import MorganicError
from .state import MorganicState


_BINARY_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def is_number(value: Any) -> bool:
    """Return True for numeric operands accepted in arithmetic blocks."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _read_variable(state: MorganicState, name: str) -> Any:
    """Read a variable reference from state with contextual errors."""
    if name not in state.env:
        raise MorganicError("Undefined variable in arithmetic block", token=name)
    value = state.env[name]
    if state.types.get(name) == '?\u00A3':
        state.env.pop(name, None)
        state.types.pop(name, None)
    return value


def _eval_node(node: ast.AST, state: MorganicState) -> Any:
    """Evaluate a limited Python AST tree generated from Morganic arithmetic."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, state)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise MorganicError("Only numeric literals are allowed in arithmetic blocks")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id != "V":
            raise MorganicError("Only variable references are allowed in arithmetic blocks")
        if len(node.args) != 1:
            raise MorganicError("Malformed variable reference")
        arg = node.args[0]
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            raise MorganicError("Malformed variable reference")
        return _read_variable(state, arg.value)

    if isinstance(node, ast.UnaryOp):
        val = _eval_node(node.operand, state)
        if not is_number(val):
            raise MorganicError("Unary operators only work on numbers")
        fn = _UNARY_OPS.get(type(node.op))
        if fn is None:
            raise MorganicError("Unsupported unary operator")
        return fn(val)

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, state)
        right = _eval_node(node.right, state)
        if not is_number(left) or not is_number(right):
            raise MorganicError("Arithmetic blocks only allow numeric operands")

        fn = _BINARY_OPS.get(type(node.op))
        if fn is None:
            raise MorganicError("Unsupported arithmetic operator")
        try:
            return fn(left, right)
        except ZeroDivisionError as exc:
            raise MorganicError(
                "Division by zero", hint="Check divisor values before using /, //, or %."
            ) from exc

    raise MorganicError(f"Unsupported syntax in arithmetic block: {type(node).__name__}")


def eval_arithmetic(expr: str, state: MorganicState) -> Any:
    """Evaluate arithmetic expression used inside `|...|` or `{...}` blocks."""
    translated = re.sub(r"`([A-Za-z_][A-Za-z0-9_]*)", r'V("\1")', expr)

    try:
        tree = ast.parse(translated, mode="eval")
    except SyntaxError as e:
        raise MorganicError(
            "Bad arithmetic expression",
            token=expr,
            hint="Use operators + - * / // % and backtick vars, e.g. |`a+3|.",
        ) from e

    return _eval_node(tree, state)

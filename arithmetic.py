from __future__ import annotations

import ast
import re
from typing import Any

from .errors import MorganicError
from .state import MorganicState

def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def eval_arithmetic(expr: str, state: MorganicState) -> Any:
    """
    Curly-brace arithmetic:
      - bare numbers are literals
      - `name means variable reference
      - operators: + - * / // %
      - parentheses are allowed
    """
    translated = re.sub(r"`([A-Za-z_][A-Za-z0-9_]*)", r'V("\1")', expr)

    try:
        tree = ast.parse(translated, mode="eval")
    except SyntaxError as e:
        raise MorganicError(f"Bad arithmetic expression: {expr!r}") from e

    def get_var(name: str) -> Any:
        if name not in state.env:
            raise MorganicError(f"Undefined variable: {name}")
        return state.env[name]

    def eval_node(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return eval_node(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise MorganicError("Only numeric literals are allowed in arithmetic blocks.")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id != "V":
                raise MorganicError("Only variable references are allowed in arithmetic blocks.")
            if len(node.args) != 1:
                raise MorganicError("Malformed variable reference.")
            arg = node.args[0]
            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                raise MorganicError("Malformed variable reference.")
            return get_var(arg.value)

        if isinstance(node, ast.UnaryOp):
            val = eval_node(node.operand)
            if not is_number(val):
                raise MorganicError("Unary operators only work on numbers.")
            if isinstance(node.op, ast.UAdd):
                return +val
            if isinstance(node.op, ast.USub):
                return -val
            raise MorganicError("Unsupported unary operator.")

        if isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            if not is_number(left) or not is_number(right):
                raise MorganicError("Arithmetic blocks only allow numeric operands.")

            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
            raise MorganicError("Unsupported operator.")

        raise MorganicError(f"Unsupported syntax in arithmetic block: {type(node).__name__}")

    return eval_node(tree)
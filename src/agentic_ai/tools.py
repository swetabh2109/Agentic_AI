"""Tools the agent can call. Add new ones by registering a function."""

from __future__ import annotations

import ast
import operator
from typing import Callable

Tool = Callable[[str], str]

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    raise ValueError("only + - * / and numbers are allowed")


def calculate(expression: str) -> str:
    """Evaluate a simple arithmetic expression."""
    try:
        value = _eval(ast.parse(expression, mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError) as exc:
        return f"error: {exc}"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def echo(text: str) -> str:
    """Return the argument unchanged."""
    return text


DEFAULT_TOOLS: dict[str, Tool] = {
    "calculate": calculate,
    "echo": echo,
}

"""MCP tool: arithmetic evaluation.

Parses the expression into an AST and walks it with an operator allowlist,
rather than calling `eval()` — `eval()` would execute arbitrary Python from
whatever string an agent (or a prompt-injected document) hands this tool.
This is the one tool in the server that never depends on the network, so
it's a reliable fallback the router agent can lean on even if web search or
the backend are unavailable.
"""

import ast
import operator
from collections.abc import Callable

from pydantic import Field

_BINARY_OPERATORS: dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_UNARY_OPERATORS: dict[type, Callable[[float], float]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.expr) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def calculate(
    expression: str = Field(description="An arithmetic expression, e.g. '12 * (4 + 3) / 2'"),
) -> float:
    """Evaluate a basic arithmetic expression: +, -, *, /, %, ** and
    parentheses. Use this for any numeric computation instead of doing the
    arithmetic yourself — it's exact where estimation isn't.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        return _eval_node(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError(f"Could not evaluate '{expression}': {exc}") from exc

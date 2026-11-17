"""Stage 1: every generated .py file is valid, complete Python."""

import ast
import re

from . import python_model
from .issues import error, warning

try:  # pure Python; listed in ai_create/requirements.txt
    from pyflakes import checker as pyflakes_checker
    from pyflakes import messages as pyflakes_messages

    _UNDEFINED = (
        pyflakes_messages.UndefinedName,
        pyflakes_messages.UndefinedLocal,
        pyflakes_messages.UndefinedExport,
    )
except ImportError:  # pragma: no cover - only when the dependency is missing
    pyflakes_checker = None

CHECK = "python"

# What the model writes instead of code when it abbreviates (rule 16 of the prompt)
_PLACEHOLDER = re.compile(
    r"\[\s*C[OÓ]DIGO\s+AQUI\s*\]|omitted for brevity|repita para|rest of the code"
    r"|same as above|c[oó]digo omitido",
    re.I,
)
# Routing inside one Lambda (rule 2): the API Gateway already calls the right Lambda
_ROUTING = re.compile(r"""\[\s*['"](?:httpMethod|routeKey)['"]\s*\]""")


def _ellipsis_only(function):
    body = [
        node
        for node in function.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    return bool(body) and all(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and node.value.value is Ellipsis
        for node in body
    )


def check_file(path, source):
    issues = []
    tree = python_model.parse(source)
    if isinstance(tree, SyntaxError):
        return [
            error(
                CHECK,
                f"invalid Python syntax at line {tree.lineno}: {tree.msg}",
                path,
            )
        ]

    if pyflakes_checker is not None:
        for message in pyflakes_checker.Checker(tree, filename=path).messages:
            if isinstance(message, _UNDEFINED):
                text = message.message % message.message_args
                issues.append(
                    error(
                        CHECK, f"line {message.lineno}: {text} (missing import?)", path
                    )
                )

    placeholder = _PLACEHOLDER.search(source)
    if placeholder:
        line = source.count("\n", 0, placeholder.start()) + 1
        issues.append(
            error(
                CHECK,
                f"line {line}: incomplete code ({placeholder.group(0)!r})",
                path,
            )
        )
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _ellipsis_only(
            node
        ):
            issues.append(
                error(
                    CHECK,
                    f"line {node.lineno}: function {node.name}() has no body (only '...')",
                    path,
                )
            )

    if _ROUTING.search(source):
        issues.append(
            warning(
                CHECK,
                "routes by httpMethod/routeKey inside the Lambda; each action should be its own Lambda",
                path,
            )
        )
    return issues


def validate_python(files):
    """Issues of every .py file in {project path: content}."""
    issues = []
    python_files = sorted(p for p in files if p.endswith(".py"))
    if not python_files:
        return [error(CHECK, "no Python file was generated")]
    if pyflakes_checker is None:
        issues.append(
            warning(
                CHECK, "pyflakes is not installed: undefined names were not checked"
            )
        )
    for path in python_files:
        issues.extend(check_file(path, files[path]))
    return issues

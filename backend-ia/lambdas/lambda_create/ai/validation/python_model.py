"""What the validators need to know about a Python file, read from its AST."""

import ast


def parse(source):
    """The module AST, or the SyntaxError that prevents parsing it."""
    try:
        return ast.parse(source or "")
    except SyntaxError as e:
        return e


def top_level_functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def accepts_event_and_context(function):
    """Lambda calls handler(event, context): two positional arguments must be accepted."""
    args = function.args
    positional = len(args.posonlyargs) + len(args.args)
    required_keywords = [
        a for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is None
    ]
    return (positional >= 2 or args.vararg is not None) and not required_keywords


def imported_modules(tree):
    """Top-level names of absolute imports: {"boto3": line, "os": line, ...}."""
    modules = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.setdefault(alias.name.split(".")[0], node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.setdefault(node.module.split(".")[0], node.lineno)
    return modules


def _is_environ(node):
    """os.environ or a bare environ (from os import environ)."""
    return (isinstance(node, ast.Attribute) and node.attr == "environ") or (
        isinstance(node, ast.Name) and node.id == "environ"
    )


def _string(node):
    return (
        node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        else None
    )


def environment_reads(tree):
    """[(variable, required, line)]: required when a missing variable raises KeyError.

    os.environ["X"] is required; os.environ.get("X") and os.getenv("X") are not (they
    return None). Reads with a default value are left out: a missing variable is expected.
    """
    reads = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _is_environ(node.value):
            name = _string(node.slice)
            if name and isinstance(node.ctx, ast.Load):
                reads.append((name, True, node.lineno))
        elif isinstance(node, ast.Call) and node.args and _string(node.args[0]):
            func = node.func
            environ_get = (
                isinstance(func, ast.Attribute)
                and func.attr == "get"
                and _is_environ(func.value)
            )
            getenv = (isinstance(func, ast.Attribute) and func.attr == "getenv") or (
                isinstance(func, ast.Name) and func.id == "getenv"
            )
            has_default = len(node.args) > 1 or bool(node.keywords)
            if (environ_get or getenv) and not has_default:
                reads.append((_string(node.args[0]), False, node.lineno))
    return reads


def method_calls(tree):
    """Names of the methods called anywhere: {"put_item": line, ...}."""
    calls = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.setdefault(node.func.attr, node.lineno)
    return calls


def string_returns(function):
    """Lines where the function returns a string (json.dumps(...), "..." or f"...")."""
    lines = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        value = node.value
        is_dumps = (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "dumps"
        )
        if is_dumps or _string(value) is not None or isinstance(value, ast.JoinedStr):
            lines.append(node.lineno)
    return lines

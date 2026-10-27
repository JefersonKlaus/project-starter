"""Validators: each one receives (result, expected) and returns a list of errors.
An empty list means the result passed.

To add a new validator: write the function and register it in VALIDATORS.
"""
import ast
import io
import re
import subprocess
import tempfile
from pathlib import Path

from pyflakes import api as pyflakes_api
from pyflakes import reporter as pyflakes_reporter


# ---------------------------------------------------------------- helpers
def _terraform(result):
    return "\n".join(result["generated_code"]["terraform"].values())


def _python_files(result):
    return {
        name: code
        for name, code in result["generated_code"]["python"].items()
        if name.endswith(".py")
    }


# ---------------------------------------------------------------- python
def validate_python(result, expected=None):
    """Valid syntax and prompt rules (no internal routing, dict response,
    configuration through os.environ)."""
    errors = []
    for name, code in _python_files(result).items():
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"{name}: syntax error on line {e.lineno}")
            continue
        if "httpMethod" in code:
            errors.append(f"{name}: internal routing (rule 2)")
        if re.search(r"return\s+json\.dumps\(", code):
            errors.append(f"{name}: returns a string instead of a dict (API Gateway proxy)")
        if re.search(r"event\[\s*['\"](region|table_name)['\"]\s*\]", code):
            errors.append(f"{name}: reads region/table_name from the event (use os.environ)")
    return errors


def validate_pyflakes(result, expected=None):
    """Finds undefined names (for example, os/logging without an import), which pass
    ast.parse but fail with NameError on the first invocation."""
    errors = []
    for name, code in _python_files(result).items():
        try:
            ast.parse(code)
        except SyntaxError:
            continue  # Already reported by validate_python.
        output = io.StringIO()
        reporter = pyflakes_reporter.Reporter(output, output)
        pyflakes_api.check(code, name, reporter)
        for line in output.getvalue().splitlines():
            if "undefined name" in line:
                errors.append(line)
    return errors


# ------------------------------------------------------------- terraform
def validate_terraform_non_empty(result, expected=None):
    """Prevents the other validators from approving an empty result."""
    count = len(re.findall(r'^\s*resource\s+"', _terraform(result), re.M))
    return [] if count >= 3 else [f"terraform has only {count} resources"]


def validate_terraform_rules(result, expected=None):
    tf = _terraform(result)
    errors = []
    if re.search(r'source_arn\s*=\s*"\*"', tf):
        errors.append('source_arn = "*" (permission is too broad)')
    runtimes = set(re.findall(r'runtime\s*=\s*"python([\d.]+)"', tf))
    for runtime in sorted(runtimes):
        version = tuple(int(x) for x in runtime.split("."))
        if version < (3, 10):
            errors.append(f"python{runtime} runtime is deprecated")
    return errors


def validate_consistency(result, expected):
    tf = _terraform(result)
    python_count = len(_python_files(result))
    terraform_count = len(re.findall(r'resource\s+"aws_lambda_function"', tf))
    role_count = len(re.findall(r'resource\s+"aws_iam_role"', tf))
    permission_count = len(re.findall(r'resource\s+"aws_lambda_permission"', tf))
    errors = []
    if python_count != terraform_count:
        errors.append(f"{python_count} .py files but {terraform_count} aws_lambda_function resources")
    if terraform_count != expected["lambdas"]:
        errors.append(f"expected {expected['lambdas']} Lambdas, got {terraform_count}")
    if role_count < terraform_count:
        errors.append(f"{role_count} roles for {terraform_count} Lambdas (rule 4)")
    if permission_count < terraform_count:
        errors.append(f"{permission_count} permissions for {terraform_count} Lambdas (rule 4)")
    for resource in expected.get("recursos", []):
        if f'"{resource}"' not in tf:
            errors.append(f"missing resource {resource}")
    return errors


def validate_routes(result, expected):
    """Each API Gateway route needs a method + integration pointing to a
    Lambda. Runs only when the case expects aws_api_gateway_rest_api.

    Use "rotas" in prompts.json when not every Lambda has a route
    (for example, a queue consumer). Default: expected number of Lambdas."""
    if "aws_api_gateway_rest_api" not in expected.get("recursos", []):
        return []
    tf = _terraform(result)
    expected_routes = expected.get("rotas", expected["lambdas"])
    method_count = len(re.findall(r'resource\s+"aws_api_gateway_method"', tf))
    integration_count = len(re.findall(r'resource\s+"aws_api_gateway_integration"', tf))
    connected_lambdas = set(
        re.findall(r"uri\s*=\s*aws_lambda_function\.(\w+)\.invoke_arn", tf)
    )
    errors = []
    if method_count < expected_routes:
        errors.append(f"{method_count} aws_api_gateway_method resources for {expected_routes} routes")
    if integration_count < expected_routes:
        errors.append(
            f"{integration_count} aws_api_gateway_integration resources for {expected_routes} routes"
        )
    if len(connected_lambdas) < expected_routes:
        errors.append(
            f"only {len(connected_lambdas)} Lambdas connected to API Gateway "
            f"(expected {expected_routes})"
        )
    return errors


def validate_terraform_cli(result, expected=None):
    """terraform init + validate in a temporary directory. Requires Terraform."""
    with tempfile.TemporaryDirectory() as temp_dir:
        for name, content in result["generated_code"]["terraform"].items():
            (Path(temp_dir) / Path(name).name).write_text(content)
        comandos = [
            ["terraform", "init", "-backend=false", "-input=false", "-no-color"],
            ["terraform", "validate", "-no-color"],
        ]
        for cmd in comandos:
            try:
                r = subprocess.run(
                    cmd, cwd=temp_dir, capture_output=True, text=True, timeout=180
                )
            except FileNotFoundError:
                return ["terraform is not installed"]
            except subprocess.TimeoutExpired:
                return [f"terraform {cmd[1]} timed out"]
            if r.returncode != 0:
                return [
                    f"terraform {cmd[1]} failed: {(r.stderr or r.stdout).strip()[:500]}"
                ]
    return []


# -------------------------------------------------------------- registro
VALIDATORS = {
    "python": validate_python,
    "pyflakes": validate_pyflakes,
    "tf_nao_vazio": validate_terraform_non_empty,
    "regras_tf": validate_terraform_rules,
    "consistencia": validate_consistency,
    "rotas": validate_routes,
    "terraform": validate_terraform_cli,
}
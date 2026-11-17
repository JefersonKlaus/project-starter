"""Stage 2: every generated .tf file is valid HCL and consistent Terraform.

Catches, without running terraform, what `terraform validate` / `apply` reject:
syntax errors, duplicated names, references to things that are not declared, missing
required arguments, DynamoDB key/attribute mismatches and arguments removed from the
AWS provider.
"""

import re
from collections import Counter

from .issues import error, warning
from .terraform_model import (
    dynamic_block_names,
    literal,
    nested_blocks,
    parse_project,
)

CHECK = "terraform"

# Required arguments of the resources the prompt asks for (AWS provider 5/6)
REQUIRED_ARGUMENTS = {
    ("resource", "aws_lambda_function"): ("function_name", "role"),
    ("resource", "aws_iam_role"): ("assume_role_policy",),
    ("resource", "aws_iam_role_policy"): ("role", "policy"),
    ("resource", "aws_iam_policy"): ("policy",),
    ("resource", "aws_iam_role_policy_attachment"): ("role", "policy_arn"),
    ("resource", "aws_lambda_permission"): ("action", "function_name", "principal"),
    ("resource", "aws_dynamodb_table"): ("name", "hash_key", "attribute"),
    ("resource", "aws_api_gateway_rest_api"): ("name",),
    ("resource", "aws_api_gateway_resource"): ("rest_api_id", "parent_id", "path_part"),
    ("resource", "aws_api_gateway_method"): (
        "rest_api_id",
        "resource_id",
        "http_method",
        "authorization",
    ),
    ("resource", "aws_api_gateway_integration"): (
        "rest_api_id",
        "resource_id",
        "http_method",
        "type",
    ),
    ("resource", "aws_api_gateway_deployment"): ("rest_api_id",),
    ("resource", "aws_api_gateway_stage"): (
        "rest_api_id",
        "deployment_id",
        "stage_name",
    ),
    ("resource", "aws_apigatewayv2_api"): ("name", "protocol_type"),
    ("resource", "aws_apigatewayv2_integration"): ("api_id", "integration_type"),
    ("resource", "aws_apigatewayv2_route"): ("api_id", "route_key"),
    ("resource", "aws_apigatewayv2_stage"): ("api_id", "name"),
    ("data", "archive_file"): ("type", "output_path"),
    ("output", None): ("value",),
}
# Arguments removed from the AWS provider (v6): terraform rejects them
REMOVED_ARGUMENTS = {
    "aws_api_gateway_deployment": {
        "stage_name": "use a separate aws_api_gateway_stage",
        "stage_description": "use a separate aws_api_gateway_stage",
        "canary_settings": "use a separate aws_api_gateway_stage",
    },
}
_PYTHON_RUNTIME = re.compile(r"^python3\.(\d+)$")
OLDEST_PYTHON_RUNTIME = 9  # python3.8 and older can no longer be created


def _duplicates(project):
    issues = []
    named = [
        b
        for b in project.blocks
        if b.kind in ("resource", "data", "variable", "output", "module")
    ]
    counts = Counter(b.address for b in named)
    for address, count in counts.items():
        if count > 1:
            files = sorted({b.file for b in named if b.address == address})
            issues.append(
                error(
                    CHECK,
                    f"{address} is declared {count} times ({', '.join(files)})",
                )
            )
    for name in dict.fromkeys(project.duplicate_locals):
        issues.append(error(CHECK, f"local.{name} is declared more than once"))
    return issues


def _undeclared_references(project):
    issues = []
    declared = project.declared
    for block in project.blocks:
        if block.kind == "terraform":
            continue  # settings (required_providers, backend): no references
        for reference in sorted(block.references() - declared):
            if reference.startswith("module."):
                continue  # outputs of modules are not followed
            if reference == block.address:
                continue
            kind = "variable" if reference.startswith("var.") else "block"
            issues.append(
                error(
                    CHECK,
                    f"{block.label} refers to {reference}, but no such {kind} is declared",
                    block.file,
                )
            )
    return issues


def _required_arguments(project):
    issues = []
    for block in project.blocks:
        required = REQUIRED_ARGUMENTS.get((block.kind, block.type)) or ()
        present = set(block.body) | dynamic_block_names(block.body)
        missing = [name for name in required if name not in present]
        if block.kind == "resource" and block.type == "aws_lambda_function":
            if "image_uri" not in block.body:  # zip package: handler and runtime too
                missing += [n for n in ("handler", "runtime") if n not in block.body]
        if block.kind == "data" and block.type == "archive_file":
            has_source = any(
                key in block.body for key in ("source_file", "source_dir", "source")
            ) or any(key.startswith("source") for key in block.body)
            if not has_source:
                missing.append("source_file/source_dir")
        if missing:
            issues.append(
                error(
                    CHECK,
                    f"{block.label} is missing required argument(s): {', '.join(missing)}",
                    block.file,
                )
            )
    return issues


def _removed_arguments(project):
    issues = []
    for block in project.of("resource"):
        for argument, hint in REMOVED_ARGUMENTS.get(block.type, {}).items():
            if argument in block.body:
                issues.append(
                    error(
                        CHECK,
                        f"{block.label} uses `{argument}`, removed from the AWS provider: {hint}",
                        block.file,
                    )
                )
    return issues


def _dynamodb_tables(project):
    """Every key needs an attribute, and every attribute must be a key (AWS rejects extras)."""
    issues = []
    for block in project.of("resource", "aws_dynamodb_table"):
        if "attribute" in dynamic_block_names(block.body):
            continue  # attributes generated by a dynamic block: not known statically
        attributes = {
            literal(a.get("name")) for a in nested_blocks(block.body, "attribute")
        }
        if None in attributes:
            continue  # names built from expressions: cannot be compared
        keys = {literal(block.get("hash_key")), literal(block.get("range_key"))}
        for index in nested_blocks(block.body, "global_secondary_index"):
            keys |= {literal(index.get("hash_key")), literal(index.get("range_key"))}
        for index in nested_blocks(block.body, "local_secondary_index"):
            keys.add(literal(index.get("range_key")))
        keys.discard(None)
        for key in sorted(keys - attributes):
            issues.append(
                error(
                    CHECK,
                    f'{block.label}: key "{key}" has no attribute {{ name = "{key}" ... }} block',
                    block.file,
                )
            )
        for name in sorted(attributes - keys):
            issues.append(
                error(
                    CHECK,
                    f'{block.label}: attribute "{name}" is not used by any key or index '
                    "(AWS rejects attribute definitions that are not indexed)",
                    block.file,
                )
            )
        billing_mode = literal(block.get("billing_mode"))
        if billing_mode in (None, "PROVISIONED") and not (
            "read_capacity" in block.body and "write_capacity" in block.body
        ):
            issues.append(
                error(
                    CHECK,
                    f"{block.label}: PROVISIONED billing (the default) needs read_capacity "
                    'and write_capacity; use billing_mode = "PAY_PER_REQUEST"',
                    block.file,
                )
            )
    return issues


def _lambda_runtimes(project):
    issues = []
    for block in project.of("resource", "aws_lambda_function"):
        runtime = literal(block.get("runtime"))
        if runtime is None:
            continue
        match = _PYTHON_RUNTIME.match(runtime)
        if not match:
            issues.append(
                error(
                    CHECK,
                    f'{block.label}: runtime "{runtime}" cannot run the generated Python code',
                    block.file,
                )
            )
        elif int(match.group(1)) < OLDEST_PYTHON_RUNTIME:
            issues.append(
                error(
                    CHECK,
                    f'{block.label}: runtime "{runtime}" is deprecated and can no longer be created',
                    block.file,
                )
            )
    return issues


def _conventions(project):
    """Rules of the prompt that do not break terraform (warnings)."""
    issues = []
    used = set()
    for block in project.blocks:
        used |= {r for r in block.references() if r.startswith("var.")}
    for block in project.of("variable"):
        if block.address not in used:
            issues.append(
                warning(
                    CHECK, f"{block.address} is declared but never used", block.file
                )
            )
        if "default" not in block.body:
            issues.append(
                warning(
                    CHECK,
                    f"{block.address} has no default: terraform apply will ask for it",
                    block.file,
                )
            )
    for block in project.of("output"):
        if not block.file.endswith("outputs.tf"):
            issues.append(
                warning(CHECK, f"{block.address} should be in outputs.tf", block.file)
            )
    if not any(b.name == "aws" for b in project.of("provider")):
        issues.append(warning(CHECK, 'no provider "aws" block (region = var.region)'))
    for block in project.of("resource", "aws_lambda_permission"):
        if literal(block.get("source_arn")) == "*":
            issues.append(
                warning(
                    CHECK,
                    f'{block.label}: source_arn = "*" lets any source invoke the Lambda',
                    block.file,
                )
            )
    return issues


def validate_terraform(files, project=None):
    """Issues of the .tf files in {project path: content}."""
    if not any(p.endswith(".tf") for p in files):
        return [error(CHECK, "no Terraform file was generated")]
    project = project or parse_project(files)
    issues = [
        error(CHECK, f"invalid HCL: {message}", path)
        for path, message in project.syntax_errors.items()
    ]
    # Block-level checks work on the files that parsed
    issues += _duplicates(project)
    issues += _required_arguments(project)
    issues += _removed_arguments(project)
    issues += _dynamodb_tables(project)
    issues += _lambda_runtimes(project)
    if project.syntax_errors:
        # Blocks of the broken file are unknown: references to them would be false alarms
        return issues
    issues += _undeclared_references(project)
    issues += _conventions(project)
    return issues

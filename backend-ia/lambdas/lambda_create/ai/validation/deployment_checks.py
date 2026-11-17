"""Stage 4: the project would work, checked without running terraform or AWS.

For each aws_lambda_function, follows what `terraform apply` and then the Lambda
runtime would do:

    filename -> data.archive_file -> source_file/source_dir exists in the project
    handler "<module>.<function>" -> module at the root of that zip -> function(event, context)
    imports -> standard library, the Lambda runtime (boto3) or a file in the same zip
              (archive_file zips the sources only: it does not pip install requirements.txt)
    os.environ["X"] -> X is in that Lambda's environment { variables }
    boto3 calls (put_item, get_object...) -> allowed by the policies of that Lambda's role

and the API Gateway wiring: AWS_PROXY integrations call the Lambda invoke_arn with POST,
every integrated Lambda has an aws_lambda_permission for apigateway.amazonaws.com, and
the API has a deployment and a stage.
"""

import fnmatch
import posixpath
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

from ..code_linker import DYNAMIC, resolve
from ..project_layout import is_under
from . import python_model
from .issues import error, warning
from .terraform_model import expression, literal, nested_blocks

CHECK = "deployment"

# Packages the python3.x Lambda runtime already has (the AWS SDK and its dependencies)
RUNTIME_PACKAGES = {
    "boto3",
    "botocore",
    "s3transfer",
    "jmespath",
    "dateutil",
    "urllib3",
    "six",
    "awslambdaric",
}
# boto3 method -> IAM action, for the services the generated Lambdas use.
# A service is only checked when the code creates its client/resource.
SERVICE_ACTIONS = {
    "dynamodb": {
        "put_item": "dynamodb:PutItem",
        "get_item": "dynamodb:GetItem",
        "update_item": "dynamodb:UpdateItem",
        "delete_item": "dynamodb:DeleteItem",
        "query": "dynamodb:Query",
        "scan": "dynamodb:Scan",
        "batch_write_item": "dynamodb:BatchWriteItem",
        "batch_get_item": "dynamodb:BatchGetItem",
        "batch_writer": "dynamodb:BatchWriteItem",
    },
    "s3": {
        "put_object": "s3:PutObject",
        "upload_file": "s3:PutObject",
        "upload_fileobj": "s3:PutObject",
        "get_object": "s3:GetObject",
        "download_file": "s3:GetObject",
        "download_fileobj": "s3:GetObject",
        "delete_object": "s3:DeleteObject",
        "list_objects_v2": "s3:ListBucket",
    },
    "sqs": {
        "send_message": "sqs:SendMessage",
        "send_message_batch": "sqs:SendMessage",
        "receive_message": "sqs:ReceiveMessage",
        "delete_message": "sqs:DeleteMessage",
    },
    "sns": {"publish": "sns:Publish"},
}
BASIC_EXECUTION_ROLE = "AWSLambdaBasicExecutionRole"
API_GATEWAY_PRINCIPAL = "apigateway.amazonaws.com"
_ARCHIVE_OUTPUT = re.compile(r"^data\.archive_file\.([\w-]+)\.output_path$")
_ARCHIVE_HASH = re.compile(r"^data\.archive_file\.([\w-]+)\.output_base64sha256$")
_LAMBDA_ATTRIBUTE = re.compile(r"aws_lambda_function\.([\w-]+)\.([\w]+)")
_ROLE_REFERENCE = re.compile(r"aws_iam_role\.([\w-]+)\b")
_POLICY_REFERENCE = re.compile(r"aws_iam_policy\.([\w-]+)\.arn")
_POLICY_DOCUMENT = re.compile(r"data\.aws_iam_policy_document\.([\w-]+)")
_ACTION_TOKEN = re.compile(r"""["']([a-z0-9-]+:[A-Za-z0-9*]+)["']""")
_WILDCARD_ACTION = re.compile(r"""(?i)actions?["']?\s*[=:]\s*\[?\s*["']\*["']""")


@dataclass
class Zip:
    """What data.archive_file puts in a Lambda zip."""

    archive: object
    root: str = None  # project folder at the root of the zip
    files: dict = field(default_factory=dict)  # path inside the zip -> project path
    verifiable: bool = True

    @property
    def modules(self):
        """Python module name -> project path ("create_item" or "pkg.mod")."""
        return {
            posixpath.splitext(inside)[0].replace("/", "."): path
            for inside, path in self.files.items()
            if inside.endswith(".py")
        }

    @property
    def top_level_names(self):
        names = set()
        for inside in self.files:
            first = inside.split("/")[0]
            names.add(posixpath.splitext(first)[0] if "/" not in inside else first)
        return names


def _zip_of(archive, files, layout, issues):
    """Contents of the zip of a data.archive_file, or None when its source is missing."""
    label = archive.label
    source_file = archive.get("source_file")
    source_dir = archive.get("source_dir")
    if source_file is None and source_dir is None:
        return Zip(archive, verifiable=False)  # inline source blocks
    attribute = "source_file" if source_file is not None else "source_dir"
    value = literal(source_file if source_file is not None else source_dir)
    target = (
        resolve(value, archive.module_dir, layout) if value is not None else DYNAMIC
    )
    if target is DYNAMIC:
        return Zip(archive, verifiable=False)
    if target is None:
        issues.append(
            error(
                CHECK,
                f'{label}: {attribute} "{value}" points outside the project',
                archive.file,
            )
        )
        return None

    if attribute == "source_file":
        if target not in files:
            issues.append(
                error(
                    CHECK,
                    f'{label}: source_file "{value}" does not exist (it resolves to "{target}")',
                    archive.file,
                )
            )
            return None
        return Zip(
            archive, posixpath.dirname(target), {posixpath.basename(target): target}
        )

    inside = {
        posixpath.relpath(path, target or "."): path
        for path in files
        if is_under(path, target)
    }
    if not inside:
        issues.append(
            error(
                CHECK,
                f'{label}: source_dir "{value}" is not a folder of the project (it resolves to "{target}")',
                archive.file,
            )
        )
        return None
    return Zip(archive, target, inside)


def _environment_of(lambda_block):
    """Names of the Lambda environment variables, or None when they are not literal."""
    environment = nested_blocks(lambda_block.body, "environment")
    if not environment:
        return set()
    variables = environment[0].get("variables")
    if isinstance(variables, dict):
        return {k for k in variables if k != "__is_block__"}
    return None


def _policy_texts(role_name, project):
    """Texts of the policies attached to aws_iam_role.<role_name>; None if unknowable."""
    texts = []
    role = project.find(f"aws_iam_role.{role_name}")
    if role is None:
        return None
    for inline in nested_blocks(role.body, "inline_policy"):
        texts.append(str(inline.get("policy")))
    managed = role.get("managed_policy_arns")
    if managed and any(BASIC_EXECUTION_ROLE not in str(arn) for arn in managed):
        return None

    def attached_to_role(block):
        return any(
            _ROLE_REFERENCE.search(r)
            and _ROLE_REFERENCE.search(r).group(1) == role_name
            for r in block.references()
        )

    for block in project.of("resource", "aws_iam_role_policy"):
        if attached_to_role(block):
            texts.append(_policy_document(block.get("policy"), project))
    attachments = project.of("resource", "aws_iam_role_policy_attachment") + project.of(
        "resource",
        "aws_iam_policy_attachment",  # roles = [...]
    )
    for block in attachments:
        if not attached_to_role(block):
            continue
        arn = str(block.get("policy_arn"))
        policy = _POLICY_REFERENCE.search(arn)
        if policy:
            source = project.find(f"aws_iam_policy.{policy.group(1)}")
            texts.append(
                _policy_document(source.get("policy"), project) if source else ""
            )
        elif BASIC_EXECUTION_ROLE not in arn:
            return None  # a managed policy: its actions are not known here
    return texts


def _policy_document(value, project):
    text = str(value)
    document = _POLICY_DOCUMENT.search(text)
    if document:
        block = project.find(f"data.aws_iam_policy_document.{document.group(1)}")
        return str(block.body) if block else text
    return text


def _allowed(action, policy_texts):
    for text in policy_texts:
        if _WILDCARD_ACTION.search(text):
            return True
        for granted in _ACTION_TOKEN.findall(text):
            if fnmatch.fnmatch(action.lower(), granted.lower()):
                return True
    return False


def _needed_actions(zip_, files, trees):
    needed = {}
    for path in zip_.files.values():
        tree = trees.get(path)
        if tree is None:
            continue
        source = files[path]
        calls = python_model.method_calls(tree)
        for service, actions in SERVICE_ACTIONS.items():
            if f'"{service}"' not in source and f"'{service}'" not in source:
                continue
            for method, action in actions.items():
                if method in calls:
                    needed.setdefault(action, (path, calls[method]))
    return needed


def _api_integrations(project):
    """{lambda name: [integration labels]} for API Gateway proxy integrations."""
    integrated = {}
    issues = []
    for block in project.of("resource", "aws_api_gateway_integration") + project.of(
        "resource", "aws_apigatewayv2_integration"
    ):
        v2 = block.type == "aws_apigatewayv2_integration"
        kind = literal(block.get("integration_type" if v2 else "type"))
        uri = str(block.get("integration_uri" if v2 else "uri") or "")
        targets = _LAMBDA_ATTRIBUTE.findall(uri)
        for name, attribute in targets:
            integrated.setdefault(name, []).append(block.label)
            if attribute != "invoke_arn" and not (v2 and attribute == "arn"):
                issues.append(
                    error(
                        CHECK,
                        f"{block.label}: uri must be aws_lambda_function.{name}.invoke_arn "
                        f"(not .{attribute})",
                        block.file,
                    )
                )
        if kind == "AWS_PROXY" and not v2:
            method = literal(block.get("integration_http_method"))
            if method != "POST":
                issues.append(
                    error(
                        CHECK,
                        f'{block.label}: an AWS_PROXY integration calls Lambda with integration_http_method = "POST" '
                        f"(found {method or 'none'})",
                        block.file,
                    )
                )
    return integrated, issues


def _api_wiring(project, integrated):
    issues = []
    lambdas = {b.name: b for b in project.of("resource", "aws_lambda_function")}
    permissions = project.of("resource", "aws_lambda_permission")
    for name, integrations in integrated.items():
        block = lambdas.get(name)
        if block is None:
            continue  # undeclared reference: reported by the terraform stage
        function_name = literal(block.get("function_name"))
        allowed = any(
            literal(p.get("principal")) == API_GATEWAY_PRINCIPAL
            and (
                any(r == f"aws_lambda_function.{name}" for r in p.references())
                or (function_name and literal(p.get("function_name")) == function_name)
            )
            for p in permissions
        )
        if not allowed:
            issues.append(
                error(
                    CHECK,
                    f"{block.label} is called by {', '.join(integrations)} but has no "
                    f'aws_lambda_permission for principal "{API_GATEWAY_PRINCIPAL}": '
                    "API Gateway would get AccessDenied",
                    block.file,
                )
            )

    for api in project.of("resource", "aws_api_gateway_rest_api"):
        deployments = [
            d
            for d in project.of("resource", "aws_api_gateway_deployment")
            if api.address in d.references()
        ]
        if not deployments:
            issues.append(
                error(
                    CHECK,
                    f"{api.label} has no aws_api_gateway_deployment: the API is never published",
                    api.file,
                )
            )
        elif not any(
            api.address in s.references()
            for s in project.of("resource", "aws_api_gateway_stage")
        ):
            issues.append(
                error(
                    CHECK,
                    f"{api.label} has no aws_api_gateway_stage: the API has no URL",
                    api.file,
                )
            )
    return issues


def _check_lambda(block, zip_, files, trees, project, api_lambdas, issues):
    label = block.label
    handler = literal(block.get("handler"))
    if not handler or "." not in handler:
        if handler is not None:
            issues.append(
                error(
                    CHECK,
                    f'{label}: handler "{handler}" must be "<module>.<function>"',
                    block.file,
                )
            )
        return
    module, function = handler.rsplit(".", 1)
    modules = zip_.modules
    path = modules.get(module)
    if path is None:
        inside = ", ".join(sorted(zip_.files)) or "nothing"
        issues.append(
            error(
                CHECK,
                f'{label}: handler "{handler}" needs {module.replace(".", "/")}.py at the root '
                f"of the zip of {zip_.archive.label}, which contains: {inside}",
                block.file,
            )
        )
        return

    tree = trees.get(path)
    if tree is not None:
        definition = python_model.top_level_functions(tree).get(function)
        if definition is None:
            issues.append(
                error(
                    CHECK,
                    f'{label}: handler "{handler}" but {path} does not define {function}()',
                    block.file,
                )
            )
        elif not python_model.accepts_event_and_context(definition):
            issues.append(
                error(
                    CHECK,
                    f"{function}() must accept (event, context): Lambda calls it with two arguments",
                    path,
                )
            )
        elif block.name in api_lambdas:
            for line in python_model.string_returns(definition):
                issues.append(
                    error(
                        CHECK,
                        f"line {line}: {function}() returns a string; API Gateway needs a dict "
                        "with statusCode, headers and body (else it answers 502)",
                        path,
                    )
                )

    # Everything the zip imports must be in the zip or in the runtime
    local = zip_.top_level_names
    has_layers = bool(block.get("layers"))
    for packaged in sorted(zip_.modules.values()):
        packaged_tree = trees.get(packaged)
        if packaged_tree is None:
            continue
        for name, line in python_model.imported_modules(packaged_tree).items():
            if (
                name in sys.stdlib_module_names
                or name in RUNTIME_PACKAGES
                or name in local
            ):
                continue
            make = warning if has_layers else error
            issues.append(
                make(
                    CHECK,
                    f"line {line}: imports {name}, which is not in the Lambda runtime nor in the "
                    f"zip of {label} (archive_file does not install requirements.txt)",
                    packaged,
                )
            )

    # Environment variables read by the code
    environment = _environment_of(block)
    if environment is not None:
        for packaged in sorted(zip_.modules.values()):
            packaged_tree = trees.get(packaged)
            if packaged_tree is None:
                continue
            for name, required, line in python_model.environment_reads(packaged_tree):
                if name in environment or name.startswith("AWS_"):
                    continue  # AWS_REGION etc. are set by the runtime
                if required:
                    issues.append(
                        error(
                            CHECK,
                            f'line {line}: reads os.environ["{name}"], but {label} does not set '
                            f"{name} in environment {{ variables }} (KeyError at runtime)",
                            packaged,
                        )
                    )
                else:
                    issues.append(
                        warning(
                            CHECK,
                            f"line {line}: reads {name}, which {label} does not set (it will be None)",
                            packaged,
                        )
                    )

    # IAM: every AWS call must be allowed by the role of this Lambda
    role = _ROLE_REFERENCE.search(str(block.get("role") or ""))
    needed = _needed_actions(zip_, files, trees)
    if role and needed:
        policies = _policy_texts(role.group(1), project)
        if policies is not None:
            for action, (path_, line) in needed.items():
                if not _allowed(action, policies):
                    issues.append(
                        error(
                            CHECK,
                            f"line {line}: calls {action.split(':')[1]}, but the role "
                            f"aws_iam_role.{role.group(1)} of {label} does not allow "
                            f'"{action}" (AccessDenied at runtime)',
                            path_,
                        )
                    )

    # Without source_code_hash, terraform apply does not redeploy changed code
    hash_expression = expression(block.get("source_code_hash")) or ""
    hash_match = _ARCHIVE_HASH.match(hash_expression)
    if not hash_match or hash_match.group(1) != zip_.archive.name:
        issues.append(
            warning(
                CHECK,
                f"{label}: source_code_hash should be data.archive_file.{zip_.archive.name}"
                ".output_base64sha256 (else code changes are not deployed)",
                block.file,
            )
        )


def validate_deployment(files, layout, project):
    if project.syntax_errors:
        # Lambdas, archives and policies of the broken file are unknown
        return [warning(CHECK, "not checked: fix the invalid HCL first")]
    issues = []
    trees = {}
    for path in files:
        if path.endswith(".py"):
            tree = python_model.parse(files[path])
            trees[path] = None if isinstance(tree, SyntaxError) else tree

    archives = {block.name: block for block in project.of("data", "archive_file")}
    zips = {}
    for name, archive in archives.items():
        zips[name] = _zip_of(archive, files, layout, issues)

    outputs = Counter()
    for archive in archives.values():
        output = literal(archive.get("output_path"))
        target = resolve(output, archive.module_dir, layout) if output else None
        if isinstance(target, str):
            outputs[target] += 1
    for path, count in outputs.items():
        if count > 1:
            issues.append(
                error(CHECK, f'{count} archive_file blocks write the same zip "{path}"')
            )

    integrated, api_issues = _api_integrations(project)
    issues += api_issues
    deployed = set()
    all_verifiable = not project.of("module")
    lambdas = project.of("resource", "aws_lambda_function")
    if not lambdas:
        issues.append(error(CHECK, "no aws_lambda_function was generated"))

    for block in lambdas:
        filename = block.get("filename")
        reference = _ARCHIVE_OUTPUT.match(expression(filename) or "")
        if reference is None:
            if literal(filename) is not None or filename is None:
                issues.append(
                    error(
                        CHECK,
                        f"{block.label}: filename must be data.archive_file.<name>.output_path "
                        f"(found {literal(filename) or 'nothing'})",
                        block.file,
                    )
                )
            else:
                all_verifiable = False
                issues.append(
                    warning(
                        CHECK,
                        f"{block.label}: filename is built from variables, its code could not be verified",
                        block.file,
                    )
                )
            continue
        if reference.group(1) not in archives:
            continue  # undeclared reference: reported by the terraform stage
        zip_ = zips[reference.group(1)]
        if zip_ is None:
            continue  # missing source: already reported
        if not zip_.verifiable:
            all_verifiable = False
            continue
        deployed.update(zip_.files.values())
        _check_lambda(block, zip_, files, trees, project, integrated, issues)

    issues += _api_wiring(project, integrated)

    if all_verifiable:
        for path in sorted(p for p in files if p.endswith(".py") and p not in deployed):
            issues.append(
                warning(
                    CHECK,
                    "not packaged by any aws_lambda_function (never deployed)",
                    path,
                )
            )
    return issues

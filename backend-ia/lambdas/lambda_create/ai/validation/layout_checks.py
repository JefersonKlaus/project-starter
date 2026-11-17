"""Stage 3: the files are where the project layout says.

The layout comes from the reference project the RAG retrieved (ai/project_layout.py)
or is the default one: Terraform root module in layout.terraform_dir, Lambda code in
layout.python_dir, one file (<action>.py) or one folder (<action>/<handler_file>) per
Lambda, zips under layout.build_dir.
"""

import posixpath

from ..code_linker import resolve
from ..project_layout import handler_function_of, is_under, join
from .issues import error, warning
from .terraform_model import literal

CHECK = "layout"
ROOT_FILES = ("main.tf", "variables.tf", "outputs.tf")


def _standard(layout):
    if layout.origin == "rag":
        sources = ", ".join(layout.references)
        return (
            f"the RAG reference project ({sources})"
            if sources
            else "the RAG reference project"
        )
    return "the default project layout"


def _folder(path):
    return f"`{path}/`" if path else "the project root"


def _terraform_placement(files, layout, project, standard):
    issues = []
    root = layout.terraform_dir
    for name in ROOT_FILES:
        path = join(root, name)
        if path not in files:
            make = error if name == "main.tf" else warning
            issues.append(
                make(
                    CHECK,
                    f"{path} is missing: Terraform lives in {_folder(root)} in {standard}",
                )
            )

    module_dirs = set()
    for block in project.of("module"):
        source = literal(block.get("source"))
        target = resolve(source, block.module_dir, layout) if source else None
        if isinstance(target, str):
            module_dirs.add(target)

    for path in sorted(p for p in files if p.endswith(".tf")):
        folder = posixpath.dirname(path)
        if folder == root or folder in module_dirs:
            continue
        if is_under(path, root):
            issues.append(
                error(
                    CHECK,
                    f"Terraform only reads the .tf files of {_folder(root)}: this file is in a "
                    "subfolder that no module block uses",
                    path,
                )
            )
        else:
            issues.append(
                error(
                    CHECK,
                    f"Terraform file outside {_folder(root)}, the Terraform folder of {standard}",
                    path,
                )
            )
    return issues


def _python_placement(files, layout, standard):
    issues = []
    code_root = layout.python_dir
    for path in sorted(p for p in files if p.endswith(".py")):
        if not is_under(path, code_root):
            issues.append(
                error(
                    CHECK,
                    f"Lambda code outside {_folder(code_root)}, the code folder of {standard}",
                    path,
                )
            )
            continue
        function = handler_function_of(path, files[path])
        if not function:
            continue  # helper module
        if layout.lambda_per_folder:
            relative = path[len(code_root) + 1 :] if code_root else path
            parts = relative.split("/")
            expected = f"{join(code_root, '<action>')}/{layout.handler_file}"
            if len(parts) != 2 or parts[1] != layout.handler_file:
                issues.append(
                    error(
                        CHECK,
                        f"each Lambda has its own folder in {standard}: expected {expected}",
                        path,
                    )
                )
        elif posixpath.dirname(path) != code_root:
            issues.append(
                error(
                    CHECK,
                    f"each Lambda is one file directly in {_folder(code_root)} in {standard}: "
                    f"expected {join(code_root, posixpath.basename(path))}",
                    path,
                )
            )
        if function != layout.handler_function:
            issues.append(
                warning(
                    CHECK,
                    f"handler function is {function}(), {standard} uses {layout.handler_function}()",
                    path,
                )
            )
    return issues


def _zip_placement(layout, project, standard):
    issues = []
    build_dir = join(layout.terraform_dir, layout.build_dir)
    for block in project.of("data", "archive_file"):
        output = literal(block.get("output_path"))
        target = resolve(output, block.module_dir, layout) if output else None
        if isinstance(target, str) and not is_under(target, build_dir):
            issues.append(
                warning(
                    CHECK,
                    f"{block.label}: zips go to {_folder(build_dir)} in {standard}",
                    block.file,
                )
            )
    return issues


def validate_layout(files, layout, project):
    standard = _standard(layout)
    return (
        _terraform_placement(files, layout, project, standard)
        + _python_placement(files, layout, standard)
        + _zip_placement(layout, project, standard)
    )

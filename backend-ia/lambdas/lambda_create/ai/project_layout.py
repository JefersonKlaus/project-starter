"""Where the files of the generated project are saved.

The layout is NOT fixed: it follows the architecture of the reference project the RAG
retrieved (where its Terraform lives, where its Lambda code lives, one file or one
folder per Lambda, handler file/function names, where the zips are built).

Only when the RAG brings nothing usable (no reference, or references without a
Terraform + Lambda Python structure) the DEFAULT_LAYOUT is used:

    <project>/
      main.tf, variables.tf, outputs.tf   Terraform root module
      lambda/<action>.py                  one file per Lambda
      build/<action>.zip                  created by terraform (data "archive_file")

Every path in this module is a POSIX path relative to the project root ("" = root).
"""

import posixpath
import re
from collections import Counter
from dataclasses import asdict, dataclass, replace

# File names that say "this folder is one Lambda" rather than naming the action
GENERIC_HANDLER_FILES = (
    "handler.py",
    "lambda_function.py",
    "main.py",
    "app.py",
    "index.py",
)

_HANDLER_DEF = re.compile(
    r"^(?:async[ \t]+)?def[ \t]+([A-Za-z_]\w*)[ \t]*\("
    r"(?:[ \t]*_?event\b[^,)]*,[ \t]*_?context\b)?",
    re.M,
)
_ROOT_MODULE = re.compile(r'^[ \t]*(?:provider[ \t]+"?aws"?|terraform)[ \t]*\{', re.M)
_OUTPUT_PATH = re.compile(
    r'output_path[ \t]*=[ \t]*"\$\{path\.(?:module|root)\}/([^"$]*)'
)


# ------------------------------------------------------------------ paths


def normalize_path(path) -> str:
    """POSIX, relative, without "." parts: 'C:\\repo\\.\\infra\\main.tf' -> 'repo/infra/main.tf'."""
    text = re.sub(r"^[A-Za-z]:", "", str(path or "").replace("\\", "/").strip())
    return "/".join(part for part in text.split("/") if part not in ("", "."))


def join(directory: str, name: str) -> str:
    return f"{directory}/{name}" if directory and name else directory or name


def relative(target: str, start: str) -> str:
    """Relative POSIX path from directory start to target (both project-relative)."""
    return posixpath.relpath(target or ".", start or ".")


def module_path(target: str, module_dir: str) -> str:
    """Terraform expression for target as seen from a .tf file in module_dir."""
    rel = relative(target, module_dir)
    return "${path.module}" if rel == "." else "${path.module}/" + rel


def is_under(path: str, directory: str) -> bool:
    return not directory or path.startswith(directory + "/")


def handler_function_of(path: str, source: str):
    """Name of the Lambda handler defined in a Python file, or None if it is not one."""
    if not path.endswith(".py"):
        return None
    names = []
    for match in _HANDLER_DEF.finditer(source or ""):
        if match.group(0).rstrip().endswith("(") and match.group(1) != "lambda_handler":
            continue  # a plain function, not (event, context)
        names.append(match.group(1))
    if "lambda_handler" in names:
        return "lambda_handler"
    return names[0] if names else None


# ----------------------------------------------------------------- layout


@dataclass(frozen=True)
class ProjectLayout:
    terraform_dir: str = ""  # Terraform root module ("" = project root)
    python_dir: str = "lambda"  # root of the Lambda code
    lambda_per_folder: bool = (
        False  # <python_dir>/<action>/<handler_file> vs <python_dir>/<action>.py
    )
    handler_file: str = "handler.py"  # only used when lambda_per_folder
    handler_function: str = "lambda_handler"
    build_dir: str = "build"  # where the zips go, relative to terraform_dir
    origin: str = "default"  # "rag" or "default"
    references: tuple = ()  # RAG sources the layout was derived from
    note: str = ""  # why the default layout was used

    # project paths of the dictionary keys returned by the model
    def terraform_path(self, key: str) -> str:
        return join(self.terraform_dir, key)

    def python_path(self, key: str) -> str:
        return join(self.python_dir, key)

    @property
    def handler_module(self) -> str:
        return posixpath.splitext(self.handler_file)[0]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["references"] = list(self.references)
        return data

    def describe(self) -> str:
        """[ESTRUTURA DO PROJETO] section of the prompt (Portuguese, like the rules)."""
        if self.origin == "rag":
            origin = (
                "arquitetura do projeto de referência do RAG ("
                + ", ".join(self.references)
                + ")"
            )
        else:
            origin = "estrutura padrão (o RAG não trouxe uma estrutura de projeto de referência)"
        terraform = (
            f"`{self.terraform_dir}/`" if self.terraform_dir else "a raiz do projeto"
        )
        code_root = f"{self.python_dir}/" if self.python_dir else ""
        code_from_tf = module_path(self.python_dir, self.terraform_dir)
        if self.lambda_per_folder:
            code = (
                f"uma pasta por Lambda, `{code_root}<acao>/{self.handler_file}` "
                f'(chave no dicionário `python`: "<acao>/{self.handler_file}"; módulos auxiliares '
                "da Lambda ficam na mesma pasta)"
            )
            source = f'source_dir  = "{code_from_tf}/<acao>"'
            handler = f"{self.handler_module}.{self.handler_function}"
        else:
            code = f'um arquivo por Lambda, `{code_root}<acao>.py` (chave no dicionário `python`: "<acao>.py")'
            source = f'source_file = "{code_from_tf}/<acao>.py"'
            handler = f"<acao>.{self.handler_function}"
        build = "${path.module}/" + self.build_dir
        return (
            f"Origem: {origin}.\n"
            f"- Terraform em {terraform}: as chaves do dicionário `terraform` são caminhos relativos a essa "
            f'pasta (ex: "main.tf") e `${{path.module}}` é essa pasta.\n'
            f"- Código das Lambdas: {code}.\n"
            f"- Cada Lambda define `def {self.handler_function}(event, context):`.\n"
            "- Empacotamento de cada Lambda:\n"
            f'    data "archive_file" "<acao>" {{\n'
            f'      type        = "zip"\n'
            f"      {source}\n"
            f'      output_path = "{build}/<acao>.zip"\n'
            "    }\n"
            f'  e na `aws_lambda_function`: handler = "{handler}", '
            "filename = data.archive_file.<acao>.output_path, "
            "source_code_hash = data.archive_file.<acao>.output_base64sha256"
        )


DEFAULT_LAYOUT = ProjectLayout()


# -------------------------------------------------------------- inference


def _ancestors(directory: str):
    """'a/b' -> ['a/b', 'a', '']"""
    while directory:
        yield directory
        directory = posixpath.dirname(directory)
    yield ""


def _depth(directory: str) -> int:
    return len(directory.split("/")) if directory else 0


def _most_common(counter: Counter):
    """Most frequent key; ties go to the shallowest path, then alphabetical (deterministic)."""

    def depth(key):
        return _depth(key[0] if isinstance(key, tuple) else key)

    return min(counter, key=lambda key: (-counter[key], depth(key), key))


def _layout_from(root, terraform, handlers, references) -> ProjectLayout:
    def rel(path):
        return path[len(root) + 1 :] if root else path

    terraform = {rel(path): content for path, content in terraform.items()}
    handlers = {rel(path): name for path, name in handlers.items()}

    # Terraform root module: the shallowest folder with a provider/terraform block
    roots = [
        posixpath.dirname(p) for p, c in terraform.items() if _ROOT_MODULE.search(c)
    ]
    terraform_dir = min(
        roots or map(posixpath.dirname, terraform), key=lambda d: (_depth(d), d)
    )

    # Lambda code, the dominant pattern wins:
    #  one file per Lambda   -> many handlers side by side in one folder (src/create.py, src/list.py)
    #  one folder per Lambda -> many sibling folders with the same handler file (lambdas/*/handler.py)
    side_by_side = Counter(posixpath.dirname(path) for path in handlers)
    flat_dir = _most_common(side_by_side)
    siblings = Counter(
        (posixpath.dirname(posixpath.dirname(path)), posixpath.basename(path))
        for path in handlers
        if posixpath.dirname(path)
    )
    folders_parent, handler_file = _most_common(siblings) if siblings else ("", "")
    folder_count = siblings[(folders_parent, handler_file)] if siblings else 0
    if folder_count >= 2:
        per_folder = folder_count >= side_by_side[flat_dir]
    else:  # a single Lambda in the reference: a generic file name means "its own folder"
        per_folder = (
            side_by_side[flat_dir] == 1
            and folder_count == 1
            and handler_file in GENERIC_HANDLER_FILES
        )

    if per_folder:
        python_dir = folders_parent
        pattern = [
            p
            for p in handlers
            if p.endswith("/" + handler_file) and is_under(p, python_dir)
        ]
    else:
        python_dir = flat_dir
        pattern = [p for p in handlers if posixpath.dirname(p) == flat_dir]

    # Where the reference builds its zips (output_path = "${path.module}/<dir>/...")
    build_dirs = Counter(
        posixpath.dirname(match.group(1))
        for content in terraform.values()
        for match in _OUTPUT_PATH.finditer(content)
        if posixpath.dirname(match.group(1))
    )

    return ProjectLayout(
        terraform_dir=terraform_dir,
        python_dir=python_dir,
        lambda_per_folder=per_folder,
        handler_file=handler_file if per_folder else DEFAULT_LAYOUT.handler_file,
        handler_function=_most_common(Counter(handlers[p] for p in pattern)),
        build_dir=_most_common(build_dirs) if build_dirs else DEFAULT_LAYOUT.build_dir,
        origin="rag",
        references=tuple(references),
    )


def infer_layout(retrieved, index_documents=()) -> ProjectLayout:
    """Layout of the reference project behind the documents the RAG retrieved.

    retrieved: documents returned for the prompt (best match first); each one is a
    reference file whose path is metadata["source"]. index_documents: the whole RAG
    index, used to see the sibling files of the retrieved ones (the search returns only
    a few files, e.g. the Terraform but not the Lambda code of the same project).

    The reference project root is the deepest folder, walking up from a retrieved file,
    that contains both Terraform files and Lambda handlers. Falls back to DEFAULT_LAYOUT.
    """
    references = [normalize_path(doc.metadata.get("source")) for doc in retrieved]
    references = [path for path in references if path]
    if not references:
        return replace(DEFAULT_LAYOUT, note="the RAG returned no reference files")

    corpus = {}
    for doc in [*retrieved, *index_documents]:
        path = normalize_path(doc.metadata.get("source"))
        if path:
            corpus.setdefault(path, doc.page_content)
    handler_names = {
        path: handler_function_of(path, content) for path, content in corpus.items()
    }

    for anchor in references:
        for root in _ancestors(posixpath.dirname(anchor)):
            terraform = {
                p: c
                for p, c in corpus.items()
                if p.endswith(".tf") and is_under(p, root)
            }
            handlers = {
                p: n for p, n in handler_names.items() if n and is_under(p, root)
            }
            if terraform and handlers:
                used = [path for path in references if is_under(path, root)]
                return _layout_from(root, terraform, handlers, used)

    return replace(
        DEFAULT_LAYOUT,
        note="the RAG references have no project with both Terraform and Lambda (Python) files",
    )

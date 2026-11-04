"""Make the generated Terraform package and invoke the Python files that were generated.

The model decides the paths inside its Terraform (following the ProjectLayout it was
given), and often gets them wrong: a source_file pointing to a folder that does not
exist, a handler naming a module that is not in the zip, several Lambdas sharing one
zip, a .py used directly as `filename`...

Nothing here imposes a layout. Each literal path is resolved the way Terraform does
(relative to the .tf file that contains it) against the files that were really
generated, and only broken links are rewritten. Repairs only touch the attributes that
link the two sides (archive_file source_file / source_dir / output_path and
aws_lambda_function filename / source_code_hash / handler). Anything that cannot be
repaired safely is returned as an issue instead of being guessed.
"""

import logging
import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field

from .project_layout import (
    DEFAULT_LAYOUT,
    ProjectLayout,
    handler_function_of,
    is_under,
    join,
    module_path,
    normalize_path,
    relative,
)

logger = logging.getLogger(__name__)


def python_functions(source: str) -> set:
    """Names of the top-level functions defined in a Python file."""
    return set(
        re.findall(r"^(?:async[ \t]+)?def[ \t]+([A-Za-z_]\w*)[ \t]*\(", source, re.M)
    )


# -------------------------------------------------------------- dictionary keys


def _clean_key(raw_name):
    """Relative POSIX path, or None when it is empty or tries to leave its folder."""
    key = normalize_path(raw_name)
    if not key or ".." in key.split("/"):
        return None
    return key


def _strip_prefix(key: str, prefix: str) -> str:
    """The model sometimes repeats the layout folder in the key ("infra/main.tf")."""
    return key[len(prefix) + 1 :] if prefix and key.startswith(prefix + "/") else key


def _normalize_keys(files, group, prefix, issues):
    normalized = {}
    for raw_name, content in files.items():
        key = _clean_key(raw_name)
        if key is None:
            issues.append(f"{group}: discarded file with invalid name {raw_name!r}")
            continue
        key = _strip_prefix(key, prefix)
        if key in normalized:
            issues.append(
                f"{group}: {raw_name!r} collides with another file {key!r}; kept the first one"
            )
            continue
        normalized[key] = content
    return normalized


def _normalize_python_keys(files, layout, fixes, issues):
    """Keys relative to layout.python_dir, shaped like the layout expects."""
    keys = _normalize_keys(files, "python", layout.python_dir, issues)
    result = {}
    basenames = Counter(posixpath.basename(key) for key in keys)
    for key, content in keys.items():
        new_key = key
        if layout.lambda_per_folder:
            # "create_item.py" -> "create_item/handler.py" (one folder per Lambda)
            stem = posixpath.splitext(key)[0]
            if (
                "/" not in key
                and handler_function_of(key, content)
                and stem != layout.handler_module
            ):
                new_key = f"{stem}/{layout.handler_file}"
        elif "/" in key and basenames[posixpath.basename(key)] == 1:
            new_key = posixpath.basename(
                key
            )  # one file per Lambda, directly in python_dir
        if new_key != key:
            if new_key in keys or new_key in result:
                new_key = key
            else:
                fixes.append(
                    f'python: "{key}" saved as "{new_key}" to follow the project layout'
                )
        result[new_key] = content
    return result


# ------------------------------------------------------------------- HCL scan

_BLOCK_HEADER = re.compile(
    r'^[ \t]*(resource|data|module)[ \t]+"?([\w-]+)"?(?:[ \t]+"?([\w-]+)"?)?[ \t]*\{',
    re.M,
)
_HEREDOC = re.compile(r"<<-?([A-Za-z_]\w*)[ \t]*\r?\n")


def _block_end(text: str, open_brace: int) -> int:
    """Index just after the "}" that closes the "{" at open_brace.

    Understands strings (with ${...} / %{...} templates nested inside), comments and
    heredocs, so braces inside them are not counted.
    """
    stack = ["code"]
    i = open_brace + 1
    n = len(text)
    while i < n:
        c = text[i]
        if stack[-1] == "string":
            if c == "\\":
                i += 2
                continue
            if text.startswith(("$${", "%%{"), i):
                i += 3
                continue
            if c in "$%" and text.startswith("{", i + 1):
                stack.append("code")
                i += 2
                continue
            if c in '"\n':  # HCL strings cannot span lines: recover on newline
                stack.pop()
            i += 1
            continue

        if c == '"':
            stack.append("string")
        elif c == "{":
            stack.append("code")
        elif c == "}":
            stack.pop()
            if not stack:
                return i + 1
        elif c == "#" or text.startswith("//", i):
            newline = text.find("\n", i)
            i = n if newline == -1 else newline
            continue
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2)
            i = n if close == -1 else close + 2
            continue
        elif text.startswith("<<", i):
            heredoc = _HEREDOC.match(text, i)
            if heredoc:
                marker = re.compile(
                    rf"^[ \t]*{re.escape(heredoc.group(1))}[ \t]*$", re.M
                )
                close = marker.search(text, heredoc.end())
                i = n if close is None else close.end()
                continue
        i += 1
    return n


@dataclass
class Block:
    file: str  # project path of the .tf file
    kind: str  # "resource", "data" or "module"
    type: str
    name: str
    start: int
    end: int
    text: str

    @property
    def module_dir(self) -> str:
        return posixpath.dirname(self.file)


def find_blocks(terraform: dict, kind: str, type_: str = None) -> list:
    blocks = []
    for file_name, text in terraform.items():
        position = 0
        while True:
            header = _BLOCK_HEADER.search(text, position)
            if not header:
                break
            end = _block_end(text, header.end() - 1)
            block_kind, block_type, block_name = header.groups()
            if block_kind == "module":
                block_type, block_name = None, block_type
            if block_kind == kind and (type_ is None or block_type == type_):
                blocks.append(
                    Block(
                        file_name,
                        block_kind,
                        block_type,
                        block_name,
                        header.start(),
                        end,
                        text[header.start() : end],
                    )
                )
            position = end
    return blocks


def _attribute(name: str) -> re.Pattern:
    """Matches `name = <expression until end of line>`; group 1 is the expression."""
    return re.compile(rf"^[ \t]*{name}[ \t]*=[ \t]*(.+?)[ \t\r]*$", re.M)


def _string_value(expression):
    match = re.fullmatch(r'"([^"]*)"', expression or "")
    return match.group(1) if match else None


def _get(block_text: str, name: str):
    match = _attribute(name).search(block_text)
    return match.group(1) if match else None


def _set(block_text: str, name: str, expression: str, after: str = None) -> str:
    """Replace attribute `name`, or insert it after attribute `after` (default: first line)."""
    match = _attribute(name).search(block_text)
    if match:
        return block_text[: match.start(1)] + expression + block_text[match.end(1) :]
    anchor = _attribute(after).search(block_text) if after else None
    position = anchor.end() if anchor else block_text.index("{") + 1
    return block_text[:position] + f"\n  {name} = {expression}" + block_text[position:]


def _apply(terraform: dict, replacements: list) -> None:
    """Apply (block, new_text) replacements, back to front in each file."""
    for block, new_text in sorted(
        replacements, key=lambda item: (item[0].file, item[0].start), reverse=True
    ):
        text = terraform[block.file]
        terraform[block.file] = text[: block.start] + new_text + text[block.end :]


# ---------------------------------------------------------------- path logic

DYNAMIC = object()  # the path depends on variables: it cannot be checked here


def resolve(value: str, module_dir: str, layout: ProjectLayout):
    """Project path a literal Terraform path points to.

    Returns DYNAMIC for expressions with variables, None for paths outside the project.
    Like Terraform: ${path.module} is the folder of the .tf file, ${path.root} and plain
    relative paths are the root module (where terraform runs).
    """
    if value is None:
        return None
    if value.startswith("${path.module}"):
        base, rest = module_dir, value[len("${path.module}") :]
    elif value.startswith(("${path.root}", "${path.cwd}")):
        base, rest = layout.terraform_dir, value.split("}", 1)[1]
    elif value.startswith("/"):
        return None
    else:
        base, rest = layout.terraform_dir, value
    if "${" in rest:
        return DYNAMIC
    path = posixpath.normpath(posixpath.join(base or ".", rest.lstrip("/")))
    if path == ".":
        return ""
    if path == ".." or path.startswith("../"):
        return None
    return path


def _module_name(path: str, zip_root: str) -> str:
    """Python module name of a file inside a zip built from zip_root."""
    return posixpath.splitext(relative(path, zip_root))[0].replace("/", ".")


def _names_of(path: str, code_root: str) -> set:
    """Names a Lambda may be referred by: its file stem, and its folder when the folder
    is the Lambda's own (below the code root, e.g. lambdas/create_item/handler.py)."""
    names = {posixpath.splitext(posixpath.basename(path))[0]}
    folder = posixpath.dirname(path)
    if folder != code_root and is_under(folder, code_root):
        names.add(posixpath.basename(folder))
    return names


def _pick(candidates, hints, code_root, single_is_match=False):
    """The single candidate path whose stem or folder matches one of the hints (in order).

    single_is_match: the candidates were already narrowed down (e.g. same file name), so
    a lone candidate is the answer. Otherwise a name must match: never a blind guess.
    """
    candidates = sorted(candidates)
    if single_is_match and len(candidates) == 1:
        return candidates[0]
    for hint in hints:
        if not hint:
            continue
        for variant in dict.fromkeys((hint, hint.replace("-", "_"))):
            matches = [
                path for path in candidates if variant in _names_of(path, code_root)
            ]
            if len(matches) == 1:
                return matches[0]
    return None


@dataclass
class Archive:
    block: Block
    text: str
    modules: dict = field(default_factory=dict)  # python module name -> project path
    zip_root: str = None  # folder whose content is at the zip root
    dynamic: bool = False


# ------------------------------------------------------------------ archives


def _link_archive(block, python, layout, fixes, issues) -> Archive:
    text = block.text
    archive = Archive(block, text)
    label = f"archive_file.{block.name}"
    py_files = [path for path in python if path.endswith(".py")]
    entry_files = [
        path for path in py_files if handler_function_of(path, python[path])
    ] or py_files

    source_file = _get(text, "source_file")
    source_dir = _get(text, "source_dir")
    if source_file is not None:
        value = _string_value(source_file)
        target = (
            resolve(value, block.module_dir, layout) if value is not None else DYNAMIC
        )
        if target is DYNAMIC:
            archive.dynamic = True
            return archive
        if target not in python:
            wanted = value
            same_name = [
                p
                for p in py_files
                if posixpath.basename(p) == posixpath.basename(wanted)
            ]
            target = _pick(
                same_name or entry_files,
                [
                    posixpath.splitext(posixpath.basename(wanted))[0],
                    posixpath.basename(posixpath.dirname(wanted)),
                    block.name,
                ],
                layout.python_dir,
                single_is_match=bool(same_name),
            )
            if target is None:
                issues.append(
                    f'{label}: source_file "{wanted}" does not match any generated Python file '
                    f"({', '.join(sorted(py_files)) or 'none'})"
                )
                return archive
            expected = module_path(target, block.module_dir)
            text = _set(text, "source_file", f'"{expected}"')
            fixes.append(f'{label}: source_file "{wanted}" -> "{expected}"')
        archive.zip_root = posixpath.dirname(target)
        archive.modules = {_module_name(target, archive.zip_root): target}

    elif source_dir is not None:
        value = _string_value(source_dir)
        target = (
            resolve(value, block.module_dir, layout) if value is not None else DYNAMIC
        )
        if target is DYNAMIC:
            archive.dynamic = True
            return archive
        if target is None or not any(is_under(p, target) for p in python):
            folders = {posixpath.dirname(p) for p in py_files}
            target = _pick(
                folders,
                [posixpath.basename(value or ""), block.name],
                layout.python_dir,
            )
            if (
                target is None
                and not layout.lambda_per_folder
                and layout.python_dir in folders
            ):
                target = layout.python_dir
            if target is None:
                issues.append(
                    f"{label}: source_dir {source_dir} does not match any folder of generated Python files "
                    f"({', '.join(sorted(folders)) or 'none'})"
                )
                return archive
            expected = module_path(target, block.module_dir)
            text = _set(text, "source_dir", f'"{expected}"')
            fixes.append(f'{label}: source_dir {source_dir} -> "{expected}"')
        archive.zip_root = target
        archive.modules = {
            _module_name(p, target): p for p in py_files if is_under(p, target)
        }

    else:
        # inline `source { content = ...  filename = "x.py" }` blocks: names inside the zip
        for name in re.findall(r'^[ \t]*filename[ \t]*=[ \t]*"([^"]+)"', text, re.M):
            if name.endswith(".py"):
                match = _pick(
                    [
                        p
                        for p in py_files
                        if posixpath.basename(p) == posixpath.basename(name)
                    ],
                    [],
                    layout.python_dir,
                    single_is_match=True,
                )
                archive.modules[_module_name(name, "")] = match
        archive.dynamic = not archive.modules

    archive.text = text
    return archive


def _fix_output_paths(archives, layout, fixes):
    """One zip per archive, never inside the folder being zipped (else it zips itself)."""
    resolved = {}
    for archive in archives:
        value = _string_value(_get(archive.text, "output_path"))
        resolved[archive.block.name] = (
            resolve(value, archive.block.module_dir, layout) if value else None
        )
    counts = Counter(path for path in resolved.values() if isinstance(path, str))

    for archive in archives:
        if archive.dynamic and _get(archive.text, "output_path"):
            continue
        block = archive.block
        current = _get(archive.text, "output_path")
        path = resolved[block.name]
        inside_source = (
            isinstance(path, str)
            and archive.zip_root is not None
            and is_under(path, archive.zip_root)
        )
        if path is DYNAMIC or (
            path is not None and counts[path] == 1 and not inside_source
        ):
            continue
        value = _string_value(current)
        folder = value.rsplit("/", 1)[0] if value and "/" in value else None
        if (
            folder
            and folder not in ("${path.module}", "${path.root}")
            and not inside_source
        ):
            expected = (
                f"{folder}/{block.name}.zip"  # keep the build folder the model chose
            )
        else:
            expected = (
                module_path(
                    join(layout.terraform_dir, layout.build_dir), block.module_dir
                )
                + f"/{block.name}.zip"
            )
        if value != expected:
            archive.text = _set(archive.text, "output_path", f'"{expected}"')
            fixes.append(
                f'archive_file.{block.name}: output_path {current or "(missing)"} -> "{expected}"'
            )


def _new_archive(name, py_file, module_dir, python, layout) -> Archive:
    """archive_file for a Lambda that has none, packaged the way the layout says."""
    folder = posixpath.dirname(py_file)
    if layout.lambda_per_folder and folder != layout.python_dir:
        source = f'source_dir  = "{module_path(folder, module_dir)}"'
        packaged = [p for p in python if p.endswith(".py") and is_under(p, folder)]
    else:
        source = f'source_file = "{module_path(py_file, module_dir)}"'
        packaged = [py_file]
    output = (
        module_path(join(layout.terraform_dir, layout.build_dir), module_dir)
        + f"/{name}.zip"
    )
    text = f'\ndata "archive_file" "{name}" {{\n  type        = "zip"\n  {source}\n  output_path = "{output}"\n}}\n'
    return Archive(
        None,
        text,
        modules={_module_name(p, folder): p for p in packaged},
        zip_root=folder,
    )


# ------------------------------------------------------------------- lambdas

_ARCHIVE_REF = re.compile(r"^data\.archive_file\.([\w-]+)\.output_path$")


def _link_lambdas(terraform, python, archives, layout, fixes, issues) -> set:
    """Link each aws_lambda_function to its zip and handler; return the packaged .py in use."""
    py_files = [path for path in python if path.endswith(".py")]
    # a Lambda is matched to a file that is an entry point, not to its helper modules
    entry_files = [
        path for path in py_files if handler_function_of(path, python[path])
    ] or py_files
    replacements = []
    appended = {}
    deployed = set()

    for block in find_blocks(terraform, "resource", "aws_lambda_function"):
        text = block.text
        label = f"aws_lambda_function.{block.name}"
        function_name = _string_value(_get(text, "function_name"))
        handler = _string_value(_get(text, "handler"))
        module, _, function = (handler or "").rpartition(".")

        # 1. filename must be the output of an archive_file that exists
        filename = _get(text, "filename") or ""
        ref = _ARCHIVE_REF.match(filename)
        archive = archives.get(ref.group(1)) if ref else None
        if archive is None:
            if filename and not _string_value(filename) and not ref:
                continue  # variables (e.g. inside a module): cannot be checked here
            literal = _string_value(filename) or ""
            py_file = _pick(
                entry_files,
                [
                    posixpath.splitext(posixpath.basename(literal))[0],
                    module.rsplit(".", 1)[-1] if module else None,
                    block.name,
                    function_name,
                ],
                layout.python_dir,
            )
            if py_file is None:
                issues.append(
                    f"{label}: filename {filename or '(missing)'} is not a data.archive_file output "
                    "and no generated Python file matches this Lambda"
                )
                continue
            existing = [
                a
                for a in archives.values()
                if py_file in a.modules.values() and len(a.modules) == 1
            ]
            if existing:
                archive = existing[0]
            else:
                name = re.sub(r"\W", "_", block.name)
                while name in archives:
                    name += "_zip"
                archive = _new_archive(name, py_file, block.module_dir, python, layout)
                archives[name] = archive
                appended.setdefault(block.file, []).append(archive.text)
                fixes.append(
                    f'{label}: created data.archive_file.{name} for "{py_file}"'
                )
            archive_name = next(n for n, a in archives.items() if a is archive)
            expected = f"data.archive_file.{archive_name}.output_path"
            text = _set(text, "filename", expected)
            fixes.append(f"{label}: filename {filename or '(missing)'} -> {expected}")
        archive_name = next(n for n, a in archives.items() if a is archive)

        # 2. source_code_hash must follow the same archive (redeploy when the code changes)
        expected_hash = f"data.archive_file.{archive_name}.output_base64sha256"
        current_hash = _get(text, "source_code_hash")
        if current_hash != expected_hash:
            text = _set(text, "source_code_hash", expected_hash, after="filename")
            fixes.append(
                f"{label}: source_code_hash {current_hash or '(missing)'} -> {expected_hash}"
            )

        # 3. handler = "<module inside the zip>.<function defined in that module>"
        if archive.dynamic or (handler is None and _get(text, "handler")):
            deployed.update(p for p in archive.modules.values() if p)
            if text != block.text:
                replacements.append((block, text))
            continue
        deployed.update(p for p in archive.modules.values() if p)
        if module not in archive.modules:
            entry_points = [
                m
                for m, p in archive.modules.items()
                if p and handler_function_of(p, python[p])
            ]
            if len(archive.modules) == 1:
                module = next(iter(archive.modules))
            elif len(entry_points) == 1:
                module = entry_points[0]
            else:
                by_path = _pick(
                    [
                        archive.modules[m]
                        for m in entry_points or archive.modules
                        if archive.modules[m]
                    ],
                    [
                        module.rsplit(".", 1)[-1] if module else None,
                        block.name,
                        function_name,
                    ],
                    layout.python_dir,
                )
                module = next(
                    (m for m, p in archive.modules.items() if p == by_path), module
                )
        py_file = archive.modules.get(module)
        if module not in archive.modules:
            issues.append(
                f'{label}: handler "{handler}" does not match any module packaged in '
                f"data.archive_file.{archive_name} ({', '.join(sorted(archive.modules)) or 'none'})"
            )
        elif py_file is not None:
            defined = python_functions(python[py_file])
            if function not in defined:
                function = next(
                    (
                        name
                        for name in (
                            layout.handler_function,
                            "lambda_handler",
                            "handler",
                        )
                        if name in defined
                    ),
                    function,
                )
            if function not in defined:
                issues.append(
                    f'{label}: "{py_file}" does not define the handler function '
                    f'"{function or layout.handler_function}"'
                )
            expected_handler = f"{module}.{function or layout.handler_function}"
            if handler != expected_handler:
                text = _set(text, "handler", f'"{expected_handler}"')
                fixes.append(f'{label}: handler "{handler}" -> "{expected_handler}"')

        if text != block.text:
            replacements.append((block, text))

    _apply(terraform, replacements)
    for file_name, blocks in appended.items():
        terraform[file_name] = (
            terraform[file_name].rstrip("\n") + "\n" + "".join(blocks)
        )
    return deployed


# ---------------------------------------------------------------------- entry


def link_generated_code(
    generated_code: dict, layout: ProjectLayout = DEFAULT_LAYOUT
) -> list:
    """Normalize the file keys and link Terraform <-> Python in place.

    generated_code["terraform"] / ["python"] keep keys relative to the layout folders;
    generated_code["files"] gets {project path: content}, the tree to save to disk.
    Returns the problems that could not be repaired (empty list = consistent).
    """
    issues = []
    fixes = []
    terraform_keys = _normalize_keys(
        generated_code.get("terraform") or {}, "terraform", layout.terraform_dir, issues
    )
    python_keys = _normalize_python_keys(
        generated_code.get("python") or {}, layout, fixes, issues
    )

    terraform = {
        layout.terraform_path(key): content for key, content in terraform_keys.items()
    }
    python = {layout.python_path(key): content for key, content in python_keys.items()}

    archives = {
        block.name: _link_archive(block, python, layout, fixes, issues)
        for block in find_blocks(terraform, "data", "archive_file")
    }
    _fix_output_paths(list(archives.values()), layout, fixes)
    _apply(
        terraform,
        [(a.block, a.text) for a in archives.values() if a.text != a.block.text],
    )
    deployed = _link_lambdas(terraform, python, archives, layout, fixes, issues)

    # Lambdas built through modules/variables cannot be followed: do not accuse their files
    verifiable = not find_blocks(terraform, "module") and not any(
        a.dynamic for a in archives.values()
    )
    if verifiable:
        for path in sorted(
            p for p in python if p.endswith(".py") and p not in deployed
        ):
            issues.append(
                f'python: "{path}" is not packaged by any aws_lambda_function'
            )

    for fix in fixes:
        logger.info("Linked generated code: %s", fix)
    for issue in issues:
        logger.warning("Generated code issue: %s", issue)

    generated_code["terraform"] = {
        key: terraform[layout.terraform_path(key)] for key in terraform_keys
    }
    generated_code["python"] = python_keys
    generated_code["files"] = {**terraform, **python}
    return issues

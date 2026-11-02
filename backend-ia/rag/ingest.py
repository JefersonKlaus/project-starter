"""Builds rag_index.json, the reference index read by lambda_create (BM25 search, no embeddings).

Point it at one or more reference projects. Every supported source file (Python,
Terraform, Markdown, YAML/JSON, shell, ...) is split into chunks; each chunk keeps
the path it came from (<project folder>/<relative path>) as its `source`.

    cd backend-ia
    python rag/ingest.py --source ../reference-project            # one project
    python rag/ingest.py --source ../todo-api ../blog-api --output rag_index.json
    aws s3 cp rag_index.json s3://<bucket>/rag_index.json

Run it again every time the reference projects change, then upload the result.
Only dependency besides langchain-core: langchain-text-splitters (requirements-dev.txt).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

# --- What gets indexed -------------------------------------------------------

# Languages with a syntax-aware splitter in langchain (split on def/class/heading...)
LANGUAGES = {
    ".py": Language.PYTHON,
    ".md": Language.MARKDOWN,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".go": Language.GO,
    ".java": Language.JAVA,
    ".html": Language.HTML,
}

# Terraform/HCL has no splitter in langchain: split on top-level blocks instead
TERRAFORM_EXTENSIONS = {".tf", ".tfvars", ".hcl"}
TERRAFORM_SEPARATORS = [
    "\nresource ",
    "\ndata ",
    "\nmodule ",
    "\nvariable ",
    "\noutput ",
    "\nlocals ",
    "\nprovider ",
    "\nterraform ",
    "\n\n",
    "\n",
    " ",
    "",
]

# Everything else worth reading, split on blank lines / lines
PLAIN_EXTENSIONS = {
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".txt",
    ".sh",
    ".sql",
}

SUPPORTED_EXTENSIONS = set(LANGUAGES) | TERRAFORM_EXTENSIONS | PLAIN_EXTENSIONS

# Folders that are never useful as reference implementations
EXCLUDED_DIRS = {
    "tests",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".git",
    ".terraform",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "build",
    "dist",
    "zip",
}

# Generated or machine-owned files: noise for the model
EXCLUDED_FILES = {
    "rag_index.json",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    ".terraform.lock.hcl",
}
EXCLUDED_SUFFIXES = (".tfstate", ".tfstate.backup", ".min.js")

# Bigger files are almost always generated output, not reference code
MAX_FILE_BYTES = 200_000


# --- Step 1: read the source files of every project ------------------------


def is_excluded(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return (
        bool(EXCLUDED_DIRS.intersection(relative.parts[:-1]))
        or path.name in EXCLUDED_FILES
        or path.name.endswith(EXCLUDED_SUFFIXES)
        or path.suffix.lower() not in SUPPORTED_EXTENSIONS
        or path.stat().st_size > MAX_FILE_BYTES
    )


def load_project(root: Path) -> list[Document]:
    """One Document per supported file under `root` (source = <root name>/<relative path>)."""
    print(f"Reading {root}...")
    documents = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if is_excluded(path, root):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"  skipping {path.relative_to(root)} (not UTF-8 text)")
            continue
        if not content.strip():
            continue
        documents.append(
            Document(
                page_content=content,
                # Relative path: keeps local folders out of the prompt and of rag_references
                metadata={
                    "source": f"{root.name}/{path.relative_to(root).as_posix()}",
                    "type": path.suffix.lower(),
                },
            )
        )
    by_type = Counter(doc.metadata["type"] for doc in documents)
    summary = ", ".join(f"{n} {ext}" for ext, n in sorted(by_type.items()))
    print(f"  {len(documents)} file(s): {summary or 'none'}")
    return documents


def load_projects(roots: list[Path]) -> list[Document]:
    documents = []
    for root in roots:
        if not root.is_dir():
            sys.exit(f"Not a directory: {root}")
        documents.extend(load_project(root))
    return documents


# --- Step 2: split large files into chunks to improve retrieval --------------


def make_splitter(extension: str, chunk_size: int, chunk_overlap: int):
    if extension in LANGUAGES:
        return RecursiveCharacterTextSplitter.from_language(
            LANGUAGES[extension], chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
    if extension in TERRAFORM_EXTENSIONS:
        return RecursiveCharacterTextSplitter(
            separators=TERRAFORM_SEPARATORS,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )


def split_documents(
    documents: list[Document], chunk_size: int = 1000, chunk_overlap: int = 200
) -> list[Document]:
    """Split every document with the splitter of its file type, keeping the input order."""
    print("Splitting code into chunks...")
    splitters = {}
    chunks = []
    for document in documents:
        extension = document.metadata["type"]
        if extension not in splitters:
            splitters[extension] = make_splitter(extension, chunk_size, chunk_overlap)
        chunks.extend(splitters[extension].split_documents([document]))
    print(f"The files were split into {len(chunks)} chunks.")
    return chunks


# --- Step 3: save in the format read by the Lambda (ai/rag.py -> load_documents)


def save_index(chunks: list[Document], output: Path) -> None:
    index = {
        "documents": [
            {"page_content": chunk.page_content, "metadata": chunk.metadata}
            for chunk in chunks
        ]
    }
    output.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Index saved with {len(chunks)} chunks in: {output}")


# --- Pipeline -----------------------------------------------------------------


def ingest(
    sources: list[str], output: str, chunk_size: int = 1000, chunk_overlap: int = 200
) -> None:
    documents = load_projects([Path(source).resolve() for source in sources])
    if not documents:
        extensions = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        sys.exit(
            "No supported files found: nothing to index.\n"
            f"Looked for {extensions} outside {sorted(EXCLUDED_DIRS)}."
        )
    chunks = split_documents(documents, chunk_size, chunk_overlap)
    save_index(chunks, Path(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        nargs="+",
        required=True,
        metavar="DIR",
        help="One or more reference projects (folders) to index",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "rag_index.json"),
        help="Destination JSON file (default: backend-ia/rag_index.json)",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=1000, help="characters per chunk"
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=200, help="characters shared by neighbours"
    )
    args = parser.parse_args()
    ingest(args.source, args.output, args.chunk_size, args.chunk_overlap)


if __name__ == "__main__":
    main()

"""Builds rag_index.json, the reference index read by the Lambda (BM25 search, no embeddings).

Run it locally every time the reference code changes, then upload the result:

    cd backend-ia/rag
    python scripts/ingest.py                                  # reads ./api, writes ./rag_index.json
    python scripts/ingest.py --source ./references --output rag_index.json
    aws s3 cp rag_index.json s3://<bucket>/rag_index.json

Only dependency besides langchain-core: langchain-text-splitters (requirements-dev.txt).
"""

import argparse
import json
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

# Folders that are never useful as reference implementations
EXCLUDED_DIRS = {"tests", "__pycache__", ".venv", "build", ".git"}


# Step 1: read the source code to build the initial documents.
def carregar_arquivos_python(diretorio: Path) -> List[Document]:
    print(f"Reading Python files from directory: {diretorio}...")
    documentos = []
    for caminho in sorted(diretorio.rglob("*.py")):
        relativo = caminho.relative_to(diretorio)
        if EXCLUDED_DIRS.intersection(relativo.parts):
            continue
        documentos.append(
            Document(
                page_content=caminho.read_text(encoding="utf-8"),
                # Relative path: keeps local folders out of the prompt and of rag_references
                metadata={"source": relativo.as_posix()},
            )
        )
    print(f"Found {len(documentos)} Python files.")
    return documentos


# Step 2: split large files into chunks to improve retrieval.
def dividir_codigo_python(
    documentos_brutos: List[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    print("Splitting code into chunks...")
    text_splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    documentos_processados = text_splitter.split_documents(documentos_brutos)
    print(f"The files were split into {len(documentos_processados)} chunks.")
    return documentos_processados


# Step 3: save the chunks in the format read by the Lambda (rag.py -> load_documents).
def salvar_indice_json(documentos: List[Document], caminho_saida: Path) -> None:
    indice = {
        "documents": [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in documentos
        ]
    }
    caminho_saida.write_text(
        json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"✅ Index saved with {len(documentos)} chunks in: {caminho_saida}")


# Orchestrates the pipeline from the project directory without relying on machine-specific paths.
def orquestrar_ingestao_de_codigo(
    pasta_scripts: str | None = None,
    caminho_saida: str | None = None,
) -> None:
    base_dir = Path(__file__).resolve().parents[1]

    pasta = Path(pasta_scripts) if pasta_scripts else base_dir / "api"
    saida = Path(caminho_saida) if caminho_saida else base_dir / "rag_index.json"

    docs_brutos = carregar_arquivos_python(pasta)
    docs_processados = dividir_codigo_python(docs_brutos)
    salvar_indice_json(docs_processados, saida)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source", help="Directory with the reference Python files (default: ../api)"
    )
    parser.add_argument(
        "--output", help="Destination JSON file (default: ../rag_index.json)"
    )
    args = parser.parse_args()
    orquestrar_ingestao_de_codigo(args.source, args.output)

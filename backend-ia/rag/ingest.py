from pathlib import Path
from typing import List

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter


# Step 1: read the source code to build the initial documents.
def carregar_arquivos_python(diretorio: str) -> List[Document]:
    print(f"Reading Python files from directory: {diretorio}...")
    loader = DirectoryLoader(diretorio, glob="**/*.py", loader_cls=TextLoader)
    documentos = loader.load()
    print(f"Found {len(documentos)} Python files.")
    return documentos


# Step 2: split large files into chunks to improve vector retrieval.
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
    print(
        f"The files were split into {len(documentos_processados)} chunks."
    )
    return documentos_processados


# Step 3: load the chunks into the vector database for semantic search.
def salvar_no_banco_vetorial(
    documentos: List[Document],
    pasta_db: str,
    modelo_embedding: str = "all-MiniLM-L6-v2",
) -> None:
    print(f"Loading embedding model ({modelo_embedding})...")
    embeddings = HuggingFaceEmbeddings(model_name=modelo_embedding)

    print("Generating embeddings and saving to ChromaDB...")
    Chroma.from_documents(
        documents=documentos, embedding=embeddings, persist_directory=pasta_db
    )
    print(f"✅ Code ingestion finished. Database saved in: {pasta_db}")


# Orchestrates the ETL pipeline from the project directory without relying on machine-specific paths.
def orquestrar_ingestao_de_codigo(
    pasta_scripts: str | None = None,
    pasta_db: str | None = None,
):
    base_dir = Path(__file__).resolve().parents[1]

    if pasta_scripts is None:
        pasta_scripts = str(base_dir / "api")
    if pasta_db is None:
        pasta_db = str(base_dir / "chroma_db_local")

    docs_brutos = carregar_arquivos_python(pasta_scripts)
    docs_processados = dividir_codigo_python(docs_brutos)
    salvar_no_banco_vetorial(docs_processados, pasta_db)


if __name__ == "__main__":
    orquestrar_ingestao_de_codigo()

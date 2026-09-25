import os
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings


# 1. Extract
def carregar_arquivos_python(diretorio: str) -> List[Document]:
    print(f"Lendo arquivos .py do diretório: {diretorio}...")
    loader = DirectoryLoader(diretorio, glob="**/*.py", loader_cls=TextLoader)
    documentos = loader.load()
    print(f"Foram encontrados {len(documentos)} arquivos Python.")
    return documentos


# 2. Transform
def dividir_codigo_python(
    documentos_brutos: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200
) -> List[Document]:
    print("Dividindo o código...")
    text_splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    documentos_processados = text_splitter.split_documents(documentos_brutos)
    print(
        f"Os arquivos foram divididos em {len(documentos_processados)} blocos (chunks)."
    )
    return documentos_processados


# 3. Load
def salvar_no_banco_vetorial(
    documentos: List[Document],
    pasta_db: str,
    modelo_embedding: str = "all-MiniLM-L6-v2",
) -> None:
    print(f"Carregando o modelo de embeddings ({modelo_embedding})...")
    embeddings = HuggingFaceEmbeddings(model_name=modelo_embedding)

    print("Gerando coordenadas matemáticas e salvando no ChromaDB...")
    Chroma.from_documents(
        documents=documentos, embedding=embeddings, persist_directory=pasta_db
    )
    print(f"✅ Ingestão de código finalizada! Banco salvo na pasta: {pasta_db}")


# Controller
def orquestrar_ingestao_de_codigo():
    # Configurações do pipeline
    pasta_scripts = "/mnt/d/codigo/auto-arch-analyzer/backend"
    pasta_db = "./chroma_db_local"

    # Execução do pipeline ETL
    docs_brutos = carregar_arquivos_python(pasta_scripts)
    docs_processados = dividir_codigo_python(docs_brutos)
    salvar_no_banco_vetorial(docs_processados, pasta_db)


if __name__ == "__main__":
    orquestrar_ingestao_de_codigo()

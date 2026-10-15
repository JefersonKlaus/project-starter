from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


class MotorRAG:
    def __init__(self):
        print("Initializing RAG engine and connecting to ChromaDB...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.banco_vetorial = Chroma(
            persist_directory="../chroma_db_local", embedding_function=self.embeddings
        )

    def buscar_gabaritos(self, prompt_usuario: str, limite: int = 3):
        # Enrich the query to help the database find reference implementations
        query_tecnica = f"{prompt_usuario} serverless architecture aws python terraform api gateway lambda dynamodb"
        print("Searching the vector database for references to the enriched query...")

        documentos = self.banco_vetorial.similarity_search(query_tecnica, k=limite)

        contexto_formatado = "\n\n---\n\n".join(
            f"Reference file (REFERENCE): {doc.metadata.get('source', 'unknown')}\n"
            f"{doc.page_content}"
            for doc in documentos
        )

        return contexto_formatado, documentos

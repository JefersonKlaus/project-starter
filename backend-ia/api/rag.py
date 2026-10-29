from pathlib import Path

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


CHROMA_DIRECTORY = Path(__file__).resolve().parents[1] / "chroma_db_local"


class RAGEngine:
    def __init__(self):
        print("Initializing RAG engine and connecting to ChromaDB...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.vector_store = Chroma(
            persist_directory=str(CHROMA_DIRECTORY),
            embedding_function=self.embeddings,
        )

    def find_references(self, user_prompt: str, limit: int = 3):
        # Enrich the query to help the database find reference implementations
        technical_query = f"{user_prompt} serverless architecture aws python terraform api gateway lambda dynamodb"
        print("Searching the vector database for references to the enriched query...")

        documents = self.vector_store.similarity_search(technical_query, k=limit)

        formatted_context = "\n\n---\n\n".join(
            f"Reference file (REFERENCE): {doc.metadata.get('source', 'unknown')}\n"
            f"{doc.page_content}"
            for doc in documents
        )

        return formatted_context, documents

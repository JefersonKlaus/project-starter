from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings


class MotorRAG:
    def __init__(self):
        print("Inicializando Motor RAG e conectando ao ChromaDB...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.banco_vetorial = Chroma(
            persist_directory="./chroma_db_local", embedding_function=self.embeddings
        )

    def buscar_gabaritos(self, prompt_usuario: str, limite: int = 3):
        # Enriquecendo a query para forçar o banco a achar os códigos modelo
        query_tecnica = f"{prompt_usuario} arquitetura serverless aws python terraform api gateway lambda dynamodb"
        print(f"Buscando referências no banco vetorial para a query enriquecida...")

        documentos = self.banco_vetorial.similarity_search(query_tecnica, k=limite)

        contexto_formatado = "\n\n---\n\n".join(
            f"Arquivo de referência (GABARITO): {doc.metadata.get('source', 'desconhecido')}\n"
            f"{doc.page_content}"
            for doc in documentos
        )

        return contexto_formatado, documentos

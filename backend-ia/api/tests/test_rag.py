from types import SimpleNamespace

from rag import RAGEngine


def test_find_references_enriches_query_and_formats_documents():
    engine = object.__new__(RAGEngine)
    documents = [
        SimpleNamespace(
            metadata={"source": "lambda.py"},
            page_content="def handler(event, context): pass",
        ),
        SimpleNamespace(metadata={}, page_content="resource aws_lambda_function"),
    ]

    class VectorStore:
        def similarity_search(self, query, k):
            assert query == (
                "todo API serverless architecture aws python terraform api gateway "
                "lambda dynamodb"
            )
            assert k == 2
            return documents

    engine.vector_store = VectorStore()

    context, result = engine.find_references("todo API", limit=2)

    assert result == documents
    assert context == (
        "Reference file (REFERENCE): lambda.py\n"
        "def handler(event, context): pass\n\n---\n\n"
        "Reference file (REFERENCE): unknown\n"
        "resource aws_lambda_function"
    )


def test_find_references_returns_empty_context_without_documents():
    engine = object.__new__(RAGEngine)

    class VectorStore:
        def similarity_search(self, query, k):
            return []

    engine.vector_store = VectorStore()

    context, documents = engine.find_references("empty")

    assert context == ""
    assert documents == []


def test_rag_engine_initializes_embeddings_and_vector_store(monkeypatch):
    embeddings = object()
    vector_store = object()
    embeddings_factory = lambda **kwargs: embeddings
    chroma_factory = lambda **kwargs: vector_store
    monkeypatch.setattr("rag.HuggingFaceEmbeddings", embeddings_factory)
    monkeypatch.setattr("rag.Chroma", chroma_factory)

    engine = RAGEngine()

    assert engine.embeddings is embeddings
    assert engine.vector_store is vector_store

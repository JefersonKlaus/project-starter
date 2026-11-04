import json
from types import SimpleNamespace

from langchain_core.documents import Document

from ai.rag import BM25Index, RAGEngine, load_documents, tokenize


def _doc(content, source=None):
    return Document(page_content=content, metadata={"source": source} if source else {})


# --- tokenize / BM25 -------------------------------------------------------


def test_tokenize_lowercases_and_splits_identifiers():
    assert tokenize('resource "aws_lambda_function" Create-Item') == [
        "resource",
        "aws",
        "lambda",
        "function",
        "create",
        "item",
    ]


def test_bm25_ranks_documents_with_more_query_terms_first():
    index = BM25Index(
        [
            _doc("terraform aws_dynamodb_table billing_mode", "table.tf"),
            _doc("python lambda handler boto3 dynamodb put_item", "create_item.py"),
            _doc("mermaid diagram of a frontend", "diagram.md"),
        ]
    )

    results = index.search("python lambda dynamodb", k=3)

    assert [doc.metadata["source"] for doc in results] == ["create_item.py", "table.tf"]


def test_bm25_search_respects_k():
    index = BM25Index([_doc("lambda a"), _doc("lambda b"), _doc("lambda c")])
    assert len(index.search("lambda", k=2)) == 2


def test_bm25_search_ignores_documents_without_matching_terms():
    index = BM25Index([_doc("nothing in common")])
    assert index.search("lambda dynamodb") == []


def test_bm25_search_is_stable_for_ties():
    index = BM25Index([_doc("lambda", "first"), _doc("lambda", "second")])
    assert [doc.metadata["source"] for doc in index.search("lambda")] == [
        "first",
        "second",
    ]


def test_bm25_handles_empty_index():
    assert BM25Index([]).search("lambda") == []


def test_bm25_handles_empty_documents():
    assert BM25Index([_doc(""), _doc("")]).search("lambda") == []


# --- index file ------------------------------------------------------------


def test_load_documents_reads_index_format(tmp_path):
    path = tmp_path / "rag_index.json"
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {"page_content": "a", "metadata": {"source": "a.py"}},
                    {"page_content": "b", "metadata": None},
                    {"page_content": "c"},
                ]
            }
        )
    )

    documents = load_documents(path)

    assert [doc.page_content for doc in documents] == ["a", "b", "c"]
    assert documents[0].metadata == {"source": "a.py"}
    assert documents[1].metadata == {} and documents[2].metadata == {}


def test_load_documents_accepts_bare_list(tmp_path):
    path = tmp_path / "rag_index.json"
    path.write_text(json.dumps([{"page_content": "a"}]))
    assert load_documents(path)[0].page_content == "a"


# --- RAGEngine -------------------------------------------------------------


def test_rag_engine_loads_index_from_file(tmp_path):
    path = tmp_path / "rag_index.json"
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {"page_content": "lambda handler", "metadata": {"source": "a.py"}}
                ]
            }
        )
    )

    engine = RAGEngine(path)

    assert [doc.metadata["source"] for doc in engine.documents] == ["a.py"]
    assert engine.index.search("lambda") == engine.documents


def test_find_references_enriches_query_and_formats_documents():
    engine = object.__new__(RAGEngine)
    documents = [
        SimpleNamespace(
            metadata={"source": "lambda.py"},
            page_content="def handler(event, context): pass",
        ),
        SimpleNamespace(metadata={}, page_content="resource aws_lambda_function"),
    ]

    class Index:
        def search(self, query, k):
            assert query == (
                "todo API serverless architecture aws python terraform api gateway "
                "lambda dynamodb"
            )
            assert k == 2
            return documents

    engine.index = Index()

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

    class Index:
        def search(self, query, k):
            return []

    engine.index = Index()

    context, documents = engine.find_references("empty")

    assert context == ""
    assert documents == []

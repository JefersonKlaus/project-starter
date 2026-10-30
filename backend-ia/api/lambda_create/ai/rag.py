"""RAG over a precomputed index of reference files (rag_index.json), searched with BM25.

The index is generated locally by the ingestion script (backend-ia/scripts).
No embeddings model is needed at query time: ranking is plain keyword BM25.
"""

import json
import math
import re
from collections import Counter

from langchain_core.documents import Document

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list:
    """Lowercase alphanumeric tokens; splits identifiers such as aws_lambda_function."""
    return TOKEN_PATTERN.findall(text.lower())


class BM25Index:
    """Minimal BM25 ranking (Okapi) over a small, in-memory list of documents."""

    def __init__(self, documents, k1: float = 1.5, b: float = 0.75):
        self.documents = list(documents)
        self.k1 = k1
        self.b = b

        self._term_frequencies = [
            Counter(tokenize(doc.page_content)) for doc in self.documents
        ]
        self._lengths = [sum(tf.values()) for tf in self._term_frequencies]
        self._average_length = (
            sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        )

        document_frequencies = Counter()
        for tf in self._term_frequencies:
            document_frequencies.update(tf.keys())
        total = len(self.documents)
        self._idf = {
            term: math.log(1 + (total - df + 0.5) / (df + 0.5))
            for term, df in document_frequencies.items()
        }

    def score(self, query_terms, position: int) -> float:
        tf = self._term_frequencies[position]
        if self._average_length:
            length_norm = (
                1 - self.b + self.b * self._lengths[position] / self._average_length
            )
        else:
            length_norm = 1.0

        score = 0.0
        for term in query_terms:
            freq = tf.get(term)
            if not freq:
                continue
            score += (
                self._idf[term] * freq * (self.k1 + 1) / (freq + self.k1 * length_norm)
            )
        return score

    def search(self, query: str, k: int = 3) -> list:
        """Return up to k documents that share terms with the query, best match first."""
        query_terms = tokenize(query)
        scored = [
            (self.score(query_terms, position), position)
            for position in range(len(self.documents))
        ]
        ranked = sorted(
            (pair for pair in scored if pair[0] > 0),
            key=lambda pair: (-pair[0], pair[1]),
        )
        return [self.documents[position] for _, position in ranked[:k]]


def load_documents(path) -> list:
    """Read rag_index.json ({"documents": [{"page_content", "metadata"}, ...]})."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    entries = data["documents"] if isinstance(data, dict) else data
    return [
        Document(
            page_content=entry["page_content"], metadata=entry.get("metadata") or {}
        )
        for entry in entries
    ]


class RAGEngine:
    def __init__(self, index_path):
        print(f"Initializing RAG engine from {index_path}...")
        self.documents = load_documents(index_path)
        self.index = BM25Index(self.documents)
        print(f"RAG index loaded with {len(self.documents)} document(s)")

    def find_references(self, user_prompt: str, limit: int = 3):
        # Enrich the query to help the index find reference implementations
        technical_query = f"{user_prompt} serverless architecture aws python terraform api gateway lambda dynamodb"
        print("Searching the reference index for the enriched query...")

        documents = self.index.search(technical_query, k=limit)

        formatted_context = "\n\n---\n\n".join(
            f"Reference file (REFERENCE): {doc.metadata.get('source', 'unknown')}\n"
            f"{doc.page_content}"
            for doc in documents
        )

        return formatted_context, documents

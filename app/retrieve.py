# app/retrieve.py
"""
Semantic retrieval + conflict detection.

Public API:
    retrieve_relevant_chunks(question, top_k, threshold) -> (chunks, conflicts)
"""

from __future__ import annotations
import os
from typing import Optional
from datetime import datetime

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from app.models import RetrievedChunk

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "policy_chunks")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Lazy-load globals
_embedding_model: Optional[SentenceTransformer] = None
_collection = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def retrieve_relevant_chunks(
    question: str,
    top_k: int = 5,
    min_score: float = 0.0,
) -> tuple[list[RetrievedChunk], list[dict]]:
    """
    Retrieve semantically similar chunks from ChromaDB.

    Returns:
        (list_of_RetrievedChunk, list_of_conflict_dicts)

    Conflict dict shape:
        {
          "topic": str,
          "sources": [{"title": ..., "page": ..., "text": ..., "effective_date": ...}, ...]
        }
    """
    model = _get_embedding_model()
    collection = _get_collection()

    # 1. Encode question
    query_embedding = model.encode([question], convert_to_numpy=True)[0].tolist()

    # 2. Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    # 3. Parse results
    chunks: list[RetrievedChunk] = []
    for i in range(len(results["ids"][0])):
        # ChromaDB returns similarity as 1 - distance for cosine
        # Distance is already in [0, 2], so similarity = 1 - distance/2
        distance = results["distances"][0][i]
        similarity = 1.0 - (distance / 2.0)
        
        if similarity < min_score:
            continue

        chunks.append(
            RetrievedChunk(
                text=results["documents"][0][i],
                score=similarity,
                metadata=results["metadatas"][0][i],
            )
        )

    # 4. Conflict detection: same section, different effective dates, both approved
    conflicts = _detect_conflicts(chunks)

    return chunks, conflicts


def _detect_conflicts(chunks: list[RetrievedChunk]) -> list[dict]:
    """
    Simple conflict detection:
      - Group chunks by (section, status=approved)
      - If multiple effective_dates exist, flag as conflict
    """
    from collections import defaultdict

    section_map = defaultdict(list)
    for chunk in chunks:
        m = chunk.metadata
        status = m.get("status", "").lower()
        section = m.get("section", "").lower()
        if status == "approved" and section:
            section_map[section].append(chunk)

    conflicts = []
    for section, chunk_list in section_map.items():
        dates = {c.metadata.get("effective_date") for c in chunk_list}
        if len(dates) > 1:
            conflicts.append({
                "topic": section,
                "sources": [
                    {
                        "title": c.metadata.get("title", "?"),
                        "page": c.metadata.get("page", "?"),
                        "text": c.text[:200],
                        "effective_date": c.metadata.get("effective_date", "?"),
                    }
                    for c in chunk_list
                ],
            })

    return conflicts

# app/ingest.py
"""
PDF → chunks → embeddings → ChromaDB pipeline.

Public API:
    ingest_pdfs(pdf_list: list[Path], manifest_path: Path) -> None
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Generator

import pymupdf  # PyMuPDF
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "policy_chunks")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Chunking parameters
TARGET_CHUNK_SIZE = 600  # characters
OVERLAP = 100


def _extract_metadata_from_pdf(doc: pymupdf.Document) -> dict:
    """Extract document-level metadata from PDF properties."""
    meta = doc.metadata or {}
    # PyMuPDF uses 'creationDate' in format like "D:20231229120000+00'00'"
    creation_date_raw = meta.get("creationDate", "")
    if creation_date_raw and creation_date_raw.startswith("D:"):
        # Parse: D:20231229... -> 2023-12-29
        date_part = creation_date_raw[2:10]
        if len(date_part) == 8:
            effective_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
        else:
            effective_date = "2024-01-01"
    else:
        effective_date = "2024-01-01"

    return {
        "title": meta.get("title", "Unknown Policy"),
        "author": meta.get("author", ""),
        "subject": meta.get("subject", ""),
        "effective_date": effective_date,
        "version": "1.0",
        "status": "approved",
    }


def _split_into_chunks(text: str, chunk_size: int, overlap: int) -> Generator[str, None, None]:
    """Sliding-window chunker."""
    start = 0
    while start < len(text):
        end = start + chunk_size
        yield text[start:end]
        start += (chunk_size - overlap)


def _chunk_pdf(
    pdf_path: Path,
    doc_id: str,
    doc_meta: dict,
) -> list[dict]:
    """
    Extract all pages from a PDF and chunk them.

    Returns:
        list of chunk dicts with keys: text, page, section, doc_id, plus doc_meta fields
    """
    doc = pymupdf.open(pdf_path)
    chunks = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        raw_text = page.get_text()
        if not raw_text.strip():
            continue

        # Simple section detection: look for all-caps headings in first 100 chars
        first_line = raw_text.split("\n", 1)[0].strip()[:100]
        section = first_line if first_line.isupper() else "General"

        for chunk_text in _split_into_chunks(raw_text, TARGET_CHUNK_SIZE, OVERLAP):
            if len(chunk_text.strip()) < 50:
                continue
            chunks.append({
                "text": chunk_text.strip(),
                "page": page_num + 1,
                "section": section,
                "doc_id": doc_id,
                **doc_meta,
            })
    return chunks


def ingest_pdfs(pdf_paths: list[Path], manifest_path: Path) -> None:
    """
    Main ingest pipeline:
      1) Read PDFs
      2) Chunk + metadata extraction
      3) Embed
      4) Store in ChromaDB
      5) Save manifest + human-readable chunks.json
    """
    # 1. Load embedding model
    print(f"[INGEST] Loading embedding model: {EMBEDDING_MODEL_NAME}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # 2. Collect all chunks
    print("[INGEST] Chunking PDFs...")
    all_chunks = []
    doc_metadata = {}

    for pdf_path in pdf_paths:
        doc_id = pdf_path.stem
        print(f"  - {pdf_path.name}")
        doc_meta = _extract_metadata_from_pdf(pymupdf.open(pdf_path))
        doc_metadata[doc_id] = doc_meta
        chunks = _chunk_pdf(pdf_path, doc_id, doc_meta)
        all_chunks.extend(chunks)

    print(f"[INGEST] Total chunks: {len(all_chunks)}")

    # 3. Generate embeddings
    print("[INGEST] Generating embeddings...")
    texts = [c["text"] for c in all_chunks]
    embeddings = embedding_model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    # 4. Store in ChromaDB
    print("[INGEST] Storing in ChromaDB...")
    client = chromadb.PersistentClient(
        path=CHROMA_DB_PATH,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    # Clear existing to avoid duplicates
    try:
        collection.delete(where={})
    except Exception:
        pass

    ids = [f"chunk_{i}" for i in range(len(all_chunks))]
    metadatas = [
        {k: str(v) for k, v in c.items() if k != "text"}
        for c in all_chunks
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=metadatas,
    )
    print(f"[INGEST] Stored {len(all_chunks)} chunks in collection '{COLLECTION_NAME}'")

    # 5. Save manifest
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "documents": doc_metadata,
                "total_chunks": len(all_chunks),
                "embedding_model": EMBEDDING_MODEL_NAME,
                "chunk_params": {"target_size": TARGET_CHUNK_SIZE, "overlap": OVERLAP},
            },
            f,
            indent=2,
        )
    print(f"[INGEST] Saved manifest to {manifest_path}")

    # 6. Save human-readable chunks.json
    chunks_file = manifest_path.parent / "processed" / "chunks.json"
    chunks_file.parent.mkdir(parents=True, exist_ok=True)
    with chunks_file.open("w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    print(f"[INGEST] Saved {len(all_chunks)} chunks to {chunks_file}")


if __name__ == "__main__":
    # Example usage:
    from pathlib import Path
    raw_dir = Path(os.getenv("RAW_DIR", "data/raw"))
    pdfs = list(raw_dir.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in", raw_dir)
    else:
        ingest_pdfs(pdfs, Path(os.getenv("MANIFEST_PATH", "data/manifest.json")))

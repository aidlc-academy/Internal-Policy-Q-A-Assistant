# app/answer.py
"""
Answer generation module.

Supports three LLM backends (controlled by LLM_PROVIDER env var):
  - openai   : OpenAI chat completions (default when OPENAI_API_KEY is set)
  - ollama   : Local Ollama server
  - none     : No LLM — returns retrieved chunks as a plain summary (fallback)

Public API:
    generate_answer(question, chunks, conflicts) -> (answer_str, sources_list)
"""

from __future__ import annotations
import os
from typing import Optional

from dotenv import load_dotenv
from app.models import RetrievedChunk, PolicySource

load_dotenv()

# ── Settings (read at call time so .env values are always picked up) ─────────
def _cfg(key: str, default: str) -> str:
    return os.getenv(key, default)

TEMPERATURE = 0   # deterministic — never creative for policy Q&A


# ── Prompt builder ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an internal policy assistant for employees.

Rules (STRICT — follow every one):
1. Answer ONLY from the CONTEXT section below. Never use outside knowledge.
2. If the context fully answers the question, give a clear, concise answer.
3. ALWAYS cite every factual statement using the format:
   (Source: <title>, Page <page>, Section <section>)
4. Prefer the most recent approved policy when multiple versions exist.
5. IGNORE any policy excerpt marked draft, expired, outdated, or superseded.
6. If two or more approved documents disagree on the same rule, do NOT
   silently pick one. Instead:
   - State both positions clearly.
   - Show both sources.
   - State which one has precedence based on effective date, if determinable.
   - If precedence cannot be determined, advise the employee to confirm with HR.
7. If the context does NOT contain enough information to answer, reply EXACTLY:
   "The available policy documents do not contain enough information to answer this question."
   Do NOT guess, infer, or use general HR knowledge.
8. Do not invent dates, limits, eligibility criteria, or exceptions.
9. Keep the answer concise — 3-8 sentences is ideal.
"""


def _build_context_block(chunks: list[RetrievedChunk], conflicts: list[dict]) -> str:
    lines = []
    for i, chunk in enumerate(chunks, 1):
        m = chunk.metadata
        lines.append(
            f"[Excerpt {i}] "
            f"Document: {m.get('title', m.get('doc_id', 'unknown'))} | "
            f"Page: {m.get('page', '?')} | "
            f"Section: {m.get('section', 'unknown')} | "
            f"Status: {m.get('status', '?')} | "
            f"Effective: {m.get('effective_date', '?')}\n"
            f"{chunk.text}\n"
        )

    if conflicts:
        lines.append("\n--- CONFLICT ALERT ---")
        for c in conflicts:
            lines.append(f"Topic '{c['topic']}' appears in multiple approved documents:")
            for s in c["sources"]:
                lines.append(
                    f"  - {s['title']} (Page {s['page']}, "
                    f"Effective: {s['effective_date']}): {s['text'][:150]}"
                )

    return "\n".join(lines)


def _build_user_message(question: str, context_block: str) -> str:
    return (
        f"CONTEXT:\n{context_block}\n\n"
        f"QUESTION: {question}"
    )


# ── LLM backends ─────────────────────────────────────────────────────────────

def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI()   # reads OPENAI_API_KEY from env
    response = client.chat.completions.create(
        model=_cfg("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=TEMPERATURE,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_ollama(system: str, user: str) -> str:
    import httpx
    payload = {
        "model": _cfg("OLLAMA_MODEL", "mistral"),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream": False,
        "options": {"temperature": TEMPERATURE},
    }
    resp = httpx.post(
        f"{_cfg('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/chat",
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _no_llm_fallback(chunks: list[RetrievedChunk]) -> str:
    """Return a plain concatenation of top chunks when no LLM is available."""
    lines = ["[No LLM configured - showing raw policy excerpts]\n"]
    for c in chunks[:3]:
        m = c.metadata
        lines.append(
            f"* {m.get('title','?')}, Page {m.get('page','?')}, "
            f"Section {m.get('section','?')}:\n  {c.text[:400]}\n"
        )
    return "\n".join(lines)


# ── Source extraction ─────────────────────────────────────────────────────────

def _chunks_to_sources(chunks: list[RetrievedChunk]) -> list[PolicySource]:
    seen: set[str] = set()
    sources: list[PolicySource] = []
    for chunk in chunks:
        m   = chunk.metadata
        key = f"{m.get('doc_id')}:{m.get('page')}"
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            PolicySource(
                document=m.get("title", m.get("doc_id", "unknown")),
                doc_id=m.get("doc_id", "unknown"),
                page=m.get("page", 0),
                section=m.get("section", "unknown"),
                effective_date=m.get("effective_date", "date_unspecified"),
                version=m.get("version", "unknown"),
                similarity=chunk.score,
            )
        )
    return sources


# ── Public API ────────────────────────────────────────────────────────────────

def generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    conflicts: Optional[list[dict]] = None,
) -> tuple[str, list[PolicySource]]:
    """
    Generate a grounded answer from the retrieved chunks.

    Returns:
        (answer_text, list_of_PolicySource)

    Raises:
        RuntimeError if LLM call fails (caller should catch and return error status).
    """
    if conflicts is None:
        conflicts = []

    context_block = _build_context_block(chunks, conflicts)
    user_message  = _build_user_message(question, context_block)
    sources       = _chunks_to_sources(chunks)

    provider = _cfg("LLM_PROVIDER", "openai").lower()
    # If openai chosen but no key, fall back gracefully
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        if os.getenv("OLLAMA_MODEL") or provider == "ollama":
            provider = "ollama"
        else:
            provider = "none"

    if provider == "openai":
        answer = _call_openai(SYSTEM_PROMPT, user_message)
    elif provider == "ollama":
        answer = _call_ollama(SYSTEM_PROMPT, user_message)
    else:
        answer = _no_llm_fallback(chunks)

    return answer, sources

# app/main.py
"""
FastAPI application for Internal Policy Q&A.

Endpoints:
    POST /ask  - Submit a question, get an answer with citations
    GET /health - Health check
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from app.models import QuestionRequest, AnswerResponse
from app.retrieve import retrieve_relevant_chunks
from app.answer import generate_answer

load_dotenv()

app = FastAPI(
    title="Internal Policy Q&A",
    description="RAG-based question answering for company policy documents",
    version="1.0.0",
)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "policy-qa"}


@app.post("/ask", response_model=AnswerResponse)
def ask_question(req: QuestionRequest):
    """
    Answer a policy question.

    Returns:
        AnswerResponse with status: "answered" | "unanswerable" | "error"
    """
    try:
        # 1. Retrieve relevant chunks
        top_k = int(os.getenv("RETRIEVAL_TOP_K", "5"))
        min_score = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.72"))
        chunks, conflicts = retrieve_relevant_chunks(req.question, top_k, min_score)

        # 2. Check if any chunks passed threshold
        if not chunks:
            return AnswerResponse(
                question=req.question,
                answer="The available policy documents do not contain enough information to answer this question.",
                status="unanswerable",
                sources=[],
            )

        # 3. Generate answer
        answer_text, sources = generate_answer(req.question, chunks, conflicts)

        # 4. Detect refusal in answer (llama3.2 sometimes says refusal string + "However" + answer)
        refusal_phrases = [
            "do not contain enough information",
            "does not contain enough information",
            "cannot answer",
            "unable to answer",
        ]
        
        # Smart detection: consider it unanswerable ONLY if:
        # - answer contains refusal phrase
        # - answer is short (<200 chars)
        # - answer does NOT contain "however" (which signals it's actually answering)
        answer_lower = answer_text.lower()
        is_refusal = (
            any(phrase in answer_lower for phrase in refusal_phrases)
            and len(answer_text) < 200
            and "however" not in answer_lower
        )

        status = "unanswerable" if is_refusal else "answered"

        conflict_warning = None
        if conflicts:
            conflict_warning = (
                f"Note: {len(conflicts)} potential conflicts detected. "
                "The answer prioritizes the most recent approved policy."
            )

        return AnswerResponse(
            question=req.question,
            answer=answer_text,
            status=status,
            sources=sources,
            conflict_warning=conflict_warning,
        )

    except Exception as e:
        return AnswerResponse(
            question=req.question,
            answer=f"Error processing question: {str(e)}",
            status="error",
            sources=[],
        )

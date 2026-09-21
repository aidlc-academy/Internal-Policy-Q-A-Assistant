# app/models.py
"""
Shared data models used across the application.
"""

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    """Incoming question from user/frontend."""
    question: str = Field(..., min_length=3, description="User question about company policy")


class PolicySource(BaseModel):
    """Metadata for one policy document reference."""
    document: str
    doc_id: str
    page: int
    section: str
    effective_date: str
    version: str
    similarity: float


class AnswerResponse(BaseModel):
    """Complete answer object returned by the API."""
    question: str
    answer: str
    status: str  # "answered" | "unanswerable" | "error"
    sources: list[PolicySource] = Field(default_factory=list)
    conflict_warning: str | None = None


class RetrievedChunk(BaseModel):
    """A single chunk returned by semantic search."""
    text: str
    score: float
    metadata: dict

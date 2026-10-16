"""HTTP endpoint for optional local-AI questions."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.service import answer_question
from app.database import get_db

router = APIRouter(prefix="/ai", tags=["Optional AI"])


class AIAskRequest(BaseModel):
    """Question body for the AI endpoint."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"question": "How many students are there?"}]})
    question: str = Field(min_length=1, max_length=500, description="A question about stored student records")


class AIAskResponse(BaseModel):
    """Grounded natural-language answer and diagnostics."""

    question: str
    intent: str
    answer: str
    records_used: int
    model: str
    ollama_available: bool


@router.post(
    "/ask",
    response_model=AIAskResponse,
    summary="Ask a question about student records (optional Ollama)",
)
def ask_about_students(payload: AIAskRequest, db: Session = Depends(get_db)) -> AIAskResponse:
    """Answer supported questions using backend-selected database records."""
    if not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )
    return AIAskResponse(**answer_question(payload.question.strip(), db))

"""Safe, database-grounded answering for the optional Ollama extension."""

import logging
from datetime import date
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app import crud
from app.ai.intents import QueryIntent, detect_intent, supported_question_message
from app.ai.ollama_client import generate_with_ollama
from app.config import OLLAMA_MODEL
from app.models import Student

logger = logging.getLogger(__name__)
_MAX_RECORDS = 50


def _student_context(student: Student, include_contact: bool) -> dict[str, Any]:
    """Select only fields required for a grounded answer; omit contact data by default."""
    record: dict[str, Any] = {
        "student_id": student.student_id,
        "name": student.name,
        "date_of_birth": student.date_of_birth.isoformat(),
        "course": student.course,
        "enrollment_date": student.enrollment_date.isoformat() if student.enrollment_date else None,
    }
    if include_contact:
        record.update({"email": student.email, "phone": student.phone, "address": student.address})
    return record


def _fetch_context(db: Session, intent: QueryIntent) -> tuple[dict[str, Any], list[dict[str, Any]], int | None]:
    """Fetch all allowed records using the existing ORM CRUD layer."""
    if intent.name == "count_students":
        count = crud.count_students(db)
        return {"count": count}, [], count

    if intent.name == "get_student":
        student = crud.get_student(db, int(intent.filters["student_id"]))
        records = [_student_context(student, intent.include_contact)] if student else []
        return {"records": records}, records, None

    if intent.name == "students_in_course":
        students = crud.list_students(
            db,
            course=str(intent.filters["course"]),
            skip=0,
            limit=_MAX_RECORDS,
        )
    elif intent.name == "list_students":
        students = crud.list_students(
            db,
            name=str(intent.filters["name"]) if "name" in intent.filters else None,
            born_after=intent.filters.get("born_after") if isinstance(intent.filters.get("born_after"), date) else None,
            born_before=intent.filters.get("born_before") if isinstance(intent.filters.get("born_before"), date) else None,
            skip=0,
            limit=_MAX_RECORDS,
        )
    else:
        return {}, [], None

    records = [_student_context(student, intent.include_contact) for student in students]
    return {"records": records, "records_capped_at": _MAX_RECORDS}, records, None


def _fallback_answer(
    question: str,
    intent: QueryIntent,
    records: list[dict[str, Any]],
    count: int | None,
) -> str:
    """Construct a deterministic response from the same retrieved data if Ollama is down."""
    if intent.name == "count_students":
        return f"There are {count or 0} student record(s) in the database."

    if intent.name == "get_student" and not records:
        return f"I couldn't find a student with ID {intent.filters['student_id']}."

    if intent.name == "students_in_course":
        course = str(intent.filters["course"])
        if not records:
            return f"I couldn't find any students in the course '{course}'."
        if "how many" in question.lower():
            return f"There are {len(records)} student(s) in '{course}'."

    if not records:
        return "No matching student records were found."

    if intent.name == "get_student":
        record = records[0]
        parts = [
            f"Student ID: {record['student_id']}",
            f"Name: {record['name']}",
            f"Date of birth: {record['date_of_birth']}",
            f"Course: {record.get('course') or 'Not provided'}",
        ]
        for field in ("email", "phone", "address"):
            if field in record:
                parts.append(f"{field.replace('_', ' ').title()}: {record.get(field) or 'Not provided'}")
        return "\n".join(parts)

    if "how many" in question.lower():
        suffix = " (showing the first 50 matches at most)" if len(records) == _MAX_RECORDS else ""
        return f"There are {len(records)} matching student record(s){suffix}."

    lines = []
    for record in records:
        line = (
            f"ID {record['student_id']}: {record['name']} — born {record['date_of_birth']}; "
            f"course: {record.get('course') or 'Not provided'}"
        )
        for field in ("email", "phone", "address"):
            if field in record:
                line += f"; {field}: {record.get(field) or 'Not provided'}"
        lines.append(line)
    suffix = "\nOnly the first 50 matches are shown." if len(records) == _MAX_RECORDS else ""
    return "\n".join(lines) + suffix


def answer_question(question: str, db: Session) -> dict[str, Any]:
    """Answer supported questions using ORM-selected records and optional Ollama phrasing."""
    intent = detect_intent(question)
    if intent is None:
        return {
            "question": question,
            "intent": "unsupported",
            "answer": supported_question_message(),
            "records_used": 0,
            "model": OLLAMA_MODEL,
            "ollama_available": False,
        }

    context, records, count = _fetch_context(db, intent)
    if intent.name != "count_students" and not records:
        # Do not ask a generative model to answer from an empty result set.
        return {
            "question": question,
            "intent": intent.name,
            "answer": _fallback_answer(question, intent, records, count),
            "records_used": 0,
            "model": OLLAMA_MODEL,
            "ollama_available": False,
        }

    try:
        answer = generate_with_ollama(question, context)
        ollama_available = True
    except Exception as exc:  # Ollama is optional; the API must still work without it.
        logger.warning("Ollama is unavailable or returned an invalid response: %s", exc)
        answer = _fallback_answer(question, intent, records, count)
        ollama_available = False

    return {
        "question": question,
        "intent": intent.name,
        "answer": answer,
        "records_used": len(records),
        "model": OLLAMA_MODEL,
        "ollama_available": ollama_available,
    }

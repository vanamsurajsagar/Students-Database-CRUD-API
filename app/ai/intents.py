"""Deterministic, allow-listed natural-language intent parsing for the AI bonus."""

from dataclasses import dataclass, field
from datetime import date
import re


@dataclass(frozen=True)
class QueryIntent:
    """A supported AI question type and its structured filters."""

    name: str
    filters: dict[str, object] = field(default_factory=dict)
    include_contact: bool = False


_SUPPORTED_MESSAGE = (
    "I can answer questions such as: how many students are there; list students; "
    "list students born after 2005; find students by name; show student ID 3; "
    "or list students in a course such as Python."
)


def supported_question_message() -> str:
    """Return help text for unsupported questions."""
    return _SUPPORTED_MESSAGE


def detect_intent(question: str) -> QueryIntent | None:
    """Recognize supported questions without asking an LLM to interpret or run SQL."""
    text = question.strip()
    lower = text.lower()
    include_contact = any(word in lower for word in ("email", "phone", "contact", "address"))

    # Individual profile queries must be recognized before general list/count questions.
    id_match = re.search(r"\b(?:student(?:\s+id)?|id)\s*#?\s*(\d+)\b", lower)
    if id_match and ("student" in lower or "student id" in lower or lower.startswith("id")):
        return QueryIntent("get_student", {"student_id": int(id_match.group(1))}, include_contact)

    # Course-specific lists include questions such as "How many students are in Python?".
    course_match = re.search(
        r"\b(?:students|learners)\s+(?:(?:who\s+)?are\s+)?(?:there\s+)?(?:in|taking|studying|enrolled\s+in)\s+(.+?)\s*[?.!]*$",
        text,
        flags=re.IGNORECASE,
    )
    if course_match:
        course = course_match.group(1).strip().rstrip("?.! ")
        if course:
            return QueryIntent("students_in_course", {"course": course}, include_contact)

    if re.search(r"\b(how many students?|student count|count (?:all )?students?|number of students?)\b", lower):
        return QueryIntent("count_students", {}, include_contact)

    year_after_match = re.search(r"\b(?:born|date of birth)\s+after\s+(19\d{2}|20\d{2})\b", lower)
    year_before_match = re.search(r"\b(?:born|date of birth)\s+before\s+(19\d{2}|20\d{2})\b", lower)
    name_match = re.search(r"\b(?:name contains|named|called)\s+([\w .'-]+?)(?:\s+(?:born|in|taking)\b|[?.!]|$)", text, flags=re.IGNORECASE)

    asks_for_list = bool(
        re.search(r"\b(list|show|find|display|all students|student list)\b", lower)
        or year_after_match
        or year_before_match
        or name_match
    )
    if asks_for_list:
        filters: dict[str, object] = {}
        if year_after_match:
            year = int(year_after_match.group(1))
            # CRUD's born_after filter is strictly greater-than a date. Since DOBs
            # are dates (not timestamps), > Dec 31 means on/after Jan 1 next year.
            filters["born_after"] = date(year, 12, 31)
        if year_before_match:
            year = int(year_before_match.group(1))
            # Strictly before Jan 1 includes every DOB up to Dec 31 of prior year.
            filters["born_before"] = date(year, 1, 1)
        if name_match:
            name = name_match.group(1).strip()
            if name:
                filters["name"] = name
        return QueryIntent("list_students", filters, include_contact)

    return None

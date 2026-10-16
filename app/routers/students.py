"""HTTP routes for student CRUD operations."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import (
    DeleteStudentResponse,
    StudentCount,
    StudentCreate,
    StudentPatch,
    StudentRead,
)

router = APIRouter(prefix="/students", tags=["Students"])


def _get_or_404(db: Session, student_id: int):
    student = crud.get_student(db, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with id {student_id} not found",
        )
    return student


def _raise_duplicate_email() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A student with this email already exists.",
    )


@router.post(
    "",
    response_model=StudentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a student",
    responses={409: {"description": "Email is already registered"}},
)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> StudentRead:
    """Create a student record."""
    try:
        return crud.create_student(db, payload)
    except crud.DuplicateEmailError:
        _raise_duplicate_email()


@router.get(
    "/count",
    response_model=StudentCount,
    summary="Count students",
)
def get_student_count(db: Session = Depends(get_db)) -> StudentCount:
    """Return the number of stored students."""
    return StudentCount(count=crud.count_students(db))


@router.get(
    "",
    response_model=list[StudentRead],
    summary="List and filter students",
)
def list_students(
    name: str | None = Query(default=None, min_length=1, max_length=100, description="Case-insensitive name contains filter"),
    course: str | None = Query(default=None, min_length=1, max_length=100, description="Case-insensitive exact course filter"),
    email: str | None = Query(default=None, min_length=3, max_length=320),
    born_after: date | None = Query(default=None, description="Date of birth strictly after this date"),
    born_before: date | None = Query(default=None, description="Date of birth strictly before this date"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[StudentRead]:
    """List students, optionally filtered and paginated."""
    return crud.list_students(
        db,
        name=name,
        course=course,
        email=email,
        born_after=born_after,
        born_before=born_before,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{student_id}",
    response_model=StudentRead,
    summary="Get a student by ID",
    responses={404: {"description": "Student not found"}},
)
def get_student(student_id: int, db: Session = Depends(get_db)) -> StudentRead:
    """Retrieve one student profile."""
    return _get_or_404(db, student_id)


@router.put(
    "/{student_id}",
    response_model=StudentRead,
    summary="Replace a student's details",
    responses={404: {"description": "Student not found"}, 409: {"description": "Email is already registered"}},
)
def update_student(student_id: int, payload: StudentCreate, db: Session = Depends(get_db)) -> StudentRead:
    """Replace all editable details for an existing student."""
    student = _get_or_404(db, student_id)
    try:
        return crud.replace_student(db, student, payload)
    except crud.DuplicateEmailError:
        _raise_duplicate_email()


@router.patch(
    "/{student_id}",
    response_model=StudentRead,
    summary="Partially update a student",
    responses={404: {"description": "Student not found"}, 409: {"description": "Email is already registered"}},
)
def patch_student(student_id: int, payload: StudentPatch, db: Session = Depends(get_db)) -> StudentRead:
    """Apply a partial update and validate the merged complete record."""
    student = _get_or_404(db, student_id)
    changes = payload.model_dump(exclude_unset=True)
    merged = {
        "name": student.name,
        "date_of_birth": student.date_of_birth,
        "email": student.email,
        "phone": student.phone,
        "course": student.course,
        "address": student.address,
        "enrollment_date": student.enrollment_date,
    }
    merged.update(changes)
    # Re-run all create-time/business validation against the complete merged record.
    try:
        validated = StudentCreate.model_validate(merged)
    except ValidationError as exc:
        message = "; ".join(error["msg"] for error in exc.errors())
        raise HTTPException(status_code=422, detail=message) from exc
    try:
        return crud.replace_student(db, student, validated)
    except crud.DuplicateEmailError:
        _raise_duplicate_email()


@router.delete(
    "/{student_id}",
    response_model=DeleteStudentResponse,
    summary="Delete a student",
    responses={404: {"description": "Student not found"}},
)
def remove_student(student_id: int, db: Session = Depends(get_db)) -> DeleteStudentResponse:
    """Delete a student record."""
    student = _get_or_404(db, student_id)
    crud.delete_student(db, student)
    return DeleteStudentResponse(
        message=f"Student {student_id} deleted successfully",
        student_id=student_id,
    )

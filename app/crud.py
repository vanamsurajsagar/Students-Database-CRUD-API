"""Database operations for student records. This module contains no HTTP code."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Student, utc_now_naive
from app.schemas import StudentCreate


class DuplicateEmailError(Exception):
    """Raised when a student's email is already registered."""


def _assign_student_fields(student: Student, data: StudentCreate) -> None:
    """Copy validated mutable fields from a schema onto a database model."""
    student.name = data.name
    student.date_of_birth = data.date_of_birth
    student.email = str(data.email).lower() if data.email is not None else None
    student.phone = data.phone
    student.course = data.course
    student.address = data.address
    student.enrollment_date = data.enrollment_date
    student.updated_at = utc_now_naive()


def _commit_or_raise_duplicate_email(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(exc).lower()
        if "students.email" in message or "email" in message and "unique constraint" in message:
            raise DuplicateEmailError("A student with this email already exists.") from exc
        raise


def create_student(db: Session, data: StudentCreate) -> Student:
    """Insert a new student and return the persisted model."""
    normalized_email = str(data.email).lower() if data.email is not None else None
    if normalized_email and db.scalar(select(Student.student_id).where(func.lower(Student.email) == normalized_email)):
        raise DuplicateEmailError("A student with this email already exists.")

    student = Student(
        name=data.name,
        date_of_birth=data.date_of_birth,
        email=normalized_email,
        phone=data.phone,
        course=data.course,
        address=data.address,
        enrollment_date=data.enrollment_date,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db.add(student)
    _commit_or_raise_duplicate_email(db)
    db.refresh(student)
    return student


def get_student(db: Session, student_id: int) -> Student | None:
    """Return one student by ID, or None if it does not exist."""
    return db.get(Student, student_id)


def count_students(db: Session) -> int:
    """Return the total number of student records."""
    return int(db.scalar(select(func.count()).select_from(Student)) or 0)


def list_students(
    db: Session,
    *,
    name: str | None = None,
    course: str | None = None,
    email: str | None = None,
    born_after: date | None = None,
    born_before: date | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Student]:
    """Return students matching optional filters, ordered by student ID."""
    statement = select(Student)
    if name:
        statement = statement.where(Student.name.ilike(f"%{name.strip()}%"))
    if course:
        statement = statement.where(func.lower(Student.course) == course.strip().lower())
    if email:
        statement = statement.where(func.lower(Student.email) == email.strip().lower())
    if born_after:
        statement = statement.where(Student.date_of_birth > born_after)
    if born_before:
        statement = statement.where(Student.date_of_birth < born_before)
    statement = statement.order_by(Student.student_id).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


def replace_student(db: Session, student: Student, data: StudentCreate) -> Student:
    """Replace all mutable fields for an existing student."""
    normalized_email = str(data.email).lower() if data.email is not None else None
    if normalized_email:
        existing_id = db.scalar(
            select(Student.student_id).where(
                func.lower(Student.email) == normalized_email,
                Student.student_id != student.student_id,
            )
        )
        if existing_id:
            raise DuplicateEmailError("A student with this email already exists.")
    _assign_student_fields(student, data)
    _commit_or_raise_duplicate_email(db)
    db.refresh(student)
    return student


def delete_student(db: Session, student: Student) -> None:
    """Delete a student that has already been found."""
    db.delete(student)
    db.commit()

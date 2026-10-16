"""Idempotently insert clearly fictional example students into the local database."""

from datetime import date

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Student
from app.schemas import StudentCreate
from app.crud import create_student, DuplicateEmailError

DUMMY_STUDENTS = [
    {"name": "Aarav Patel", "date_of_birth": date(2004, 5, 16), "email": "aarav.patel@example.com", "phone": "+15550001001", "course": "Computer Science", "address": "Demo Address 1, Example City", "enrollment_date": date(2023, 7, 1)},
    {"name": "Meera Joshi", "date_of_birth": date(2005, 8, 22), "email": "meera.joshi@example.com", "phone": "+15550001002", "course": "Artificial Intelligence", "address": "Demo Address 2, Example City", "enrollment_date": date(2024, 7, 1)},
    {"name": "Rohan Shah", "date_of_birth": date(2002, 1, 9), "email": "rohan.shah@example.com", "phone": "+15550001003", "course": "Data Science", "address": "Demo Address 3, Example City", "enrollment_date": date(2022, 7, 1)},
    {"name": "Anaya Desai", "date_of_birth": date(2007, 11, 3), "email": "anaya.desai@example.com", "phone": "+15550001004", "course": "Computer Science", "address": "Demo Address 4, Example City", "enrollment_date": date(2025, 7, 1)},
    {"name": "Kabir Mehta", "date_of_birth": date(2000, 3, 14), "email": "kabir.mehta@example.com", "phone": "+15550001005", "course": "Information Technology", "address": "Demo Address 5, Example City", "enrollment_date": date(2020, 7, 1)},
    {"name": "Isha Trivedi", "date_of_birth": date(2006, 6, 27), "email": "isha.trivedi@example.com", "phone": "+15550001006", "course": "Artificial Intelligence", "address": "Demo Address 6, Example City", "enrollment_date": date(2024, 7, 1)},
    {"name": "Vivaan Rao", "date_of_birth": date(2003, 9, 5), "email": "vivaan.rao@example.com", "phone": "+15550001007", "course": "Data Science", "address": "Demo Address 7, Example City", "enrollment_date": date(2023, 7, 1)},
    {"name": "Diya Nair", "date_of_birth": date(2008, 2, 18), "email": "diya.nair@example.com", "phone": "+15550001008", "course": "Computer Science", "address": "Demo Address 8, Example City", "enrollment_date": date(2025, 7, 1)},
    {"name": "Advik Kumar", "date_of_birth": date(2001, 12, 30), "email": "advik.kumar@example.com", "phone": "+15550001009", "course": "Information Technology", "address": "Demo Address 9, Example City", "enrollment_date": date(2021, 7, 1)},
    {"name": "Sara Khan", "date_of_birth": date(2005, 4, 11), "email": "sara.khan@example.com", "phone": "+15550001010", "course": "Artificial Intelligence", "address": "Demo Address 10, Example City", "enrollment_date": date(2024, 7, 1)},
]


def main() -> None:
    """Create tables and add only seed records whose email is not present."""
    Base.metadata.create_all(bind=engine)
    inserted = 0
    with SessionLocal() as db:
        for item in DUMMY_STUDENTS:
            exists = db.scalar(select(Student.student_id).where(Student.email == item["email"]))
            if exists:
                continue
            try:
                create_student(db, StudentCreate.model_validate(item))
                inserted += 1
            except DuplicateEmailError:
                # Safe if two seed processes are run at nearly the same time.
                continue
    print(f"Seed complete. Inserted {inserted} new dummy student(s); existing records were kept.")


if __name__ == "__main__":
    main()

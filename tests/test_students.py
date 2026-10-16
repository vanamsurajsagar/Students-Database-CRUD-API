"""End-to-end tests for the mandatory student CRUD API."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud
from app.database import Base
from app.models import Student
from app.schemas import StudentCreate


def payload(**overrides):
    data = {
        "name": "Aarav Patel",
        "date_of_birth": "2004-05-16",
        "email": "aarav@example.com",
        "phone": "+91 98765-43210",
        "course": "Computer Science",
        "address": "Demo Road, Example City",
        "enrollment_date": "2024-07-01",
    }
    data.update(overrides)
    return data


def create(client, **overrides):
    return client.post("/students", json=payload(**overrides))


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_student_success_and_normalization(client):
    response = create(client, email="  AARAV@EXAMPLE.COM  ", phone="+91 98765-43210", name="  Aarav Patel  ")
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == 1
    assert data["name"] == "Aarav Patel"
    assert data["email"] == "aarav@example.com"
    assert data["phone"] == "+919876543210"
    assert data["date_of_birth"] == "2004-05-16"
    assert data["created_at"]
    assert data["updated_at"]


def test_missing_name_is_rejected(client):
    data = payload()
    data.pop("name")
    assert client.post("/students", json=data).status_code == 422


def test_bad_email_is_rejected(client):
    assert create(client, email="not-an-email").status_code == 422


def test_bad_phone_is_rejected(client):
    assert create(client, phone="123-ABC").status_code == 422


def test_future_date_of_birth_is_rejected(client):
    assert create(client, date_of_birth="2999-01-01").status_code == 422


def test_date_of_birth_before_1900_is_rejected(client):
    assert create(client, date_of_birth="1899-12-31").status_code == 422


def test_missing_both_contact_methods_is_rejected(client):
    assert create(client, email=None, phone=None).status_code == 422


def test_enrollment_date_before_dob_is_rejected(client):
    assert create(client, enrollment_date="2000-01-01").status_code == 422


def test_duplicate_email_returns_409(client):
    assert create(client).status_code == 201
    response = create(client, name="Another Student", phone="+15550001002")
    assert response.status_code == 409
    assert response.json()["detail"] == "A student with this email already exists."


def test_list_students_and_name_filter(client):
    create(client, name="Anna Jones", email="anna@example.com", phone="+15550001001")
    create(client, name="Annabelle Brown", email="annabelle@example.com", phone="+15550001002")
    create(client, name="Rahul Shah", email="rahul@example.com", phone="+15550001003")
    response = client.get("/students", params={"name": "ann"})
    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["Anna Jones", "Annabelle Brown"]


def test_course_filter_is_case_insensitive_exact_match(client):
    create(client, course="Computer Science")
    create(client, name="Meera Joshi", email="meera@example.com", phone="+15550001002", course="computer science")
    create(client, name="Kiran Rao", email="kiran@example.com", phone="+15550001003", course="AI/ML")
    response = client.get("/students", params={"course": "COMPUTER SCIENCE"})
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_email_filter_is_case_insensitive(client):
    create(client, email="aarav@example.com")
    response = client.get("/students", params={"email": "AARAV@EXAMPLE.COM"})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_born_after_filter_is_strict(client):
    create(client, date_of_birth="2005-01-01")
    create(client, name="Young Student", email="young@example.com", phone="+15550001002", date_of_birth="2006-01-01")
    response = client.get("/students", params={"born_after": "2005-01-01"})
    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["Young Student"]


def test_born_before_filter_is_strict(client):
    create(client, date_of_birth="2005-01-01")
    create(client, name="Older Student", email="older@example.com", phone="+15550001002", date_of_birth="2004-12-31")
    response = client.get("/students", params={"born_before": "2005-01-01"})
    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["Older Student"]


def test_pagination_and_ordering(client):
    create(client, name="Student One", email="one@example.com", phone="+15550001001")
    create(client, name="Student Two", email="two@example.com", phone="+15550001002")
    create(client, name="Student Three", email="three@example.com", phone="+15550001003")
    response = client.get("/students", params={"skip": 1, "limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Student Two"


def test_invalid_pagination_is_rejected(client):
    assert client.get("/students", params={"skip": -1}).status_code == 422
    assert client.get("/students", params={"limit": 201}).status_code == 422


def test_count_endpoint(client):
    assert client.get("/students/count").json() == {"count": 0}
    create(client)
    assert client.get("/students/count").json() == {"count": 1}


def test_get_student_success_and_not_found(client):
    created = create(client).json()
    response = client.get(f"/students/{created['student_id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Aarav Patel"
    missing = client.get("/students/999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Student with id 999 not found"


def test_put_replaces_student_fields(client):
    created = create(client).json()
    updated_payload = payload(
        name="Updated Name",
        email="updated@example.com",
        phone="+15550009999",
        course="Data Science",
    )
    response = client.put(f"/students/{created['student_id']}", json=updated_payload)
    assert response.status_code == 200
    assert response.json()["student_id"] == created["student_id"]
    assert response.json()["name"] == "Updated Name"
    assert response.json()["course"] == "Data Science"


def test_put_missing_student_returns_404(client):
    response = client.put("/students/42", json=payload())
    assert response.status_code == 404


def test_patch_updates_only_submitted_fields(client):
    created = create(client).json()
    response = client.patch(f"/students/{created['student_id']}", json={"course": "AI/ML"})
    assert response.status_code == 200
    assert response.json()["course"] == "AI/ML"
    assert response.json()["name"] == "Aarav Patel"


def test_patch_empty_body_is_rejected(client):
    created = create(client).json()
    response = client.patch(f"/students/{created['student_id']}", json={})
    assert response.status_code == 422


def test_patch_cannot_remove_only_contact_method(client):
    created = create(client, phone=None).json()
    response = client.patch(f"/students/{created['student_id']}", json={"email": None})
    assert response.status_code == 422


def test_patch_duplicate_email_returns_409(client):
    first = create(client, email="one@example.com", phone="+15550001001").json()
    second = create(client, name="Second Student", email="two@example.com", phone="+15550001002").json()
    response = client.patch(f"/students/{second['student_id']}", json={"email": first["email"]})
    assert response.status_code == 409


def test_delete_then_get_returns_404(client):
    created = create(client).json()
    student_id = created["student_id"]
    response = client.delete(f"/students/{student_id}")
    assert response.status_code == 200
    assert response.json() == {
        "message": f"Student {student_id} deleted successfully",
        "student_id": student_id,
    }
    assert client.get(f"/students/{student_id}").status_code == 404


def test_delete_missing_student_returns_404(client):
    assert client.delete("/students/998").status_code == 404


def test_database_persists_across_brand_new_engine_and_session(tmp_path):
    database_file = tmp_path / "persistence.sqlite3"
    url = f"sqlite:///{database_file}"
    engine_one = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine_one)
    SessionOne = sessionmaker(bind=engine_one, expire_on_commit=False)
    with SessionOne() as session:
        record = crud.create_student(
            session,
            StudentCreate(
                name="Persistent Student",
                date_of_birth=date(2003, 3, 3),
                email="persistent@example.com",
                phone="+15550001009",
            ),
        )
        student_id = record.student_id
    engine_one.dispose()

    engine_two = create_engine(url, connect_args={"check_same_thread": False})
    SessionTwo = sessionmaker(bind=engine_two, expire_on_commit=False)
    with SessionTwo() as session:
        loaded = session.get(Student, student_id)
        assert loaded is not None
        assert loaded.name == "Persistent Student"
    engine_two.dispose()

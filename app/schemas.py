"""Pydantic request/response schemas and validation rules."""

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


_MIN_DATE = date(1900, 1, 1)
_PHONE_PATTERN = re.compile(r"^\+?\d{10,15}$")


def _clean_name(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _clean_email(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().lower()
        return value or None
    return value


def _clean_phone(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = re.sub(r"[\s-]", "", value.strip())
        if not cleaned:
            return None
        if not _PHONE_PATTERN.fullmatch(cleaned):
            raise ValueError("Phone must contain 10-15 digits and may start with '+'.")
        return cleaned
    return value


def _clean_optional_text(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def _validate_date(value: date | None, field_name: str) -> date | None:
    if value is None:
        return value
    if value < _MIN_DATE:
        raise ValueError(f"{field_name} must not be earlier than 1900-01-01.")
    if field_name == "Date of birth" and value > date.today():
        raise ValueError("Date of birth cannot be in the future.")
    return value


class StudentCreate(BaseModel):
    """Fields required or accepted when creating a student."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Aarav Patel",
                    "date_of_birth": "2004-05-16",
                    "email": "aarav@example.com",
                    "phone": "+919876543210",
                    "course": "Computer Science",
                    "address": "Rajkot, Gujarat",
                    "enrollment_date": "2024-07-01",
                }
            ]
        }
    )

    name: str = Field(min_length=2, max_length=100, description="Student's full name")
    date_of_birth: date = Field(description="Date of birth in YYYY-MM-DD format")
    email: EmailStr | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=16)
    course: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    enrollment_date: date | None = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: Any) -> Any:
        return _clean_name(value)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: Any) -> Any:
        return _clean_email(value)

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, value: Any) -> Any:
        return _clean_phone(value)

    @field_validator("course", "address", mode="before")
    @classmethod
    def clean_optional_text(cls, value: Any) -> Any:
        return _clean_optional_text(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, value: date) -> date:
        return _validate_date(value, "Date of birth")  # type: ignore[return-value]

    @field_validator("enrollment_date")
    @classmethod
    def validate_enrollment_date(cls, value: date | None) -> date | None:
        return _validate_date(value, "Enrollment date")

    @model_validator(mode="after")
    def validate_contact_and_dates(self) -> "StudentCreate":
        if self.email is None and self.phone is None:
            raise ValueError("At least one contact method (email or phone) must be provided.")
        if self.enrollment_date is not None and self.enrollment_date < self.date_of_birth:
            raise ValueError("Enrollment date cannot be earlier than date of birth.")
        return self


class StudentPatch(BaseModel):
    """Fields accepted for a partial student update."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"course": "Artificial Intelligence and Machine Learning"}
            ]
        }
    )

    name: str | None = Field(default=None, min_length=2, max_length=100)
    date_of_birth: date | None = None
    email: EmailStr | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=16)
    course: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    enrollment_date: date | None = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: Any) -> Any:
        return _clean_name(value)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: Any) -> Any:
        return _clean_email(value)

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, value: Any) -> Any:
        return _clean_phone(value)

    @field_validator("course", "address", mode="before")
    @classmethod
    def clean_optional_text(cls, value: Any) -> Any:
        return _clean_optional_text(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, value: date | None) -> date | None:
        return _validate_date(value, "Date of birth")

    @field_validator("enrollment_date")
    @classmethod
    def validate_enrollment_date(cls, value: date | None) -> date | None:
        return _validate_date(value, "Enrollment date")

    @model_validator(mode="after")
    def validate_patch_fields(self) -> "StudentPatch":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for a PATCH request.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Name cannot be null.")
        if "date_of_birth" in self.model_fields_set and self.date_of_birth is None:
            raise ValueError("Date of birth cannot be null.")
        return self


class StudentRead(BaseModel):
    """Student representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    student_id: int
    name: str
    date_of_birth: date
    email: EmailStr | None
    phone: str | None
    course: str | None
    address: str | None
    enrollment_date: date | None
    created_at: datetime
    updated_at: datetime


class StudentCount(BaseModel):
    """Count response."""

    count: int


class DeleteStudentResponse(BaseModel):
    """Response returned after deleting a student."""

    message: str
    student_id: int


class ErrorResponse(BaseModel):
    """Generic API error response."""

    detail: str

"""Tests for allow-listed intents and the optional Ollama endpoint."""

import httpx

from app.ai import service
from app.ai.intents import detect_intent


def payload(**overrides):
    data = {
        "name": "Aarav Patel",
        "date_of_birth": "2004-05-16",
        "email": "aarav@example.com",
        "phone": "+15550001001",
        "course": "Computer Science",
    }
    data.update(overrides)
    return data


def test_intent_count_students():
    intent = detect_intent("How many students are there?")
    assert intent is not None
    assert intent.name == "count_students"


def test_intent_birth_year_boundary():
    intent = detect_intent("List students born after 2005")
    assert intent is not None
    assert intent.name == "list_students"
    assert str(intent.filters["born_after"]) == "2005-12-31"


def test_unsupported_question_gives_helpful_response(client):
    response = client.post("/ai/ask", json={"question": "Tell me a joke"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "unsupported"
    assert "list students born after 2005" in data["answer"]
    assert data["records_used"] == 0


def test_ai_endpoint_uses_ollama_when_available(client, monkeypatch):
    client.post("/students", json=payload())
    captured = {}

    def fake_generate(question, context):
        captured["question"] = question
        captured["context"] = context
        return "There is 1 student in the database."

    monkeypatch.setattr(service, "generate_with_ollama", fake_generate)
    response = client.post("/ai/ask", json={"question": "How many students are there?"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "There is 1 student in the database."
    assert data["ollama_available"] is True
    assert captured["context"] == {"count": 1}


def test_ai_falls_back_to_database_grounded_answer_when_ollama_fails(client, monkeypatch):
    client.post("/students", json=payload())

    def failed_generate(question, context):
        raise httpx.ConnectError("Ollama is not running")

    monkeypatch.setattr(service, "generate_with_ollama", failed_generate)
    response = client.post("/ai/ask", json={"question": "How many students are there?"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "There are 1 student record(s) in the database."
    assert data["ollama_available"] is False


def test_ai_born_after_2005_uses_only_matching_records(client, monkeypatch):
    client.post("/students", json=payload(date_of_birth="2005-12-31"))
    client.post(
        "/students",
        json=payload(name="Young Student", email="young@example.com", phone="+15550001002", date_of_birth="2006-01-01"),
    )
    captured = {}

    def fake_generate(question, context):
        captured["context"] = context
        return "The matching student was born in 2006."

    monkeypatch.setattr(service, "generate_with_ollama", fake_generate)
    response = client.post("/ai/ask", json={"question": "List students born after 2005"})
    assert response.status_code == 200
    assert response.json()["records_used"] == 1
    assert [row["name"] for row in captured["context"]["records"]] == ["Young Student"]


def test_ai_omits_contact_fields_unless_question_needs_them(client, monkeypatch):
    client.post("/students", json=payload())
    seen = []

    def fake_generate(question, context):
        seen.append(context)
        return "Student found."

    monkeypatch.setattr(service, "generate_with_ollama", fake_generate)
    client.post("/ai/ask", json={"question": "Show student ID 1"})
    client.post("/ai/ask", json={"question": "Show student ID 1 and their email"})
    assert "email" not in seen[0]["records"][0]
    assert seen[1]["records"][0]["email"] == "aarav@example.com"


def test_ai_get_nonexistent_student_is_deterministic(client, monkeypatch):
    def should_not_call_model(question, context):
        raise AssertionError("Ollama should not be called when no record exists")

    monkeypatch.setattr(service, "generate_with_ollama", should_not_call_model)
    response = client.post("/ai/ask", json={"question": "Show student ID 123"})
    assert response.status_code == 200
    assert response.json()["answer"] == "I couldn't find a student with ID 123."
    assert response.json()["ollama_available"] is False


def test_ai_does_not_call_model_for_empty_results(client, monkeypatch):
    def should_not_call_model(question, context):
        raise AssertionError("Ollama should not be called when no records match")

    monkeypatch.setattr(service, "generate_with_ollama", should_not_call_model)
    response = client.post("/ai/ask", json={"question": "List students born after 2005"})
    assert response.status_code == 200
    assert response.json()["answer"] == "No matching student records were found."
    assert response.json()["ollama_available"] is False


def test_intent_course_question(client, monkeypatch):
    intent = detect_intent("How many students are in Python?")
    assert intent is not None
    assert intent.name == "students_in_course"
    assert intent.filters["course"] == "Python"

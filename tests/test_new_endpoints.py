from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mindloom.models import EthemeralTaskType, Status

app_module = importlib.import_module("mindloom.app")


@dataclass(frozen=True)
class EndpointCase:
    path: str
    payload: dict[str, Any]
    task_type: EthemeralTaskType
    expected_content: str


ENDPOINT_CASES = [
    EndpointCase(
        path="/summarize",
        payload={
            "content": "Mindloom helps automate writing workflows.",
            "max_length": 25,
            "model": "ministral-3:latest",
        },
        task_type=EthemeralTaskType.SUMMARIZE,
        expected_content="Maximum length: 25\n\nMindloom helps automate writing workflows.",
    ),
    EndpointCase(
        path="/translate",
        payload={
            "content": "Please send the report by Friday.",
            "target_language": "German",
            "source_language": "English",
            "model": "ministral-3:latest",
        },
        task_type=EthemeralTaskType.TRANSLATE,
        expected_content=(
            "Target language: German\n"
            "Source language: English\n\n"
            "Please send the report by Friday."
        ),
    ),
    EndpointCase(
        path="/code/explain",
        payload={
            "content": "def add(a, b):\n    return a + b",
            "language": "Python",
            "model": "ministral-3:latest",
        },
        task_type=EthemeralTaskType.EXPLAIN_CODE,
        expected_content="Language: Python\n\ndef add(a, b):\n    return a + b",
    ),
    EndpointCase(
        path="/git/commit-message",
        payload={
            "content": "diff --git a/app.py b/app.py\n+print('hello')",
            "model": "ministral-3:latest",
        },
        task_type=EthemeralTaskType.COMMIT_MESSAGE,
        expected_content="diff --git a/app.py b/app.py\n+print('hello')",
    ),
    EndpointCase(
        path="/extract/actions",
        payload={
            "content": "1) Finalize roadmap. 2) Share with team. 3) Book kickoff call.",
            "model": "ministral-3:latest",
        },
        task_type=EthemeralTaskType.EXTRACT_ACTIONS,
        expected_content="1) Finalize roadmap. 2) Share with team. 3) Book kickoff call.",
    ),
    EndpointCase(
        path="/rewrite/tone",
        payload={
            "content": "Can you send that update soon?",
            "target_tone": "formal",
            "model": "ministral-3:latest",
        },
        task_type=EthemeralTaskType.REWRITE_TONE,
        expected_content="Target tone: formal\n\nCan you send that update soon?",
    ),
    EndpointCase(
        path="/proofread",
        payload={
            "content": "The team have delivered there report yesterday.",
            "model": "ministral-3:latest",
        },
        task_type=EthemeralTaskType.PROOFREAD,
        expected_content="The team have delivered there report yesterday.",
    ),
    EndpointCase(
        path="/code/generate-tests",
        payload={
            "content": "def divide(a, b):\n    return a / b",
            "language": "Python",
            "framework": "pytest",
            "model": "ministral-3:latest",
        },
        task_type=EthemeralTaskType.GENERATE_TESTS,
        expected_content="Language: Python\nFramework: pytest\n\ndef divide(a, b):\n    return a / b",
    ),
]


@pytest.fixture
def make_harness(monkeypatch: pytest.MonkeyPatch):
    def _make(chat_raises: bool = False, raise_server_exceptions: bool = True):
        create_calls: list[Any] = []
        update_calls: list[dict[str, Any]] = []

        monkeypatch.setattr(app_module.database, "init_db", lambda: None)
        monkeypatch.setattr(app_module.database, "close_db", lambda: None)

        def fake_create_job(_db, job_data):
            create_calls.append(job_data)
            return SimpleNamespace(id=1000 + len(create_calls))

        def fake_update_job_status(_db, job_id, status, result=None):
            update_calls.append({"job_id": job_id, "status": status, "result": result})
            return None

        if chat_raises:
            def fake_chat_ollama(_user_input, _system_prompt, _model=None):
                raise RuntimeError("simulated LLM failure")
        else:
            def fake_chat_ollama(_user_input, _system_prompt, _model=None):
                return SimpleNamespace(content="mocked response")

        monkeypatch.setattr(app_module.database, "create_job", fake_create_job)
        monkeypatch.setattr(app_module.database, "update_job_status", fake_update_job_status)
        monkeypatch.setattr(app_module, "chat_ollama", fake_chat_ollama)

        def override_get_db():
            yield object()

        app_module.app.dependency_overrides[app_module.get_db] = override_get_db
        client = TestClient(app_module.app, raise_server_exceptions=raise_server_exceptions)
        return client, create_calls, update_calls

    yield _make
    app_module.app.dependency_overrides.clear()


@pytest.mark.parametrize("case", ENDPOINT_CASES, ids=lambda case: case.path)
def test_new_endpoints_happy_path_returns_section_response(case: EndpointCase, make_harness):
    client, _, _ = make_harness()
    with client:
        response = client.post(case.path, json=case.payload)

    assert response.status_code == 200
    data = response.json()
    assert data == {"content": "mocked response", "length": len("mocked response")}


@pytest.mark.parametrize("case", ENDPOINT_CASES, ids=lambda case: case.path)
def test_new_endpoints_persist_job_with_expected_task_type(case: EndpointCase, make_harness):
    client, create_calls, update_calls = make_harness()
    with client:
        response = client.post(case.path, json=case.payload)

    assert response.status_code == 200
    assert len(create_calls) == 1
    assert create_calls[0].task_type is case.task_type
    assert create_calls[0].content == case.expected_content
    assert update_calls[-1]["status"] is Status.COMPLETED
    assert update_calls[-1]["result"] == "mocked response"


@pytest.mark.parametrize("case", ENDPOINT_CASES, ids=lambda case: case.path)
def test_new_endpoints_mark_job_failed_when_llm_errors(case: EndpointCase, make_harness):
    client, _, update_calls = make_harness(chat_raises=True, raise_server_exceptions=False)
    with client:
        response = client.post(case.path, json=case.payload)

    assert response.status_code == 500
    assert update_calls[-1]["status"] is Status.FAILED

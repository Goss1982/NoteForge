# ruff: noqa: E402
import os
import tempfile
from pathlib import Path

# Tests always use an isolated temporary DB and files, never deployment state.
_test_root = tempfile.TemporaryDirectory(prefix="noteforge-tests-")
os.environ["DATABASE_URL"] = os.environ.get("NOTEFORGE_TEST_DATABASE_URL") or "sqlite:///" + str(
    Path(_test_root.name) / "test.db"
)
os.environ["DATA_DIR"] = str(Path(_test_root.name) / "data")
os.environ["ADMIN_PASSWORD"] = "test-password-for-noteforge"
os.environ["SECRET_KEY"] = "test-signing-key-32-characters-minimum"
os.environ["COOKIE_SECURE"] = "false"
os.environ["PUBLIC_URL"] = "http://testserver"
os.environ["OPENAI_API_KEY"] = ""
os.environ["RMAPI_CONFIG"] = str(Path(_test_root.name) / "unpaired")

import fitz
import pytest
from fastapi.testclient import TestClient

from app.auth import failures
from app.db import Base, Session, engine
from app.main import app


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    failures.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"password": os.environ["ADMIN_PASSWORD"]}).status_code == 200
        yield c


@pytest.fixture
def pdf_bytes():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 60), "Alex to send the proposal on Friday. Budget: GBP 2500.")
        return doc.tobytes()


@pytest.fixture
def imported(client, pdf_bytes):
    response = client.post(
        "/api/notebooks/import", files={"file": ("Meeting.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 202, response.text
    return response.json()


@pytest.fixture
def extraction():
    return {
        "transcript": "Alex to send the proposal on Friday. Budget: GBP 2500.",
        "category": "Meeting",
        "purpose": "Possible planning meeting",
        "blocks": [
            {
                "kind": "text",
                "text": "Alex to send the proposal on Friday. Budget: GBP 2500.",
                "evidence_quote": "Budget: GBP 2500.",
                "confidence": 0.9,
                "uncertain": False,
            }
        ],
        "insights": [
            {
                "kind": "action",
                "text": "Send the proposal",
                "evidence_quote": "Alex to send the proposal on Friday.",
                "owner": "Alex",
                "due_date": "Friday",
                "confidence": 0.9,
            }
        ],
        "uncertainties": [],
    }


@pytest.fixture
def provider(monkeypatch, extraction):
    from app.schemas import DocumentContent, Extraction

    class Provider:
        model = "test-vision-model"
        calls = 0

        def close(self):
            pass

        def extract(self, path):
            assert path.is_file()
            self.__class__.calls += 1
            return Extraction.model_validate(extraction)

        def generate(self, kind, pages):
            return DocumentContent.model_validate(
                {
                    "title": "Meeting follow-up",
                    "sections": [
                        {
                            "heading": "Actions",
                            "paragraphs": [
                                {
                                    "kind": "fact",
                                    "text": "Alex is to send the proposal on Friday.",
                                    "citations": [
                                        {
                                            "page_id": pages[0]["page_id"],
                                            "quote": "Alex to send the proposal on Friday.",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                    "missing_information": ["Meeting date not specified"],
                }
            )

    monkeypatch.setattr("app.services.AIProvider", Provider)
    return Provider


@pytest.fixture
def ready(client, imported, provider):
    from app.jobs import claim, finish
    from app.models import Job
    from app.services import generate_document, process_revision

    item = claim()
    assert item
    process_revision(item[0], imported["revision_id"])
    finish(*item)
    auto = claim()
    assert auto
    with Session() as db:
        payload = db.get(Job, auto[0]).payload
    generate_document(auto[0], payload["revision_id"], payload["kind"])
    finish(*auto)
    return {**imported, "document_id": auto[0]}

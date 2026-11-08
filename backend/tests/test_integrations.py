import json
import subprocess
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI
from sqlalchemy import func, select

from app.config import settings
from app.db import Session
from app.jobs import enqueue
from app.models import Notebook, Revision
from app.providers import AIProvider
from app.remarkable import RemarkableClient
from app.services import sync_cloud


def test_real_sdk_responses_contract(monkeypatch, tmp_path, extraction):
    seen = []

    def handle(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "error": None,
                "incomplete_details": None,
                "instructions": None,
                "max_output_tokens": 10000,
                "model": "test-vision",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": json.dumps(extraction), "annotations": []}
                        ],
                    }
                ],
                "parallel_tool_calls": False,
                "tools": [],
                "tool_choice": "auto",
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
            },
        )

    cfg = settings()
    monkeypatch.setattr(cfg, "openai_api_key", "test-key")
    provider = AIProvider()
    provider.client = OpenAI(
        api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handle)), max_retries=0
    )
    image = tmp_path / "image.png"
    image.write_bytes(b"png-test-fixture")
    result = provider.extract(image)
    assert result.transcript == extraction["transcript"]
    request = seen[0]
    assert request["store"] is False
    assert request["input"][0]["content"][1]["type"] == "input_image"
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True
    provider.client.close()


def test_missing_ai_configuration_is_explicit():
    with pytest.raises(RuntimeError, match="not configured"):
        AIProvider()


def test_rmapi_uses_json_noninteractive_and_no_shell(monkeypatch, tmp_path):
    config = tmp_path / "rmapi.conf"
    config.write_text("private-token-fixture")
    monkeypatch.setattr(settings(), "rmapi_config", config)
    seen = []

    def run(args, **kwargs):
        seen.append((args, kwargs))
        assert kwargs.get("shell", False) is False
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                [
                    {"id": "uuid", "name": "Folder", "type": "CollectionType"},
                    {"id": "12345678-1234-1234-1234-123456789012", "name": "Notes", "type": "DocumentType"},
                ]
            ),
        )

    monkeypatch.setattr(subprocess, "run", run)
    docs = RemarkableClient().list_documents()
    assert len(docs) == 1
    assert seen[0][0][1:] == ["-ni", "-json", "find", "/"]
    assert seen[0][1]["env"]["RMAPI_CONFIG"] == str(config)


def test_rmapi_failures_never_expose_tokens(monkeypatch, tmp_path):
    config = tmp_path / "rmapi.conf"
    config.write_text("token")
    monkeypatch.setattr(settings(), "rmapi_config", config)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="sensitive-token", stderr="token"),
    )
    with pytest.raises(RuntimeError) as error:
        RemarkableClient().list_documents()
    assert "sensitive-token" not in str(error.value)


def test_sync_is_incremental_preserves_revisions_and_detects_renames(monkeypatch, client, pdf_bytes):
    import io
    import zipfile

    nodes = [
        {
            "id": "12345678-1234-1234-1234-123456789012",
            "type": "DocumentType",
            "name": "Planning",
            "version": 1,
            "modifiedClient": "2026-11-08T10:00:00Z",
            "parent": "",
        }
    ]
    downloads = []

    class Client:
        def list_documents(self):
            return nodes

        def download(self, id):
            downloads.append(id)
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as z:
                z.writestr("doc.content", json.dumps({"pages": ["page"]}))
                z.writestr("doc.pdf", pdf_bytes + f"\n%version {nodes[0]['version']}".encode())
            return stream.getvalue()

    monkeypatch.setattr("app.services.RemarkableClient", Client)
    with Session.begin() as db:
        j = enqueue(db, "sync", {}, "sync")
        job_id = j.id
    sync_cloud(job_id)
    sync_cloud(job_id)
    assert len(downloads) == 1
    nodes[0]["version"] = 2
    sync_cloud(job_id)
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Notebook)) == 1
        assert db.scalar(select(func.count()).select_from(Revision)) == 2
    nodes[0]["name"] = "Renamed planning"
    sync_cloud(job_id)
    with Session() as db:
        assert db.scalar(select(Notebook)).title == "Renamed planning"
        assert db.scalar(select(func.count()).select_from(Revision)) == 2
    assert len(downloads) == 3


def test_migration_round_trip_and_model_parity():
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext

    from alembic import command
    from app.db import Base, engine

    Base.metadata.drop_all(engine)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_postgres_concurrent_claims_are_unique():
    from concurrent.futures import ThreadPoolExecutor

    from app.db import engine
    from app.jobs import claim

    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL SKIP LOCKED concurrency is exercised in the PostgreSQL CI job")
    with Session.begin() as db:
        for index in range(12):
            enqueue(db, "sync", {}, f"concurrent-{index}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(lambda _: claim(), range(12)))
    ids = [item[0] for item in claimed if item]
    assert len(ids) == len(set(ids)) == 12

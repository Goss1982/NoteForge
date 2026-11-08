import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from .config import settings
from .db import Session
from .jobs import enqueue, progress
from .models import AuditLog, Document, DocumentVersion, Notebook, Page, Revision, now
from .providers import AIProvider, validate_document
from .remarkable import RemarkableClient
from .rendering import render_pages, validate_upload
from .storage import safe_path, store_original


def ingest(db, data: bytes, filename: str, notebook: Notebook | None = None):
    suffix = Path(filename).suffix.lower()
    validate_upload(data, suffix)
    digest, path = store_original(data, suffix)
    if notebook is None:
        notebook = Notebook(title=Path(filename).stem[:500], source="upload")
        db.add(notebook)
        db.flush()
    existing = db.scalar(
        select(Revision).where(Revision.notebook_id == notebook.id, Revision.sha256 == digest)
    )
    if existing:
        notebook.latest_revision_id = existing.id
        notebook.updated_at = now()
        # If a previously seen version returns, preserve it and retry only unfinished work.
        if existing.status != "ready":
            enqueue(db, "process", {"revision_id": existing.id}, f"process:{existing.id}")
        return notebook, existing
    revision = Revision(notebook_id=notebook.id, sha256=digest, original_path=path, filename=filename[:500])
    db.add(revision)
    db.flush()
    notebook.latest_revision_id = revision.id
    notebook.updated_at = now()
    enqueue(db, "process", {"revision_id": revision.id}, f"process:{revision.id}")
    db.add(AuditLog(action="source.ingested", target=revision.id, detail={"sha256": digest}))
    return notebook, revision


def sync_cloud(job_id: str):
    client = RemarkableClient()
    nodes = client.list_documents()
    count = 0
    errors = 0
    for i, node in enumerate(nodes):
        if node.get("parent") == "trash":
            continue
        # rmapi writes remote names to its download working directory.
        name = node.get("name", "")
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            errors += 1
            continue
        version = hashlib.sha256(
            json.dumps(
                [node.get("version"), node.get("modifiedClient"), name], separators=(",", ":")
            ).encode()
        ).hexdigest()
        with Session() as db:
            notebook = db.scalar(select(Notebook).where(Notebook.external_id == node["id"]))
            if notebook and notebook.remote_version == version:
                continue
        progress(job_id, f"Downloading cloud notebook {i + 1} of {len(nodes)}")
        try:
            data = client.download(node["id"])
            with Session.begin() as db:
                notebook = db.scalar(select(Notebook).where(Notebook.external_id == node["id"]))
                if not notebook:
                    notebook = Notebook(title=name[:500], source="remarkable", external_id=node["id"])
                    db.add(notebook)
                    db.flush()
                notebook.title = name[:500]
                ingest(db, data, name + ".rmdoc", notebook)
                notebook.remote_version = version
            count += 1
        except Exception:
            errors += 1
            # Failure is visible, without exposing external payloads or tokens.
            with Session.begin() as db:
                db.add(AuditLog(action="sync.item_failed", target=str(node.get("id", "unknown")), detail={}))
    if errors:
        raise RuntimeError(f"Synced {count} changed notebooks; {errors} cloud items failed. See audit log.")
    with Session.begin() as db:
        db.add(
            AuditLog(action="sync.completed", target=job_id, detail={"changed": count, "listed": len(nodes)})
        )


def process_revision(job_id: str, revision_id: str):
    with Session() as db:
        revision = db.get(Revision, revision_id)
        if not revision:
            raise ValueError("Source revision does not exist")
        path = safe_path(revision.original_path)
        if revision.status != "ready":
            revision.status = "processing"
            db.commit()
        has_pages = db.scalar(select(Page.id).where(Page.revision_id == revision_id).limit(1))
    if not has_pages:
        progress(job_id, "Rendering original pages")
        images, warning = render_pages(path, revision_id)
        with Session.begin() as db:
            for number, image in enumerate(images, 1):
                db.add(Page(revision_id=revision_id, number=number, image_path=str(image)))
            revision = db.get(Revision, revision_id)
            revision.warning = warning
            revision.status = "processing"
    provider = AIProvider()
    try:
        with Session() as db:
            page_ids = db.scalars(
                select(Page.id).where(Page.revision_id == revision_id).order_by(Page.number)
            ).all()
        for i, page_id in enumerate(page_ids):
            with Session() as db:
                page = db.get(Page, page_id)
                if page.extraction is not None:
                    continue
                image = safe_path(page.image_path)
            progress(job_id, f"Reading handwriting · page {i + 1} of {len(page_ids)}")
            result = provider.extract(image)
            with Session.begin() as db:
                page = db.get(Page, page_id)
                page.extraction = result.model_dump()
                page.search_text = result.transcript
                page.model = provider.model
    finally:
        provider.close()
    with Session.begin() as db:
        revision = db.get(Revision, revision_id)
        revision.status = "ready"
        notebook = db.get(Notebook, revision.notebook_id)
        pages = db.scalars(select(Page).where(Page.revision_id == revision_id)).all()
        categories = [
            p.extraction["category"] for p in pages if p.extraction and p.extraction["transcript"].strip()
        ]
        if notebook.latest_revision_id == revision_id:
            notebook.category = max(sorted(set(categories)), key=categories.count) if categories else "Other"
        if (
            settings().auto_document_type
            and any(p.search_text.strip() for p in pages)
            and not db.scalar(
                select(Document.id)
                .where(Document.revision_id == revision_id, Document.kind == settings().auto_document_type)
                .limit(1)
            )
        ):
            enqueue(
                db,
                "generate",
                {"revision_id": revision_id, "kind": settings().auto_document_type},
                f"auto-generate:{revision_id}",
            )
        db.add(AuditLog(action="extraction.completed", target=revision_id, detail={"pages": len(pages)}))


def generate_document(job_id: str, revision_id: str, kind: str):
    with Session() as db:
        if db.get(Document, job_id):
            return
        revision = db.get(Revision, revision_id)
        if not revision or revision.status != "ready":
            raise ValueError("Source extraction is not complete")
        pages = db.scalars(select(Page).where(Page.revision_id == revision_id).order_by(Page.number)).all()
        payload = [{"page_id": p.id, "page_number": p.number, "extraction": p.extraction} for p in pages]
        notebook_id = revision.notebook_id
    if not any(p["extraction"]["transcript"].strip() for p in payload):
        raise ValueError("Notebook has no legible content to generate from")
    progress(job_id, "Drafting document and validating source citations")
    provider = AIProvider()
    try:
        content = provider.generate(kind, payload)
    finally:
        provider.close()
    validate_document(content, {p["page_id"]: p["extraction"]["transcript"] for p in payload})
    with Session.begin() as db:
        if db.get(Document, job_id):
            return
        db.add(
            Document(
                id=job_id,
                notebook_id=notebook_id,
                revision_id=revision_id,
                title=content.title,
                kind=kind,
                content=content.model_dump(),
                model=provider.model,
            )
        )
        db.flush()
        db.add(DocumentVersion(document_id=job_id, number=1, content=content.model_dump(), reviewed=False))
        db.add(AuditLog(action="document.generated", target=job_id, detail={"revision_id": revision_id}))

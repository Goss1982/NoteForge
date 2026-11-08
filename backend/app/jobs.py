from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .db import Session
from .models import Job, Revision, now, uid

LEASE_SECONDS = 600
MAX_ATTEMPTS = 3


def enqueue(db, kind: str, payload: dict, key: str) -> Job:
    existing = db.scalar(select(Job).where(Job.active_key == key))
    if existing:
        return existing
    job = Job(kind=kind, payload=payload, active_key=key)
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        return db.scalar(select(Job).where(Job.active_key == key))
    return job


def claim() -> tuple[str, str] | None:
    with Session.begin() as db:
        stamp = now()
        # Reclaim leases after process failure. Three attempts is a hard bound.
        stale = db.scalars(
            select(Job)
            .where(Job.status == "running", Job.lease_until < stamp)
            .with_for_update(skip_locked=True)
        ).all()
        for job in stale:
            job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
            job.error = "Worker lease expired"
            if job.status == "failed":
                job.active_key = None
                if job.kind == "process":
                    revision = db.get(Revision, job.payload.get("revision_id"))
                    if revision and revision.status != "ready":
                        revision.status = "failed"
            job.updated_at = stamp
        job = db.scalar(
            select(Job)
            .where(Job.status == "queued", Job.available_at <= stamp)
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.status = "running"
        job.attempts += 1
        job.lease_token = uid()
        job.lease_until = stamp + timedelta(seconds=LEASE_SECONDS)
        job.updated_at = stamp
        return job.id, job.lease_token


def heartbeat(job_id: str, token: str):
    with Session.begin() as db:
        result = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.lease_token == token, Job.status == "running")
            .values(lease_until=now() + timedelta(seconds=LEASE_SECONDS), updated_at=now())
        )
        return result.rowcount == 1


def progress(job_id: str, message: str):
    with Session.begin() as db:
        job = db.get(Job, job_id)
        job.progress = message[:500]
        job.updated_at = now()


def finish(job_id: str, token: str, error: str | None = None):
    with Session.begin() as db:
        job = db.get(Job, job_id)
        if job.lease_token != token or job.status != "running":
            return
        if error:
            job.error = error[:1000]
            job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
            job.available_at = now() + timedelta(seconds=30 * 2**job.attempts)
            job.progress = "Retry scheduled" if job.status == "queued" else "Needs attention"
        else:
            job.status = "completed"
            job.error = None
            job.progress = "Completed"
        job.updated_at = now()
        job.lease_until = None
        if job.status in ("completed", "failed"):
            job.active_key = None

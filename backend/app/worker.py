import logging
import signal
import threading
from datetime import timedelta

from sqlalchemy import select

from .config import settings
from .db import Session
from .jobs import claim, enqueue, finish, heartbeat
from .models import Job, Revision, RuntimeState, now
from .services import generate_document, process_revision, sync_cloud

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("noteforge.worker")
stop = threading.Event()


def tick():
    with Session.begin() as db:
        state = db.get(RuntimeState, "worker")
        if not state:
            db.add(RuntimeState(key="worker", value="running", updated_at=now()))
        else:
            state.updated_at = now()
        if settings().rmapi_config.is_file():
            latest = db.scalar(select(Job).where(Job.kind == "sync").order_by(Job.created_at.desc()).limit(1))
            if not latest or latest.created_at.replace(tzinfo=now().tzinfo) < now() - timedelta(
                seconds=settings().sync_interval_seconds
            ):
                enqueue(db, "sync", {}, "sync")


def execute(job_id: str, token: str):
    done = threading.Event()

    def keepalive():
        while not done.wait(30):
            if not heartbeat(job_id, token):
                return

    thread = threading.Thread(target=keepalive, daemon=True)
    thread.start()
    try:
        with Session() as db:
            job = db.get(Job, job_id)
            kind, payload = job.kind, job.payload
        if kind == "sync":
            sync_cloud(job_id)
        elif kind == "process":
            process_revision(job_id, payload["revision_id"])
        elif kind == "generate":
            generate_document(job_id, payload["revision_id"], payload["kind"])
        else:
            raise ValueError("Unknown job type")
        finish(job_id, token)
    except Exception as exc:
        # Do not persist SDK exception bodies: they can contain user data or credentials.
        safe_error = (
            str(exc)
            if isinstance(exc, (ValueError, RuntimeError))
            else f"{type(exc).__name__}: processing failed; check provider configuration and server connectivity."
        )
        log.warning("Job %s failed (%s)", job_id, type(exc).__name__)
        finish(job_id, token, safe_error)
        with Session.begin() as db:
            job = db.get(Job, job_id)
            if job.status == "failed" and job.kind == "process":
                revision = db.get(Revision, job.payload["revision_id"])
                if revision:
                    revision.status = "failed"
    finally:
        done.set()
        thread.join(timeout=2)


def main():
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.is_set():
        try:
            tick()
            item = claim()
            if item:
                execute(*item)
            else:
                stop.wait(3)
        except Exception as exc:
            log.error("Worker loop error: %s", type(exc).__name__)
            stop.wait(5)


if __name__ == "__main__":
    main()

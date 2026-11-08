"""Container healthcheck: idle heartbeat OR active job lease renewal must be recent."""

import sys
from datetime import timedelta

from sqlalchemy import select

from .db import Session
from .models import Job, RuntimeState, now


def main():
    with Session() as db:
        state = db.get(RuntimeState, "worker")
        job = db.scalar(select(Job).where(Job.status == "running").order_by(Job.updated_at.desc()).limit(1))
        stamps = [s for s in [state.updated_at if state else None, job.updated_at if job else None] if s]
        ok = stamps and max(s.replace(tzinfo=now().tzinfo) for s in stamps) > now() - timedelta(seconds=100)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

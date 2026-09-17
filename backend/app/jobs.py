"""Tracks jobs in Redis.

RQ handles the queued/started/finished/failed status. We attach our own
fields to each job (filename, batch ID, which model was used, when it was
created). When several files are uploaded together, their job IDs are
grouped into a batch so the UI can poll them all at once.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from redis import Redis
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job as RqJob

from .config import get_settings

QUEUE_NAME = "default"
BATCH_KEY = "selfbg:batch:{batch_id}"


@lru_cache(maxsize=1)
def _connection() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def _queue() -> Queue:
    return Queue(QUEUE_NAME, connection=_connection())


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def job_dir(job_id: str) -> Path:
    return Path(get_settings().data_dir) / job_id


def input_path(job_id: str, suffix: str) -> Path:
    return job_dir(job_id) / f"input{suffix}"


def result_path(job_id: str) -> Path:
    return job_dir(job_id) / "result.png"


@dataclass
class JobView:
    id: str
    status: str
    filename: str
    batch_id: str | None
    model: str
    created_at: str
    started_at: str | None
    ended_at: str | None
    error: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def enqueue_job(
    job_id: str,
    filename: str,
    batch_id: str,
    model_name: str | None = None,
) -> None:
    from .tasks import process_image  # local import breaks the tasks<->jobs cycle

    settings = get_settings()
    _queue().enqueue_call(
        func=process_image,
        args=(job_id,),
        kwargs={"model_name": model_name},
        job_id=job_id,
        meta={
            "filename": filename,
            "batch_id": batch_id,
            "model": model_name or settings.model,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        result_ttl=settings.result_ttl_seconds,
        failure_ttl=settings.result_ttl_seconds,
        ttl=settings.result_ttl_seconds,
    )

    conn = _connection()
    key = BATCH_KEY.format(batch_id=batch_id)
    conn.sadd(key, job_id)
    conn.expire(key, settings.result_ttl_seconds)


def get_job(job_id: str) -> JobView | None:
    try:
        j = RqJob.fetch(job_id, connection=_connection())
    except NoSuchJobError:
        return None
    meta = j.meta or {}
    return JobView(
        id=j.id,
        status=j.get_status(),
        filename=meta.get("filename", ""),
        batch_id=meta.get("batch_id"),
        model=meta.get("model", get_settings().model),
        created_at=meta.get("created_at", ""),
        started_at=j.started_at.isoformat() if j.started_at else None,
        ended_at=j.ended_at.isoformat() if j.ended_at else None,
        error=(j.exc_info.strip().splitlines()[-1] if j.is_failed and j.exc_info else None),
    )


def get_batch(batch_id: str) -> list[JobView] | None:
    conn = _connection()
    key = BATCH_KEY.format(batch_id=batch_id)
    raw_ids = conn.smembers(key)
    if not raw_ids:
        return None
    ids = sorted(rid.decode() for rid in raw_ids)
    jobs = [get_job(job_id) for job_id in ids]
    return [j for j in jobs if j is not None]

"""Deletes old job folders from disk on a loop.

RQ auto-expires job records in Redis after `result_ttl_seconds`, but the
uploaded image and result PNG on disk would sit there forever without a
cleanup pass. This container runs that pass every hour by default: for
each folder under /data/jobs, if its Redis record is gone (or the folder
is much older than the TTL and has no record at all), the folder is
deleted.

Run as `python -m app.workers.cleaner`.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq.exceptions import NoSuchJobError
from rq.job import Job as RqJob

from ..config import get_settings

logger = logging.getLogger(__name__)

# Skip folders that were created very recently, in case the API just wrote
# the file and is about to enqueue the job. Prevents a rare race where the
# cleaner would delete a folder between the write and the enqueue call.
CREATION_GRACE_SECONDS = 300


def _connection() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def clean_once(now: float | None = None) -> tuple[int, int]:
    """Run one cleanup pass. Returns (folders scanned, folders deleted)."""
    settings = get_settings()
    data_root = Path(settings.data_dir)
    if not data_root.exists():
        return (0, 0)

    now_epoch = time.time() if now is None else now
    max_age = settings.result_ttl_seconds
    connection = _connection()

    scanned = 0
    deleted = 0

    for folder in data_root.iterdir():
        if not folder.is_dir():
            continue

        age = now_epoch - folder.stat().st_mtime
        if age < CREATION_GRACE_SECONDS:
            continue

        scanned += 1

        try:
            RqJob.fetch(folder.name, connection=connection)
            job_exists = True
        except NoSuchJobError:
            job_exists = False

        should_delete = (not job_exists) or age > (max_age * 2)

        if should_delete:
            try:
                shutil.rmtree(folder)
                deleted += 1
            except OSError as exc:
                logger.warning("Failed to delete %s: %s", folder, exc)

    return (scanned, deleted)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    interval = get_settings().cleanup_interval_seconds
    logger.info("Cleaner started; scanning %s every %ds", get_settings().data_dir, interval)

    while True:
        try:
            scanned, deleted = clean_once()
            if scanned or deleted:
                logger.info("Cleanup pass: scanned=%d deleted=%d", scanned, deleted)
        except RedisConnectionError as exc:
            logger.warning("Redis unavailable, skipping this pass: %s", exc)
        except Exception:
            logger.exception("Cleanup pass failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()

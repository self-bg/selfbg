"""What the video_worker container runs.

Loads the RVM model into memory first (so the first video doesn't wait
for it), then watches Redis for video jobs and processes them one at a
time. Run this with `python -m app.workers.video`.
"""

from __future__ import annotations

import logging

from redis import Redis
from rq import Queue, Worker

from ..config import get_settings
from ..video import warmup

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()

    logger.info("Warming RVM")
    warmup()
    logger.info("Model ready; connecting to %s", settings.redis_url)

    connection = Redis.from_url(settings.redis_url)
    queue = Queue("video", connection=connection)
    Worker([queue], connection=connection).work(with_scheduler=False)


if __name__ == "__main__":
    main()

"""Entrypoint for the RQ worker container.

Warms the model before starting the worker so the first job doesn't pay
the model-load cost. Run as `python -m app.worker`.
"""

from __future__ import annotations

import logging

from redis import Redis
from rq import Queue, Worker

from .config import get_settings
from .matting import warmup

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()

    logger.info("Warming model %s", settings.model)
    warmup()
    logger.info("Model ready; connecting to %s", settings.redis_url)

    connection = Redis.from_url(settings.redis_url)
    queue = Queue("default", connection=connection)
    Worker([queue], connection=connection).work(with_scheduler=False)


if __name__ == "__main__":
    main()

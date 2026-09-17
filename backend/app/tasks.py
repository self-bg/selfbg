"""The job the worker runs.

RQ needs each job to be a standard Python function it can call by name, so
this file just holds one: process_image.

Instead of sending image bytes through Redis (slow, and eats memory on
big batches), the API saves the upload to disk in a folder named after
the job. The worker reads the file from that folder, runs the model,
and saves the result PNG in the same folder.
"""

from __future__ import annotations

from .jobs import job_dir, result_path
from .matting import remove_background


def process_image(job_id: str, model_name: str | None = None) -> str:
    d = job_dir(job_id)
    inputs = sorted(d.glob("input.*"))
    if not inputs:
        raise FileNotFoundError(f"No input file found in {d}")
    body = inputs[0].read_bytes()
    output = remove_background(body, model_name=model_name)
    dest = result_path(job_id)
    dest.write_bytes(output)
    return str(dest)

"""The jobs the workers run.

RQ needs each job to be a standard Python function it can call by name.
Two live here — one for images (called by the image worker) and one for
videos (called by the video worker).

Instead of sending file bytes through Redis (slow, and eats memory on
big batches), the API saves the upload to disk in a folder named after
the job. The worker reads the file from that folder, runs the model,
and saves the result in the same folder.
"""

from __future__ import annotations

from .job_store import job_dir, result_path
from .matting import remove_background


def process_image(job_id: str, model_name: str | None = None) -> str:
    d = job_dir(job_id)
    inputs = sorted(d.glob("input.*"))
    if not inputs:
        raise FileNotFoundError(f"No input file found in {d}")
    body = inputs[0].read_bytes()
    output = remove_background(body, model_name=model_name)
    dest = result_path(job_id, "image")
    dest.write_bytes(output)
    return str(dest)


def process_video(job_id: str) -> str:
    # Imported here so the image worker doesn't need to load the video
    # dependencies (ONNX Runtime, RVM model file, etc.).
    from .video import process_video as run_video

    d = job_dir(job_id)
    inputs = sorted(d.glob("input.*"))
    if not inputs:
        raise FileNotFoundError(f"No input file found in {d}")
    dest = result_path(job_id, "video")
    run_video(inputs[0], dest)
    return str(dest)

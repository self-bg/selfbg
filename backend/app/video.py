"""Video background removal using Robust Video Matting (RVM).

Reads a video file, runs each frame through RVM to get a foreground and
an alpha matte, and writes a WebM VP9 video with a transparent
background. RVM's recurrent hidden state is threaded from frame to frame
so edges stay stable with no flicker per frame.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import numpy as np
import onnxruntime as ort

from .config import get_settings

logger = logging.getLogger(__name__)

_session: RvmSession | None = None  # type: ignore[name-defined]


class RvmSession:
    """Holds an ONNX Runtime session for RVM and its per-video recurrent
    state. Reset the state before each new video."""

    def __init__(self, model_path: Path) -> None:
        logger.info("Loading RVM model from %s", model_path)
        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        self.reset_state()

    def reset_state(self) -> None:
        # RVM expects four recurrent hidden state tensors. Start with tiny
        # zero placeholders; the model reshapes on first inference.
        self.rec = [np.zeros([1, 1, 1, 1], dtype=np.float32) for _ in range(4)]

    def process_frame(self, rgb: np.ndarray, downsample_ratio: float = 0.5) -> np.ndarray:
        """Process a single RGB frame (H, W, 3) uint8 → RGBA (H, W, 4) uint8."""
        src = rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        outputs = self.session.run(
            None,
            {
                "src": src,
                "r1i": self.rec[0],
                "r2i": self.rec[1],
                "r3i": self.rec[2],
                "r4i": self.rec[3],
                "downsample_ratio": np.array([downsample_ratio], dtype=np.float32),
            },
        )
        fgr, pha, r1o, r2o, r3o, r4o = outputs
        self.rec = [r1o, r2o, r3o, r4o]
        fgr_hwc = np.clip(fgr[0].transpose(1, 2, 0) * 255, 0, 255).astype(np.uint8)
        pha_hw = np.clip(pha[0, 0] * 255, 0, 255).astype(np.uint8)
        return np.dstack([fgr_hwc, pha_hw])


def get_session() -> RvmSession:
    """Lazy singleton so the model loads once and stays in memory."""
    global _session
    if _session is None:
        _session = RvmSession(Path(get_settings().rvm_model_path))
    return _session


def warmup() -> None:
    get_session()


def _probe(path: Path) -> tuple[int, int, float, float]:
    """Return (width, height, fps, duration_seconds) for a video file."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format",
            "-show_streams", "-select_streams", "v:0",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    stream = info["streams"][0]
    width = int(stream["width"])
    height = int(stream["height"])

    fps_str = stream.get("r_frame_rate", "0/0")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    else:
        fps = float(fps_str)
    duration = float(info["format"].get("duration", 0.0))
    return width, height, fps, duration


def _target_dims(src_w: int, src_h: int, max_short: int) -> tuple[int, int]:
    """Scale so the shorter side is at most `max_short`, keeping aspect
    ratio. Round to even numbers because most video codecs require it."""
    short = min(src_w, src_h)
    if short <= max_short:
        return src_w & ~1, src_h & ~1
    scale = max_short / short
    return int(round(src_w * scale)) & ~1, int(round(src_h * scale)) & ~1


def process_video(input_path: Path, output_path: Path) -> None:
    """Run RVM over the input video and write a WebM VP9 with alpha."""
    settings = get_settings()
    session = get_session()

    src_w, src_h, fps, duration = _probe(input_path)
    if duration > settings.max_video_duration_seconds:
        raise ValueError(
            f"Video is {duration:.1f}s; the current limit is "
            f"{settings.max_video_duration_seconds}s."
        )
    if fps <= 0:
        raise ValueError("Could not read the video's frame rate.")

    dst_w, dst_h = _target_dims(src_w, src_h, settings.max_video_short_side_px)
    logger.info(
        "Processing %s: %dx%d @ %.2ffps for %.2fs → %dx%d",
        input_path.name, src_w, src_h, fps, duration, dst_w, dst_h,
    )
    session.reset_state()

    frame_bytes = dst_w * dst_h * 3
    decode_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", str(input_path),
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-vf", f"scale={dst_w}:{dst_h}",
        "pipe:1",
    ]
    encode_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgba",
        "-s", f"{dst_w}x{dst_h}",
        "-r", f"{fps:.6f}",
        "-i", "pipe:0",
        "-c:v", "libvpx-vp9",
        "-pix_fmt", "yuva420p",
        "-b:v", "2M",
        "-auto-alt-ref", "0",
        str(output_path),
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dec = subprocess.Popen(decode_cmd, stdout=subprocess.PIPE)
    enc = subprocess.Popen(encode_cmd, stdin=subprocess.PIPE)

    assert dec.stdout is not None
    assert enc.stdin is not None

    try:
        frame_count = 0
        while True:
            raw = dec.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(dst_h, dst_w, 3)
            rgba = session.process_frame(frame)
            enc.stdin.write(rgba.tobytes())
            frame_count += 1
            if frame_count % 30 == 0:
                logger.info("… %d frames", frame_count)
        enc.stdin.close()
    except Exception:
        dec.kill()
        enc.kill()
        raise

    dec_ret = dec.wait()
    enc_ret = enc.wait()
    if dec_ret != 0 or enc_ret != 0:
        raise RuntimeError(
            f"FFmpeg failed (decode exit {dec_ret}, encode exit {enc_ret})"
        )
    logger.info("Done: wrote %d frames to %s", frame_count, output_path)

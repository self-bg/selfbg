"""Settings — defaults and derived properties."""

from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.model == "birefnet-general"
    assert s.max_upload_mb == 25
    assert s.max_video_upload_mb == 200
    assert s.max_video_duration_seconds == 30


def test_upload_bytes_computed_from_mb():
    s = Settings(_env_file=None)
    assert s.max_upload_bytes == s.max_upload_mb * 1024 * 1024
    assert s.max_video_upload_bytes == s.max_video_upload_mb * 1024 * 1024

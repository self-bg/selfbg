"""Settings validation — the server refuses to start with a bad API key."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(key: str | None) -> Settings:
    """Build Settings from an explicit key, ignoring any .env / env vars."""
    kwargs = {"api_key": key} if key is not None else {}
    return Settings(_env_file=None, **kwargs)


def test_rejects_empty_key():
    with pytest.raises(ValidationError):
        _settings("")


@pytest.mark.parametrize("key", ["short", "a" * 15, "1234567890abcde"])
def test_rejects_short_key(key: str):
    with pytest.raises(ValidationError):
        _settings(key)


@pytest.mark.parametrize("key", ["a" * 16, "b" * 32, "some-16-char-key"])
def test_accepts_valid_key(key: str):
    s = _settings(key)
    assert s.api_key == key


def test_upload_bytes_computed_from_mb():
    s = _settings("a" * 16)
    assert s.max_upload_bytes == s.max_upload_mb * 1024 * 1024
    assert s.max_video_upload_bytes == s.max_video_upload_mb * 1024 * 1024

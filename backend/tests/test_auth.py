"""API key middleware — matches the configured key, rejects everything else."""

import pytest
from fastapi import HTTPException

from app.auth import require_api_key
from app.config import get_settings


async def test_accepts_correct_key():
    await require_api_key(x_api_key=get_settings().api_key)  # doesn't raise


@pytest.mark.parametrize("bad", [None, "", "wrong", "TEST-api-key-0123456789abcdef"])
async def test_rejects_wrong_key(bad):
    with pytest.raises(HTTPException) as exc:
        await require_api_key(x_api_key=bad)
    assert exc.value.status_code == 401

"""Set the mandatory SELFBG_API_KEY before any app module loads settings.

Without this, importing anything from `app.*` triggers the pydantic
validator on Settings and blows up with a ValidationError."""

import os

os.environ.setdefault("SELFBG_API_KEY", "test-api-key-0123456789abcdef")

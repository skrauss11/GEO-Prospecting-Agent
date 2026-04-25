"""
MadTech Growth — Shared configuration.

Single source of truth for API credentials, model defaults, and environment
setup. Loaded once at import time; every module imports from here instead of
duplicating os.environ.get calls.
"""

import os

from dotenv import load_dotenv

# Load .env once, at module import time.  Modules that import shared.config
# do not need their own load_dotenv() call.
load_dotenv(override=True)

# ─── Nous Gateway ────────────────────────────────────────────────────────────
NOUS_API_KEY = os.environ.get("NOUS_API_KEY", "")
NOUS_BASE_URL = os.environ.get("NOUS_BASE_URL", "https://gateway.nous.uno/v1")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "moonshotai/kimi-k2.6")

# ─── Discord ─────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


def get_openai_client():
    """Return a pre-configured OpenAI-compatible client (Nous gateway)."""
    from openai import OpenAI

    if not NOUS_API_KEY:
        raise RuntimeError(
            "NOUS_API_KEY is not set. Add it to your .env or environment."
        )
    return OpenAI(base_url=NOUS_BASE_URL, api_key=NOUS_API_KEY)

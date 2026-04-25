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


def call_with_retry(fn, *, max_attempts: int = 3, base_delay: float = 2.0,
                    label: str = "llm_call"):
    """
    Run `fn()` with exponential backoff on transient errors.
    Retries on connection errors, timeouts, and 5xx responses.
    Re-raises on the final attempt.
    """
    import time

    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

    transient = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)

    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except transient as e:
            if attempt == max_attempts:
                print(f"    [{label}] gave up after {attempt} attempts: {e}", flush=True)
                raise
            delay = base_delay * (2 ** (attempt - 1))
            print(f"    [{label}] attempt {attempt} failed ({type(e).__name__}); retrying in {delay:.1f}s", flush=True)
            time.sleep(delay)

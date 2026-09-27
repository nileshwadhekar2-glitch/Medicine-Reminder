"""
database.py - Supabase PostgreSQL connection helper
"""

import os
from pathlib import Path
try:
    from supabase import create_client, Client
except ImportError as e:
    raise ImportError(
        "The 'supabase' package is not installed. "
        "Run: pip install supabase"
    ) from e

try:
    from dotenv import load_dotenv
except ImportError as e:
    raise ImportError(
        "The 'python-dotenv' package is not installed. "
        "Run: pip install python-dotenv"
    ) from e

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# Lazy-initialised singleton — created on first use, not at import time
_supabase_client: Client | None = None


def get_supabase() -> Client:
    """Return the shared Supabase client, creating it on first call.

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_KEY are not set in the environment.
    """
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_URL:
            raise ValueError(
                "Missing environment variable: SUPABASE_URL. "
                "Add it to your .env file."
            )
        if not SUPABASE_KEY:
            raise ValueError(
                "Missing environment variable: SUPABASE_KEY. "
                "Add it to your .env file."
            )
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    return _supabase_client

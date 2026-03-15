"""
Supabase client singleton.

Provides a single shared Supabase client instance for the application.
Uses the service role key for server-side operations (bypasses RLS).
"""

import logging

from supabase import Client, create_client

from src.config.settings import settings

logger = logging.getLogger("mreit-monitor.supabase")

_client: Client | None = None


def get_supabase_client() -> Client:
    """Get or create the shared Supabase client."""
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
        logger.info("Supabase client initialized for %s", settings.supabase_url)
    return _client

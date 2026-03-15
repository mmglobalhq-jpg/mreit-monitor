"""
Shared FastAPI dependencies.
"""

from src.services.supabase_client import get_supabase_client

# Re-export for use in route dependencies
__all__ = ["get_supabase_client"]

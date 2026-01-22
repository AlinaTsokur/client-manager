"""
Supabase client initialization.
"""
from supabase import create_client, Client
from config.settings import settings

_client: Client | None = None


def get_supabase_client() -> Client:
    """Get or create Supabase client singleton."""
    global _client
    
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError(
                "Supabase credentials not configured. "
                "Please set SUPABASE_URL and SUPABASE_KEY in .env file."
            )
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    
    return _client

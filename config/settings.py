"""
Application settings loaded from environment variables.
"""
import os
from dotenv import load_dotenv

# Load .env file (only works locally, Railway sets env vars directly)
load_dotenv()


class Settings:
    """Application configuration."""
    
    @property
    def SUPABASE_URL(self) -> str:
        return os.getenv("SUPABASE_URL", "")
    
    @property
    def SUPABASE_KEY(self) -> str:
        return os.getenv("SUPABASE_KEY", "")
    
    @property
    def YANDEX_TOKEN(self) -> str:
        return os.getenv("YANDEX_TOKEN", "")
    
    # App paths
    FONTS_DIR: str = "fonts"
    TEMPLATES_DIR: str = "templates"
    
    def validate(self) -> bool:
        """Check if required settings are configured."""
        if not self.SUPABASE_URL or not self.SUPABASE_KEY:
            return False
        return True


settings = Settings()

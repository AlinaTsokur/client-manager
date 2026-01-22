"""
Application settings loaded from environment variables.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class Settings:
    """Application configuration."""
    
    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # Yandex Disk
    YANDEX_TOKEN: str = os.getenv("YANDEX_TOKEN", "")
    
    # App paths
    FONTS_DIR: str = "fonts"
    TEMPLATES_DIR: str = "templates"
    
    def validate(self) -> bool:
        """Check if required settings are configured."""
        if not self.SUPABASE_URL or not self.SUPABASE_KEY:
            return False
        return True


settings = Settings()

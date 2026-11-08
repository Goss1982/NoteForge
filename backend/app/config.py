from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    database_url: str = "sqlite:///./noteforge.db"
    data_dir: Path = Path("./data")
    admin_password: str = Field(min_length=12)
    secret_key: str = Field(min_length=32)
    public_url: str = "http://localhost:3000"
    cookie_secure: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    rmapi_config: Path = Path("/data/remarkable/rmapi.conf")
    rmapi_binary: str = "rmapi"
    sync_interval_seconds: int = Field(default=300, ge=60)
    auto_document_type: str = "meeting_minutes"
    max_upload_mb: int = Field(default=40, ge=1, le=100)
    max_pages: int = Field(default=100, ge=1, le=500)
    max_image_pixels: int = 25_000_000
    session_hours: int = 12

    @model_validator(mode="after")
    def check(self):
        if "replace-with" in self.admin_password or "replace-with" in self.secret_key:
            raise ValueError("Replace example credentials or run scripts/configure.py before starting")
        if self.auto_document_type not in ("", "meeting_minutes", "brief", "report", "action_plan"):
            raise ValueError("Unsupported AUTO_DOCUMENT_TYPE")
        return self


@lru_cache
def settings():
    return Settings()

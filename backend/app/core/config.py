from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic import field_validator
from typing_extensions import Annotated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Competency Evolution API"
    version: str = "0.4.0"
    environment: str = "local"
    database_url: str | None = None
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Firebase Auth: ID tokens are verified against this project.
    firebase_project_id: str = "student-competence"
    # Verified emails that are promoted to admin on first login (comma-separated).
    admin_emails: Annotated[list[str], NoDecode] = []

    # Evidence storage
    storage_backend: Literal["local", "gcs"] = "local"
    gcs_bucket: str | None = None
    local_storage_dir: str = "./uploads"
    max_upload_mb: int = 10

    @field_validator("cors_origins", "admin_emails", mode="before")
    @classmethod
    def split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip().lower() if "@" in s else s.strip() for s in v.split(",") if s.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()

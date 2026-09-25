"""Evidence file storage: local disk in development, a private Cloud Storage bucket in production.

Files are never public. They are streamed back through the API after an ownership/role check.
"""

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class Storage(Protocol):
    def save(self, key: str, data: bytes, content_type: str) -> None: ...
    def load(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        return path

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class GCSStorage:
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage  # imported lazily: not needed for local dev/tests

        self.bucket = storage.Client().bucket(bucket)

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self.bucket.blob(key).upload_from_string(data, content_type=content_type)

    def load(self, key: str) -> bytes:
        return self.bucket.blob(key).download_as_bytes()

    def delete(self, key: str) -> None:
        from google.api_core.exceptions import NotFound

        try:
            self.bucket.blob(key).delete()
        except NotFound:
            pass


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "gcs":
        if not settings.gcs_bucket:
            raise RuntimeError("GCS_BUCKET must be set when STORAGE_BACKEND=gcs")
        return GCSStorage(settings.gcs_bucket)
    return LocalStorage(settings.local_storage_dir)

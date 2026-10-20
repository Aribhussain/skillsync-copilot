"""Blob storage behind a tiny interface, chosen by STORAGE_BACKEND:
local  files under storage/ (lite mode, default)
s3     MinIO / any S3-compatible store (Docker full mode)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from app.core.config import Settings


class BlobStorage(Protocol):
    def put(self, key: str, data: bytes) -> str: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("Invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3Storage:
    """MinIO / S3 via the `minio` client (installed from requirements-full.txt)."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        from minio import Minio  # full-mode dependency, imported lazily

        u = urlparse(endpoint)
        self.client = Minio(
            u.netloc or u.path, access_key=access_key, secret_key=secret_key, secure=u.scheme == "https"
        )
        self.bucket = bucket
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

    def put(self, key: str, data: bytes) -> str:
        self.client.put_object(
            self.bucket, key, io.BytesIO(data), length=len(data), content_type="application/octet-stream"
        )
        return key

    def get(self, key: str) -> bytes:
        resp = self.client.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def exists(self, key: str) -> bool:
        from minio.error import S3Error

        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False


def make_storage(settings: Settings) -> BlobStorage:
    if settings.storage_backend == "s3":
        return S3Storage(
            settings.s3_endpoint, settings.s3_access_key, settings.s3_secret_key, settings.s3_bucket
        )
    return LocalStorage(settings.storage_path)

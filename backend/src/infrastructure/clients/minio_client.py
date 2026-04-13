"""MinIO / S3-compatible object storage client.

Stores and retrieves:
  proposals/   — generated proposal PDFs (P2 output)
  quotations/  — generated quotation .docx files
  requirements/ — uploaded requirements documents (P2 input)

All generated documents are stored here (VM3) rather than on local disk,
so both FastAPI (VM1) and Celery workers (VM2) can read/write them.

Usage:
    client = MinIOStorageClient()
    # Upload
    url = await client.upload_file(bucket, object_name, file_bytes, content_type)
    # Presigned download link (1-hour TTL)
    download_url = await client.presign_download(bucket, object_name)
    # Check existence
    exists = await client.exists(bucket, object_name)
"""

import io
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

import structlog
from minio import Minio
from minio.error import S3Error

from src.core.exceptions import DocumentGenerationError
from src.core.settings import settings

log = structlog.get_logger()


def _make_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


class MinIOStorageClient:
    """Thin async-compatible wrapper around the synchronous minio-py SDK.

    minio-py is synchronous; we run it in a thread-pool executor for async
    compatibility without blocking the event loop.
    """

    def __init__(self) -> None:
        self._client = _make_client()

    def _ensure_bucket(self, bucket: str) -> None:
        """Create bucket if it doesn't exist (idempotent)."""
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)
            log.info("minio.bucket_created", bucket=bucket)

    # ── Upload ────────────────────────────────────────────────────────────────

    def upload_bytes(
        self,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload raw bytes and return the object path (bucket/object_name)."""
        self._ensure_bucket(bucket)
        try:
            self._client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            log.info("minio.uploaded", bucket=bucket, object=object_name, size=len(data))
            return f"{bucket}/{object_name}"
        except S3Error as exc:
            log.error("minio.upload_failed", bucket=bucket, object=object_name, error=str(exc))
            raise DocumentGenerationError(f"MinIO upload failed: {exc}") from exc

    def upload_file(
        self,
        bucket: str,
        object_name: str,
        file_path: str | Path,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload from a local file path."""
        path = Path(file_path)
        self._ensure_bucket(bucket)
        try:
            self._client.fput_object(
                bucket_name=bucket,
                object_name=object_name,
                file_path=str(path),
                content_type=content_type,
            )
            log.info("minio.file_uploaded", bucket=bucket, object=object_name, path=str(path))
            return f"{bucket}/{object_name}"
        except S3Error as exc:
            raise DocumentGenerationError(f"MinIO file upload failed: {exc}") from exc

    # ── Download ──────────────────────────────────────────────────────────────

    def download_bytes(self, bucket: str, object_name: str) -> bytes:
        """Download an object and return its raw bytes."""
        try:
            response = self._client.get_object(bucket, object_name)
            return response.read()
        except S3Error as exc:
            raise DocumentGenerationError(f"MinIO download failed: {exc}") from exc
        finally:
            response.close()
            response.release_conn()

    # ── Presigned URL ─────────────────────────────────────────────────────────

    def presign_download(
        self,
        bucket: str,
        object_name: str,
        expiry_seconds: int | None = None,
    ) -> str:
        """Generate a time-limited presigned download URL.

        The URL is valid for MINIO_PRESIGN_EXPIRY_SECONDS (default 1 hour).
        Clients can download directly from this URL without going through FastAPI.
        """
        expiry = timedelta(seconds=expiry_seconds or settings.MINIO_PRESIGN_EXPIRY_SECONDS)
        try:
            url = self._client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=expiry,
            )
            return url
        except S3Error as exc:
            raise DocumentGenerationError(f"Presigned URL generation failed: {exc}") from exc

    # ── Metadata / existence ──────────────────────────────────────────────────

    def exists(self, bucket: str, object_name: str) -> bool:
        """Return True if the object exists in the given bucket."""
        try:
            self._client.stat_object(bucket, object_name)
            return True
        except S3Error:
            return False

    def delete(self, bucket: str, object_name: str) -> None:
        """Delete an object (no-op if it doesn't exist)."""
        try:
            self._client.remove_object(bucket, object_name)
            log.info("minio.deleted", bucket=bucket, object=object_name)
        except S3Error as exc:
            log.warning("minio.delete_failed", bucket=bucket, object=object_name, error=str(exc))

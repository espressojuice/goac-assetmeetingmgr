"""Hetzner Object Storage service (S3-compatible) for packet PDF storage."""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """S3-compatible object storage for packet PDFs.

    Gracefully degrades when S3 credentials are not configured —
    methods return None or empty lists instead of raising.
    """

    def __init__(self):
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.S3_REGION
        self.enabled = bool(
            self.endpoint_url
            and settings.S3_ACCESS_KEY
            and settings.S3_SECRET_KEY
        )
        self._client = None

        if not self.enabled:
            logger.warning(
                "S3 storage not configured — packet upload/download disabled. "
                "Set S3_ENDPOINT_URL, S3_ACCESS_KEY, and S3_SECRET_KEY to enable."
            )

    # ------------------------------------------------------------------ #
    # Lazy client
    # ------------------------------------------------------------------ #
    def _get_client(self):
        """Return a boto3 S3 client, creating it on first use."""
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=self.region,
            )
        return self._client

    # ------------------------------------------------------------------ #
    # Upload
    # ------------------------------------------------------------------ #
    def upload_packet(
        self, file_bytes: bytes, store_id: str, meeting_date: str
    ) -> Optional[str]:
        """Store an original packet PDF in object storage.

        Key format: ``packets/{store_id}/{meeting_date}/original.pdf``

        Returns the S3 key on success, or None if storage is unavailable.
        """
        if not self.enabled:
            logger.info(
                "S3 disabled — skipping upload for store=%s date=%s",
                store_id,
                meeting_date,
            )
            return None

        key = f"packets/{store_id}/{meeting_date}/original.pdf"
        try:
            self._get_client().put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_bytes,
                ContentType="application/pdf",
            )
            logger.info("Uploaded packet to s3://%s/%s", self.bucket_name, key)
            return key
        except Exception:
            logger.exception(
                "Failed to upload packet for store=%s date=%s",
                store_id,
                meeting_date,
            )
            return None

    # ------------------------------------------------------------------ #
    # Presigned download URL
    # ------------------------------------------------------------------ #
    def get_packet_url(
        self, store_id: str, meeting_date: str, expiry: int = 3600
    ) -> Optional[str]:
        """Generate a presigned URL for downloading a packet PDF.

        Args:
            store_id: The store identifier.
            meeting_date: The meeting date string (e.g. ``2026-02-11``).
            expiry: URL lifetime in seconds (default 1 hour).

        Returns the presigned URL, or None if storage is unavailable.
        """
        if not self.enabled:
            return None

        key = f"packets/{store_id}/{meeting_date}/original.pdf"
        try:
            url = self._get_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiry,
            )
            return url
        except Exception:
            logger.exception(
                "Failed to generate presigned URL for store=%s date=%s",
                store_id,
                meeting_date,
            )
            return None

    # ------------------------------------------------------------------ #
    # List packets for a store
    # ------------------------------------------------------------------ #
    def list_packets(self, store_id: str) -> list[dict]:
        """List all packet objects for a given store.

        Returns a list of dicts with ``key``, ``last_modified``, and ``size``.
        Returns an empty list if storage is unavailable.
        """
        if not self.enabled:
            return []

        prefix = f"packets/{store_id}/"
        try:
            response = self._get_client().list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix
            )
            results = []
            for obj in response.get("Contents", []):
                results.append(
                    {
                        "key": obj["Key"],
                        "last_modified": obj["LastModified"],
                        "size": obj["Size"],
                    }
                )
            return results
        except Exception:
            logger.exception(
                "Failed to list packets for store=%s", store_id
            )
            return []

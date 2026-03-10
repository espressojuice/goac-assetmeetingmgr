"""Tests for upload API endpoints."""

import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio


UPLOAD_URL = "/api/v1/upload"
BULK_URL = "/api/v1/upload/bulk"

STORE_ID = "11111111-1111-1111-1111-111111111111"
FAKE_STORE_ID = "99999999-9999-9999-9999-999999999999"


def _make_pdf_file(filename="report.pdf", content=b"%PDF-1.4 fake pdf content", field="file"):
    """Create a fake PDF UploadFile-compatible tuple for httpx."""
    return (field, (filename, io.BytesIO(content), "application/pdf"))


def _mock_processing_result(meeting_id: str) -> dict:
    return {
        "pages_extracted": 27,
        "records_parsed": {"NewVehicleInventory": 15, "UsedVehicleInventory": 22},
        "unhandled_pages": [],
        "flags_generated": {"yellow": 3, "red": 2, "total": 5},
        "packet_path": f"/uploads/{STORE_ID}/{meeting_id}/packet.pdf",
        "flagged_items_path": f"/uploads/{STORE_ID}/{meeting_id}/flagged_items.pdf",
    }


@pytest.mark.asyncio
class TestUploadEndpoint:

    async def test_upload_with_valid_pdf(self, client, sample_store, auth_headers):
        """Upload a valid PDF and get processing summary."""
        mock_result = _mock_processing_result("test-meeting-id")

        with patch("app.api.routes.upload.ProcessingService") as MockService:
            instance = MockService.return_value
            instance.process_upload = AsyncMock(return_value=mock_result)

            response = await client.post(
                UPLOAD_URL,
                files=[_make_pdf_file()],
                data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["pages_extracted"] == 27
        assert data["records_parsed"]["NewVehicleInventory"] == 15
        assert data["flags_generated"]["total"] == 5
        assert "meeting_id" in data

    async def test_upload_non_pdf_returns_422(self, client, sample_store, auth_headers):
        """Uploading a non-PDF file returns 422."""
        response = await client.post(
            UPLOAD_URL,
            files=[("file", ("report.xlsx", io.BytesIO(b"fake"), "application/octet-stream"))],
            data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "PDF" in response.json()["detail"]

    async def test_upload_invalid_store_returns_404(self, client, auth_headers):
        """Uploading with a nonexistent store_id returns 404."""
        response = await client.post(
            UPLOAD_URL,
            files=[_make_pdf_file()],
            data={"store_id": FAKE_STORE_ID, "meeting_date": "2026-02-11"},
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_upload_invalid_date_format(self, client, sample_store, auth_headers):
        """Uploading with invalid date format returns 422."""
        response = await client.post(
            UPLOAD_URL,
            files=[_make_pdf_file()],
            data={"store_id": STORE_ID, "meeting_date": "02/11/2026"},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "YYYY-MM-DD" in response.json()["detail"]

    async def test_upload_invalid_store_id_format(self, client, auth_headers):
        """Uploading with invalid UUID format returns 422."""
        response = await client.post(
            UPLOAD_URL,
            files=[_make_pdf_file()],
            data={"store_id": "not-a-uuid", "meeting_date": "2026-02-11"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_upload_processing_failure_sets_error_status(self, client, sample_store, auth_headers):
        """When processing fails, meeting status is set to error and 500 returned."""
        with patch("app.api.routes.upload.ProcessingService") as MockService:
            instance = MockService.return_value
            instance.process_upload = AsyncMock(side_effect=RuntimeError("Parser exploded"))

            response = await client.post(
                UPLOAD_URL,
                files=[_make_pdf_file()],
                data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
                headers=auth_headers,
            )

        assert response.status_code == 500
        assert "Processing failed" in response.json()["detail"]

    async def test_upload_creates_meeting_if_not_exists(self, client, sample_store, auth_headers):
        """First upload for a store+date combo creates a new meeting."""
        mock_result = _mock_processing_result("new-meeting-id")

        with patch("app.api.routes.upload.ProcessingService") as MockService:
            instance = MockService.return_value
            instance.process_upload = AsyncMock(return_value=mock_result)

            response = await client.post(
                UPLOAD_URL,
                files=[_make_pdf_file()],
                data={"store_id": STORE_ID, "meeting_date": "2026-03-15"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["meeting_id"]

    async def test_upload_reuses_existing_meeting(self, client, sample_store, sample_meeting, auth_headers):
        """Uploading to an existing store+date reuses the meeting."""
        mock_result = _mock_processing_result(str(sample_meeting.id))

        with patch("app.api.routes.upload.ProcessingService") as MockService:
            instance = MockService.return_value
            instance.process_upload = AsyncMock(return_value=mock_result)

            response = await client.post(
                UPLOAD_URL,
                files=[_make_pdf_file()],
                data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["meeting_id"] == str(sample_meeting.id)

    async def test_upload_unauthenticated_returns_401(self, client, sample_store):
        """Unauthenticated upload returns 401."""
        response = await client.post(
            UPLOAD_URL,
            files=[_make_pdf_file()],
            data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestBulkUploadEndpoint:

    async def test_bulk_upload_multiple_files(self, client, sample_store, auth_headers):
        """Bulk upload with multiple PDFs processes all and merges results."""
        mock_result = _mock_processing_result("test-meeting-id")

        with patch("app.api.routes.upload.ProcessingService") as MockService:
            instance = MockService.return_value
            instance.process_upload = AsyncMock(return_value=mock_result)

            response = await client.post(
                BULK_URL,
                files=[
                    _make_pdf_file("report1.pdf", field="files"),
                    _make_pdf_file("report2.pdf", field="files"),
                ],
                data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["files_processed"] == 2
        assert data["total_pages_extracted"] == 54  # 27 * 2
        assert data["records_parsed"]["NewVehicleInventory"] == 30  # 15 * 2

    async def test_bulk_upload_non_pdf_rejected(self, client, sample_store, auth_headers):
        """Bulk upload rejects non-PDF files."""
        response = await client.post(
            BULK_URL,
            files=[
                _make_pdf_file("report.pdf", field="files"),
                ("files", ("data.csv", io.BytesIO(b"csv"), "text/csv")),
            ],
            data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_bulk_upload_empty_files_rejected(self, client, sample_store, auth_headers):
        """Bulk upload with no files returns 422."""
        response = await client.post(
            BULK_URL,
            data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_bulk_upload_partial_failure(self, client, sample_store, auth_headers):
        """If one file fails processing, the entire batch fails."""
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Second file failed")
            return _mock_processing_result("test-meeting-id")

        with patch("app.api.routes.upload.ProcessingService") as MockService:
            instance = MockService.return_value
            instance.process_upload = AsyncMock(side_effect=side_effect)

            response = await client.post(
                BULK_URL,
                files=[
                    _make_pdf_file("report1.pdf", field="files"),
                    _make_pdf_file("report2.pdf", field="files"),
                ],
                data={"store_id": STORE_ID, "meeting_date": "2026-02-11"},
                headers=auth_headers,
            )

        assert response.status_code == 500
        assert "report2.pdf" in response.json()["detail"]

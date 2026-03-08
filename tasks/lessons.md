# Lessons Learned

- **2026-03-08**: Project initialized. Reference packet is Ashdown Classic Chevrolet 02/11/2026 (27 pages). All parsers must handle handwritten notes gracefully.
- **2026-03-08**: FloorplanReconciliation gets its own model — the variance between book value and floorplan balance is the most politically sensitive data point in the system.
- **2026-03-08**: R&R PDF formats vary between report types. Section identifiers need multiple variants. Parser must be defensive — log warnings on unparseable rows, never crash.
- **2026-03-08**: F&I chargeback section identifiers (850, 851) are too short for simple substring matching — need context-aware `can_handle` to avoid false positives.
- **2026-03-08**: For 'lt' comparisons (like parts turnover), yellow threshold must be HIGHER than red — yellow at <2.0 means 'getting low,' red at <1.0 means 'critical.' Check red first to avoid double-flagging.
- **2026-03-08**: ReportLab's Table class handles page breaks for long tables automatically with `repeatRows` parameter — use it so column headers repeat on continuation pages. Alternating row colors via TableStyle with `ROWBACKGROUNDS`.
- **2026-03-08**: When testing PDF generators, bypass the async DB layer by calling section builder methods directly with mock data dicts. Use pdfplumber for round-trip validation (generate → extract text → assert content).
- **2026-03-08**: FastAPI's UploadFile with Form() fields works for multipart uploads. Use Body() for JSON payloads in non-upload routes. Pydantic response schemas with response_model give you auto-validation and OpenAPI docs for free.
- **2026-03-08**: Python 3.9 doesn't support `str | None` or `list[X]` in runtime annotations. Use `from __future__ import annotations` or `Optional[str]` / `List[X]` from typing. Always check target Python version.
- **2026-03-08**: For httpx test client with FastAPI bulk file uploads, the `files` param field name must match the FastAPI parameter name exactly (e.g., `files` not `file`).

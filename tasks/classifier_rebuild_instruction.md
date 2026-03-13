# Claude Code Instruction: Rebuild Packet Classifier

Read these files first for context:
- `data/reference_signatures.md` — the full reference signatures document (CRITICAL — contains all OCR patterns)
- `data/packet_requirements.md` — classification rules, multi-page handling, GL 0504 disambiguation
- `backend/app/services/packet_validator.py` — the current classifier to rewrite
- `backend/app/api/schemas.py` — the Pydantic models (ClassifiedPage, UnclassifiedPage, etc.)

## What to do

Rewrite `backend/app/services/packet_validator.py` to implement the improved classifier described in `data/reference_signatures.md`. The current classifier does per-page keyword matching without any context awareness. The new version must handle:

### 1. Multi-page document grouping (continuation pages)

Schedule Summaries and Open ROs commonly span multiple pages. The current classifier treats each page independently which causes misclassification of continuation pages (pages that say "Schedule Summary" at the top without repeating the schedule number).

Add a `_previous_classification` tracker that the classify loop uses. After classifying each page, if the next page is a "Schedule Summary" with no schedule number OR an "Open ROs" with no "Report Format:" subtitle, inherit the previous page's classification.

Specifically: if a page starts with "Schedule Summary" (case-insensitive) and has NO line matching `Schedule#:` in the first 10 lines, AND the previous page was classified as a Schedule Summary type (doc IDs 4,5,7,9,10,13,15), then assign this page to the same document type as the previous page.

Same for Open ROs: if page starts with "Open ROs" but has no "Report Format:" line, and the previous page was Open RO List (#6), inherit that classification.

### 2. GL 0504 account-based classification

Replace the current overly-broad GL 0504 matching. The key insight from the reference signatures is that ALL GL 0504 pages share the same format — "0504" in the top-right, "GL INQUIRY" header — but the ACCOUNT NUMBER determines the subtype:

- Account 15A or "POLICY ADJ NEW" → GL 0504 New (#8)
- Account 15B or "POLICY ADJ USD/USED" → GL 0504 Used (#8)
- Account 15 (no suffix, no NEW/USED text) → GL 0504 New & Used (#8) BUT flag `needs_user_disambiguation: true`
- Account 850 + "F&I CHARGEBACK" (no "90") → F&I Chargeback New (#12)
- Account 850A + "F&I OV 90" → F&I Chargeback Over 90 New (#12)
- Account 851 + "F&I CHARGEBACK" (no "90") → F&I Chargeback Used (#12)
- Account 851A + "F&I OV 90" → F&I Chargeback Over 90 Used (#12)

Create a dedicated `_classify_gl_0504(text) -> tuple[int | None, str, bool]` method that returns (doc_id, subtype_label, needs_disambiguation). The subtype_label should be descriptive like "GL 0504 New", "F&I Chargeback — Used Over 90", etc. The needs_disambiguation flag is True only when account 15 has no A/B suffix and no NEW/USED context.

For the document checklist: GL 0504 New & Used (#8) should be marked found if ANY of the 15/15A/15B accounts are found. GL 0504 Chargebacks (#12) should be marked found if ANY of the 850/850A/851/851A accounts are found. Not all 4 chargeback subtypes will be present — do NOT flag missing subtypes as missing documents.

### 3. Schedule number extraction for Schedule Summaries

Instead of matching keywords in the body of Schedule Summaries, extract the schedule number from the header line. Pattern: `Schedule#:\s*(\d+)` in the first 10 lines. Then map:

- 200 with "ACCOUNTS RECEIVABLE" → Service & Parts Receivables (#4)
- 200 or 205 with "CONTRACT" → Contracts in Transit (#13)
- 220 → Wholesales (#15)
- 237 → New Inventory (#9)
- 240 → Used Inventory (#10)
- 263 → Warranty Claims (#5)
- 277 → Loaner Inventory (#7)

This is more reliable than matching keywords in the body text, which can cause false positives.

### 4. Enhanced ClassifiedPage schema

Add an optional `subtype` field to `ClassifiedPage` in schemas.py:

```python
class ClassifiedPage(BaseModel):
    page_number: int
    document_type: str
    confidence: int
    subtype: str | None = None  # e.g., "F&I Chargeback — New Over 90", "GL 0504 New"
    needs_user_input: bool = False  # True when GL 0504 New/Used can't be determined
```

### 5. Intro/cover page detection

The first page of many packets is an "ASSET MEETING" intro/cover page that summarizes the whole packet. The current `_is_summary_cover_page` method works but should also catch pages that don't have 3+ schedule references — if the page has "ASSET MEETING" AND contains a store name but does NOT match any specific document signature, classify it as "Intro Page" and add it to unclassified_pages with snippet "(Intro/cover page — not a required document)".

### 6. Classification priority order

The classification should check in this specific order (most distinctive patterns first):

1. "Open ROs" → #6 (check continuation)
2. "SLOW TO ACCOUNTING" → #14
3. "WHOLESALE DEALS IN A DATE RANGE" → #11
4. "MISSING TITLE" → #16
5. "Core Inventory Value" or "2222" → #3
6. "MONTHLY ANALYSIS" or "2213" → #2
7. "ASSET MEETING" → Intro page (skip)
8. "0504" + "GL INQUIRY" → GL 0504 family → subclassify by account number
9. "Schedule Summary" + schedule number → map by schedule number
10. "Schedule Summary" with no number → continuation page
11. Employee roster pattern → #1
12. No match → Unrecognized

### 7. Implementation approach

Keep the same public API (validate, validate_detailed, validate_detailed_with_progress) but rewrite the internal classification logic. The `_classify_page_with_score` method should become `_classify_page_contextual(text, previous_doc_id) -> tuple[int | None, int, str | None, bool]` returning (doc_id, score, subtype, needs_user_input).

Keep all existing helper methods (_extract_text, _tesseract_ocr_page, _count_pages) unchanged.

Update the classify loop in validate_detailed_with_progress to:
1. Track `previous_doc_id` across pages
2. Pass it to the contextual classifier
3. Populate the new `subtype` and `needs_user_input` fields on ClassifiedPage

### 8. Testing

After making changes:
1. Run `cd backend && python -m pytest tests/ -x -q` to make sure existing tests pass
2. If there are specific classifier tests, update them for the new behavior
3. Test against the Ashdown reference PDF if it's in testdata — run the validator and verify all 16 document types (minus Missing Titles which may OCR poorly) are correctly classified

### Key files to modify:
- `backend/app/services/packet_validator.py` — main rewrite
- `backend/app/api/schemas.py` — add subtype + needs_user_input to ClassifiedPage

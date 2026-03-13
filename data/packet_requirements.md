# Asset Meeting Packet — Required Documents

> This is the canonical list of documents that must be included in every asset meeting packet. The system validates incoming uploads against this list and notifies the user of any missing documents.

## Required Documents

| # | Document | Source | Where to Find It |
|---|----------|--------|-----------------|
| 1 | Reynolds Employee List | R&R Dynamic Reporting | Reynolds → Dynamic Reporting → Employee List |
| 2 | Parts 2213 | R&R Report 2213 | Reynolds → Reports → 2213 Parts Inventory |
| 3 | Parts 2222 | R&R Report 2222 | Reynolds → Reports → 2222 Parts Analysis |
| 4 | Schedule Summary — Service and Parts Receivables | R&R Schedule Summary | Reynolds → Schedule Summary → Service & Parts |
| 5 | Schedule Summary — Warranty Claims | R&R Schedule Summary | Reynolds → Schedule Summary → Warranty Claims |
| 6 | Service 3617 "Open RO List" | R&R Report 3617 | Reynolds → Reports → 3617 Open RO List |
| 7 | Schedule Summary — Loaner Inventory | R&R Schedule Summary | Reynolds → Schedule Summary → Loaner Inventory |
| 8 | GL 0504 New & Used | R&R General Ledger | Reynolds → GL → 0504 → New & Used |
| 9 | Schedule Summary — New Inventory | R&R Schedule Summary | Reynolds → Schedule Summary → New Inventory (Sch 237) |
| 10 | Schedule Summary — Used Inventory | R&R Schedule Summary | Reynolds → Schedule Summary → Used Inventory (Sch 240) |
| 11 | Wholesale Deals in Range | R&R Dynamic Reporting | Reynolds → Dynamic Reporting → Wholesale Deals |
| 12 | GL 0504 Chargebacks | R&R General Ledger | Reynolds → GL → 0504 → Chargebacks |
| 13 | Schedule Summary — Contracts in Transit | R&R Schedule Summary | Reynolds → Schedule Summary → CIT (Sch 200/205) |
| 14 | Slow to Accounting | R&R Report | Reynolds → Reports → Slow to Accounting |
| 15 | Schedule Summary — Wholesales | R&R Schedule Summary | Reynolds → Schedule Summary → Wholesales |
| 16 | Missing Titles | Google Sheets | Google Sheets — maintained manually outside R&R, printed/exported and included in packet |

## Classification Rules

### Multi-Page Documents

Most documents can span multiple pages. The classifier must handle:

- **Explicit pagination**: Look for "Page X of Y", "1 of 3", "2 of 3" etc. Group consecutive pages of the same document together.
- **Continuation pages**: Page 2+ of a Schedule Summary may only say "Schedule Summary" at the top WITHOUT repeating the schedule number (e.g., page 1 says "Schedule Number 237 New Vehicle Inventory" but page 2 just says "Schedule Summary"). The classifier must use context from the previous page to know this is still the same document.
- **Examples of multi-page documents**: Open RO List (commonly 3-4 pages), New/Used Inventory schedules, Parts reports, Warranty Claims.
- **Rule**: If a page has no clear document identifier AND the previous page was classified, check if this page looks like a continuation (same column layout, no new document header, "Schedule Summary" only at top).

### GL 0504 Disambiguation

GL 0504 pages are complex because the same GL account covers multiple document types:

- **0504 New Inventory** — May show as "0504A" or just "0504" with new vehicle context
- **0504 Used Inventory** — May show as "0504-15B" or "0504" with used vehicle context
- **0504 F&I Chargebacks** — Says "F&I CHARGEBACK" on the page
- **0504 F&I Chargebacks Over 90 Days** — Says "F&I" and "OVER 90 DAYS" on the page

**Important**: Not every store uses A/B account suffixes. When the system cannot determine if a 0504 page is New or Used, it should **let the user pick** from a dropdown: "Is this New or Used?"

The system CAN automatically distinguish:
- F&I Chargeback (normal) vs F&I Over 90 Days — the text says it on the page
- New vs Used — ONLY if the account suffix (A/B) or explicit "NEW"/"USED" text is present

The system SHOULD ask the user when:
- 0504 page has no clear New/Used indicator

### F&I Chargeback Subtypes

There are up to 4 chargeback document types that may be present:

1. **F&I Chargeback — New** (0504, new context)
2. **F&I Chargeback — New Over 90 Days** (0504, new + "over 90 days")
3. **F&I Chargeback — Used** (0504, used context)
4. **F&I Chargeback — Used Over 90 Days** (0504, used + "over 90 days")

Not all will be present — if a store has no used chargebacks over 90 days, that section simply won't exist. Do NOT flag these as missing if they're absent.

### Unrecognized / Extra Pages

Some users will include extra documents that are not part of the required 16 (e.g., intro pages, cover sheets, notes). When the classifier encounters a page it cannot match to any required document:

- Mark it as "Unrecognized"
- Show the page to the user with a text preview
- Ask: "We found a page we don't recognize. Is this one of the required documents? If so, which one? If not, we'll skip it."
- Allow the user to either assign it to a document type or dismiss it
- Do NOT pass unrecognized pages forward into processing unless the user assigns them

### Schedule Summary Identification

Schedule Summaries are identified by the schedule number on the FIRST page:

| Schedule # | Document |
|-----------|----------|
| 200 or 205 | Contracts in Transit |
| 237 | New Vehicle Inventory |
| 240 | Used Vehicle Inventory |
| 263 | Warranty Claims |
| 277 | Loaner Inventory / Service Loaners |

Continuation pages may only say "Schedule Summary" — use the previous page's classification.

## Upload Validation Behavior

When a user uploads a packet PDF, the system should:

1. Scan every page and classify it against the required documents list
2. Group multi-page documents together using pagination markers and context
3. For GL 0504 pages where New/Used cannot be determined, prompt the user to classify
4. Display results showing:
   - **Classified pages**: grouped by document type with page ranges (e.g., "Open RO List: Pages 12-15")
   - **Unrecognized pages**: with text preview and option to assign or dismiss
   - **Required documents checklist**: green checkmarks for found, red X for missing with "Where to Find It" instructions
5. Allow the user to proceed with a partial packet (with warnings) or re-upload
6. Store the original uploaded PDF in S3 for archival

## Section Detection Keywords

These keywords/patterns help the system identify each document within a packet:

| # | Document | Detection Keywords |
|---|----------|--------------------|
| 1 | Reynolds Employee List | "EMPLOYEE", "PERSONNEL", employee roster headers |
| 2 | Parts 2213 | "2213", "PARTS INVENTORY" |
| 3 | Parts 2222 | "2222", "PARTS ANALYSIS", "MONTHLY ANALYSIS" |
| 4 | Service and Parts Receivables | "SERVICE", "PARTS RECEIVABLE", schedule summary headers |
| 5 | Warranty Claims | "WARRANTY", "CLAIM", schedule 263 |
| 6 | Open RO List (3617) | "3617", "OPEN RO", "REPAIR ORDER" |
| 7 | Loaner Inventory | "LOANER", "SERVICE LOANER", schedule 277 |
| 8 | GL 0504 New & Used | "0504" with NEW/USED/A/B context — may need user disambiguation |
| 9 | New Inventory | "NEW VEHICLE", "NEW CAR", schedule 237, "Schedule Summary" + "237" |
| 10 | Used Inventory | "USED VEHICLE", "USED CAR", schedule 240, "Schedule Summary" + "240" |
| 11 | Wholesale Deals in Range | "WHOLESALE DEAL", "WHOLESALE" with date range |
| 12 | GL 0504 Chargebacks | "F&I CHARGEBACK", "F&I" + "0504", "OVER 90 DAYS" for subtypes |
| 13 | Contracts in Transit | "CONTRACT IN TRANSIT", "CIT", schedule 200 or 205 |
| 14 | Slow to Accounting | "SLOW TO ACCOUNTING", "SLOW-TO-ACCOUNTING" |
| 15 | Wholesales | "WHOLESALE", schedule summary with wholesale context |
| 16 | Missing Titles | "MISSING TITLE", "TITLE" with missing/open context |

## Parser Coverage

| # | Document | Parser | Status |
|---|----------|--------|--------|
| 1 | Reynolds Employee List | — | Not parsed (reference/presence check only) |
| 2 | Parts 2213 | parts_parser | Covered |
| 3 | Parts 2222 | parts_parser | Covered |
| 4 | Service and Parts Receivables | financial_parser | Covered |
| 5 | Warranty Claims | operations_parser | Covered |
| 6 | Open RO List (3617) | operations_parser | Covered |
| 7 | Loaner Inventory | inventory_parser | Covered |
| 8 | GL 0504 New & Used | — | Needs review — user disambiguation may be needed |
| 9 | New Inventory | inventory_parser | Covered (Sch 237) |
| 10 | Used Inventory | inventory_parser | Covered (Sch 240) |
| 11 | Wholesale Deals in Range | — | Needs review |
| 12 | GL 0504 Chargebacks | financial_parser | Covered — 4 subtypes (new/used × normal/over 90) |
| 13 | Contracts in Transit | financial_parser | Covered (Sch 200/205) |
| 14 | Slow to Accounting | operations_parser | Covered |
| 15 | Wholesales | — | Needs review |
| 16 | Missing Titles | operations_parser | Presence check + parsed if data available |

## Reference Examples

> This section will be populated with OCR text signatures from labeled reference pages to train the classifier.
> Each document type will have: the canonical header text, common variations, continuation page patterns, and OCR artifacts to expect.

*(Pending — Bryan will provide labeled printout photos for each document type)*

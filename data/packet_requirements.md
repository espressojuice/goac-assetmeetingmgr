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
| 13 | Schedule Summary — Contracts in Transit | R&R Schedule Summary | Reynolds → Schedule Summary → CIT (Sch 200) |
| 14 | Slow to Accounting | R&R Report | Reynolds → Reports → Slow to Accounting |
| 15 | Schedule Summary — Wholesales | R&R Schedule Summary | Reynolds → Schedule Summary → Wholesales |
| 16 | Missing Titles | Google Sheets | Google Sheets — maintained manually outside R&R, printed/exported and included in packet |

## Upload Validation Behavior

When a user uploads a packet PDF, the system should:

1. Scan the document to identify which of the 16 required sections are present
2. Check each section off against this list
3. Display results to the user showing:
   - Which documents were found (with page numbers)
   - Which documents are **missing** — with the "Where to Find It" instructions so the user knows exactly where to pull them from in Reynolds
4. Allow the user to proceed with a partial packet (with warnings) or re-upload a complete one
5. Store the original uploaded PDF in S3 for archival

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
| 8 | GL 0504 New & Used | "GL 0504", "GENERAL LEDGER", "0504" with NEW/USED context |
| 9 | New Inventory | "NEW VEHICLE", "NEW CAR", schedule 237 |
| 10 | Used Inventory | "USED VEHICLE", "USED CAR", schedule 240 |
| 11 | Wholesale Deals in Range | "WHOLESALE DEAL", "WHOLESALE" with date range |
| 12 | GL 0504 Chargebacks | "CHARGEBACK", "F&I", "0504" with chargeback context |
| 13 | Contracts in Transit | "CONTRACT IN TRANSIT", "CIT", schedule 200 |
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
| 8 | GL 0504 New & Used | — | Needs review |
| 9 | New Inventory | inventory_parser | Covered (Sch 237) |
| 10 | Used Inventory | inventory_parser | Covered (Sch 240) |
| 11 | Wholesale Deals in Range | — | Needs review |
| 12 | GL 0504 Chargebacks | financial_parser | Covered |
| 13 | Contracts in Transit | financial_parser | Covered (Sch 200) |
| 14 | Slow to Accounting | operations_parser | Covered |
| 15 | Wholesales | — | Needs review |
| 16 | Missing Titles | operations_parser | Presence check + parsed if data available |

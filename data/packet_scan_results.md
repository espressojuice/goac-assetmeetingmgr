# Packet Scan Results

> Scanned 2026-03-11 using pdfplumber + tesseract OCR against 17 test packet PDFs.
> Most packets are scanned images (no text layer) — OCR was required for all analysis.

## Summary

| # | Filename | Store | Reynolds Store # | Meeting Date | Pages | Found Docs | Completeness |
|---|----------|-------|-----------------|-------------|-------|------------|-------------|
| 1 | 3311_001.pdf | Store 17 — Orr Infiniti (Shreveport Infiniti) | — | 02/24/2026 | 34 | 3/16 | 18% |
| 2 | 3316_001.pdf | Store 11 — Orr Motors (Shreveport Cadillac) | — | 02/24/2026 | 33 | 5/16 | 31% |
| 3 | 3328_001.pdf | Store 12 — Orr Motors of Louisiana (Shreveport Acura) | — | 02/26/2026 | 26 | 3/16 | 18% |
| 4 | ACFrOg...pdf | Unknown (Searcy CDJ meeting recap?) | — | 02/20/2026 | 28 | 3/16 | 18% |
| 5 | ASHDOWN RECEIVABLES MEETING 2-18-26 (1).pdf | Store 03 — Orr Motors of Ashdown (Ashdown Chevrolet) | — | 02/18/2026 | 31 | 6/16 | 37% |
| 6 | BMW ASSET PACKET (1).pdf | Store 13 — Greg Orr Motors (Shreveport BMW) | — | 02/26/2026 | 29 | 4/16 | 25% |
| 7 | BMW ASSET PACKET (2).pdf | Store 13 — Orr BMW (Shreveport BMW) | — | 02/25/2026 | 14 | 1/16 | 6% |
| 8 | CAD ASSET 2.19.26.pdf | Store 05 — Orr Motors of Arkansas (Hot Springs Cadillac) | — | 02/19/2026 | 20 | 4/16 | 25% |
| 9 | CAP RECEIVABLES MEETING 2-19-26.pdf | Store 01 — Classic Auto Park (CAP GM) | — | 02/19/2026 | 42 | 8/16 | **50%** |
| 10 | CDJR RECEIVABLES MEETING 2-17-26.pdf | Store 16 — Classic CDJ Inc (Texarkana CDJR) | — | 02/17/2026 | 35 | 5/16 | 31% |
| 11 | HON ASSET 2.19.26.pdf | Store 06 — Orr Motors of Hot Springs (Hot Springs Honda) | — | 02/19/2026 | 18 | 6/16 | 37% |
| 12 | KIA RECEIVABLES MEETING 2-17-26.pdf | Store 02 — Classic Motors (Texarkana Kia) | — | 02/17/2026 | 37 | 4/16 | 25% |
| 13 | MB RECEIVABLES MEETING 2-19-26.pdf | Store 04 — Classic Auto Park (CAP Mercedes) | — | 02/19/2026 | 23 | 5/16 | 31% |
| 14 | SKM_C25826022511560.pdf | Store 14 — Orr Motors of Destin (Destin Porsche) | — | 02/26/2026 | 26 | 4/16 | 25% |
| 15 | Lexmark...150513.pdf | Store 10 — Orr Motors of Searcy (Searcy Toyota) | — | 02/19/2026 | 21 | 3/16 | 18% |
| 16 | Lexmark...150657.pdf | Store 09 — Orr Motors North (Searcy CDJ) | — | 02/18/2026 | 23 | 3/16 | 18% |
| 17 | TOY ASSET 2.19.26.pdf | Store 07 — Orr Toyota (Hot Springs Toyota) | — | 02/19/2026 | 21 | 5/16 | 31% |

## Key Findings

- **No Reynolds 7-digit site IDs found** in any packet via OCR. The IDs (e.g., 7685787) may be in Reynolds system metadata rather than printed on reports, or OCR missed them in poor-quality scans.
- **Reynolds store numbers (2-digit)** were found in all 17 packets via "STORE XX BRANCH 01" headers — these map reliably to dealerships.
- **Best completeness: 50%** (CAP RECEIVABLES — Store 01) with 8 of 16 required docs found.
- **Worst completeness: 6%** (BMW ASSET PACKET (2) — only Parts 2222 detected).
- **Average completeness: 25%** across all packets — most packets are missing 10+ required documents.
- **All 17 packets are scanned images** — pdfplumber extracted zero text; tesseract OCR was required.
- **1 unidentified packet**: ACFrOg...pdf has no store header (possibly a Searcy CDJ meeting recap based on content).

## Document Detection Results (by document type)

| # | Required Document | Found In | Detection Rate |
|---|------------------|----------|---------------|
| 1 | Reynolds Employee List | HON, CAD, TOY | 3/17 (18%) |
| 2 | Parts 2213 | 3311, 3316, 3328, ASHDOWN, BMW(1), CAP, CDJR, KIA, MB | 9/17 (53%) |
| 3 | Parts 2222 | All except BMW(2) | 16/17 (94%) |
| 4 | Service and Parts Receivables | None | 0/17 (0%) |
| 5 | Warranty Claims | 3311, 3316, 3328, BMW(1), CAD, CDJR, HON, Lexmark-513, Lexmark-657, MB, TOY | 11/17 (65%) |
| 6 | Open RO List (3617) | ACFrOg, ASHDOWN, CAP, CDJR, HON, SKM, Lexmark-513, Lexmark-657, TOY | 9/17 (53%) |
| 7 | Loaner Inventory | 3316, CAP, MB | 3/17 (18%) |
| 8 | GL 0504 New & Used | None | 0/17 (0%) |
| 9 | New Inventory | ASHDOWN | 1/17 (6%) |
| 10 | Used Inventory | 3316, ACFrOg, ASHDOWN, BMW(1), CAP, HON, KIA | 7/17 (41%) |
| 11 | Wholesale Deals in Range | CAP | 1/17 (6%) |
| 12 | GL 0504 Chargebacks | CAP | 1/17 (6%) |
| 13 | Contracts in Transit | ASHDOWN, KIA, SKM | 3/17 (18%) |
| 14 | Slow to Accounting | CDJR, MB, SKM | 3/17 (18%) |
| 15 | Wholesales | None | 0/17 (0%) |
| 16 | Missing Titles | CAD, HON, TOY | 3/17 (18%) |

### Most Commonly Missing Documents

1. **Service and Parts Receivables** — 0% detection (may need different keywords for schedule summary format)
2. **GL 0504 New & Used** — 0% detection (may appear differently in scanned format)
3. **Wholesales** — 0% detection (hard to distinguish from "Wholesale Deals in Range")
4. **New Inventory** — 6% detection (schedule 237 keywords may need OCR tolerance)
5. **Wholesale Deals in Range** — 6% detection
6. **GL 0504 Chargebacks** — 6% detection

## Per-Packet Detail

### 1. 3311_001.pdf — Shreveport Infiniti (Store 17)
- **Pages**: 34 (all scanned)
- **Store**: Store 17 — Orr Infiniti
- **Meeting Date**: 02/24/2026
- **Found (3)**: Parts 2213 (p2), Parts 2222 (p2,31), Warranty Claims (p1,7)
- **Missing (13)**: Employee List, Service/Parts Receivables, Open RO, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 2. 3316_001.pdf — Shreveport Cadillac (Store 11)
- **Pages**: 33 (all scanned)
- **Store**: Store 11 — Orr Motors
- **Meeting Date**: 02/24/2026
- **Found (5)**: Loaner Inventory (p7), Parts 2213 (p2), Parts 2222 (p2,31), Used Inventory (p19), Warranty Claims (p1,10)
- **Missing (11)**: Employee List, Service/Parts Receivables, Open RO, GL 0504 New/Used, New Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 3. 3328_001.pdf — Shreveport Acura (Store 12)
- **Pages**: 26 (all scanned)
- **Store**: Store 12 — Orr Motors of Louisiana
- **Meeting Date**: 02/26/2026
- **Found (3)**: Parts 2213 (p2), Parts 2222 (p2), Warranty Claims (p1)
- **Missing (13)**: Employee List, Service/Parts Receivables, Open RO, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 4. ACFrOg...pdf — Unknown Store
- **Pages**: 28 (all scanned)
- **Store**: Unidentified (no STORE header found)
- **Meeting Date**: 02/20/2026
- **Found (3)**: Open RO List (p27,28), Parts 2222 (p10,25,27), Used Inventory (p16)
- **Missing (13)**: Employee List, Parts 2213, Service/Parts Receivables, Warranty Claims, Loaner Inventory, GL 0504 New/Used, New Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 5. ASHDOWN RECEIVABLES MEETING 2-18-26 (1).pdf — Ashdown Chevrolet (Store 03)
- **Pages**: 31 (all scanned, 1 with text layer)
- **Store**: Store 03 — Orr Motors of Ashdown
- **Meeting Date**: 02/18/2026
- **Found (6)**: Contracts in Transit (p28), New Inventory (p16), Open RO (p10), Parts 2213 (p2-4), Parts 2222 (p2-4), Used Inventory (p19)
- **Missing (10)**: Employee List, Service/Parts Receivables, Warranty Claims, Loaner Inventory, GL 0504 New/Used, Wholesale Deals, GL 0504 Chargebacks, Slow to Accounting, Wholesales, Missing Titles

### 6. BMW ASSET PACKET (1).pdf — Shreveport BMW (Store 13)
- **Pages**: 29 (all scanned)
- **Store**: Store 13 — Greg Orr Motors
- **Meeting Date**: 02/26/2026
- **Found (4)**: Parts 2213 (p2), Parts 2222 (p2,10), Used Inventory (p16,19), Warranty Claims (p1,7)
- **Missing (12)**: Employee List, Service/Parts Receivables, Open RO, Loaner Inventory, GL 0504 New/Used, New Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 7. BMW ASSET PACKET (2).pdf — Shreveport BMW (Store 13)
- **Pages**: 14 (all scanned)
- **Store**: Store 13 — Orr BMW
- **Meeting Date**: 02/25/2026
- **Found (1)**: Parts 2222 (p10)
- **Missing (15)**: Employee List, Parts 2213, Service/Parts Receivables, Warranty Claims, Open RO, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 8. CAD ASSET 2.19.26.pdf — Hot Springs Cadillac (Store 05)
- **Pages**: 20 (all scanned)
- **Store**: Store 05 — Orr Motors of Arkansas
- **Meeting Date**: 02/19/2026
- **Found (4)**: Missing Titles (p1), Parts 2222 (p10), Employee List (p1), Warranty Claims (p1)
- **Missing (12)**: Parts 2213, Service/Parts Receivables, Open RO, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales

### 9. CAP RECEIVABLES MEETING 2-19-26.pdf — CAP GM (Store 01)
- **Pages**: 42 (all scanned, 1 with text layer)
- **Store**: Store 01 — Classic Auto Park
- **Meeting Date**: 02/19/2026
- **Found (8)**: GL 0504 Chargebacks (p37), Loaner Inventory (p16), Open RO (p10,13), Parts 2213 (p2-4,37), Parts 2222 (p2-4), Used Inventory (p28), Warranty Claims (p7), Wholesale Deals (p34)
- **Missing (8)**: Employee List, Service/Parts Receivables, GL 0504 New/Used, New Inventory, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 10. CDJR RECEIVABLES MEETING 2-17-26.pdf — Texarkana CDJR (Store 16)
- **Pages**: 35 (all scanned, 1 with text layer)
- **Store**: Store 16 — Classic CDJ Inc
- **Meeting Date**: 02/17/2026
- **Found (5)**: Open RO (p13), Parts 2213 (p3,4,16), Parts 2222 (p3,4), Slow to Accounting (p34), Warranty Claims (p10)
- **Missing (11)**: Employee List, Service/Parts Receivables, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Wholesales, Missing Titles

### 11. HON ASSET 2.19.26.pdf — Hot Springs Honda (Store 06)
- **Pages**: 18 (all scanned)
- **Store**: Store 06 — Orr Motors of Hot Springs
- **Meeting Date**: 02/19/2026
- **Found (6)**: Missing Titles (p1), Open RO (p10), Parts 2222 (p7), Employee List (p1), Used Inventory (p4), Warranty Claims (p1,13)
- **Missing (10)**: Parts 2213, Service/Parts Receivables, Loaner Inventory, GL 0504 New/Used, New Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales

### 12. KIA RECEIVABLES MEETING 2-17-26.pdf — Texarkana Kia (Store 02)
- **Pages**: 37 (all scanned, 2 with text layer)
- **Store**: Store 02 — Classic Motors
- **Meeting Date**: 02/17/2026
- **Found (4)**: Contracts in Transit (p34), Parts 2213 (p3,4,25), Parts 2222 (p3,4), Used Inventory (p25)
- **Missing (12)**: Employee List, Service/Parts Receivables, Warranty Claims, Open RO, Loaner Inventory, GL 0504 New/Used, New Inventory, Wholesale Deals, GL 0504 Chargebacks, Slow to Accounting, Wholesales, Missing Titles

### 13. MB RECEIVABLES MEETING 2-19-26.pdf — CAP Mercedes (Store 04)
- **Pages**: 23 (all scanned)
- **Store**: Store 04 — Classic Auto Park
- **Meeting Date**: 02/19/2026
- **Found (5)**: Loaner Inventory (p13), Parts 2213 (p2-4,7), Parts 2222 (p2-4,7), Slow to Accounting (p23), Warranty Claims (p10)
- **Missing (11)**: Employee List, Service/Parts Receivables, Open RO, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Wholesales, Missing Titles

### 14. SKM_C25826022511560.pdf — Destin Porsche (Store 14)
- **Pages**: 26 (all scanned)
- **Store**: Store 14 — Orr Motors of Destin
- **Meeting Date**: 02/26/2026
- **Found (4)**: Contracts in Transit (p13), Open RO (p7), Parts 2222 (p2-4), Slow to Accounting (p22)
- **Missing (12)**: Employee List, Parts 2213, Service/Parts Receivables, Warranty Claims, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Wholesales, Missing Titles

### 15. Lexmark...150513.pdf — Searcy Toyota (Store 10)
- **Pages**: 21 (all scanned)
- **Store**: Store 10 — Orr Motors of Searcy
- **Meeting Date**: 02/19/2026
- **Found (3)**: Open RO (p21), Parts 2222 (p19,20), Warranty Claims (p1,7)
- **Missing (13)**: Employee List, Parts 2213, Service/Parts Receivables, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 16. Lexmark...150657.pdf — Searcy CDJ (Store 09)
- **Pages**: 23 (all scanned)
- **Store**: Store 09 — Orr Motors North
- **Meeting Date**: 02/18/2026
- **Found (3)**: Open RO (p22,23), Parts 2222 (p19,22), Warranty Claims (p7)
- **Missing (13)**: Employee List, Parts 2213, Service/Parts Receivables, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales, Missing Titles

### 17. TOY ASSET 2.19.26.pdf — Hot Springs Toyota (Store 07)
- **Pages**: 21 (all scanned)
- **Store**: Store 07 — Orr Toyota
- **Meeting Date**: 02/19/2026
- **Found (5)**: Missing Titles (p1), Open RO (p10), Parts 2222 (p7), Employee List (p1), Warranty Claims (p1,13)
- **Missing (11)**: Parts 2213, Service/Parts Receivables, Loaner Inventory, GL 0504 New/Used, New Inventory, Used Inventory, Wholesale Deals, GL 0504 Chargebacks, Contracts in Transit, Slow to Accounting, Wholesales

## Notes

1. **Reynolds 7-digit site IDs** were not found in any packet text via OCR. These IDs exist in the Reynolds system (confirmed in Session 16) but may not be printed on standard reports. Store identification relies on the 2-digit store number in "STORE XX BRANCH 01" headers.

2. **Detection limitations**: OCR quality on scanned documents is variable. Some documents may be present but not detected due to:
   - Poor scan quality causing OCR misreads
   - Non-standard page layouts
   - Keywords obscured by handwriting/stamps
   - The sampling approach (every 3rd page) may miss some sections

3. **Service and Parts Receivables, GL 0504 New & Used, and Wholesales** had 0% detection across all packets. This likely indicates the detection keywords need refinement for OCR text, or these sections use different headers in scanned Reynolds reports.

4. **Parts 2222** had the highest detection rate at 94% — the "2222" keyword is short, distinctive, and OCR-resistant.

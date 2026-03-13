# Document Reference Signatures

> Built from the Ashdown labeled reference PDF (data/reference_ashdown_labeled.pdf).
> Each entry shows the document type, the reference page(s) in the labeled PDF,
> the exact OCR text patterns tesseract produces, and the classification rules.

---

## Page Map (Ashdown Reference PDF — 27 pages)

| PDF Page | Document Type | Notes |
|----------|--------------|-------|
| 1 | Intro Page (NOT required) | "ASSET MEETING" + store name + summary table |
| 2 | Employee List (#1) | Names + roles roster |
| 3-5 | Parts 2213 (#2) | 3 pages, "MONTHLY ANALYSIS" + "2213" |
| 6 | Parts 2222 (#3) | "Core Inventory Value" |
| 7 | Schedule Summary — Service & Parts Receivables (#4) | Schedule#: 200 |
| 8 | Schedule Summary — Warranty Claims (#5) | Schedule#: 263 |
| 9-10 | Open RO List 3617 (#6) | 2 pages, "Open ROs" |
| 11 | Schedule Summary — Loaner Inventory (#7) | Schedule#: 277 |
| 12 | GL 0504 New (#8) | Account 15A, "POLICY ADJ NEW" |
| 13 | GL 0504 Used (#8) | Account 15B, "POLICY ADJ USD" |
| 14-15 | Schedule Summary — New Inventory (#9) | Schedule#: 237, 2 pages |
| 16-18 | Schedule Summary — Used Inventory (#10) | Schedule#: 240, 3 pages (page 16 is continuation from New, actually starts Used) |
| 19 | Wholesale Deals in Range (#11) | "WHOLESALE DEALS IN A DATE RANGE" |
| 20 | GL 0504 F&I Chargeback — New (#12a) | Account 850, "F&I CHARGEBACK" |
| 21 | GL 0504 F&I Chargeback Over 90 — New (#12b) | Account 850A, "F&I OV 90 DAY" |
| 22 | GL 0504 F&I Chargeback — Used (#12c) | Account 851, "F&I CHARGEBACK" |
| 23 | GL 0504 F&I Chargeback Over 90 — Used (#12d) | Account 851A, "F&I OV 90 DAY" |
| 24 | Schedule Summary — Contracts in Transit (#13) | Schedule#: 205 |
| 25 | Slow to Accounting (#14) | "SLOW TO ACCOUNTING" |
| 26 | Schedule Summary — Wholesales (#15) | Schedule#: 220 |
| 27 | Missing Titles (#16) | "MISSING TITLE" (Google Sheets format) |

---

## 1. Employee List

**Required**: Yes (#1)
**Reference pages**: 2
**Multi-page**: Rare (usually 1 page)

### OCR Signature
```
Primary patterns (ANY match → classify):
- "EMPLOYEE" in first 10 lines
- "PERSONNEL" in first 10 lines
- List of names followed by role/department codes

Observed OCR text (page 2):
  Line 1-2: Store abbreviation (e.g., "ASH")
  Body: Name roster — LASTNAME FIRSTNAME format
  Roles seen: SALES, TECH, SERVICE ADVISOR, PARTS, PORTER, MANAGER, BDC

Secondary patterns:
- Dense list of proper names (ALL CAPS) with department codes
- No financial data, no account numbers, no VINs
- May have date header like "ASH 2/9/26"
```

### Key Distinguishing Features
- Only document that is a pure name/personnel roster
- No dollar amounts, no account numbers
- May be very poorly OCR'd due to handwritten or small print

---

## 2. Parts 2213

**Required**: Yes (#2)
**Reference pages**: 3-5 (3 pages)
**Multi-page**: Common (2-4 pages)

### OCR Signature
```
Primary patterns (ANY match → classify):
- "2213" anywhere on page
- "MONTHLY ANALYSIS" in first 10 lines

Observed OCR (pages 3-5):
  Header area: "MONTHLY ANALYSIS" + "2213"
  "STORE 03 BRANCH 01" + store name
  Page markers: "PAGE 1", "PAGE 2", "PAGE 3" (top right area)

  Page 1 keywords: "COST OF SALES", "NORMAL STOCK PARTS", "SUMMARY"
  Page 2 keywords: "OUTSTANDING ORDERS", "SUMMARY"
  Page 3 keywords: "ADDS", "DELETES", "ADJUSTMENTS", "PHYSICAL INVENTORY"

Continuation pages:
- Still say "MONTHLY ANALYSIS" and "2213" in header
- Have PAGE 2, PAGE 3 markers
```

### Key Distinguishing Features
- "2213" is unique — no other document uses this number
- Always has "MONTHLY ANALYSIS" header
- Has store/branch info: "STORE XX BRANCH XX"
- Contains parts inventory data with dollar amounts

---

## 3. Parts 2222

**Required**: Yes (#3)
**Reference pages**: 6
**Multi-page**: Usually 1 page

### OCR Signature
```
Primary patterns (ANY match → classify):
- "2222" anywhere on page
- "Core Inventory Value" in first 5 lines
- "PARTS ANALYSIS" in first 10 lines

Observed OCR (page 6):
  Line 1: "Core Inventory Value"
  Line 2: "Makes: GM" (or other make)
  Line 3: "Sources Included: All"
  Body: Table with Part#, Description, Source, Bin, Status, Age columns
  Footer: "Store: 03 - ORR MOTORS OF ASHDOWN, INC" + "Page 1 of 1"

Secondary patterns:
- "Core" + "Inventory" + "Value" together
- Part numbers (alphanumeric codes)
- "Page X of Y" footer
```

### Key Distinguishing Features
- "Core Inventory Value" header is unique to this report
- "2222" number is unique
- Contains individual part-level detail (Part#, Description)
- Smaller/denser table format than 2213

---

## 4. Schedule Summary — Service & Parts Receivables

**Required**: Yes (#4)
**Reference pages**: 7
**Multi-page**: Can be 1-3 pages

### OCR Signature
```
Primary patterns (ALL must match):
- "Schedule Summary" in first 3 lines
- "Schedule#: 200" OR "ACCOUNTS RECEIVABLE" in first 10 lines

Observed OCR (page 7):
  Line 1: "Schedule Summary"
  Line 2: "Schedule#: 200 ACCOUNTS RECEIVABLE"
  Line 3: "Cutoff Date: MM/DD/YY"
  Lines 4-6: "Days: All", "Control#(s): All", "Include zero balance..."
  Table headers: Customer#, Name, Total, Current, 31-60, 61-90, 91-120, 121+, Remarks
  Footer: "Store: XX - STORE NAME" + "Page X of Y"

Schedule number: 200
```

### Key Distinguishing Features
- Schedule#: 200 is unique to this document
- "ACCOUNTS RECEIVABLE" in schedule description
- Aging columns (Current/31-60/61-90/91-120/121+)
- Standard Schedule Summary format

---

## 5. Schedule Summary — Warranty Claims

**Required**: Yes (#5)
**Reference pages**: 8
**Multi-page**: Can be 1-3 pages

### OCR Signature
```
Primary patterns (ALL must match):
- "Schedule Summary" in first 3 lines
- "Schedule#: 263" OR "WARR CLAIMS" OR "WARRANTY" in first 10 lines

Observed OCR (page 8):
  Line 1: "Schedule Summary"
  Line 2: "Schedule#: 263 WARR CLAIMS-GM 263"
  Line 3: "Cutoff Date: MM/DD/YY"
  Table: Control#, Description, Total, Current, 31-60, 61-90, 91-120
  Body: VIN-based entries with dollar amounts

Schedule number: 263
```

### Key Distinguishing Features
- Schedule#: 263 is unique to warranty claims
- "WARR CLAIMS" or "WARRANTY" in schedule description
- VIN numbers in the data rows
- Aging columns like other Schedule Summaries

---

## 6. Open RO List (3617)

**Required**: Yes (#6)
**Reference pages**: 9-10 (2 pages)
**Multi-page**: Very common (2-5 pages)

### OCR Signature
```
Primary patterns (ANY match → classify):
- "Open ROs" in first 3 lines
- "3617" anywhere on page
- "REPAIR ORDER" in first 10 lines

Observed OCR (page 9):
  Line 1: "Open ROs"
  Line 2: "Report Format: Detail"
  Line 3: "Include: All Open ROs"
  Line 4: "Branch: Include ROs from current branch only"
  Table headers: RO#, CWI, Advisor, Dept, Make, Customer Name, VIN, Tags, RO Date, Prom Date

Continuation pages (page 10):
  Line 1: "Open ROs" (repeated header, but NO "Report Format" subtitle)
  Same column layout
  Page marker: "Page 2 of 2"

Footer: "Page X of Y" + record count
```

### Key Distinguishing Features
- "Open ROs" header is unique
- Contains RO (Repair Order) numbers
- Detail format with VIN, Customer Name, Advisor columns
- "3617" report number may appear in header or footer
- Continuation pages still say "Open ROs" at top

---

## 7. Schedule Summary — Loaner Inventory

**Required**: Yes (#7)
**Reference pages**: 11
**Multi-page**: Usually 1 page

### OCR Signature
```
Primary patterns (ALL must match):
- "Schedule Summary" in first 3 lines
- "Schedule#: 277" OR "LOANER" in first 10 lines

Observed OCR (page 11):
  Line 1: "Schedule Summary"
  Line 2: "Schedule#: 277 LOANERS"
  Line 3: "Cutoff Date: MM/DD/YY"
  Table headers: Vehicle, VIN, Description, Control#, 277, 312, Days, Remarks
  Body: Individual vehicle entries with VINs

Schedule number: 277
```

### Key Distinguishing Features
- Schedule#: 277 is unique to loaner inventory
- "LOANERS" or "SERVICE LOANER" in schedule description
- VIN numbers and vehicle descriptions
- Different column structure than other Schedule Summaries (277, 312 columns)

---

## 8. GL 0504 New & Used

**Required**: Yes (#8)
**Reference pages**: 12 (New/A), 13 (Used/B)
**Multi-page**: Usually 1 page each

### OCR Signature
```
Primary patterns (ALL must match):
- "0504" in top-right corner area
- "GL INQUIRY" in first 5 lines
- "ACCOUNT 15" OR "ACCOUNT" + "15A" OR "15B" in first 15 lines
- NOT "850" or "851" or "F&I" or "CHARGEBACK" (those are F&I chargebacks)

New variant (page 12):
  Header: date + "CASSIED" + store name + "0504" + "PAGE X"
  "GL INQUIRY FOR MM/DD/YYYY THRU MM/DD/YYYY"
  "ACCOUNT 15A" or "ACCOUNT" with "A" suffix
  "POLICY ADJ NEW" in description line
  Table: SRC, REFERENCE NO., DATE, PORT CONTROL NO., DEBIT AMOUNT, CREDIT AMOUNT, NAME, DESCRIPTION

Used variant (page 13):
  Same GL format
  "ACCOUNT 15B" or "ACCOUNT" with "B" suffix
  "POLICY ADJ USD" (Used) in description line

DISAMBIGUATION RULES:
- If "15A" or "POLICY ADJ NEW" → New
- If "15B" or "POLICY ADJ USD" or "POLICY ADJ USED" → Used
- If just "15" with no A/B suffix and no NEW/USED text → ASK USER
```

### Key Distinguishing Features
- "0504" top-right is shared with F&I chargebacks — must check account number
- Account 15A = New, Account 15B = Used
- "POLICY ADJ" in description distinguishes from chargebacks
- Same "GL INQUIRY" format as chargebacks — differentiate by account number
- "CASSIED" or similar appears (operator name at top — OCR varies)

---

## 9. Schedule Summary — New Inventory

**Required**: Yes (#9)
**Reference pages**: 14-15 (2 pages, may have continuation)
**Multi-page**: Very common (2-5 pages)

### OCR Signature
```
Primary patterns (ALL must match):
- "Schedule Summary" in first 3 lines
- "Schedule#: 237" OR "NEW VEH INVENTORY" in first 10 lines

Observed OCR (page 14):
  Line 1: "Schedule Summary"
  Line 2: "Schedule#: 237 NEW VEH INVENTORY 231-237"
  Line 3: "Cutoff Date: MM/DD/YY"
  Table headers: Control#, Description, Total, 237, 231, 310, Days, VIN, Days in Stock
  Body: Vehicle entries with VINs, descriptions like "26 CHEVROLET TRUCK"

Continuation pages (page 15):
  Line 1: "Schedule Summary" (no schedule number!)
  Same column layout: Control#, Description, Total, 237, 231, 310...
  Use previous page context to classify

Schedule number: 237
```

### Key Distinguishing Features
- Schedule#: 237 is unique to new vehicle inventory
- "NEW VEH INVENTORY" in schedule description
- Columns include 237, 231, 310 (account sub-codes)
- VIN numbers and vehicle descriptions (year + make + model)
- "Days in Stock" column

---

## 10. Schedule Summary — Used Inventory

**Required**: Yes (#10)
**Reference pages**: 16-18 (3 pages)
**Multi-page**: Very common (2-6+ pages)

### OCR Signature
```
Primary patterns (ALL must match):
- "Schedule Summary" in first 3 lines
- "Schedule#: 240" OR "USED VEHICLE INVENTORY" in first 10 lines

Observed OCR (page 16):
  Line 1: "Schedule Summary"
  Line 2: "Schedule#: 240 USED VEHICLE INVENTORY"
  Line 3: "Cutoff Date: MM/DD/YY"
  Table headers: Control#, Description, Total, 240, 241, 311, 311X, Days, VIN, Days in Stock
  Body: Vehicle entries with VINs

Continuation pages (pages 17-18):
  Line 1: "Schedule Summary" (no schedule number)
  Same column layout: Control#, Description, Total, 240, 241, 311, 311X...
  Use previous page context to classify

Schedule number: 240
```

### Key Distinguishing Features
- Schedule#: 240 is unique to used vehicle inventory
- "USED VEHICLE INVENTORY" in schedule description
- Columns include 240, 241, 311, 311X (different from New which has 237, 231, 310)
- VIN numbers and vehicle descriptions
- "Days in Stock" column

---

## 11. Wholesale Deals in Range

**Required**: Yes (#11)
**Reference pages**: 19
**Multi-page**: Usually 1 page

### OCR Signature
```
Primary patterns (ANY match → classify):
- "WHOLESALE DEALS" in first 5 lines
- "WHOLESALE DEALS IN A DATE RANGE" or similar

Observed OCR (page 19):
  Line 1: "WHOLESALE DEALS IN A DATE RANGE"
  Line 2: "- ASH" (store abbreviation)
  Line 3: "Run Areas"
  Criteria section: "DEAL-CATEG-DR = W" + date range filters
  Table headers: REV-DATE, JRNL-DATE, STK-NO, MAKE, CARLINE, VIN, SAL...
  Footer: "MAST-FANDI" + page/record count

NOTE: This is NOT the same as "Wholesales" (#15) which is a Schedule Summary.
This is a Dynamic Reporting export — different format entirely.
```

### Key Distinguishing Features
- "WHOLESALE DEALS IN A DATE RANGE" is unique (vs Schedule Summary Wholesales)
- NOT a Schedule Summary — different report format
- Has criteria/filter section with "DEAL-CATEG-DR = W"
- "MAST-FANDI" in footer (Reynolds report system footer)
- Contains deal-level data: stock numbers, VINs, make/model

---

## 12. GL 0504 Chargebacks (4 subtypes)

**Required**: Yes (#12) — but not all 4 subtypes will always be present
**Reference pages**: 20 (New normal), 21 (New over 90), 22 (Used normal), 23 (Used over 90)
**Multi-page**: Usually 1 page each

### Subtype A: F&I Chargeback — New

```
Primary patterns:
- "0504" in top-right
- "GL INQUIRY" in first 5 lines
- "ACCOUNT 850" (not 850A) in first 15 lines
- "F&I CHARGEBACK" in account description line
- NOT "OV 90" or "OVER 90"

Observed OCR (page 20):
  Header: date + operator + store name + "0504" + "PAGE X"
  "GL INQUIRY FOR MM/DD/YYYY THRU MM/DD/YYYY"
  "ACCOUNT 850" + "C/S - F&I CHARGEBACK * OPEN BALANCE *"
  Table: SRC, REFERENCE NO., DATE, PORT CONTROL NO., DEBIT AMOUNT, CREDIT AMOUNT
  Descriptions: "AT/xxxxxx/LASTNAME" format (deal references)

Account: 850
```

### Subtype B: F&I Chargeback Over 90 — New

```
Primary patterns:
- "0504" in top-right
- "GL INQUIRY" in first 5 lines
- "ACCOUNT 850A" in first 15 lines
- "F&I OV 90 DAY" or "F&I OVER 90" in account description

Observed OCR (page 21):
  "ACCOUNT 850A" + "C/S - F&I OV 90 DAY * OPEN BALANCE *"
  Same GL format as above

Account: 850A
```

### Subtype C: F&I Chargeback — Used

```
Primary patterns:
- "0504" in top-right
- "GL INQUIRY" in first 5 lines
- "ACCOUNT 851" (not 851A) in first 15 lines
- "F&I CHARGEBACK" in account description

Observed OCR (page 22):
  "ACCOUNT 851" + "C/S - F&I CHARGEBACK * OPEN BALANCE *"
  Same GL format

Account: 851
```

### Subtype D: F&I Chargeback Over 90 — Used

```
Primary patterns:
- "0504" in top-right
- "GL INQUIRY" in first 5 lines
- "ACCOUNT 851A" in first 15 lines
- "F&I OV 90 DAY" or "F&I OVER 90" in account description

Observed OCR (page 23):
  "ACCOUNT 851A" + "C/S - F&I OV 90 DAY * OPEN BALANCE *"
  Same GL format

Account: 851A
```

### Account Number Summary

| Account | Type |
|---------|------|
| 15A | GL 0504 New (Policy Adj) |
| 15B | GL 0504 Used (Policy Adj) |
| 850 | F&I Chargeback — New |
| 850A | F&I Chargeback Over 90 — New |
| 851 | F&I Chargeback — Used |
| 851A | F&I Chargeback Over 90 — Used |

### GL 0504 Master Classification Logic

```
IF page has "0504" AND "GL INQUIRY":
  Extract account number from "ACCOUNT XXX" line

  IF account starts with "15":
    IF "A" suffix OR "NEW" in description → GL 0504 New (#8)
    IF "B" suffix OR "USED" or "USD" in description → GL 0504 Used (#8)
    IF no suffix and no NEW/USED text → ASK USER (dropdown: New or Used)

  IF account = "850":
    → F&I Chargeback New (#12a)
  IF account = "850A":
    → F&I Chargeback Over 90 New (#12b)
  IF account = "851":
    → F&I Chargeback Used (#12c)
  IF account = "851A":
    → F&I Chargeback Over 90 Used (#12d)
```

---

## 13. Schedule Summary — Contracts in Transit

**Required**: Yes (#13)
**Reference pages**: 24
**Multi-page**: Usually 1 page

### OCR Signature
```
Primary patterns (ALL must match):
- "Schedule Summary" in first 3 lines
- "Schedule#: 200" OR "Schedule#: 205" with "CONTRACT" in first 10 lines

IMPORTANT: Schedule 200 is ALSO used for Service & Parts Receivables (#4).
Disambiguate by checking the schedule DESCRIPTION:
- "200 ACCOUNTS RECEIVABLE" → Service & Parts Receivables (#4)
- "205 CONTRACTS IN TRANSIT" → Contracts in Transit (#13)
- "200" with "CONTRACT" → Contracts in Transit (#13) — some stores use 200 not 205

Observed OCR (page 24):
  Line 1: "Schedule Summary" (may be cut off as "hedule Summary")
  Line 2: "Schedule#: 205 CONTRACTS IN TRANSIT ASHD"
  Line 3: "Cutoff Date: MM/DD/YY"
  Table headers: Control#, Description, Total, 205, 210, Days, Remarks
  Body: Customer names with dollar amounts
  Footer: "Store: XX - STORE NAME" + "Page X of Y" + "X records listed"

Schedule number: 200 or 205
```

### Key Distinguishing Features
- "CONTRACTS IN TRANSIT" or "CIT" in schedule description
- Schedule 205 is the primary identifier (but 200 can also be CIT)
- Column "205" and "210" in table headers
- Customer names with funding status in Remarks (e.g., "FUNDED", "READY TO TURN")
- Handwritten notes common (Bryan writes status updates on printouts)

---

## 14. Slow to Accounting

**Required**: Yes (#14)
**Reference pages**: 25
**Multi-page**: Usually 1 page

### OCR Signature
```
Primary patterns (ANY match → classify):
- "SLOW TO ACCOUNTING" in first 5 lines
- "SLOW-TO-ACCOUNTING" in first 5 lines

Observed OCR (page 25):
  Line 1: "5H SLOW TO ACCOUNTING" (the "5H" is a report prefix, OCR may garble)
  Criteria: "AT = C And" + "AL-CATEG = R, L, W, Or"
  Table headers: AL DTE, DEAL NO, STOCK NO, D.., BYR FIRST NME/INIT, BYR LAST NAME,
                 FI-FMI, VEH-GRS, BANK-NAME
  Body: Deal rows with names, stock numbers, gross amounts, bank names
  Footer: "MAST-FANDI" + "Page X of Y" + "X records listed"

NOTE: "MAST-FANDI" footer is shared with Wholesale Deals report — both are R&R
Dynamic Reporting exports. Distinguish by header content.
```

### Key Distinguishing Features
- "SLOW TO ACCOUNTING" header is unique
- "5H" prefix (R&R report code) — OCR may read as "SH" or garble
- "MAST-FANDI" footer (shared with Wholesale Deals)
- Contains deal numbers, customer names, bank names
- Filter criteria block near top

---

## 15. Schedule Summary — Wholesales

**Required**: Yes (#15)
**Reference pages**: 26
**Multi-page**: Usually 1 page

### OCR Signature
```
Primary patterns (ALL must match):
- "Schedule Summary" in first 3 lines
- "Schedule#: 220" OR "WHOLESALES" in first 10 lines

Observed OCR (page 26):
  Line 1: "Schedule Summary"
  Line 2: "Schedule#: 220 WHOLESALES 220A"
  Line 3: "Cutoff Date: MM/DD/YY"
  Table headers: Customer#, Name, Total, Current, 31-60, 61-90, 91-120, 121+, Remarks
  Body: Customer entries with aging amounts
  Footer: "Store: XX - STORE NAME" + "Page X of Y"

Schedule number: 220

NOTE: This is NOT the same as "Wholesale Deals in Range" (#11).
#11 is a Dynamic Reporting export. #15 is a Schedule Summary.
```

### Key Distinguishing Features
- Schedule#: 220 is unique to wholesales schedule
- "WHOLESALES" in schedule description (may include "220A")
- Standard Schedule Summary aging format
- Distinguish from Wholesale Deals (#11) by "Schedule Summary" header

---

## 16. Missing Titles

**Required**: Yes (#16)
**Reference pages**: 27
**Multi-page**: Usually 1 page

### OCR Signature
```
Primary patterns (ANY match → classify):
- "MISSING TITLE" in first 10 lines (may be store-specific: "ASHDOWN MISSING TITLE")
- "TITLE" with "MISSING" nearby

Observed OCR (page 27):
  NOTE: This page OCR'd very poorly (mostly underscores) because it's a
  Google Sheets export with thin lines. Visual inspection shows:

  Header: "[STORE] MISSING TITLE" (e.g., "ASHDOWN MISSING TITLE")
  Table headers: CUSTOMER NAME, CUST#, Lienholder Information, Stock#,
                 Date Traded, Sent P/O, Year/Make/Model, ADDT INFORMATION
  Body: Customer entries with vehicle details and tracking notes

  This document comes from Google Sheets (not R&R) so its format varies
  more than other documents. May appear as:
  - Printed Google Sheets with gridlines
  - Excel export
  - Sometimes with color highlighting (lost in B&W scan)

FALLBACK: If OCR fails on this page, check for:
- Tabular layout with customer names + vehicle info
- Not matching any other document type
- Relatively sparse/clean compared to R&R reports
```

### Key Distinguishing Features
- Only document NOT from Reynolds (comes from Google Sheets)
- "MISSING TITLE" in header
- Contains customer names, stock numbers, year/make/model
- Lienholder information column is unique to this report
- May OCR poorly due to thin gridlines from spreadsheet export

---

## Classification Priority Order

When classifying a page, check in this order (most distinctive first):

1. **"Open ROs"** → Open RO List (#6)
2. **"SLOW TO ACCOUNTING"** → Slow to Accounting (#14)
3. **"WHOLESALE DEALS IN A DATE RANGE"** → Wholesale Deals (#11)
4. **"MISSING TITLE"** → Missing Titles (#16)
5. **"Core Inventory Value"** or "2222"** → Parts 2222 (#3)
6. **"MONTHLY ANALYSIS"** or **"2213"** → Parts 2213 (#2)
7. **"ASSET MEETING"** → Intro Page (skip/unrecognized)
8. **"0504" + "GL INQUIRY"** → GL 0504 family → use account number to subtype
9. **"Schedule Summary" + schedule number** → use schedule number:
   - 200 + "ACCOUNTS RECEIVABLE" → Service & Parts Receivables (#4)
   - 200 or 205 + "CONTRACT" → Contracts in Transit (#13)
   - 220 + "WHOLESALES" → Wholesales (#15)
   - 237 + "NEW VEH" → New Inventory (#9)
   - 240 + "USED VEH" → Used Inventory (#10)
   - 263 + "WARR CLAIMS" → Warranty Claims (#5)
   - 277 + "LOANER" → Loaner Inventory (#7)
10. **"Schedule Summary" with no schedule number** → continuation page → use previous page's classification
11. **Employee roster pattern** (names + roles, no financial data) → Employee List (#1)
12. **No match** → Unrecognized → show to user

---

## Continuation Page Detection

A page is likely a continuation if ALL of these are true:

1. Page starts with "Schedule Summary" but has NO "Schedule#:" line in first 10 lines
2. OR page starts with "Open ROs" but has NO "Report Format:" subtitle
3. OR page has same column layout as previous page (check for matching header words)
4. Previous page was classified as a multi-page document type

When a continuation is detected:
- Inherit the classification from the previous page
- Group page numbers together (e.g., "New Inventory: Pages 14-16")

---

## Schedule Summary Common Format

All Schedule Summaries share this structure:

```
Line 1: "Schedule Summary"
Line 2: "Schedule#: NNN DESCRIPTION"
Line 3: "Cutoff Date: MM/DD/YY"
Line 4: "Days: All"
Line 5: "Control#(s): All"
Line 6: "Include zero balance and activity: No"
[blank line]
[Table headers — vary by schedule type]
[Data rows]
[Footer: Store info + Page X of Y + record count + timestamp]
```

The schedule number on line 2 is the PRIMARY classifier. If OCR garbles the number, fall back to description keywords.

---

## GL 0504 Common Format

All GL 0504 pages share this structure:

```
Top-left: date + operator name (e.g., "CASSIED")
Center: store name (e.g., "CLASSIC CHEVROLET")
Top-right: "0504" + "PAGE X"
Line 2 area: "GL INQUIRY FOR MM/DD/YYYY THRU MM/DD/YYYY"
[Column headers: SRC, REFERENCE NO., DATE, PORT CONTROL NO., DEBIT AMOUNT, CREDIT AMOUNT, NAME, DESCRIPTION]
Account line: "ACCOUNT NNN" + description + "* OPEN BALANCE *" + amount
[Data rows]
[Summary: "* TOTAL CURRENT ACTIVITY *" + "* CLOSING BALANCE *"]
```

The ACCOUNT NUMBER is the PRIMARY classifier for GL 0504 subtypes.

---

## OCR Quality Notes

From the Ashdown reference scans, tesseract produces these common artifacts:

- "CASSIED" for operator name (varies: "CADDIED", "CAOSIED", etc.) — ignore this
- Schedule Summary "Schedule#:" may OCR as "5chedule#:" or "Schedu1e#:"
- Numbers are generally reliable (account numbers, schedule numbers)
- Store names may have OCR errors but are recognizable
- "GL INQUIRY" sometimes OCRs as "CL INQUIRY" or "OL INQUIRY"
- Page headers/footers are more reliable than body text
- The word "Schedule" at top of continuation pages is very consistent
- Dollar amounts and VINs OCR well
- Handwritten notes (Bryan's annotations) will produce garbage — ignore

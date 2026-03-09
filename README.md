# GOAC Asset Meeting Manager

Automate, standardize, and enforce accountability for asset/receivable meetings across all Gregg Orr Auto Collection dealership locations.

## Roadmap

### Phase 1: Packet Generator + Flagging *(COMPLETE)*
Parse R&R DMS exports (PDF schedules, GL reports) into structured data. Apply configurable flagging rules to surface issues. Generate standardized meeting packets and flagged-item reports.

### Phase 2: Accountability Web App
Web interface for meeting scheduling, packet review, flag responses, and escalation tracking. Google Calendar integration for automated scheduling. Email notifications via SendGrid/Postmark.

### Phase 3: Full Automation
Automated DMS export ingestion, trend analysis, cross-store benchmarking, and executive dashboards.

## Tech Stack

- **Backend**: FastAPI (Python) + PostgreSQL + SQLAlchemy + Alembic
- **Frontend**: Next.js
- **APIs**: Google Calendar API, SendGrid/Postmark
- **Data Sources**: R&R DMS PDF exports

## Data Models

16 models across 7 model files. All models use UUID primary keys, timezone-aware timestamps, and indexes on `store_id`/`meeting_id`.

### Core
| Model | Table | Description |
|-------|-------|-------------|
| Store | `stores` | Dealership locations with GM info and meeting cadence |
| Meeting | `meetings` | Per-store meeting instances with status tracking |

### Inventory (`inventory.py`)
| Model | Table | Description |
|-------|-------|-------------|
| NewVehicleInventory | `new_vehicle_inventory` | New vehicle stock with floorplan and book values |
| UsedVehicleInventory | `used_vehicle_inventory` | Used vehicle stock with market value and acquisition source |
| ServiceLoaner | `service_loaners` | Loaner vehicles with negative equity tracking |
| FloorplanReconciliation | `floorplan_reconciliations` | Book vs floorplan variance (Schedule 237/240) |

### Parts (`parts.py`)
| Model | Table | Description |
|-------|-------|-------------|
| PartsInventory | `parts_inventory` | GL 242/243/244 parts balances |
| PartsAnalysis | `parts_analysis` | Monthly turnover, obsolescence, stock order metrics |

### Financial (`financial.py`)
| Model | Table | Description |
|-------|-------|-------------|
| Receivable | `receivables` | Aged receivables (200/220/2612) with 30/60/90 buckets |
| FIChargeback | `fi_chargebacks` | F&I reserve chargebacks (850/851 accounts) |
| ContractInTransit | `contracts_in_transit` | Unfunded deals with days-in-transit tracking |
| Prepaid | `prepaids` | Prepaid expenses (GL 2741) |
| PolicyAdjustment | `policy_adjustments` | Policy/goodwill adjustments (GL 15A/15B) |

### Operations (`operations.py`)
| Model | Table | Description |
|-------|-------|-------------|
| OpenRepairOrder | `open_repair_orders` | Open ROs with service type and aging |
| WarrantyClaim | `warranty_claims` | Warranty claims with status tracking |
| MissingTitle | `missing_titles` | Vehicles missing titles with days-missing count |
| SlowToAccounting | `slow_to_accounting` | Deals slow to reach accounting |

### Flags (`flag.py`)
| Model | Table | Description |
|-------|-------|-------------|
| Flag | `flags` | Flagged items with severity, category, and response tracking |

### Enums
- `MeetingStatus`: pending, processing, completed, error
- `ReconciliationType`: new_237, used_240
- `PartsCategory`: parts_242, tires_243, gas_oil_grease_244
- `ReceivableType`: parts_service_200, wholesale_220, factory_2612
- `FlagCategory`: inventory, parts, financial, operations
- `FlagSeverity`: yellow, red
- `FlagStatus`: open, responded, escalated

## Parser Architecture

The parser framework processes R&R DMS PDF exports through a three-layer pipeline:

```
PDF Upload → PDFExtractor → ParserRouter → [InventoryParser, PartsParser, FinancialParser, OperationsParser] → ProcessingService → Database
```

**PDFExtractor** (`parsers/pdf_extractor.py`) — Uses pdfplumber to extract text, lines, and tables from each PDF page into a standardized page dict format. Falls back to OCR (EasyOCR + pypdfium2) for scanned pages with no text layer. Detects landscape pages and retries with 90° rotation.

**ParserRouter** (`parsers/router.py`) — Routes pages to parsers based on section identifiers. Each page is matched to parser(s) that recognize its content. Unhandled pages are tracked for logging.

**BaseParser** (`parsers/base.py`) — Abstract base with shared utilities: `clean_currency()`, `clean_int()`, `parse_date()`, `extract_table_rows()`, `find_section_in_pages()`. All parsers inherit from this.

**InventoryParser** (`parsers/inventory_parser.py`) — Handles schedules 237 (new vehicles), 240 (used vehicles), 277 (service loaners). Tries pdfplumber table extraction first, falls back to line-by-line regex parsing. Computes FloorplanReconciliation records with book vs floorplan variance.

**PartsParser** (`parsers/parts_parser.py`) — Handles GL 242 (parts), 243 (tires), 244 (gas/oil/grease) inventory summaries and parts monthly analysis (turnover, stock order performance, obsolescence).

**FinancialParser** (`parsers/financial_parser.py`) — Handles receivables aging (schedules 200, 220, GL 2612), F&I chargebacks (accounts 850/851 with context-aware matching), contracts in transit (schedule 205), prepaids (GL 2741), and policy adjustments (GL 15A/15B).

**OperationsParser** (`parsers/operations_parser.py`) — Handles open repair orders (with CP/warranty/internal service types), warranty claims (schedule 263), missing titles, and slow-to-accounting deals.

**ProcessingService** (`services/processing_service.py`) — Orchestrates the full pipeline: extract → parse → save → flag → generate PDFs. Maps parser output dicts to SQLAlchemy model instances. After saving records, runs the FlaggingEngine to generate Flag records. Then generates both output PDFs and updates the Meeting record with file paths and completed status.

## Output Documents

The system generates two PDF documents per meeting:

### Standardized Packet (`generators/packet_generator.py`)
A clean, consistent PDF replacing manually-assembled packets. Every store's packet looks the same regardless of who prepared it. Structure:
- **Cover Page** — GOAC branding, store name, meeting date, flag summary
- **Section 1: Executive Summary** — Quick stats (vehicle counts, floorplan exposure, aging, negative equity, turnover, receivables), red flag alert, floorplan reconciliation
- **Section 2: New Vehicle Inventory** — Sorted by days oldest-first, color-coded (red >120 days, yellow >90), subtotals, floorplan reconciliation box
- **Section 3: Used Vehicle Inventory** — Sorted by days oldest-first, color-coded (red >90, yellow >60), over-60/90 counts
- **Section 4: Service Loaners** — Color-coded by days and negative equity thresholds, total negative equity prominently displayed
- **Section 5: Parts** — Inventory summary (GL 242/243/244) and monthly analysis with turnover color-coding (red <1.0, yellow <2.0)
- **Section 6: Receivables** — Aging table per type with color-coded non-zero aging buckets
- **Section 7: F&I Chargebacks** — Over-90 balances highlighted in red
- **Section 8: Contracts in Transit** — Color-coded by days (red >14, yellow >7)
- **Section 9: Operations** — Open ROs, missing titles, slow-to-accounting deals

Footer on every page: page number, store/date identifier, generation timestamp (CT), CONFIDENTIAL marker.

### Flagged Items Report (`generators/flagged_items_report.py`)
A separate PDF listing ONLY items requiring a response. This is what managers must answer within 24 hours (Phase 2 accountability). Structure:
- **Header** — "FLAGGED ITEMS — ACTION REQUIRED", store name, meeting date, 24-hour deadline
- **Red Flags Section** — Escalated items with category label, flag message, value/threshold, blank response line and manager/date fields
- **Yellow Flags Section** — Warning items in same format
- **Summary Footer** — Total red/yellow counts, submission deadline, auto-escalation notice

## Flagging Engine

The flagging engine (`app/flagging/`) evaluates parsed meeting data against configurable rules to generate yellow (warning) and red (escalate) flags.

**FlagRule** (`flagging/rules.py`) — Dataclass defining a rule: category, model, field, thresholds, comparison type, and message template. 15 default rules stored in `DEFAULT_RULES`.

**FlaggingEngine** (`flagging/engine.py`) — Queries parsed records per meeting, evaluates each against enabled rules, and produces `Flag` model instances. Red threshold is checked first to avoid double-flagging.

### Rules (15 total)

| # | Rule | Model | Field | Yellow | Red | Comparison |
|---|------|-------|-------|--------|-----|------------|
| 1 | Used Vehicle Age | UsedVehicleInventory | days_in_stock | >60 | >90 | gt |
| 2 | New Vehicle Age | NewVehicleInventory | days_in_stock | >90 | >120 | gt |
| 3 | Service Loaner Days | ServiceLoaner | days_in_service | >60 | >90 | gt |
| 4 | Service Loaner Neg Equity | ServiceLoaner | negative_equity | >$30K | >$50K | gt |
| 5 | Floorplan Variance | FloorplanReconciliation | variance | abs>$100 | abs>$1K | abs_gt |
| 6 | Receivable Over 30 | Receivable | over_30 | >$0 | — | any_gt |
| 7 | Receivable Over 60 | Receivable | over_60 | — | >$0 | any_gt |
| 8 | F&I Chargeback Current | FIChargeback | current_balance | >$0 | — | any_gt |
| 9 | F&I Chargeback Over 90 | FIChargeback | over_90_balance | — | >$0 | any_gt |
| 10 | Contract In Transit Age | ContractInTransit | days_in_transit | >7 | >14 | gt |
| 11 | Missing Title | MissingTitle | days_missing | >=0 | >=14 | gte |
| 12 | Open RO Age | OpenRepairOrder | days_open | >14 | >30 | gt |
| 13 | Slow To Accounting | SlowToAccounting | days_to_accounting | >5 | >10 | gt |
| 14 | Parts True Turnover | PartsAnalysis | true_turnover | <2.0 | <1.0 | lt |
| 15 | Parts Obsolete Value | PartsAnalysis | obsolete_value | >$500 | >$2K | gt |

Comparison types: `gt` (greater than), `lt` (less than — lower is worse), `gte` (greater or equal), `any_gt` (any amount > 0), `abs_gt` (absolute value exceeds threshold).

## API Endpoints

All routes are prefixed with `/api/v1`. Health check is at root `/health`.

### Upload
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/upload` | Upload a single R&R report PDF for processing |
| POST | `/api/v1/upload/bulk` | Upload multiple PDFs for the same meeting |

### Packets
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/packets/{meeting_id}` | Download the generated packet PDF |
| GET | `/api/v1/packets/{meeting_id}/flagged-items` | Download the flagged items report PDF |
| GET | `/api/v1/packets/{meeting_id}/summary` | Get JSON summary of meeting data and flags |

### Flags
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/flags/{meeting_id}` | Get flags with optional severity/category/status filters |
| GET | `/api/v1/flags/{meeting_id}/stats` | Get flag statistics (counts by severity, status, category) |
| PATCH | `/api/v1/flags/{flag_id}/respond` | Submit a response to a flagged item |

### Stores
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/stores` | List all active stores |
| GET | `/api/v1/stores/{store_id}` | Get store details with recent meetings |
| POST | `/api/v1/stores` | Create a new store |
| GET | `/api/v1/stores/{store_id}/meetings` | Get recent meetings for a store |

### Meetings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/meetings/{meeting_id}` | Get meeting details |
| GET | `/api/v1/meetings/{meeting_id}/data/{category}` | Get parsed data by category (inventory/parts/financial/operations) |

## Phase 1 Deliverables

- [x] PostgreSQL data models for all report categories
- [x] PDF parser framework with category-specific parsers (inventory, parts, financial, operations)
- [x] Configurable flagging engine with initial rule set
- [x] Standardized PDF packet generator (9 sections, color-coded tables, footers)
- [x] Flagged items report generator (red/yellow sections, response lines, 24-hour deadline)
- [x] Upload API endpoints (18 endpoints, 5 route modules, Pydantic schemas)
- [x] Simple upload web UI (vanilla HTML/JS served by FastAPI)
- [x] Test against Ashdown reference packet (66 integration tests, all passing)
- [x] Floorplan reconciliation (Schedule 237 vs 231/310 variance)
- [x] Flagging engine validation against parsed Ashdown data (15 tests)
- [x] Output PDF generation (packet + flagged items report)

## Quick Start

```bash
# 1. Start PostgreSQL
docker compose up -d db

# 2. Set up backend
cd backend
python3 -m pip install -r requirements.txt
alembic upgrade head

# 3. Run the server
uvicorn app.main:app --reload

# 4. Open the UI
open http://localhost:8000
```

Or with Docker Compose:

```bash
docker compose up -d
# Open http://localhost:8000
```

The upload UI lets you:
1. Create/select a store
2. Upload R&R report PDFs (drag-and-drop or file picker)
3. View processing results (records parsed, flags generated)
4. Download the standardized packet and flagged items report PDFs
5. Review flagged items with severity/category filters

## Setup (Development)

```bash
# Copy environment file
cp .env.example .env

# Start services
docker compose up -d

# Run migrations
cd backend && alembic upgrade head

# Run tests
cd backend && python3 -m pytest tests/ -v
```

## Tested Against

**Ashdown Classic Chevrolet** — 27-page scanned reference packet (02/11/2026):
- 52 new vehicles, 60 used vehicles, 4 service loaners
- 4 contracts in transit, 4 F&I chargebacks, 2 receivables, 2 policy adjustments
- 58 open repair orders, 16 warranty claims, 3 missing titles, 2 slow-to-accounting
- 3 parts analysis records, 2 floorplan reconciliations
- 54 flags generated (34 red, 20 yellow)
- Both output PDFs (packet + flagged items report) generated successfully

## Current Status

**Phase 1 COMPLETE — Tested against Ashdown Classic Chevrolet reference packet (27 pages, 02/11/2026).** Full data pipeline with REST API and upload UI. 16 models, 4 parsers (with OCR support), 15 flagging rules, 2 PDF generators, 18 API endpoints, upload web UI. 308 tests passing (242 unit + 66 integration).

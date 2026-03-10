# GOAC Asset Meeting Manager

Automate, standardize, and enforce accountability for asset/receivable meetings across all Gregg Orr Auto Collection dealership locations.

## Roadmap

### Phase 1: Packet Generator + Flagging *(COMPLETE)*
Parse R&R DMS exports (PDF schedules, GL reports) into structured data. Apply configurable flagging rules to surface issues. Generate standardized meeting packets and flagged-item reports.

### Phase 2: Accountability Web App *(COMPLETE)*
Web interface for meeting scheduling, packet review, flag responses, and escalation tracking. Google OAuth authentication with role-based access (corporate/gm/manager). Next.js frontend with corporate dashboard, store detail, and meeting detail pages. Email notifications via SendGrid. Full RBAC on all API routes.

### Phase 3: Full Automation
Automated DMS export ingestion, trend analysis, cross-store benchmarking, and executive dashboards.

## Tech Stack

- **Backend**: FastAPI (Python) + PostgreSQL + SQLAlchemy + Alembic
- **Frontend**: Next.js 14 (App Router) + NextAuth + Tailwind CSS
- **Auth**: Google OAuth via NextAuth → backend JWT
- **APIs**: Google Calendar API, SendGrid/Postmark
- **Data Sources**: R&R DMS PDF exports

## Data Models

21 models across 9 model files. All models use UUID primary keys, timezone-aware timestamps, and indexes on `store_id`/`meeting_id`.

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

### Users & Auth (`user.py`)
| Model | Table | Description |
|-------|-------|-------------|
| User | `users` | Users with Google OAuth, roles, and login tracking |
| UserStore | `user_stores` | Store access associations for GMs and managers |

### Accountability (`accountability.py`)
| Model | Table | Description |
|-------|-------|-------------|
| FlagAssignment | `flag_assignments` | Assign flags to users with deadlines |
| FlagResponseRecord | `flag_responses` | Individual responses to assigned flags |
| Notification | `notifications` | In-app and email notifications |
| MeetingAttendance | `meeting_attendance` | Track who attended each meeting |

### Enums
- `MeetingStatus`: pending, processing, completed, error
- `ReconciliationType`: new_237, used_240
- `PartsCategory`: parts_242, tires_243, gas_oil_grease_244
- `ReceivableType`: parts_service_200, wholesale_220, factory_2612
- `FlagCategory`: inventory, parts, financial, operations
- `FlagSeverity`: yellow, red
- `FlagStatus`: open, responded, escalated
- `UserRole`: corporate, gm, manager, viewer
- `AssignmentStatus`: pending, acknowledged, responded, overdue, escalated
- `NotificationType`: flag_assigned, deadline_reminder, overdue_notice, escalation, response_received

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

## Email Notifications (SendGrid)

The system sends transactional emails for accountability events:

| Email Type | Trigger | Recipients |
|-----------|---------|------------|
| Flag Assigned | Auto-assign or manual assign | Assigned manager |
| Deadline Reminder | 6 hours before deadline (hourly check) | Assigned manager |
| Overdue Notice | Daily at 7 AM CT | Assigned manager |
| Escalation | Daily at 7 AM CT (when overdue flags exist) | Corporate users |
| Response Received | Manager submits flag response | Corporate users |
| Packet Ready | Meeting packet generated | Store GM |
| Daily Digest | 7:30 AM CT Mon-Fri | Corporate users |

### SendGrid DNS Setup

To enable email delivery, configure these DNS records on your sending domain:

1. **SPF**: Add `include:sendgrid.net` to your domain's SPF record
2. **DKIM**: Add the two CNAME records from SendGrid's Sender Authentication dashboard
3. **DMARC**: Add a DMARC policy record (e.g., `v=DMARC1; p=none;`)

### Environment Variables

```bash
SENDGRID_API_KEY=SG.your_api_key_here    # Required for sending; emails logged when empty
NOTIFICATION_ENABLED=true                  # Master switch for all notifications
```

### Graceful Degradation

When `SENDGRID_API_KEY` is not set, the email service logs all emails that *would* have been sent and returns success. This enables local development and testing without a SendGrid account. Email failures never crash the processing pipeline.

## API Endpoints

All routes are prefixed with `/api/v1`. Health check is at root `/health`.

All routes require JWT authentication unless noted. Access is scoped by role: **corporate** (all stores), **gm** (their stores), **manager** (their stores, read-only, own flags only).

### Auth (Public)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/callback` | Google OAuth callback — creates/updates user, returns JWT |
| GET | `/api/v1/auth/me` | Get current user profile (requires JWT) |

### Upload (Corporate + GM)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/upload` | Upload a single R&R report PDF. GM: own stores only |
| POST | `/api/v1/upload/bulk` | Upload multiple PDFs for the same meeting |

### Packets (Authenticated, store-scoped)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/packets/{meeting_id}` | Download the generated packet PDF |
| GET | `/api/v1/packets/{meeting_id}/flagged-items` | Download the flagged items report PDF |
| GET | `/api/v1/packets/{meeting_id}/summary` | Get JSON summary of meeting data and flags |

### Flags (Authenticated, store-scoped)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/flags/{meeting_id}` | Get flags (manager: only assigned flags) |
| GET | `/api/v1/flags/{meeting_id}/stats` | Get flag statistics |
| PATCH | `/api/v1/flags/{flag_id}/respond` | Submit a response to a flagged item |
| POST | `/api/v1/flags/{flag_id}/assign` | Assign flag to user (corporate + GM only) |
| POST | `/api/v1/flags/{flag_id}/respond-workflow` | Submit response (assigned user or corporate) |
| POST | `/api/v1/flags/{flag_id}/escalate` | Escalate flag (corporate + GM only) |
| GET | `/api/v1/flags/my/assigned` | Get flags assigned to current user |
| GET | `/api/v1/flags/overdue/all` | Get overdue flags (scoped by role) |
| POST | `/api/v1/meetings/{meeting_id}/auto-assign` | Auto-assign flags (corporate + GM only) |

### Stores (Authenticated, store-scoped)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/stores` | List stores (filtered by role) |
| GET | `/api/v1/stores/{store_id}` | Get store details |
| POST | `/api/v1/stores` | Create a new store (corporate only) |
| GET | `/api/v1/stores/{store_id}/meetings` | Get recent meetings for a store |
| GET | `/api/v1/stores/{store_id}/flag-trends` | Get flag trend data (last 6 meetings) |

### Meetings (Authenticated, store-scoped)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/meetings/{meeting_id}` | Get meeting details |
| GET | `/api/v1/meetings/{meeting_id}/data/{category}` | Get parsed data by category |
| GET | `/api/v1/meetings/{meeting_id}/flags` | Get flags with filters and sorting |

### Dashboard (Authenticated, store-scoped)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dashboard` | Aggregated overview (filtered by role) |

### Notifications (Authenticated, own only)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/notifications` | Get current user's notifications |
| PATCH | `/api/v1/notifications/{notification_id}/read` | Mark a notification as read |
| POST | `/api/v1/notifications/read-all` | Mark all notifications as read |
| GET | `/api/v1/notifications/unread-count` | Get unread notification count |

## Deployment

Deployed to **assetmeeting.goac.io** on an existing Hetzner VPS (5.161.71.87) running Ubuntu 24.04. The server uses **Traefik v2.11** as a shared reverse proxy with automatic HTTPS via Let's Encrypt. Other apps on the same server (greggorr.com, ctrl.goac.io, ocrmypdf.goac.io) all share Traefik. Apps are deployed to `/opt/{project-name}/`.

### Prerequisites
- **Server**: Hetzner VPS with Docker, Traefik, and the `web` Docker network already configured
- **Domain**: DNS A record for `assetmeeting.goac.io` pointing to server IP
- **Google OAuth**: Credentials configured for assetmeeting.goac.io
- **SendGrid API key** (optional — emails are logged when not set)

### Architecture
- **Traefik** (shared, already running) handles HTTPS termination and routing via Docker labels
- **api** container: `/api/*` routes → FastAPI on port 8000 (priority 2)
- **frontend** container: all other routes → Next.js on port 3000 (priority 1)
- **db** container: PostgreSQL 16 (internal network only, no host port)
- **backup** container: daily pg_dump with 7-day retention
- 2GB swap configured as safety net for OCR memory spikes

### First-Time Setup

```bash
# 1. Run server setup (as root)
scp deploy/setup-server.sh root@5.161.71.87:/tmp/
ssh root@5.161.71.87 'bash /tmp/setup-server.sh'

# 2. SSH as deploy user
ssh deploy@5.161.71.87

# 3. Configure environment
cd /opt/assetmeetinghelper
nano .env  # Fill in all secrets

# 4. Start services
docker compose -f docker-compose.prod.yml up -d

# 5. Run database migrations
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

Traefik automatically provisions HTTPS via Let's Encrypt — just ensure the DNS A record for `assetmeeting.goac.io` points to the server.

### Ongoing Deploys

Push to `main` triggers GitHub Actions: runs tests → deploys via SSH.

Manual deploy: `ssh deploy@5.161.71.87 'bash /opt/assetmeetinghelper/deploy/deploy.sh'`

### Useful Commands

```bash
# View logs (all services or specific)
deploy/logs.sh
deploy/logs.sh api

# Run migrations
deploy/migrate.sh

# Manual backup
deploy/backup-now.sh

# Restore from backup
deploy/restore.sh backups/backup_20260309_120000.sql.gz
```

### GitHub Actions Secrets

Set these in your repo's Settings → Secrets:
- `DEPLOY_HOST` — `5.161.71.87`
- `DEPLOY_USER` — `deploy`
- `DEPLOY_SSH_KEY` — Private SSH key for deploy user
- `DEPLOY_PORT` — SSH port (default 22)

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

**Phase 1 COMPLETE.** Full data pipeline with REST API and upload UI. 16 models, 4 parsers (with OCR support), 15 flagging rules, 2 PDF generators, 18 API endpoints, upload web UI. 308 tests passing (242 unit + 66 integration).

**Phase 2 COMPLETE.** Auth system (Google OAuth + JWT), role-based access control (corporate/gm/manager) on all routes, 6 accountability models (incl. UserStore), corporate dashboard, store/meeting detail pages, flag response workflow, email notifications (SendGrid), automated reminders/escalation, in-app notification center. 25 API endpoints, Next.js frontend with NextAuth. 455 tests passing.

**Deployment Infrastructure READY.** Production Docker Compose with Traefik (auto-HTTPS via existing reverse proxy), GitHub Actions CI/CD (test → deploy), automated daily backups with 7-day retention. Deployed to assetmeeting.goac.io on Hetzner VPS at /opt/assetmeetinghelper/.

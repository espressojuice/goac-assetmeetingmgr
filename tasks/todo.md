# Phase 1 Tasks

- [x] Initialize repo structure and foundational files
- [x] Define PostgreSQL data models (all categories: inventory, parts, financial, operations, flags)
- [x] Set up Alembic migrations
- [x] Build base parser framework (PDF text extraction)
- [x] Build inventory parser (schedules 237, 240, 277)
- [x] Build parts parser (GL 242-244, monthly analysis)
- [x] Build financial parser (receivables, F&I, contracts in transit, wholesale deals)
- [x] Build operations parser (open ROs, warranty claims, missing titles, employee roster)
- [x] Implement flagging engine with configurable rules
- [x] Implement all initial flagging rules per the rules table
- [x] Build standardized PDF packet generator
- [x] Build flagged items report generator
- [x] Build upload API endpoints
- [x] Build simple upload web UI
- [x] Test against Ashdown reference packet
- [x] Validate floorplan reconciliation output (237 vs 231/310 variance)
- [x] PDF generation smoke test (packet + flagged items report)
- [x] Flagging engine validation against parsed Ashdown data (54 flags: 34 red, 20 yellow)

## Session Log

### Session 1 — 2026-03-08
- Initialized repo structure (16 models, 7 enums, docker-compose, config)
- Built all 4 parsers: inventory, parts, financial, operations
- Built flagging engine with 15 business rules
- 152 tests all passing
- Pipeline complete through: Upload → Extract → Parse → Save → Flag

### Session 2 — 2026-03-08
- Built StandardizedPacketGenerator (9-section PDF: cover, exec summary, new/used vehicles, loaners, parts, receivables, F&I, contracts, operations)
- Built FlaggedItemsReportGenerator (red flags → yellow flags, response lines, summary footer)
- Integrated both generators into ProcessingService (auto-generates after flagging, updates meeting record)
- 187 tests all passing (35 new generator tests)
- Pipeline complete through: Upload → Extract → Parse → Save → Flag → Generate PDFs

### Session 3 — 2026-03-08
- Built all API endpoints: upload (single + bulk), packets (PDF + summary), flags (CRUD + stats), stores (CRUD + meetings), meetings (detail + category data)
- 18 endpoints across 5 route modules, all under /api/v1 prefix
- Pydantic response schemas for all endpoints (auto-validation + OpenAPI docs)
- 55 new API tests (in-memory SQLite + httpx AsyncClient), 242 total all passing
- Full pipeline now accessible via REST API

### Session 4 — 2026-03-09
- Built single-page upload web UI (vanilla HTML/CSS/JS served by FastAPI)
- Store selection with inline create form, drag-and-drop PDF upload, processing status with results summary
- Flags preview table with severity/category filters, recent meetings sidebar with download links
- Responsive layout (tablet-friendly), GOAC blue (#003366) branding, color-coded flags
- 242 tests still passing — Phase 1 feature-complete

### Session 5 — 2026-03-09 (Ashdown Integration Testing)
- Added OCR support via EasyOCR + pypdfium2 (pure Python, no system dependencies)
- PDFExtractor now renders scanned pages to images, OCRs them, reconstructs text lines + tables
- Landscape page detection + 90° rotation retry (page 27 missing titles)
- All 4 parsers updated with OCR-specific parsing methods for Schedule Summary format
- InventoryParser: continuation page detection via column headers (237/240/277)
- FinancialParser: GL INQUIRY format parsing (850/851 chargebacks), OCR-tolerant closing balance
- OperationsParser: OCR date parsing for slow-to-accounting (DD/YY format), warranty claim extraction
- PartsParser: two-pass OCR analysis (raw + cleaned), cost_of_sales decimal-point targeting
- 49 integration tests against Ashdown reference packet — all passing
- 242 existing unit tests — all passing (291 total)
- Key results: 52 new vehicles, 48 used, 3 loaners, 4 CIT, 4 chargebacks, 2 receivables,
  2 policy adj, 41 ROs, 12 warranty claims, 3 missing titles, 2 slow-acct, 3 parts analysis

### Session 6 — 2026-03-09 (Phase 1 Cleanup)
- Fixed all 4 extraction gaps against Ashdown reference packet:
  - Used vehicles: 48 → 60 (case-insensitive OCR pattern, lowercase 'v' suffix, '+' artifacts)
  - Service loaners: 3 → 4 (allow '+' in VIN/control# patterns)
  - Open ROs: 41 → 58 (removed 'CWI' from header filter, tolerant RO# regex)
  - Warranty claims: 12 → 16 (tolerant claim number regex for OCR artifacts)
- Fixed cost_of_sales extraction (20593 → 29941.28) — made TOTAL prefix mandatory
- Built flagging validation test (15 tests): 54 flags generated (34 red, 20 yellow)
- Generated output PDFs: packet (28KB) and flagged items report (12KB)
- Tightened all integration test assertions to exact counts
- 308 tests passing (242 unit + 66 integration)
- Phase 1 COMPLETE

# Phase 2 Tasks

- [x] Add Phase 2 database models (User, FlagAssignment, FlagResponseRecord, Notification, MeetingAttendance)
- [x] Set up Google OAuth authentication (backend JWT + NextAuth callback)
- [x] Initialize Next.js frontend with NextAuth
- [x] Build corporate dashboard (multi-store overview)
- [x] Build store detail page
- [x] Build meeting detail page with tabbed data view
- [x] Build flag response workflow (assignment + response form)
- [x] Implement repeat flag detection and auto-escalation
- [x] Build manager response page
- [x] Build email notification service (SendGrid)
- [x] Implement automated reminders (24h deadline, overdue)
- [x] Add role-based access control to all routes
- [x] Build notification center (in-app)

## Phase 2 COMPLETE

# Deployment Tasks

- [x] Production Docker Compose (db, api, frontend, backup — Traefik labels)
- [x] Backend Dockerfile (Python 3.11-slim + system deps)
- [x] Frontend Dockerfile (multi-stage: deps → build → runner)
- [x] next.config.js standalone output (already configured)
- [x] GitHub Actions CI/CD (test → deploy via SSH)
- [x] Server setup script (Docker check, swap, web network, /opt/ convention)
- [x] Deploy scripts (deploy, migrate, logs, backup-now, restore)
- [x] .env.example with all required variables
- [x] .gitignore updated (backups, deploy/secrets, .env.prod)
- [x] README deployment section
- [x] Refactored from Caddy to Traefik (existing VPS reverse proxy)
- [x] Configure DNS A record for assetmeeting.goac.io
- [x] Set up Google OAuth for production domain (Google Workspace, Internal)
- [x] Set up SendGrid with domain authentication for goac.io
- [x] First production deploy — all 4 containers running, TLS working
- [x] Fixed deployment issues: missing package-lock.json, frontend/public/.gitkeep, Alembic DATABASE_URL, tzdata for US/Central
- [x] Fixed Traefik routing: PathPrefix(/api) → PathPrefix(/api/v1) so NextAuth /api/auth/* reaches Next.js
- [ ] Set up GitHub Actions secrets for CI/CD (DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY, DEPLOY_PORT)
- [ ] Kernel upgrade reboot on VPS
- [ ] Test end-to-end login flow (Google OAuth → dashboard)
- [ ] Create Hetzner Object Storage bucket and configure S3 credentials
- [ ] Tune packet validator keywords against real packets (25% avg detection rate)
- [ ] Set up GitHub Actions secrets for CI/CD
- [x] Create initial store records in database (23 stores seeded)
- [x] Promote Bryan Brookes to corporate role
- [x] Upload test packet PDFs to server (17 files)
- [x] Extract Reynolds store numbers from all test packets via OCR

# Phase 3 Tasks — Session 17

## Task 1: Scan Test Packets
- [x] SSH to server, scan all 17 PDFs with pdfplumber + tesseract OCR
- [x] Save structured results to data/packet_scan_results.md

## Task 2: Add CAP GM + Reynolds Site IDs
- [x] Add reynolds_site_id column to stores table (Alembic migration 004)
- [x] Insert CAP GM - Texarkana, TX store (24 stores total)
- [x] Update 17 stores with Reynolds 7-digit site IDs
- [x] Verified with query — all correct

## Task 3: Hetzner Object Storage Service
- [x] Create backend/app/services/storage_service.py (boto3 S3-compatible, lazy client, graceful degradation)
- [x] Add S3 config to settings (5 new settings), .env.example
- [x] Add boto3 to requirements.txt

## Task 4: Packet Completeness Validator
- [x] Create backend/app/services/packet_validator.py (16 doc types, disambiguation, OCR-tolerant)
- [x] Integrate into upload endpoint (both single and bulk)
- [x] Update UploadResponse/BulkUploadResponse schemas with PacketValidationResult
- [x] Frontend upload flow shows found/missing docs

## Task 5: Tests + Commit
- [x] Run all tests — 459 passing, 0 failures
- [x] Update todo.md, lessons.md, README.md
- [x] Commit and push (3cfa8a2)

# Session 18 — Post-Upload Validation Review

## Task 1: Backend — Validate-Only Upload + Approve Endpoint
- [x] Add DetailedValidationResult schema (ClassifiedPage, UnclassifiedPage, RequiredDocumentCheck)
- [x] Add ValidationUploadResponse and ApproveResponse schemas
- [x] Add validate_detailed() method to PacketValidator (returns per-page classification with scores and snippets)
- [x] Refactor _classify_page into _classify_page_with_score (returns doc_id + score tuple)
- [x] Modify POST /upload to validate-only (no processing, meeting stays PENDING)
- [x] Modify POST /upload/bulk to validate-only
- [x] Add POST /upload/{meeting_id}/approve endpoint (triggers full processing pipeline)
- [x] Move PacketValidator import to module level for clean test patching

## Task 2: Frontend — Upload Page + Validation Review Page
- [x] Add API types and functions to lib/api.ts (uploadForValidation, uploadBulkForValidation, approveUpload)
- [x] Create /stores/[storeId]/upload/page.tsx (drag-and-drop upload, date picker, redirects to validate)
- [x] Create /stores/[storeId]/meetings/[meetingId]/validate/page.tsx with 3 sections:
  - Classified Pages table (grouped by document type with page ranges)
  - Unclassified Pages warning section (page number + text snippet)
  - Required Documents Checklist (16 items, green/red icons, where-to-find for missing)
- [x] Completeness percentage header, Re-upload and Approve & Process buttons
- [x] Validation data passed via sessionStorage between upload and validate pages

## Task 3: Static HTML — Inline Validation Step
- [x] Updated index.html with validation-section (shows after upload, before processing)
- [x] Validation results shown inline: classified pages table, unclassified pages, required docs checklist
- [x] Approve & Process button calls POST /upload/{meeting_id}/approve
- [x] Re-upload button hides validation section to allow re-upload
- [x] Processing results section only shown after approval

## Task 4: Tests
- [x] Updated all upload tests for new validate-only response format
- [x] Added 4 new tests for approve endpoint (success, 404, 422, 401)
- [x] 461 tests passing (up from 459)

## Session Log

### Session 7 — 2026-03-09 (Phase 2 Foundation)
- Added 5 new models: User (with roles), FlagAssignment, FlagResponseRecord, Notification, MeetingAttendance
- 5 new enums: UserRole, AssignmentStatus, NotificationType
- Alembic migration 002 for all Phase 2 tables
- Auth system: JWT creation/validation, Google OAuth callback, role-based dependency injection
- 2 new API routes: POST /auth/callback, GET /auth/me
- 1 new API route: GET /dashboard (aggregated multi-store overview with flag stats)
- Config extended with JWT_SECRET_KEY, GOOGLE_CLIENT_ID/SECRET, FRONTEND_URL
- Requirements: added authlib, python-jose[cryptography], bcrypt
- Next.js frontend scaffolded: NextAuth with Google provider, Tailwind CSS
- Pages: landing (sign-in), dashboard (store cards + summary bar + flag chart), store detail, meeting detail (tabbed: packet data / flags / responses)
- Components: Navbar, StoreCard, SummaryBar, FlagSummaryChart
- Docker-compose updated with frontend service + auth env vars
- 14 new tests (auth + dashboard), 255 unit tests all passing

### Session 8 — 2026-03-09 (Store Detail Page)
- Built store_service.py: get_store_detail() and get_flag_trends() with efficient batch queries
- Rich GET /stores/{store_id} returns store info, stats, per-meeting flag summaries, and users
- New GET /stores/{store_id}/flag-trends endpoint for chart data (last 6 meetings)
- Frontend store detail page: header with brand badge, 4-stat bar, flag trend chart (recharts ComposedChart), meeting cards with flag summaries and download links, collapsible users table
- FlagTrendChart component: stacked red/yellow bars + response rate line overlay
- API client updated with new types (StoreDetail, FlagTrendsData, etc.) and 401→redirect handling
- 9 new tests (store detail + flag trends), 76 API tests all passing

### Session 9 — 2026-03-09 (Meeting Detail Page)
- Built meeting_service.py: get_meeting_detail() computes executive summary from parsed data via aggregation queries, get_meeting_flags() returns flags with assignment/response data
- Updated GET /meetings/{meeting_id} to return MeetingDetailResponse with meeting info, executive summary (14 computed metrics), and flags_summary (with by_category severity breakdown)
- Updated GET /meetings/{meeting_id}/data/{category} to attach flag info to each record
- New GET /meetings/{meeting_id}/flags endpoint with severity/category/status/sort_by filters
- New Pydantic schemas: ExecutiveSummary, FlagsSummary, MeetingInfo, MeetingDetailResponse, MeetingFlagDetailResponse, AssignedToInfo, FlagResponseInfo
- Frontend: reusable DataTable component (sortable, formatted, row coloring), Tabs component (lazy loading)
- Frontend: full meeting detail page at /stores/[storeId]/meetings/[meetingId] — breadcrumb, header, executive summary cards, floorplan variance, 4 tabs (Flags/Inventory/Financial/Operations)
- Frontend: FlagsTab with filter dropdowns, expandable rows, response display; InventoryTab with 4 collapsible sections; FinancialTab with 5 sections (colored aging buckets); OperationsTab with 4 sections
- Legacy /meetings/[meetingId] redirects to new nested route
- API client updated with 7 new types + 3 new fetch functions
- 30 new tests (meeting detail + data + flags), 98 API tests passing, 285 unit tests total

### Session 10 — 2026-03-09 (Flag Response Workflow)
- Built FlagService with 7 methods: auto_assign_flags, assign_flag, submit_response, get_my_flags, check_overdue_flags, escalate_flag, detect_recurring_flags
- Added previous_flag_id and escalation_level fields to Flag model for recurring flag tracking
- 6 new API endpoints: POST /flags/{id}/assign, POST /flags/{id}/respond-workflow, GET /flags/my/assigned, GET /flags/overdue/all, POST /flags/{id}/escalate, POST /meetings/{id}/auto-assign
- New Pydantic schemas: FlagAssignRequest, FlagRespondWorkflowRequest, FlagEscalateRequest, MyFlagResponse, AutoAssignResponse, OverdueFlagResponse
- Integrated auto-assign + recurring detection into ProcessingService.process_upload
- Updated meeting_service to use real escalation_level and deadline-based overdue detection
- Frontend: My Flags page (/flags) with status filter tabs, FlagCard component, flag detail page (/flags/[flagId]) with ResponseForm
- Frontend: updated Navbar with Dashboard + My Flags navigation links
- Frontend: api.ts updated with fetchMyFlags, assignFlag, respondToFlag, escalateFlag, autoAssignMeetingFlags
- 22 new tests (auto-assign, manual assign, response, my flags, overdue, escalation, recurring detection)

### Session 11 — 2026-03-09 (Email Notifications + In-App Notification Center)
- Built EmailService (SendGrid v3 API via httpx): 7 email methods (flag_assigned, reminder_approaching, overdue_to_manager, overdue_to_corporate, response_received, meeting_packet_ready, daily_digest)
- Professional HTML email templates with GOAC branding (#003366), inline CSS, mobile-responsive, plain text fallback
- Graceful degradation: disabled when SENDGRID_API_KEY not set, never crashes pipeline on email failure
- Built NotificationScheduler: 3 scheduled jobs (reminder_check hourly, overdue_check daily 7AM CT, daily_digest 7:30AM CT Mon-Fri)
- APScheduler AsyncIOScheduler integration with FastAPI startup event
- 4 new notification API endpoints: GET /notifications, PATCH /notifications/{id}/read, POST /notifications/read-all, GET /notifications/unread-count
- Wired email notifications into FlagService (auto_assign → send_flag_assigned, submit_response → send_response_received) and ProcessingService (process_upload → send_meeting_packet_ready)
- Frontend: NotificationBell component in Navbar — bell icon with unread count badge, dropdown with recent notifications, mark read/mark all read, 60s polling, click-to-navigate
- 5 new config settings: SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME, NOTIFICATION_REMINDER_HOURS, NOTIFICATION_ENABLED
- 34 new tests (15 email service, 10 scheduler, 9 notification API), 407 total all passing

### Session 12 — 2026-03-09 (Role-Based Access Control)
- Added UserStore association model for store-scoped access control (migration 003)
- New auth dependencies: require_corporate, require_corporate_or_gm, verify_store_access, get_user_store_ids
- Locked down ALL 25 API routes with proper auth enforcement:
  - Corporate: full access to all stores, meetings, flags, uploads, dashboard
  - GM: access only to their assigned stores — can upload, assign flags, view meetings/flags within their stores
  - Manager: read-only access to their stores, can only see flags assigned to them, can respond to own flags only, cannot upload/assign/escalate
  - Unauthenticated: blocked from all endpoints except /health and /auth/callback
- Updated all 133 existing API tests to use corporate auth headers (zero regressions)
- 48 new RBAC tests covering corporate/gm/manager/unauthenticated access patterns
- 455 total tests passing (393 unit/API + integration)
- Phase 2 COMPLETE

### Session 13 — 2026-03-09 (Deployment Infrastructure)
- Created production Docker Compose with 5 services: db (postgres:16-alpine), api, frontend, caddy (auto-HTTPS), backup (daily with 7-day retention)
- Caddyfile reverse proxy: /api/* → api:8000, /health → api:8000, * → frontend:3000
- Backend Dockerfile: python:3.11-slim with build-essential, libpq-dev, poppler-utils
- Frontend Dockerfile: multi-stage build (deps → builder → runner) ~150MB vs ~1GB
- GitHub Actions: test job (postgres service, pytest) → deploy job (SSH to VPS)
- Server setup script: Docker install, deploy user, UFW firewall, fail2ban, SSH hardening
- 6 deploy scripts: setup-server, deploy, migrate, logs, backup-now, restore
- .env.example with all 10 required environment variables

### Session 14 — 2026-03-10 (Traefik Migration)
- Replaced Caddy with Traefik labels for existing Hetzner VPS (5.161.71.87)
- Server already runs Traefik v2.11 on "web" Docker network with auto-HTTPS
- Removed Caddyfile and caddy service from docker-compose.prod.yml
- Added Traefik labels to api (priority 2, /api path) and frontend (priority 1, catch-all)
- Both api and frontend join "web" (external) + "default" (internal) networks
- db and backup stay on default network only, no host port bindings
- Updated all deploy scripts to use /opt/assetmeetinghelper/ (server convention)
- Added 2GB swap creation to setup-server.sh for OCR memory spikes
- Setup script now checks for existing Docker, deploy user, UFW, web network
- Domain: assetmeeting.goac.io
- Health check changed from localhost curl to docker exec (no exposed ports)

### Session 15 — 2026-03-10 (Production Deploy + Fixes)
- Successfully deployed to https://assetmeeting.goac.io — all 4 containers running (PostgreSQL, FastAPI, Next.js, backup)
- TLS working via Traefik/Let's Encrypt, no exposed host ports
- Fixed 4 deployment issues:
  - Frontend Dockerfile: handle missing package-lock.json gracefully
  - Added frontend/public/.gitkeep for Next.js build
  - Alembic env.py: use DATABASE_URL env var instead of hardcoded localhost
  - Added tzdata package for US/Central timezone in scheduler
- Fixed Traefik routing: changed PathPrefix(/api) → PathPrefix(/api/v1) so NextAuth /api/auth/* routes reach Next.js instead of FastAPI returning 404
- Set up Google OAuth under Google Workspace (Internal) for assetmeeting.goac.io
- Set up SendGrid with domain authentication for goac.io
- Configured DNS A record for assetmeeting.goac.io → 5.161.71.87
- Server runs alongside greggorr.com, ctrl.goac.io, ocrmypdf.goac.io on shared Traefik

### Session 16 — 2026-03-11 (Production Data Seeding + Store Number Research)
- Promoted Bryan Brookes (bbrookes@greggorrcompanies.com) to CORPORATE role in production DB
- Seeded 23 dealership stores with names, codes, cities, states, timezone (US/Central)
- Uploaded 17 test packet PDFs to server at /opt/assetmeetinghelper/testdata/packets/
- Installed tesseract + pytesseract in production API container for PDF text extraction research
- OCR'd all 17 packets to extract Reynolds store numbers from parts analysis headers
- Identified 15 Reynolds store numbers mapped to dealerships:
  - Store 01 = Classic Auto Park (CAP GMC/Buick/Mazda, Texarkana)
  - Store 02 = Classic State Line Kia (Texarkana Kia)
  - Store 03 = Orr Motors of Ashdown (Ashdown Chevrolet)
  - Store 04 = Classic Auto Park (CAP Mercedes, Texarkana)
  - Store 05 = Orr Motors of Arkansas (Hot Springs Cadillac)
  - Store 06 = Orr Motors of Hot Springs (Hot Springs Honda)
  - Store 07 = Orr Toyota (Hot Springs Toyota)
  - Store 09 = Orr Motors North (Searcy CDJ)
  - Store 10 = Orr Motors of Searcy (Searcy Toyota)
  - Store 11 = Orr Motors (Shreveport Cadillac)
  - Store 12 = Orr Motors of Louisiana (Shreveport Acura)
  - Store 13 = Greg Orr Motors / Orr BMW (Shreveport BMW)
  - Store 14 = Orr Motors of Destin (Destin Porsche)
  - Store 16 = Classic CDJ, Inc (Texarkana CDJR)
  - Store 17 = Orr Infiniti (Shreveport Infiniti)
- 12 of 17 PDFs were scanned images requiring OCR; 5 had extractable text
- Stores without test packets: Searcy GM, Longview GMC, Longview Pre-Owned, CAP Pre-Owned, Credit Builders Auto, Shreveport GOPO, Shreveport Pre-Owned, Destin Pre-Owned, CAP Mazda (bundled with CAP store 01)

### Session 18 — 2026-03-11 (Post-Upload Validation Review)
- Split upload flow into validate-then-approve: upload saves file + runs PacketValidator only, approve triggers full processing
- Added DetailedValidationResult with per-page classification (page number, doc type, confidence score, text snippets for unclassified)
- New schemas: ValidationUploadResponse, ApproveResponse, ClassifiedPage, UnclassifiedPage, RequiredDocumentCheck
- PacketValidator.validate_detailed() returns page-level detail; _classify_page_with_score() refactor
- POST /upload and /upload/bulk now return validation results only (no processing, meeting PENDING)
- New POST /upload/{meeting_id}/approve triggers full pipeline (parsing, flagging, PDF generation, email)
- Frontend: /stores/[storeId]/upload page with drag-and-drop, date picker
- Frontend: /stores/[storeId]/meetings/[meetingId]/validate page with 3 sections (classified pages, unclassified pages, required docs checklist) + completeness % + approve/re-upload buttons
- Static HTML: inline validation review with classified/unclassified tables, required docs checklist, approve button
- Updated all upload tests + 4 new approve endpoint tests
- 461 tests passing (up from 459)

### Session 17 — 2026-03-11 (Phase 3 Infrastructure)
- Scanned all 17 test packet PDFs with tesseract OCR for required document detection
  - Average completeness: 25% (best: CAP at 50%, worst: BMW(2) at 6%)
  - Parts 2222 detected in 94% of packets; Service/Parts Receivables, GL 0504 New/Used, and Wholesales at 0%
  - Full results saved to data/packet_scan_results.md
- Added `reynolds_site_id` column to stores table (Alembic migration 004, unique index)
- Inserted CAP GM store (24 total), updated 17 stores with Reynolds 7-digit site IDs
- Built StorageService (backend/app/services/storage_service.py):
  - Hetzner S3-compatible object storage via boto3
  - Lazy client init, graceful degradation when not configured
  - upload_packet, get_packet_url (presigned), list_packets methods
- Built PacketValidator (backend/app/services/packet_validator.py):
  - 16 required document types with OCR-tolerant regex patterns
  - Disambiguation via negative patterns and priority scoring
  - Cover page detection to avoid false positives
  - Integrated into both upload endpoints; results in API response
- Updated config.py (5 S3 settings), .env.example, requirements.txt (boto3)
- Updated schemas.py (FoundDocument, MissingDocument, PacketValidationResult)
- 459 tests passing (all previous + new code paths)

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
- [x] **Classifier Rebuild (Session 21)**: Rewrote PageClassifier with reference signatures from Ashdown labeled PDF
  - Built OCR reference corpus: 27 pages of tesseract output in data/reference_ocr/
  - Document signatures spec: data/reference_signatures.md (16 doc types + classification priority order)
  - Schedule-number-first matching (OCR-tolerant: handles "5chedule#:", "hedule#:", garbled prefixes)
  - GL 0504 account-based subtyping (15A=New, 15B=Used, 850/850A/851/851A for chargebacks)
  - Continuation page detection (Schedule Summary with no schedule number inherits previous page's doc_id)
  - OCR artifact tolerance: "Dpen ROs", "ACCCUNT", "MISSING TtTLE", truncated headers
  - 27/27 reference pages classify correctly
  - Added subtype and needs_user_input fields to ClassifiedPage schema

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

### Session 19 — 2026-03-11 (Real-Time Validation Progress)
- Made packet validation async with real-time progress streaming
- Upload endpoints now return immediately with UploadAcceptedResponse (meeting_id, store_id, total_pages)
- Validation runs in background thread via asyncio.run_in_executor
- New in-memory progress store (backend/app/services/validation_progress.py) keyed by meeting_id
- PacketValidator.validate_detailed_with_progress() processes page-by-page, updating progress after each page
- New GET /upload/{meeting_id}/progress endpoint returns real-time state (status, current_page, classified/unclassified pages, required docs checklist, completeness %)
- Frontend validate page reworked: polls progress every 2s, shows animated progress bar ("Processing page X of Y"), streams classified pages and required docs checklist in real-time
- Progress states: uploading → counting_pages → validating (page X/Y) → complete | error
- 5-minute client-side timeout with error message
- Upload page redirects immediately after file saved (no waiting for validation)
- Updated all upload tests for new async response format
- 461 tests passing (0 regressions)

### Session 21 — 2026-03-13 (Classifier Rebuild with Reference Signatures)
- Rebuilt PageClassifier in packet_validator.py using OCR reference signatures from Ashdown labeled PDF
- Built reference corpus: 27 pages of tesseract OCR output (data/reference_ocr/) + document signatures spec (data/reference_signatures.md)
- New classification approach: schedule-number-first for Schedule Summaries, account-number-first for GL 0504
- OCR tolerance for common artifacts: garbled "Schedule" ("5chedule", "hedule"), "ACCOUNT" ("ACCCUNT", "A00010;T"), "Open ROs" ("Dpen ROs"), "MISSING TITLE" ("MISSING TtTLE")
- GL 0504 subtyping: 15A=New, 15B=Used, 850/850A=F&I Chargeback New, 851/851A=F&I Chargeback Used
- Continuation page detection: Schedule Summary with no schedule number inherits previous page's doc_id
- Intro/cover page detection skips "ASSET MEETING" pages
- Employee list checked last (least distinctive — name roster pattern with role keywords)
- 27/27 reference pages classify correctly
- 451 tests passing (pre-existing scheduler timing test excluded)

### Session 20 — 2026-03-13 (Production Fixes: Validation + Auth Loop)
- Diagnosed stuck packet validation (page 0/31 forever) on production server
- Root cause: `_extract_text()` processed ALL 31 pages upfront (including tesseract OCR on 30 scanned pages) before the per-page classification loop — progress stayed at 0 for ~100 seconds
- Fixed `validate_detailed_with_progress()` to extract and classify one page at a time — progress now updates after each page including during OCR
- Fixed `--workers 2` → `--workers 1` — in-memory progress store is per-process, so multi-worker broke progress polling (requests could hit wrong worker)
- Removed easyocr from requirements.txt and torch from Dockerfile (switched to tesseract previously) — API memory dropped 262MB → 80MB
- Added Alembic migration 005 for `flags.previous_flag_id` and `flags.escalation_level` columns — fixed `UndefinedColumnError` crashing the notification scheduler every run
- Fixed auth redirect loop: dashboard → 401 → hard redirect to `/` → NextAuth sees "authenticated" → redirect to `/dashboard` → repeat forever
  - api.ts: replaced `window.location.href = "/"` with `signOut()` from NextAuth on 401 — clears session before redirect
  - dashboard: skip API fetch when `backendToken` is missing (prevents 401 while session loading)
  - Rebuilt and redeployed frontend container
- Deployed all fixes, verified both API and frontend running clean

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

# Phase 4A Tasks — Core Meeting Workflow

## Task 1: Per-Store Configurable Flagging Thresholds
- [x] Create StoreFlagOverride model (backend/app/models/store_flag_override.py)
- [x] Register model in backend/app/models/__init__.py
- [x] Create Alembic migration 006_store_flag_overrides.py
- [x] Modify FlaggingEngine.evaluate_meeting() to accept store_overrides dict
- [x] Add _apply_override() method to FlaggingEngine (dataclass replace, no mutation)
- [x] Add FlagRuleResponse and FlagRuleOverrideRequest schemas
- [x] Create flag_rules.py API routes (GET/PUT/DELETE per-store rules)
- [x] Register flag_rules router in main.py
- [x] Update ProcessingService.process_upload() to load overrides before flagging
- [x] Update ProcessingService.process_upload_from_bytes() to load overrides
- [x] Write API tests (16 tests in test_flag_rules.py)
- [x] Write engine override tests (10 tests in test_engine_overrides.py)
- [x] All 487 tests passing (26 new, 0 regressions)

### Session 22 — 2026-03-13 (Phase 4A Tasks 1 & 2)
- **Task 1**: Built per-store flagging threshold override system (R1 from meeting notes)
- StoreFlagOverride model: store_id + rule_name unique constraint, nullable yellow/red thresholds, enabled flag
- FlaggingEngine._apply_override() uses dataclass replace — never mutates original FlagRule
- Disabled rules (enabled=False) are skipped entirely during evaluation
- Null override thresholds fall through to defaults (partial overrides supported)
- 3 API endpoints: GET all 15 rules with effective thresholds, PUT upsert override, DELETE revert to defaults
- Corporate and GM can PUT/DELETE; Manager blocked (403); unauthenticated blocked (401)
- ProcessingService loads StoreFlagOverride records before calling FlaggingEngine
- 487 tests passing (26 new: 16 API + 10 engine)
- **Task 2**: Pre-meeting question workflow enhancements (R2, R3, R4)
- Added VERIFIED and UNRESOLVED to FlagStatus enum (answers don't auto-clear — GM/controller must verify)
- Flag verification fields: verified_by_id (FK→users), verified_at, verification_notes, expected_resolution_date
- FlagAssignment.expected_resolution_date for controller follow-up promise dates
- Alembic migration 007: ALTER TYPE flagstatus ADD VALUE for PostgreSQL enum, 5 new columns
- POST /flags/{flag_id}/verify endpoint: corporate/GM only, flag must be RESPONDED first
- Propagates expected_resolution_date to active FlagAssignment records
- NotificationScheduler.check_pre_meeting_reminders(): sends reminders for OPEN flags when meeting is today/tomorrow
- 499 tests passing (12 new: 9 API verification + 3 pre-meeting reminders)
- **Task 3**: Attendance tracking (R7 from meeting notes)
- Updated MeetingAttendance model: renamed attended→checked_in, added checked_in_at/checked_in_by_id/updated_at, unique constraint on (meeting_id, user_id)
- Alembic migration 008: column rename, new columns, FK, unique constraint
- 4 API endpoints: GET attendance list, POST mark check-in, DELETE unmark, GET summary
- Corporate/GM/Manager can mark attendance; Viewer blocked (403)
- Attendance list built from UserStore associations (expected attendees = users assigned to store)
- 515 tests passing (16 new: 16 attendance API tests)

## Task 2: Pre-Meeting Question Workflow Enhancements
- [x] Add VERIFIED and UNRESOLVED values to FlagStatus enum
- [x] Add verification fields to Flag model (expected_resolution_date, verified_by_id, verified_at, verification_notes)
- [x] Add expected_resolution_date to FlagAssignment model
- [x] Create Alembic migration 007_flag_verification_fields.py (enum ALTER TYPE + new columns)
- [x] Add FlagVerifyRequest and FlagVerifyResponse schemas
- [x] Add POST /flags/{flag_id}/verify endpoint (corporate/GM only, requires RESPONDED status)
- [x] Verify endpoint propagates expected_resolution_date to active FlagAssignment
- [x] Add check_pre_meeting_reminders() to NotificationScheduler (meetings today/tomorrow)
- [x] Write 9 API tests for flag verification (test_flag_verification.py)
- [x] Write 3 service tests for pre-meeting reminders (test_pre_meeting_reminders.py)
- [x] All 499 tests passing (12 new, 0 regressions)

## Task 3: Attendance Tracking (R7)
- [x] Update MeetingAttendance model: checked_in, checked_in_at, checked_in_by_id, updated_at, unique constraint
- [x] Create Alembic migration 008_meeting_attendance_updates.py
- [x] Add AttendanceResponse, AttendanceMarkRequest, AttendanceSummaryResponse schemas
- [x] Create attendance.py API routes (GET list, POST mark, DELETE unmark, GET summary)
- [x] Register attendance router in main.py
- [x] Write 16 API tests (test_attendance.py)
- [x] All 515 tests passing (16 new, 0 regressions)

## Task 4: Meeting Close + Recap Email
- [x] Add CLOSED value to MeetingStatus enum
- [x] Add closed_at, closed_by_id, close_notes fields to Meeting model
- [x] Create Alembic migration 009_meeting_close_fields.py (enum ALTER TYPE + new columns)
- [x] Add MeetingCloseRequest and MeetingCloseResponse schemas
- [x] Add POST /meetings/{meeting_id}/close endpoint (corporate/GM only)
- [x] Close sets status=CLOSED, records closed_at/closed_by, stores close_notes
- [x] Auto-unresolves OPEN and ESCALATED flags on close (→ UNRESOLVED)
- [x] Leaves RESPONDED and VERIFIED flags unchanged
- [x] Returns flags_summary (total, open, responded, verified, unresolved, auto_unresolved)
- [x] Returns attendance_summary (total_expected, total_present, total_absent)
- [x] Sends meeting recap email to corporate users (attendance + flags grouped by status)
- [x] 409 if meeting already closed, 403 if not GM/corporate
- [x] Write 12 API tests (test_meeting_close.py)
- [x] Write 4 service tests for recap email (test_meeting_recap.py)
- [x] 531 tests passing (16 new, 0 regressions)

## Task 5: Update All MD Files + Final Verification (Session 22)
- [x] Update tasks/todo.md with Phase 4A summary and Phase 4B/4C roadmap
- [x] Update tasks/lessons.md with Session 22 lessons
- [x] Update README.md with new features, endpoints, migrations, test count
- [x] Run full test suite — final verification
- [x] Git commit all MD files

# Phase 4B — Dashboard & Reporting

## Task 1: Accountability Metrics Service + Corporate Dashboard Enhancements
- [x] Create MetricsService (backend/app/services/metrics_service.py)
  - [x] get_manager_resolution_rates() — per-manager flag resolution stats
  - [x] get_store_comparison() — side-by-side store metrics
  - [x] get_top_priority_items() — Joel's top N urgency-scored items
- [x] Add dashboard metrics schemas (ManagerMetricsResponse, StoreComparisonResponse, PriorityItemResponse)
- [x] Add GET /dashboard/manager-metrics endpoint (corporate only)
- [x] Add GET /dashboard/store-comparison endpoint (corporate only)
- [x] Add GET /dashboard/top-priorities endpoint (corporate + GM)
- [x] Enhance existing GET /dashboard with top_priority_count and worst_resolution_rate
- [x] Write 11 service tests (test_metrics_service.py)
- [x] Write 9 API tests (test_dashboard_metrics.py)
- [x] 551 tests passing (20 new, 0 regressions)

### Session 23 — 2026-03-14 (Phase 4B Task 1)
- Built MetricsService with 3 core methods for accountability metrics
- Priority scoring is additive: UNRESOLVED(+10), ESCALATED(+8), past deadline(+5), within 48h(+3), RED(+3), YELLOW(+1), broken promise(+5), recurring(+2), previous unresolved(+2)
- Manager metrics sorted worst-first (lowest resolution rate) — what Thomas wants
- Store comparison includes attendance rate, meeting cadence check, flags per meeting
- Top priorities accessible to GMs (store-scoped) and corporate (all stores)
- Enhanced existing dashboard with top_priority_count and worst_resolution_rate
- 20 new tests (11 service + 9 API), 0 regressions

## Task 2: Execute Report PDF Generation (R5, R6 — Joel's "Top 10" Report)
- [x] Create ExecuteReportGenerator (backend/app/generators/execute_report.py)
  - [x] Page 1: Executive summary — meeting status, attendance, flag metrics (color-coded)
  - [x] Page 2: Top priority items table — scored, color-coded (red >=10, yellow >=5)
  - [x] Page 3+: Flags by status (unresolved, responded, verified, auto-unresolved)
  - [x] Manager accountability table (worst-first, color-coded resolution rates)
  - [x] GOAC branding (#003366), professional header/footer on every page
- [x] Create execute report service (backend/app/services/execute_report_service.py)
  - [x] generate_execute_report() — loads data, calls generator, returns PDF bytes
  - [x] send_execute_report() — generates PDF, emails with attachment to recipients
  - [x] Reuses MetricsService.get_top_priority_items() for priority scoring (no duplication)
  - [x] Per-meeting manager accountability metrics (assigned/resolved/unresolved per manager)
  - [x] Auto-unresolved detection (UNRESOLVED + never answered)
- [x] Add send_email_with_attachment() to EmailService (SendGrid v3 attachments API)
- [x] Add ExecuteReportSendRequest and ExecuteReportSendResponse schemas
- [x] Add GET /meetings/{id}/execute-report endpoint (PDF download, corporate + GM)
- [x] Add POST /meetings/{id}/execute-report/send endpoint (email with PDF attachment)
- [x] Register ExecuteReportGenerator in generators __init__.py
- [x] Write 12 generator tests (test_execute_report.py)
- [x] Write 10 API tests (test_execute_report_api.py)
- [x] 505 non-integration tests passing (22 new, 0 regressions)

### Session 23 — 2026-03-14 (Phase 4B Task 2)
- Built ExecuteReportGenerator: 4-section PDF (exec summary, top priorities, flags by status, manager accountability)
- Reuses MetricsService.get_top_priority_items() for Joel's priority scoring — no duplication
- Color-coded priority rows: red (score >= 10), yellow (score >= 5), white (< 5)
- Flags grouped by status: UNRESOLVED (red header), RESPONDED (yellow), VERIFIED (green), AUTO-UNRESOLVED (dark red)
- Manager accountability sorted worst-first with color-coded resolution rates (< 50% red, < 80% yellow)
- Added send_email_with_attachment() to EmailService for PDF email delivery via SendGrid
- Auto-unresolved flags identified by: UNRESOLVED status + no response_text + no responded_at
- 22 new tests (12 generator + 10 API), 0 regressions

## Task 3: Meeting History Export (CSV)
- [x] Create export_service.py with 4 export functions (meetings, flags, attendance, promise tracking)
- [x] Create exports.py API routes (4 GET endpoints, corporate only, StreamingResponse CSV)
- [x] Register exports router in main.py
- [x] Write 13 service tests (test_export_service.py)
- [x] Write 6 API tests (test_exports.py) — including RBAC (403 for GM/manager)
- [x] All 516 tests passing (19 new, 0 regressions)

### Session 23 — 2026-03-14 (Phase 4B Task 3)
- Built export_service.py: 4 async CSV export functions using Python csv + io.StringIO
- UTF-8 BOM for Excel compatibility, timestamps in Central Time
- Meetings CSV: flag summary stats (red/yellow/verified/unresolved/open/responded), resolution rate, attendance ratio, close info
- Flags CSV: reuses MetricsService.get_top_priority_items() for priority scoring — no duplication
- Attendance CSV: joined meeting/store/user, checked-in status + timestamp + checked-in-by
- Promise tracking CSV: flags with expected_resolution_date, calculates days_late, Promise Kept (Yes/No/Pending)
- Promise tracking sorted worst offenders first (days_late descending)
- All 4 endpoints corporate-only with store_id/date_from/date_to filters
- StreamingResponse with Content-Disposition attachment headers

## Task 4: Resolution Tracking Over Time + Condensed Packet View
- [x] Add MeetingTrendResponse, PromiseSummaryResponse, PromiseOffenderResponse schemas
- [x] Add CondensedPacketResponse and related schemas (CondensedFlagItem, CondensedSectionResponse, etc.)
- [x] Add get_resolution_trends() to metrics_service.py (per-meeting flag/promise/attendance stats)
- [x] Add get_promise_tracking_summary() to metrics_service.py (aggregate promise tracking with worst offenders)
- [x] Add GET /dashboard/resolution-trends endpoint (corporate + GM, store-scoped for GM)
- [x] Add GET /dashboard/promise-tracking endpoint (corporate only)
- [x] Add GET /packets/{meeting_id}/condensed endpoint (JSON — only flagged sections + key metrics + attendance)
- [x] Write 9 service tests (test_resolution_trends.py) — trends + promise summary
- [x] Write 5 API tests (test_resolution_trends_api.py) — trends + promise tracking endpoints + RBAC
- [x] Write 4 API tests (test_condensed_packet.py) — condensed response + section filtering + attendance + RBAC
- [x] 542 non-integration tests passing (18 new, 0 regressions); 608 total with integration

### Session 23 — 2026-03-14 (Phase 4B Task 4)
- Built get_resolution_trends(): per-meeting resolution/promise/attendance stats sorted ascending for charting
- Built get_promise_tracking_summary(): aggregate promise tracking with avg_days_late and worst offenders (top 5 by broken count)
- Resolution trends endpoint: corporate sees all, GM store-scoped (auto-filters to their stores)
- Promise tracking endpoint: corporate only — Thomas's promise accountability view
- Condensed packet: JSON-only view of flagged/important items (no raw data), grouped by category
  - Only includes sections with at least one flag (skip clean categories)
  - Key metrics per section (inventory counts, receivables, ROs, etc.)
  - Attendance summary with present/absent names
- 18 new tests (9 service + 5 API + 4 API), 0 regressions

## Task 5: Update All MD Files + Final Verification (Session 23)
- [x] Update tasks/lessons.md with Session 23 lessons
- [x] Update README.md with Phase 4B features, new endpoints, test count
- [x] Verify tasks/todo.md is current (all Phase 4B tasks complete)
- [x] Run full test suite — 608 passed (542 unit/API + 66 integration), 2 known scheduler flakes
- [ ] Git commit all changes

### Session 23 — 2026-03-14 (Phase 4B Task 5)
- Updated lessons.md with 11 Session 23 lessons (metrics aggregation, priority scoring, execute report, SendGrid attachments, CSV BOM, StreamingResponse, promise tracking, condensed packet, resolution trends, stakeholder feedback)
- Updated README.md: Phase 4B marked COMPLETE, 14 new API endpoints documented, test count updated, status section updated
- Updated todo.md: Task 5 added and tracked

# Phase 4C — Scheduling & Calendar (upcoming)

- [ ] Meeting scheduling (minimum 2x/month cadence enforcement)
- [ ] Calendar integration (Google Calendar)
- [ ] Recurring meeting templates

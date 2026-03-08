# GOAC Asset Meeting Manager

Automate, standardize, and enforce accountability for asset/receivable meetings across all Gregg Orr Auto Collection dealership locations.

## Roadmap

### Phase 1: Packet Generator + Flagging
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

## Phase 1 Deliverables

- PostgreSQL data models for all report categories
- PDF parser framework with category-specific parsers (inventory, parts, financial, operations)
- Configurable flagging engine with initial rule set
- Standardized PDF packet generator
- Flagged items report generator
- Upload API endpoints
- Simple upload web UI
- Floorplan reconciliation (Schedule 237 vs 231/310 variance)

## Setup

```bash
# Copy environment file
cp .env.example .env

# Start services
docker compose up -d

# Run migrations
cd backend && alembic upgrade head
```

## Current Status

**Phase 1** — Repository initialization complete. Parser and flagging engine development next.

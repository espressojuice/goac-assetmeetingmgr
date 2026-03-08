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
- [ ] Build standardized PDF packet generator
- [ ] Build flagged items report generator
- [ ] Build upload API endpoints
- [ ] Build simple upload web UI
- [ ] Test against Ashdown reference packet
- [ ] Validate floorplan reconciliation output (237 vs 231/310 variance)

## Session Log

### Session 1 — 2026-03-08
- Initialized repo structure (16 models, 7 enums, docker-compose, config)
- Built all 4 parsers: inventory, parts, financial, operations
- Built flagging engine with 15 business rules
- 152 tests all passing
- Pipeline complete through: Upload → Extract → Parse → Save → Flag

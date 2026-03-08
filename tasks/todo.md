# Phase 1 Tasks

- [x] Initialize repo structure and foundational files
- [ ] Define PostgreSQL data models (all categories: inventory, parts, financial, operations, flags)
- [ ] Set up Alembic migrations
- [ ] Build base parser framework (PDF text extraction)
- [ ] Build inventory parser (schedules 237, 240, 277)
- [ ] Build parts parser (GL 242-244, monthly analysis)
- [ ] Build financial parser (receivables, F&I, contracts in transit, wholesale deals)
- [ ] Build operations parser (open ROs, warranty claims, missing titles, employee roster)
- [ ] Implement flagging engine with configurable rules
- [ ] Implement all initial flagging rules per the rules table
- [ ] Build standardized PDF packet generator
- [ ] Build flagged items report generator
- [ ] Build upload API endpoints
- [ ] Build simple upload web UI
- [ ] Test against Ashdown reference packet
- [ ] Validate floorplan reconciliation output (237 vs 231/310 variance)

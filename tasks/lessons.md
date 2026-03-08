# Lessons Learned

- **2026-03-08**: Project initialized. Reference packet is Ashdown Classic Chevrolet 02/11/2026 (27 pages). All parsers must handle handwritten notes gracefully.
- **2026-03-08**: FloorplanReconciliation gets its own model — the variance between book value and floorplan balance is the most politically sensitive data point in the system.
- **2026-03-08**: R&R PDF formats vary between report types. Section identifiers need multiple variants. Parser must be defensive — log warnings on unparseable rows, never crash.
- **2026-03-08**: F&I chargeback section identifiers (850, 851) are too short for simple substring matching — need context-aware `can_handle` to avoid false positives.
- **2026-03-08**: For 'lt' comparisons (like parts turnover), yellow threshold must be HIGHER than red — yellow at <2.0 means 'getting low,' red at <1.0 means 'critical.' Check red first to avoid double-flagging.

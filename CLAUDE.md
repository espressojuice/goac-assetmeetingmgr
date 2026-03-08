# GOAC Asset Meeting Manager

## Workflow Rules

- **Plan mode default** for non-trivial tasks (3+ steps or architectural decisions)
- **Update tasks/lessons.md** after any correction from the user
- **Never mark a task complete** without proving it works (run tests, check logs, demonstrate correctness)
- **Simplicity first** — minimal impact changes, only touch what's necessary
- **No temporary fixes** — find root causes, senior developer standards
- **All timestamps are Central Time** (US/Central)
- When completing work, always update `tasks/todo.md`, `tasks/lessons.md`, and `README.md`

## Tech Stack

- **Backend**: FastAPI + PostgreSQL (SQLAlchemy async, Alembic migrations)
- **Frontend**: Next.js
- **Project Tracking**: Linear (workspace: goac-dev, team: GOA)

## Task Management

1. Write plan to `tasks/todo.md` with checkable items
2. Check in before starting implementation
3. Mark items complete as you go
4. High-level summary at each step
5. Add review section to `tasks/todo.md`
6. Capture lessons in `tasks/lessons.md` after corrections

## Core Principles

- Make every change as simple as possible
- Find root causes — no temporary fixes
- Changes should only touch what's necessary
- Verify before marking done

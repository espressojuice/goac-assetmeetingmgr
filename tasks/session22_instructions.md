# Session 22 — Claude Code Instructions

## Paste this entire block into Claude Code:

```
Read tasks/phase4_meeting_notes.md, tasks/todo.md, and tasks/lessons.md first. This is Session 22. We are starting Phase 4 based on a meeting with corporate (Thomas, Amanda) about what they want from the asset meeting tool.

## PHASE 4A: Per-Store Flagging Rules + Pre-Meeting Question Workflow

This session focuses on TWO foundational features:
1. Per-store configurable flagging thresholds
2. Pre-meeting question workflow with answer verification

### TASK 1: Per-Store Flagging Rules (Database + Engine)

Currently, flagging rules in backend/app/flagging/rules.py are hardcoded DEFAULT_RULES with fixed thresholds. The meeting made clear that each store needs its own thresholds because brands turn at different rates (Kia faster than GM). 120-day used car write-downs and floor plan variance thresholds differ per store due to packs.

**What to build:**

A. Create a new model `StoreFlagOverride` in a new file `backend/app/models/store_flag_override.py`:
```python
class StoreFlagOverride(Base):
    __tablename__ = "store_flag_overrides"

    id: UUID primary key
    store_id: FK to stores.id (not null)
    rule_name: String(100) not null  # matches FlagRule.name (e.g., "Used Vehicle Age")
    yellow_threshold: Numeric nullable  # null = use default
    red_threshold: Numeric nullable  # null = use default
    enabled: Boolean default True  # can disable a rule for a specific store
    created_at, updated_at timestamps

    # Unique constraint on (store_id, rule_name)
    # Index on store_id
```

B. Create Alembic migration `006_store_flag_overrides.py`

C. Modify `backend/app/flagging/engine.py` FlaggingEngine:
- Add `store_overrides: dict[str, StoreFlagOverride]` parameter to `evaluate()`
- When evaluating a rule, check if there's a store override for that rule_name
- If override exists and has a threshold value, use it; otherwise use the default
- If override exists and enabled=False, skip the rule entirely

D. Add API endpoints in a new route file `backend/app/api/routes/flag_rules.py`:
- `GET /api/v1/stores/{store_id}/flag-rules` — returns all 15 rules with current thresholds (default or overridden) for that store
- `PUT /api/v1/stores/{store_id}/flag-rules/{rule_name}` — upsert a StoreFlagOverride (corporate/GM only)
- `DELETE /api/v1/stores/{store_id}/flag-rules/{rule_name}` — delete override, revert to default (corporate/GM only)

E. Update `backend/app/services/processing_service.py` to load store overrides before calling the flagging engine.

F. Write tests for:
- StoreFlagOverride model CRUD
- FlaggingEngine with overrides (override threshold, disabled rule, partial override)
- API endpoints (get rules, upsert override, delete override, auth checks)

### TASK 2: Pre-Meeting Question Workflow Enhancements

The current system generates flags and can auto-assign them. The meeting wants a more explicit "pre-meeting question" flow:

1. Flags become questions that managers must answer BEFORE the meeting
2. Managers get daily notifications until they answer
3. During the meeting, the GM/controller reviews answers and marks each as: VERIFIED (resolved), UNRESOLVED (needs more work), or NEEDS_FOLLOWUP (with a promise date)
4. Answers do NOT auto-clear flags — verification is required

**What to build:**

A. Add new FlagStatus values to `backend/app/models/flag.py`:
```python
class FlagStatus(str, enum.Enum):
    OPEN = "open"              # just created, needs response
    RESPONDED = "responded"     # manager typed an answer (pre-meeting)
    VERIFIED = "verified"       # GM/controller verified answer is acceptable (during/after meeting)
    UNRESOLVED = "unresolved"   # GM/controller says answer is not good enough
    ESCALATED = "escalated"     # escalated to corporate
```

B. Add fields to the Flag model:
- `expected_resolution_date`: Date nullable — controller can set when this should be cleared
- `verified_by_id`: FK to users.id nullable — who verified/rejected the answer
- `verified_at`: DateTime nullable
- `verification_notes`: Text nullable — notes from the meeting discussion

C. Add fields to FlagAssignment model:
- `expected_resolution_date`: Date nullable — promise date for follow-up items

D. Create Alembic migration `007_flag_verification_fields.py` for the new columns and enum values

E. Add/update API endpoints:
- `POST /api/v1/flags/{flag_id}/verify` — Mark a flag as verified/unresolved/needs-followup (corporate/GM only). Accepts: status (verified|unresolved), verification_notes, expected_resolution_date
- Update existing `GET /api/v1/flags/my/assigned` to show expected_resolution_date and verification status

F. Update notification scheduler in `backend/app/services/notification_scheduler.py`:
- Add daily check: for any meeting with flags that have status=OPEN and meeting date is tomorrow or today, send reminder to assigned managers who haven't responded
- Make this check run daily at 8 AM CT

G. Write tests for:
- Flag verification endpoint (verify, mark unresolved, set expected date)
- Auth checks (only corporate/GM can verify)
- Notification scheduler for pre-meeting reminders
- FlagStatus enum migration

### TASK 3: Attendance Tracking Frontend

MeetingAttendance model already exists. Wire it up.

A. Add API endpoints to `backend/app/api/routes/meetings.py`:
- `GET /api/v1/meetings/{meeting_id}/attendance` — returns attendance records
- `POST /api/v1/meetings/{meeting_id}/attendance` — bulk upsert attendance (list of {user_id, attended, role_in_meeting}). Corporate/GM only.

B. Add frontend component: Meeting attendance section on the meeting detail page
- Show list of store users with checkboxes for attended/not attended
- Role dropdown (facilitator, participant, remote)
- Save button

C. Write tests for attendance API endpoints

### TASK 4: Post-Meeting Close-Out

A. Add a `MeetingStatus` value: `CLOSED` (after `COMPLETED`). Meeting flow: PENDING → COMPLETED (after processing) → CLOSED (after post-meeting review)

B. Add fields to Meeting model:
- `closed_at`: DateTime nullable
- `closed_by_id`: FK to users.id nullable
- `meeting_notes`: Text nullable — general meeting notes

C. Add API endpoint:
- `POST /api/v1/meetings/{meeting_id}/close` — Close a meeting (corporate/GM only). Triggers email recap to corporate group. Accepts: meeting_notes

D. Add email template for meeting recap:
- Send to configurable corporate email list
- Include: store name, meeting date, attendance summary, flags summary (total/responded/verified/unresolved), unresolved items list with owners

E. Create Alembic migration `008_meeting_close_fields.py`

F. Write tests

### TASK 5: Update MD Files

After ALL tasks above are complete:
- Update tasks/todo.md with Phase 4A tasks and session 22 log
- Update tasks/lessons.md with any new patterns learned
- Update README.md with Phase 4 features
- Run ALL tests and report count

### IMPORTANT RULES:
- All timestamps are Central Time (US/Central)
- Run tests after each task, not just at the end
- Each migration should be its own file (006, 007, 008)
- Don't break any existing tests
- Follow existing code patterns (look at how current models, routes, and tests are structured)
- Keep changes minimal and focused — don't refactor existing working code
```

# Phase 4 — Meeting Notes Analysis (March 13, 2026)

## Meeting Participants
- **Speaker 0** = Thomas (Owner/Corporate Leader)
- **Speaker 1** = Bryan (Developer/Tech)
- **Speaker 2** = Amanda (Controller/Corporate Accounting)
- **Speaker 3/4** = Additional participants (Thomas's team)
- **Speaker 5** = Greg (Executive, walked in mid-meeting)

## Context (Chopped Off Beginning)
Each store needs its own flagging criteria because different brands turn at different rates (e.g., Kia products turn faster than GM products). Store-level criteria must be individually configurable.

---

## Requirements Extracted (Numbered for Tracking)

### R1: Per-Store Flagging Criteria
- Each store gets its own thresholds (not one-size-fits-all)
- Kia turns faster than GM → different day-in-stock thresholds
- Floor plan variance thresholds differ by store because of packs
- Need to compare packs vs average RO per store
- Used car write-down at 120 days varies by store
- **Yellow flags** for approaching thresholds (e.g., approaching 120-day write-down)
- **Red flags** for exceeded thresholds

### R2: Pre-Meeting Question Generation & Portal
- System generates questions based on flagging criteria automatically
- Questions are specific: "What is holding this deal from being posted?" with target resolution date and owner
- Managers go to a web portal to answer questions BEFORE the meeting
- System pings/notifies managers every day until they answer
- Questions are assigned by department (auto-assign based on flag category → department → person)

### R3: Answer Verification (NOT Auto-Clear)
- Answers typed before the meeting do NOT automatically clear the flag
- During the meeting, moderator (GM/controller) reviews answers
- If answer is "BS" or insufficient, it stays unresolved
- Checkbox-style: resolved / still unresolved for each flag
- After meeting, responsible person updates with the real action plan
- Record of what was discussed must persist

### R4: Controller Follow-Up Dates
- Controller can set expected resolution date (e.g., "should be cleared by Tuesday")
- If not cleared by next meeting, shows with expected date vs. actual ("should have been cleared March 16, still here March 18")
- Essentially a promise date that gets tracked

### R5: Condensed Packet (Only Flagged Items)
- Current packets are 30+ pages of raw data
- Condense to 5 pages of only the important/flagged stuff
- Remove all the "fluff" that isn't discussed
- Service/parts: only show total investment, aging, dirty core
- Don't print schedules nobody looks at (like full 22-11/22-13 detail)
- Only flagged items + summary

### R6: Summary Page (At-a-Glance)
- Standardized format for ALL stores
- First page of meeting packet
- Attendance section
- Key metrics at a glance
- Red flag count by category

### R7: Attendance Tracking via Website
- Office manager goes to website after meeting
- Marks who attended / who didn't attend
- Standardized format across all stores
- Corporate can see attendance history

### R8: Meeting Scheduling & Cadence Tracking
- At beginning of month, stores set when meetings will be
- Minimum: every other week (2x/month) for all stores
- Some stores weekly (e.g., Longview weekly except last week of month)
- Corporate needs visibility: are stores actually having meetings?
- Dashboard should show which stores are on track vs. behind

### R9: Google Calendar Integration (Future)
- When meetings are scheduled, push to Google Calendar
- Long-term: overlay with vacation schedules
- Store-wide calendar of meetings and events
- **NOT in initial build** — but design for it

### R10: Post-Meeting Workflow
- Office manager enters attendance on website
- Goes through each flag and marks: resolved / unresolved / needs follow-up
- Can add notes per flag (meeting discussion notes)
- After meeting completion → email recap to corporate group
- Corporate people who should receive recap: Amanda, Thomas, Tim, Lance, Cathy

### R11: Corporate Dashboard Enhancements
- Unresolved items across all stores
- Per-manager accountability metrics: "Tommy is at 10% resolved, everyone else at 95%"
- Track resolution rates by person and by store
- Historical meeting access (go back and review past meetings even if all resolved)
- Dashboard accessible to: Thomas, Amanda, Tim, Lance, Cathy (corporate team)

### R12: Email Recap After Meeting
- After meeting is marked complete, email summary to configurable corporate group
- Include: attendance, flags discussed, resolved vs unresolved, action items
- Corporate can look at recap and say "this is crap" and push back

### R13: No Zoom/Audio Integration (Scrapped)
- Most meetings are in-person with corporate on cell phone
- No audio capture — nobody would review it
- No Zoom/Google Meet integration for now

### R14: Reports Stay Manual (For Now)
- Office managers run reports from Reynolds manually
- Build saved report templates in Reynolds
- Reynolds API access is $1,200/month and not worth it if switching to Techion
- Future: if they switch DMS, can auto-pull data
- Controllers should review reports before uploading (catch clerical errors)

### R15: Prepaids Simplified
- Prepaids can be automated/simplified
- Amanda and Cathy review them separately
- Don't necessarily need full prepaid detail in meeting packet for everyone

### R16: Parts Report Input Needed
- Get Rick DeMond's input on what's important for parts in receivable meetings
- Currently: total investment, aging breakdown, dirty core are the key items
- Negative on hand is worth flagging
- Most detail on 22-11/22-13 reports isn't looked at

---

## What Already Exists (No Work Needed)
- ✅ Flag assignment and response workflow
- ✅ Email notifications (SendGrid) — 7 types
- ✅ Corporate dashboard (multi-store overview)
- ✅ Meeting detail pages with tabbed data
- ✅ Upload and validation flow
- ✅ MeetingAttendance model (exists but needs frontend)
- ✅ Historical meeting access
- ✅ Role-based access control
- ✅ Notification center (in-app)
- ✅ Recurring flag detection
- ✅ Auto-escalation

## What Needs Building/Modifying

### HIGH PRIORITY (Phase 4A — Core Meeting Workflow)
1. **Per-store flagging rules** (R1) — StoreFlagRule model + admin UI + engine changes
2. **Pre-meeting question workflow** (R2) — Already partially exists via flag assignments, needs "pre-meeting question" mode
3. **Meeting-time answer verification** (R3) — New FlagStatus values (VERIFIED_RESOLVED, UNRESOLVED_NEEDS_FOLLOWUP), meeting review page
4. **Controller follow-up dates** (R4) — Add expected_resolution_date to Flag/FlagAssignment, track promise dates
5. **Attendance tracking frontend** (R7) — Wire up existing MeetingAttendance model to frontend
6. **Post-meeting workflow** (R10) — Meeting close-out page, email recap

### MEDIUM PRIORITY (Phase 4B — Dashboard & Reporting)
7. **Condensed packet / flagged-only view** (R5) — Already partially exists with flagged items report
8. **Summary page** (R6) — Already exists in packet generator, may need tweaking
9. **Corporate dashboard enhancements** (R11) — Accountability metrics, resolution rates
10. **Email recap after meeting** (R12) — New email template + trigger on meeting close

### LOWER PRIORITY (Phase 4C — Scheduling & Calendar)
11. **Meeting scheduling & cadence tracking** (R8) — MeetingSchedule model, cadence enforcement
12. **Google Calendar integration** (R9) — Design for it, don't build yet

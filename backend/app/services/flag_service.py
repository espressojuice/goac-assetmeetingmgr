"""Flag assignment, response, and recurring detection service."""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.meeting import Meeting
from app.models.store import Store
from app.models.user import User, UserRole
from app.models.accountability import (
    AssignmentStatus,
    FlagAssignment,
    FlagResponseRecord,
    Notification,
    NotificationType,
)

from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

# Maps flag category to the user role that should handle it.
# Falls back to GM if no match found.
_CATEGORY_ROLE_MAP: dict[FlagCategory, list[UserRole]] = {
    FlagCategory.INVENTORY: [UserRole.GM],
    FlagCategory.PARTS: [UserRole.MANAGER, UserRole.GM],
    FlagCategory.FINANCIAL: [UserRole.MANAGER, UserRole.GM],
    FlagCategory.OPERATIONS: [UserRole.MANAGER, UserRole.GM],
}


class FlagService:

    # ------------------------------------------------------------------
    # Auto-assign
    # ------------------------------------------------------------------
    async def auto_assign_flags(
        self,
        meeting_id: str,
        db: AsyncSession,
        assigned_by_id: Optional[str] = None,
    ) -> dict:
        """Auto-assign unassigned flags for a meeting based on category-to-role mapping.

        Since there is no store-user join table yet, assignment uses the
        store's ``gm_email`` to locate a GM user.  All flags without a
        matching role-specific user fall back to that GM.  If no GM is
        found the flag is left unassigned.

        Sets deadline to meeting_date + 1 day (24 hours represented as
        the next calendar day, since FlagAssignment.deadline is a Date).

        Returns summary dict with assigned/unassigned counts.
        """
        meeting_uuid = uuid.UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id

        # Load meeting + store
        result = await db.execute(
            select(Meeting, Store)
            .join(Store, Meeting.store_id == Store.id)
            .where(Meeting.id == meeting_uuid)
        )
        row = result.first()
        if not row:
            return {"assigned_count": 0, "unassigned_count": 0, "by_category": {}}

        meeting, store = row[0], row[1]
        deadline = meeting.meeting_date + datetime.timedelta(days=1)

        # Find GM user via store.gm_email
        gm_user: Optional[User] = None
        if store.gm_email:
            gm_result = await db.execute(
                select(User).where(User.email == store.gm_email)
            )
            gm_user = gm_result.scalar_one_or_none()

        # Determine the assigner (system or a specific user)
        assigner_id: Optional[uuid.UUID] = None
        if assigned_by_id:
            assigner_id = uuid.UUID(assigned_by_id) if isinstance(assigned_by_id, str) else assigned_by_id
        elif gm_user:
            assigner_id = gm_user.id

        # Load unassigned flags for this meeting
        flags_result = await db.execute(
            select(Flag).where(Flag.meeting_id == meeting_uuid)
        )
        all_flags = list(flags_result.scalars().all())

        # Find which flags already have assignments
        existing_result = await db.execute(
            select(FlagAssignment.flag_id).where(
                FlagAssignment.flag_id.in_([f.id for f in all_flags])
            )
        )
        assigned_flag_ids = {row[0] for row in existing_result.all()}
        unassigned_flags = [f for f in all_flags if f.id not in assigned_flag_ids]

        assigned_count = 0
        unassigned_count = 0
        by_category: dict[str, int] = {}

        for flag in unassigned_flags:
            # For now, all roles fall back to GM since we don't have
            # a store-user role mapping table yet.
            target_user = gm_user

            if target_user and assigner_id:
                assignment = FlagAssignment(
                    flag_id=flag.id,
                    assigned_to_id=target_user.id,
                    assigned_by_id=assigner_id,
                    status=AssignmentStatus.PENDING,
                    deadline=deadline,
                )
                db.add(assignment)
                assigned_count += 1
                cat_key = flag.category.value
                by_category[cat_key] = by_category.get(cat_key, 0) + 1

                # Create notification for the assignee
                notification = Notification(
                    user_id=target_user.id,
                    notification_type=NotificationType.FLAG_ASSIGNED,
                    title="New flag assigned",
                    message=f"You have been assigned a {flag.severity.value} {flag.category.value} flag: {flag.message[:100]}",
                    reference_id=flag.id,
                )
                db.add(notification)
            else:
                unassigned_count += 1

        await db.flush()

        # Send email notifications for new assignments
        if assigned_count > 0 and gm_user:
            try:
                email_svc = EmailService()
                for flag in unassigned_flags:
                    if gm_user and assigner_id:
                        await email_svc.send_flag_assigned(gm_user, flag, meeting, store)
            except Exception:
                logger.warning("Failed to send flag assignment emails", exc_info=True)

        return {
            "assigned_count": assigned_count,
            "unassigned_count": unassigned_count,
            "by_category": by_category,
        }

    # ------------------------------------------------------------------
    # Manual assign / reassign
    # ------------------------------------------------------------------
    async def assign_flag(
        self,
        flag_id: str,
        assigned_to_id: str,
        assigned_by_id: str,
        db: AsyncSession,
        deadline: Optional[datetime.date] = None,
    ) -> FlagAssignment:
        """Manually assign or reassign a flag to a user."""
        flag_uuid = uuid.UUID(flag_id) if isinstance(flag_id, str) else flag_id
        to_uuid = uuid.UUID(assigned_to_id) if isinstance(assigned_to_id, str) else assigned_to_id
        by_uuid = uuid.UUID(assigned_by_id) if isinstance(assigned_by_id, str) else assigned_by_id

        # Verify flag exists
        flag = (await db.execute(select(Flag).where(Flag.id == flag_uuid))).scalar_one_or_none()
        if not flag:
            raise ValueError(f"Flag {flag_id} not found")

        # Verify target user exists
        target = (await db.execute(select(User).where(User.id == to_uuid))).scalar_one_or_none()
        if not target:
            raise ValueError(f"User {assigned_to_id} not found")

        # Check for existing assignment
        existing = (await db.execute(
            select(FlagAssignment).where(FlagAssignment.flag_id == flag_uuid)
        )).scalar_one_or_none()

        if existing:
            existing.assigned_to_id = to_uuid
            existing.assigned_by_id = by_uuid
            existing.status = AssignmentStatus.PENDING
            if deadline:
                existing.deadline = deadline
            assignment = existing
        else:
            # Default deadline: flag's meeting date + 1 day
            if not deadline:
                meeting = (await db.execute(
                    select(Meeting).where(Meeting.id == flag.meeting_id)
                )).scalar_one_or_none()
                deadline = meeting.meeting_date + datetime.timedelta(days=1) if meeting else datetime.date.today() + datetime.timedelta(days=1)

            assignment = FlagAssignment(
                flag_id=flag_uuid,
                assigned_to_id=to_uuid,
                assigned_by_id=by_uuid,
                status=AssignmentStatus.PENDING,
                deadline=deadline,
            )
            db.add(assignment)

        # Notification
        notification = Notification(
            user_id=to_uuid,
            notification_type=NotificationType.FLAG_ASSIGNED,
            title="Flag assigned to you",
            message=f"A {flag.severity.value} {flag.category.value} flag has been assigned to you: {flag.message[:100]}",
            reference_id=flag_uuid,
        )
        db.add(notification)

        await db.flush()
        return assignment

    # ------------------------------------------------------------------
    # Submit response
    # ------------------------------------------------------------------
    async def submit_response(
        self,
        flag_id: str,
        responder_id: str,
        response_text: str,
        db: AsyncSession,
    ) -> FlagResponseRecord:
        """Submit a response to a flag.

        Creates FlagResponseRecord, updates Flag status + inline fields,
        and updates the assignment status if one exists.
        """
        flag_uuid = uuid.UUID(flag_id) if isinstance(flag_id, str) else flag_id
        user_uuid = uuid.UUID(responder_id) if isinstance(responder_id, str) else responder_id

        flag = (await db.execute(select(Flag).where(Flag.id == flag_uuid))).scalar_one_or_none()
        if not flag:
            raise ValueError(f"Flag {flag_id} not found")

        user = (await db.execute(select(User).where(User.id == user_uuid))).scalar_one_or_none()
        if not user:
            raise ValueError(f"User {responder_id} not found")

        now = datetime.datetime.now(datetime.timezone.utc)

        # Update Flag inline fields
        flag.response_text = response_text
        flag.responded_by = user.name
        flag.responded_at = now
        flag.status = FlagStatus.RESPONDED

        # Find assignment
        assignment = (await db.execute(
            select(FlagAssignment).where(FlagAssignment.flag_id == flag_uuid)
        )).scalar_one_or_none()

        assignment_id: Optional[uuid.UUID] = None
        if assignment:
            assignment.status = AssignmentStatus.RESPONDED
            assignment_id = assignment.id

            # Notify the assigner that a response was submitted
            notification = Notification(
                user_id=assignment.assigned_by_id,
                notification_type=NotificationType.RESPONSE_RECEIVED,
                title="Flag response received",
                message=f"{user.name} responded to a {flag.category.value} flag: {response_text[:100]}",
                reference_id=flag_uuid,
            )
            db.add(notification)

        # Create response record
        record = FlagResponseRecord(
            flag_id=flag_uuid,
            user_id=user_uuid,
            assignment_id=assignment_id,
            response_text=response_text,
        )
        db.add(record)

        await db.flush()

        # Notify corporate users of the response
        try:
            email_svc = EmailService()
            store = (await db.execute(
                select(Store).where(Store.id == flag.store_id)
            )).scalar_one_or_none()
            if store:
                corporate_result = await db.execute(
                    select(User).where(
                        and_(User.role == UserRole.CORPORATE, User.is_active == True)  # noqa: E712
                    )
                )
                corporate_users = list(corporate_result.scalars().all())
                if corporate_users:
                    record.user = user  # Attach user for email template
                    await email_svc.send_response_received(
                        corporate_users, flag, record, store
                    )
        except Exception:
            logger.warning("Failed to send response notification emails", exc_info=True)

        return record

    # ------------------------------------------------------------------
    # My flags
    # ------------------------------------------------------------------
    async def get_my_flags(
        self,
        user_id: str,
        db: AsyncSession,
        status: Optional[str] = None,
        store_id: Optional[str] = None,
    ) -> list[dict]:
        """Get all flags assigned to a user with meeting/store context."""
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        query = (
            select(FlagAssignment, Flag, Meeting, Store)
            .join(Flag, FlagAssignment.flag_id == Flag.id)
            .join(Meeting, Flag.meeting_id == Meeting.id)
            .join(Store, Flag.store_id == Store.id)
            .where(FlagAssignment.assigned_to_id == user_uuid)
        )

        if status:
            if status == "overdue":
                today = datetime.date.today()
                query = query.where(
                    and_(
                        FlagAssignment.deadline < today,
                        FlagAssignment.status.in_([
                            AssignmentStatus.PENDING,
                            AssignmentStatus.ACKNOWLEDGED,
                        ]),
                    )
                )
            else:
                query = query.where(Flag.status == FlagStatus(status))

        if store_id:
            query = query.where(Flag.store_id == uuid.UUID(store_id))

        # Sort: overdue first (pending + past deadline), then by deadline ascending
        query = query.order_by(FlagAssignment.deadline.asc())

        result = await db.execute(query)
        rows = result.all()

        today = datetime.date.today()
        output = []
        for assignment, flag, meeting, store in rows:
            is_overdue = (
                assignment.deadline < today
                and assignment.status in (AssignmentStatus.PENDING, AssignmentStatus.ACKNOWLEDGED)
            )
            days_overdue = (today - assignment.deadline).days if is_overdue else 0

            output.append({
                "id": str(flag.id),
                "assignment_id": str(assignment.id),
                "category": flag.category.value,
                "severity": flag.severity.value,
                "message": flag.message,
                "field_name": flag.field_name,
                "field_value": flag.field_value,
                "threshold": flag.threshold,
                "status": flag.status.value,
                "assignment_status": assignment.status.value,
                "store_id": str(store.id),
                "store_name": store.name,
                "meeting_id": str(meeting.id),
                "meeting_date": str(meeting.meeting_date),
                "deadline": str(assignment.deadline),
                "is_overdue": is_overdue,
                "days_overdue": days_overdue,
                "escalation_level": flag.escalation_level,
                "response_text": flag.response_text,
                "responded_at": flag.responded_at.isoformat() if flag.responded_at else None,
                "created_at": flag.created_at.isoformat() if flag.created_at else None,
            })

        # Sort: overdue first, then by deadline
        output.sort(key=lambda x: (not x["is_overdue"], x["deadline"]))
        return output

    # ------------------------------------------------------------------
    # Overdue flags
    # ------------------------------------------------------------------
    async def check_overdue_flags(
        self,
        db: AsyncSession,
        store_id: Optional[str] = None,
    ) -> list[dict]:
        """Find all flags past deadline that haven't been responded to."""
        today = datetime.date.today()

        query = (
            select(FlagAssignment, Flag, Meeting, Store, User)
            .join(Flag, FlagAssignment.flag_id == Flag.id)
            .join(Meeting, Flag.meeting_id == Meeting.id)
            .join(Store, Flag.store_id == Store.id)
            .join(User, FlagAssignment.assigned_to_id == User.id)
            .where(
                and_(
                    FlagAssignment.deadline < today,
                    FlagAssignment.status.in_([
                        AssignmentStatus.PENDING,
                        AssignmentStatus.ACKNOWLEDGED,
                    ]),
                )
            )
        )

        if store_id:
            query = query.where(Flag.store_id == uuid.UUID(store_id))

        query = query.order_by(FlagAssignment.deadline.asc())
        result = await db.execute(query)
        rows = result.all()

        output = []
        for assignment, flag, meeting, store, user in rows:
            days_overdue = (today - assignment.deadline).days
            output.append({
                "id": str(flag.id),
                "assignment_id": str(assignment.id),
                "category": flag.category.value,
                "severity": flag.severity.value,
                "message": flag.message,
                "status": flag.status.value,
                "store_name": store.name,
                "meeting_date": str(meeting.meeting_date),
                "deadline": str(assignment.deadline),
                "days_overdue": days_overdue,
                "assigned_to_name": user.name,
                "assigned_to_email": user.email,
            })

        return output

    # ------------------------------------------------------------------
    # Escalate
    # ------------------------------------------------------------------
    async def escalate_flag(
        self,
        flag_id: str,
        db: AsyncSession,
        reason: Optional[str] = None,
    ) -> Flag:
        """Manually escalate a flag."""
        flag_uuid = uuid.UUID(flag_id) if isinstance(flag_id, str) else flag_id

        flag = (await db.execute(select(Flag).where(Flag.id == flag_uuid))).scalar_one_or_none()
        if not flag:
            raise ValueError(f"Flag {flag_id} not found")

        flag.status = FlagStatus.ESCALATED
        flag.escalation_level += 1

        # Update assignment status too
        assignment = (await db.execute(
            select(FlagAssignment).where(FlagAssignment.flag_id == flag_uuid)
        )).scalar_one_or_none()
        if assignment:
            assignment.status = AssignmentStatus.ESCALATED
            if reason:
                assignment.notes = reason

        await db.flush()
        return flag

    # ------------------------------------------------------------------
    # Recurring flag detection
    # ------------------------------------------------------------------
    async def detect_recurring_flags(
        self,
        meeting_id: str,
        db: AsyncSession,
    ) -> int:
        """Detect recurring flags by comparing with the previous meeting.

        A flag recurs if same category + field_name + field_value existed
        in the previous meeting for the same store and was not adequately
        resolved (status != responded).

        For recurring flags: links via previous_flag_id, increments
        escalation_level, upgrades severity to red, appends RECURRING tag.

        Returns count of recurring flags detected.
        """
        meeting_uuid = uuid.UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id

        # Get current meeting + store
        meeting = (await db.execute(
            select(Meeting).where(Meeting.id == meeting_uuid)
        )).scalar_one_or_none()
        if not meeting:
            return 0

        # Find previous meeting for same store (by date)
        prev_meeting = (await db.execute(
            select(Meeting)
            .where(
                and_(
                    Meeting.store_id == meeting.store_id,
                    Meeting.meeting_date < meeting.meeting_date,
                )
            )
            .order_by(Meeting.meeting_date.desc())
            .limit(1)
        )).scalar_one_or_none()

        if not prev_meeting:
            return 0

        # Load previous meeting's flags
        prev_flags_result = await db.execute(
            select(Flag).where(Flag.meeting_id == prev_meeting.id)
        )
        prev_flags = list(prev_flags_result.scalars().all())

        # Index previous flags by (category, field_name, field_value)
        prev_index: dict[tuple, Flag] = {}
        for pf in prev_flags:
            key = (pf.category.value, pf.field_name, pf.field_value or "")
            prev_index[key] = pf

        # Load current meeting's flags
        curr_flags_result = await db.execute(
            select(Flag).where(Flag.meeting_id == meeting_uuid)
        )
        curr_flags = list(curr_flags_result.scalars().all())

        recurring_count = 0
        for cf in curr_flags:
            key = (cf.category.value, cf.field_name, cf.field_value or "")
            prev_flag = prev_index.get(key)

            if prev_flag and prev_flag.status != FlagStatus.RESPONDED:
                cf.previous_flag_id = prev_flag.id
                cf.escalation_level = prev_flag.escalation_level + 1
                cf.severity = FlagSeverity.RED
                occurrence = cf.escalation_level + 1
                if " (RECURRING" not in cf.message:
                    cf.message += f" (RECURRING — Meeting #{occurrence})"
                recurring_count += 1

        if recurring_count > 0:
            await db.flush()

        return recurring_count

"""
SLA Service — manages task creation, SLA checkpoints, and work hours calculation.
Implements BUSINESS_RULES.md §10-§17.
"""

import logging
import uuid
from datetime import datetime, timedelta, time
from typing import Optional, List

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Task, SLACheckpoint, TaskEvent, User, RoutingRule
from src.utils.config import settings

logger = logging.getLogger(__name__)

# SLA durations by priority (in work hours for P1-P3, calendar hours for P0)
SLA_DURATIONS = {
    "P0": 2,    # 2 calendar hours (24/7)
    "P1": 8,    # 8 work hours
    "P2": 24,   # 24 work hours
    "P3": 12,   # 12 work hours
}

# Escalation thresholds after 100% SLA breach (in hours)
ESCALATION_HOURS = {
    "+24h": 24,
    "+48h": 48,
    "+72h": 72,
}

# Work hours configuration
WORK_START = time(9, 0)   # 09:00
WORK_END = time(18, 0)    # 18:00
WORK_HOURS_PER_DAY = 9    # hours


class SLAService:
    """Manages SLA lifecycle: creation, checkpoints, pauses, escalation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ================================================================
    # TASK CREATION
    # ================================================================

    async def create_task(
        self,
        title: str,
        description: str,
        task_type: str,
        priority: str,
        creator_id: uuid.UUID,
        assignee_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        department_id: Optional[uuid.UUID] = None,
    ) -> Task:
        """
        Create a new task with SLA checkpoints.

        Returns the created Task object.
        """
        now = datetime.utcnow()
        sla_hours = SLA_DURATIONS.get(priority, 24)
        sla_due = self._calculate_due_date(now, sla_hours, priority)

        task = Task(
            id=uuid.uuid4(),
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            creator_id=creator_id,
            assignee_id=assignee_id,
            project_id=project_id,
            department_id=department_id,
            status="new",
            sla_version=1,
            sla_due_at=sla_due,
            deadline=sla_due,
            created_at=now,
        )

        self.session.add(task)

        # Create initial event
        event = TaskEvent(
            id=uuid.uuid4(),
            task_id=task.id,
            event_type="created",
            actor_id=creator_id,
            new_value=f"priority={priority}, type={task_type}",
            created_at=now,
        )
        self.session.add(event)

        # Generate SLA checkpoints
        await self._create_checkpoints(task.id, now, sla_due, priority, sla_version=1)

        await self.session.commit()
        logger.info(f"Task created: {task.id} [{task_type}/{priority}] due={sla_due}")
        return task

    # ================================================================
    # CHECKPOINT GENERATION
    # ================================================================

    async def _create_checkpoints(
        self,
        task_id: uuid.UUID,
        created_at: datetime,
        sla_due: datetime,
        priority: str,
        sla_version: int,
    ):
        """Create 6 SLA checkpoints for a task."""
        total_duration = sla_due - created_at

        # Pre-breach checkpoints (based on % of SLA)
        checkpoints_data = [
            ("50%", created_at + total_duration * 0.5),
            ("80%", created_at + total_duration * 0.8),
            ("100%", sla_due),
        ]

        # Post-breach escalation checkpoints
        for label, hours in ESCALATION_HOURS.items():
            if priority == "P0":
                # P0: calendar hours
                escalation_time = sla_due + timedelta(hours=hours)
            else:
                # P1-P3: work hours
                escalation_time = self._add_work_hours(sla_due, hours)
            checkpoints_data.append((label, escalation_time))

        for threshold, check_at in checkpoints_data:
            checkpoint = SLACheckpoint(
                id=uuid.uuid4(),
                task_id=task_id,
                threshold=threshold,
                next_check_at=check_at,
                is_processed=False,
                sla_version=sla_version,
            )
            self.session.add(checkpoint)

    # ================================================================
    # PAUSE / RESUME
    # ================================================================

    async def pause_task(
        self,
        task_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
    ):
        """
        Pause a task. SLA timer stops.
        §17.1: sla_version does NOT change. Only unprocessed checkpoints shift.
        """
        now = datetime.utcnow()

        stmt = (
            update(Task)
            .where(Task.id == task_id)
            .values(status="paused", paused_at=now, pause_reason=reason)
        )
        await self.session.execute(stmt)

        # Log event
        event = TaskEvent(
            id=uuid.uuid4(),
            task_id=task_id,
            event_type="paused",
            actor_id=actor_id,
            comment=reason,
            created_at=now,
        )
        self.session.add(event)
        await self.session.commit()
        logger.info(f"Task {task_id} paused: {reason}")

    async def resume_task(
        self,
        task_id: uuid.UUID,
        actor_id: uuid.UUID,
    ):
        """
        Resume a paused task. Shift unprocessed checkpoints by pause duration.
        §17.1: sla_version does NOT change.
        """
        now = datetime.utcnow()

        # Get task to find paused_at
        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one()

        if not task.paused_at:
            logger.warning(f"Task {task_id} is not paused")
            return

        pause_duration = now - task.paused_at

        # Shift unprocessed checkpoints
        result = await self.session.execute(
            select(SLACheckpoint).where(
                and_(
                    SLACheckpoint.task_id == task_id,
                    SLACheckpoint.is_processed == False,
                    SLACheckpoint.sla_version == task.sla_version,
                )
            )
        )
        checkpoints = result.scalars().all()

        for cp in checkpoints:
            cp.next_check_at = cp.next_check_at + pause_duration

        # Also shift sla_due_at
        new_due = task.sla_due_at + pause_duration

        stmt = (
            update(Task)
            .where(Task.id == task_id)
            .values(
                status="in_progress",
                paused_at=None,
                pause_reason=None,
                sla_due_at=new_due,
                deadline=new_due,
            )
        )
        await self.session.execute(stmt)

        # Log event
        event = TaskEvent(
            id=uuid.uuid4(),
            task_id=task_id,
            event_type="resumed",
            actor_id=actor_id,
            comment=f"Paused for {pause_duration}",
            created_at=now,
        )
        self.session.add(event)
        await self.session.commit()
        logger.info(f"Task {task_id} resumed. Checkpoints shifted by {pause_duration}")

    # ================================================================
    # REASSIGN / CHANGE PRIORITY
    # ================================================================

    async def reassign_task(
        self,
        task_id: uuid.UUID,
        new_assignee_id: uuid.UUID,
        actor_id: uuid.UUID,
    ):
        """
        Reassign task. §14.5 / §17.1: sla_version increases,
        old unprocessed checkpoints annulled, new set created.
        """
        now = datetime.utcnow()

        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one()

        old_assignee = str(task.assignee_id)
        new_version = task.sla_version + 1

        # Annul old unprocessed checkpoints
        await self._annul_checkpoints(task_id, task.sla_version)

        # Update task
        new_due = self._calculate_due_date(now, SLA_DURATIONS[task.priority], task.priority)
        stmt = (
            update(Task)
            .where(Task.id == task_id)
            .values(
                assignee_id=new_assignee_id,
                sla_version=new_version,
                sla_due_at=new_due,
                deadline=new_due,
            )
        )
        await self.session.execute(stmt)

        # Create new checkpoints
        await self._create_checkpoints(task_id, now, new_due, task.priority, new_version)

        # Log event
        event = TaskEvent(
            id=uuid.uuid4(),
            task_id=task_id,
            event_type="reassigned",
            actor_id=actor_id,
            old_value=old_assignee,
            new_value=str(new_assignee_id),
            created_at=now,
        )
        self.session.add(event)
        await self.session.commit()
        logger.info(f"Task {task_id} reassigned. New SLA version: {new_version}")

    # ================================================================
    # HELPER: WORK HOURS CALCULATION
    # ================================================================

    def _calculate_due_date(
        self,
        start: datetime,
        hours: int,
        priority: str,
    ) -> datetime:
        """Calculate due date considering work hours (P1-P3) or calendar (P0)."""
        if priority == "P0":
            return start + timedelta(hours=hours)
        return self._add_work_hours(start, hours)

    def _add_work_hours(self, start: datetime, hours: int) -> datetime:
        """
        Add N work hours to a datetime, skipping non-work time.
        Work hours: 09:00-18:00, Mon-Fri (simplified, no holiday calendar yet).
        """
        remaining = hours
        current = start

        while remaining > 0:
            # If outside work hours, advance to next work start
            if current.time() < WORK_START:
                current = current.replace(
                    hour=WORK_START.hour, minute=0, second=0, microsecond=0
                )
            elif current.time() >= WORK_END:
                # Move to next day 09:00
                current = current + timedelta(days=1)
                current = current.replace(
                    hour=WORK_START.hour, minute=0, second=0, microsecond=0
                )
                # Skip weekends
                while current.weekday() >= 5:
                    current = current + timedelta(days=1)
                continue

            # Skip weekends
            if current.weekday() >= 5:
                current = current + timedelta(days=1)
                current = current.replace(
                    hour=WORK_START.hour, minute=0, second=0, microsecond=0
                )
                continue

            # Calculate available hours today
            end_of_day = current.replace(
                hour=WORK_END.hour, minute=0, second=0, microsecond=0
            )
            available = (end_of_day - current).total_seconds() / 3600

            if remaining <= available:
                current = current + timedelta(hours=remaining)
                remaining = 0
            else:
                remaining -= available
                # Move to next work day
                current = current + timedelta(days=1)
                current = current.replace(
                    hour=WORK_START.hour, minute=0, second=0, microsecond=0
                )
                # Skip weekends
                while current.weekday() >= 5:
                    current = current + timedelta(days=1)

        return current

    # ================================================================
    # HELPER: ANNUL CHECKPOINTS
    # ================================================================

    async def _annul_checkpoints(self, task_id: uuid.UUID, sla_version: int):
        """Mark all unprocessed checkpoints as processed (annulled)."""
        stmt = (
            update(SLACheckpoint)
            .where(
                and_(
                    SLACheckpoint.task_id == task_id,
                    SLACheckpoint.sla_version == sla_version,
                    SLACheckpoint.is_processed == False,
                )
            )
            .values(is_processed=True)
        )
        await self.session.execute(stmt)

"""
Database models for A1 AI System.
11 tables as defined in BUSINESS_RULES.md §16.
"""

import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date,
    ForeignKey, Text, Float, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ============================================================
# 1. USERS
# ============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(String, unique=True, nullable=True)
    phone_number = Column(String(20), unique=True, nullable=False)  # E.164 format
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # admin, top_manager, manager, worker
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    departments = relationship("UserDepartment", back_populates="user")
    projects = relationship("UserProject", back_populates="user")


# ============================================================
# 2. DEPARTMENTS
# ============================================================
class Department(Base):
    __tablename__ = "departments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    head_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    head = relationship("User", foreign_keys=[head_id])
    members = relationship("UserDepartment", back_populates="department")


# ============================================================
# 3. USER_DEPARTMENTS (many-to-many)
# ============================================================
class UserDepartment(Base):
    __tablename__ = "user_departments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "department_id", name="uq_user_department"),
    )

    user = relationship("User", back_populates="departments")
    department = relationship("Department", back_populates="members")


# ============================================================
# 4. PROJECTS (строительные объекты)
# ============================================================
class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status = Column(String(50), default="active")  # active, completed, paused
    created_at = Column(DateTime, default=datetime.utcnow)

    manager = relationship("User", foreign_keys=[manager_id])
    members = relationship("UserProject", back_populates="project")


# ============================================================
# 5. USER_PROJECTS (many-to-many with default flag)
# ============================================================
class UserProject(Base):
    __tablename__ = "user_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    is_default = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project"),
    )

    user = relationship("User", back_populates="projects")
    project = relationship("Project", back_populates="members")


# ============================================================
# 6. ROUTING_RULES (матрица назначения)
# ============================================================
class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(50), nullable=False)  # safety, procurement, hr, etc.
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    default_assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    default_priority = Column(String(5), default="P2")  # P0, P1, P2, P3

    __table_args__ = (
        Index("ix_routing_task_project", "task_type", "project_id"),
    )

    department = relationship("Department")
    default_assignee = relationship("User", foreign_keys=[default_assignee_id])
    project = relationship("Project")


# ============================================================
# 7. TASKS (задачи)
# ============================================================
class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), nullable=False)
    source = Column(String(50), default="telegram")  # telegram, manual, system

    # People
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Context
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)

    # Status and priority
    status = Column(String(20), default="new")  # new, in_progress, paused, done, cancelled
    priority = Column(String(5), nullable=False)  # P0, P1, P2, P3

    # SLA
    sla_version = Column(Integer, default=1)
    remaining_sla_seconds = Column(Integer, nullable=True)
    sla_due_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)

    # Metadata
    pause_reason = Column(Text, nullable=True)
    close_comment = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_assignee", "assignee_id"),
        Index("ix_tasks_sla_due", "sla_due_at"),
    )

    creator = relationship("User", foreign_keys=[creator_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    project = relationship("Project")
    department = relationship("Department")
    events = relationship("TaskEvent", back_populates="task", order_by="TaskEvent.created_at")
    checkpoints = relationship("SLACheckpoint", back_populates="task")


# ============================================================
# 8. TASK_EVENTS (неизменяемая история)
# ============================================================
class TaskEvent(Base):
    __tablename__ = "task_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    # Types: created, accepted, paused, resumed, completed, cancelled,
    #        reassigned, priority_changed, deadline_changed, extension_requested,
    #        extension_approved, extension_rejected
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="events")
    actor = relationship("User")


# ============================================================
# 9. SLA_CHECKPOINTS (контрольные точки)
# ============================================================
class SLACheckpoint(Base):
    __tablename__ = "sla_checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    threshold = Column(String(10), nullable=False)  # 50%, 80%, 100%, +24h, +48h, +72h
    next_check_at = Column(DateTime, nullable=False)
    is_processed = Column(Boolean, default=False)
    sla_version = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sla_pending", "next_check_at", "is_processed"),
        UniqueConstraint("task_id", "threshold", "sla_version", name="uq_sla_checkpoint"),
    )

    task = relationship("Task", back_populates="checkpoints")


# ============================================================
# 10. NOTIFICATION_LOG (журнал уведомлений)
# ============================================================
class NotificationLog(Base):
    __tablename__ = "notification_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    threshold = Column(String(10), nullable=False)
    sla_version = Column(Integer, nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    message_text = Column(Text, nullable=True)
    telegram_message_id = Column(String, nullable=True)
    status = Column(String(20), default="sent")  # sent, failed, retrying
    sent_at = Column(DateTime, default=datetime.utcnow)
    retry_count = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("task_id", "threshold", "sla_version", "recipient_id",
                         name="uq_notification_dedup"),
    )


# ============================================================
# 11. WORK_CALENDAR (производственный календарь)
# ============================================================
class WorkCalendar(Base):
    __tablename__ = "work_calendar"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, unique=True, nullable=False)
    is_workday = Column(Boolean, nullable=False)
    description = Column(String(255), nullable=True)  # e.g., "Новый год"

    __table_args__ = (
        Index("ix_calendar_date", "date"),
    )

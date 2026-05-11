from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.phases import Phase
    from app.models.sub_projects import SubProject
    from app.models.users import User


class TaskStatus(enum.StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    overdue = "overdue"
    completed = "completed"


class Task(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_sub_project_phase", "sub_project_id", "phase_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_status_plan_end_date", "status", "plan_end_date"),
    )

    task_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    sub_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    phase_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("phases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=enum_values),
        nullable=False,
        default=TaskStatus.not_started,
        server_default=TaskStatus.not_started.value,
    )

    sub_project: Mapped[SubProject] = relationship()
    phase: Mapped[Phase] = relationship()
    executors: Mapped[list[TaskExecutor]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskExecutor(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_executors"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_executors_task_user"),
        Index("ix_task_executors_status", "status"),
        Index("ix_task_executors_user_status", "user_id", "status"),
    )

    task_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=enum_values),
        nullable=False,
        default=TaskStatus.not_started,
        server_default=TaskStatus.not_started.value,
    )

    task: Mapped[Task] = relationship(back_populates="executors")
    user: Mapped[User] = relationship()

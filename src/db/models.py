"""SQLAlchemy models for VC Scout"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class JobStatus(str, PyEnum):
    """Status of a research job"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Session(Base):
    """Anonymous user session for tracking history"""
    
    __tablename__ = "sessions"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    session_token: Mapped[str] = mapped_column(
        String(64), 
        unique=True, 
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Relationships
    jobs: Mapped[list["Job"]] = relationship(
        "Job", 
        back_populates="session",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Session {self.session_token[:8]}...>"


class Job(Base):
    """A market validation research job"""
    
    __tablename__ = "jobs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True
    )
    original_idea: Mapped[str] = mapped_column(Text)
    current_idea: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), 
        default=JobStatus.PENDING
    )
    pivot_attempts: Mapped[int] = mapped_column(Integer, default=0)
    final_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    
    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="jobs")
    steps: Mapped[list["JobStep"]] = relationship(
        "JobStep",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobStep.timestamp"
    )
    pivot_history: Mapped[list["PivotHistory"]] = relationship(
        "PivotHistory",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="PivotHistory.attempt_num"
    )
    
    def __repr__(self) -> str:
        return f"<Job {self.id} - {self.status.value}>"


class JobStep(Base):
    """Individual node execution within a job"""
    
    __tablename__ = "job_steps"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        index=True
    )
    node_name: Mapped[str] = mapped_column(String(64))
    pivot_attempt: Mapped[int] = mapped_column(Integer, default=0)
    input_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="steps")
    
    def __repr__(self) -> str:
        return f"<JobStep {self.node_name} @ pivot {self.pivot_attempt}>"


class PivotHistory(Base):
    """Record of pivot decisions made during analysis"""
    
    __tablename__ = "pivot_history"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        index=True
    )
    attempt_num: Mapped[int] = mapped_column(Integer)
    original_idea: Mapped[str] = mapped_column(Text)
    suggested_pivot: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="pivot_history")
    
    def __repr__(self) -> str:
        return f"<PivotHistory #{self.attempt_num} score={self.score}>"

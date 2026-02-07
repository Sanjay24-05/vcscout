"""Repository layer for database operations"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Job, JobStatus, JobStep, PivotHistory, Session


class SessionRepository:
    """Repository for Session operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create(self, session_token: str) -> Session:
        """Get existing session or create new one"""
        stmt = select(Session).where(Session.session_token == session_token)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session is None:
            session = Session(session_token=session_token)
            self.db.add(session)
            await self.db.flush()
        
        return session
    
    async def get_by_token(self, session_token: str) -> Session | None:
        """Get session by token"""
        stmt = select(Session).where(Session.session_token == session_token)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class JobRepository:
    """Repository for Job operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self, 
        session_id: uuid.UUID, 
        idea: str
    ) -> Job:
        """Create a new job"""
        job = Job(
            session_id=session_id,
            original_idea=idea,
            current_idea=idea,
            status=JobStatus.PENDING,
            pivot_attempts=0,
        )
        self.db.add(job)
        await self.db.flush()
        return job
    
    async def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        """Get job by ID with all relationships loaded"""
        stmt = (
            select(Job)
            .where(Job.id == job_id)
            .options(
                selectinload(Job.steps),
                selectinload(Job.pivot_history),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_session(
        self, 
        session_id: uuid.UUID,
        limit: int = 20
    ) -> list[Job]:
        """Get jobs for a session, most recent first"""
        stmt = (
            select(Job)
            .where(Job.session_id == session_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def update_status(
        self, 
        job_id: uuid.UUID, 
        status: JobStatus,
        error_message: str | None = None
    ) -> None:
        """Update job status"""
        job = await self.get_by_id(job_id)
        if job:
            job.status = status
            if status == JobStatus.COMPLETED or status == JobStatus.FAILED:
                job.completed_at = datetime.now(timezone.utc)
            if error_message:
                job.error_message = error_message
            await self.db.flush()
    
    async def update_current_idea(
        self, 
        job_id: uuid.UUID, 
        new_idea: str,
        pivot_attempts: int
    ) -> None:
        """Update the current idea after a pivot"""
        job = await self.get_by_id(job_id)
        if job:
            job.current_idea = new_idea
            job.pivot_attempts = pivot_attempts
            await self.db.flush()
    
    async def set_final_report(
        self, 
        job_id: uuid.UUID, 
        report: str
    ) -> None:
        """Set the final report"""
        job = await self.get_by_id(job_id)
        if job:
            job.final_report = report
            await self.db.flush()


class JobStepRepository:
    """Repository for JobStep operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        job_id: uuid.UUID,
        node_name: str,
        pivot_attempt: int,
        input_state: dict[str, Any],
        output_state: dict[str, Any],
        duration_ms: int | None = None,
        error: str | None = None,
    ) -> JobStep:
        """Record a node execution step"""
        step = JobStep(
            job_id=job_id,
            node_name=node_name,
            pivot_attempt=pivot_attempt,
            input_state=input_state,
            output_state=output_state,
            duration_ms=duration_ms,
            error=error,
        )
        self.db.add(step)
        await self.db.flush()
        return step
    
    async def get_by_job(self, job_id: uuid.UUID) -> list[JobStep]:
        """Get all steps for a job"""
        stmt = (
            select(JobStep)
            .where(JobStep.job_id == job_id)
            .order_by(JobStep.timestamp)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class PivotHistoryRepository:
    """Repository for PivotHistory operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        job_id: uuid.UUID,
        attempt_num: int,
        original_idea: str,
        suggested_pivot: str,
        reason: str,
        score: int,
    ) -> PivotHistory:
        """Record a pivot decision"""
        pivot = PivotHistory(
            job_id=job_id,
            attempt_num=attempt_num,
            original_idea=original_idea,
            suggested_pivot=suggested_pivot,
            reason=reason,
            score=score,
        )
        self.db.add(pivot)
        await self.db.flush()
        return pivot
    
    async def get_by_job(self, job_id: uuid.UUID) -> list[PivotHistory]:
        """Get pivot history for a job"""
        stmt = (
            select(PivotHistory)
            .where(PivotHistory.job_id == job_id)
            .order_by(PivotHistory.attempt_num)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

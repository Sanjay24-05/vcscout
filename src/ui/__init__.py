"""Streamlit UI components and helpers"""

import asyncio
import uuid
from datetime import datetime
from typing import Any

import streamlit as st

from src.db.connection import get_session, init_db
from src.db.models import JobStatus
from src.db.repository import JobRepository, PivotHistoryRepository, SessionRepository


def get_or_create_session_token() -> str:
    """Get or create a session token for the current user"""
    if "session_token" not in st.session_state:
        st.session_state.session_token = str(uuid.uuid4())
    return st.session_state.session_token


async def ensure_db_session(session_token: str) -> uuid.UUID:
    """Ensure the session exists in the database and return its ID"""
    async with get_session() as db:
        session_repo = SessionRepository(db)
        session = await session_repo.get_or_create(session_token)
        return session.id


async def get_session_jobs(session_token: str) -> list[dict[str, Any]]:
    """Get all jobs for the current session"""
    async with get_session() as db:
        session_repo = SessionRepository(db)
        session = await session_repo.get_by_token(session_token)
        
        if not session:
            return []
        
        job_repo = JobRepository(db)
        jobs = await job_repo.get_by_session(session.id)
        
        return [
            {
                "id": str(job.id),
                "original_idea": job.original_idea[:50] + "..." if len(job.original_idea) > 50 else job.original_idea,
                "status": job.status.value,
                "pivot_attempts": job.pivot_attempts,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
                "has_report": job.final_report is not None,
            }
            for job in jobs
        ]


async def get_job_details(job_id: str) -> dict[str, Any] | None:
    """Get full job details including steps and pivot history"""
    async with get_session() as db:
        job_repo = JobRepository(db)
        job = await job_repo.get_by_id(uuid.UUID(job_id))
        
        if not job:
            return None
        
        pivot_repo = PivotHistoryRepository(db)
        pivots = await pivot_repo.get_by_job(job.id)
        
        return {
            "id": str(job.id),
            "original_idea": job.original_idea,
            "current_idea": job.current_idea,
            "status": job.status.value,
            "pivot_attempts": job.pivot_attempts,
            "final_report": job.final_report,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "steps": [
                {
                    "node_name": step.node_name,
                    "pivot_attempt": step.pivot_attempt,
                    "duration_ms": step.duration_ms,
                    "error": step.error,
                    "timestamp": step.timestamp,
                }
                for step in job.steps
            ],
            "pivot_history": [
                {
                    "attempt_num": pivot.attempt_num,
                    "original_idea": pivot.original_idea,
                    "suggested_pivot": pivot.suggested_pivot,
                    "reason": pivot.reason,
                    "score": pivot.score,
                    "timestamp": pivot.timestamp,
                }
                for pivot in pivots
            ],
        }


def render_thought_trace(job_details: dict[str, Any]) -> None:
    """Render the thought trace, debate transcript, and pivot history expander"""
    
    with st.expander("🧠 Thought Trace & Pivot History", expanded=False):
        steps = job_details.get("steps", [])
        pivots = job_details.get("pivot_history", [])
        
        if not steps and not pivots:
            st.info("No execution history available yet.")
            return
        
        # Timeline of steps
        st.markdown("### Execution Timeline")
        
        for step in steps:
            node_name = step["node_name"]
            duration = step.get("duration_ms", 0)
            error = step.get("error")
            pivot_num = step.get("pivot_attempt", 0)
            
            # Icon based on node
            icons = {
                "input_validator": "🛡️",
                "market_researcher": "🔍",
                "competitor_analyst": "📊",
                "debate_panel": "⚔️",
                "devils_advocate": "😈",
                "apply_pivot": "🔄",
                "writer": "✍️",
                "handle_invalid": "⚠️",
            }
            icon = icons.get(node_name, "⚙️")
            
            # Format
            if error:
                st.error(f"{icon} **{node_name}** (Pivot #{pivot_num}) - ❌ Failed: {error}")
            else:
                st.success(f"{icon} **{node_name}** (Pivot #{pivot_num}) - ✅ {duration}ms")
        
        # Check for debate result and show transcript
        _render_debate_transcript(job_details)
        
        # Pivot history
        if pivots:
            st.markdown("### Pivot Decisions")
            
            for pivot in pivots:
                st.markdown(f"""
**Pivot #{pivot['attempt_num']}** (Score: {pivot['score']}/10)

- **Before:** {pivot['original_idea']}
- **After:** {pivot['suggested_pivot']}
- **Reason:** {pivot['reason']}
---
""")


def _render_debate_transcript(job_details: dict[str, Any]) -> None:
    """Render the debate transcript if present in the job's output state"""
    # Look for debate_result in the steps' output states
    steps = job_details.get("steps", [])
    
    debate_transcript = None
    debate_result = None
    
    for step in steps:
        if step.get("node_name") == "debate_panel":
            # The output_state might contain debate_result
            output = step.get("output_state") or {}
            if "debate_result" in output:
                debate_result = output["debate_result"]
                debate_transcript = debate_result.get("debate_transcript", [])
                break
    
    if not debate_transcript and not debate_result:
        return
    
    st.markdown("### ⚔️ Debate Transcript")
    
    # Show summary cards
    if debate_result:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🐂 Bull Case (Investment Thesis)**")
            st.info(debate_result.get("bull_case", "N/A"))
        
        with col2:
            st.markdown("**🐻 Bear Case (Risk Analysis)**")
            st.warning(debate_result.get("bear_case", "N/A"))
        
        if debate_result.get("synthesis"):
            st.markdown("**⚖️ Synthesis**")
            st.markdown(debate_result["synthesis"])
        
        if debate_result.get("idea_was_pivoted"):
            st.success(f"**💡 Debate-Refined Idea:** {debate_result.get('final_idea', 'N/A')}")
    
    # Show full transcript in a sub-expander
    if debate_transcript:
        with st.expander("📜 Full Debate Transcript", expanded=False):
            for msg in debate_transcript:
                speaker = msg.get("speaker", "Unknown")
                content = msg.get("content", "")
                
                icons = {"Bull": "🐂", "Bear": "🐻", "Synthesizer": "⚖️"}
                icon = icons.get(speaker, "💬")
                
                st.markdown(f"**{icon} {speaker}:**")
                st.markdown(content)
                st.markdown("---")


def render_status_badge(status: str) -> str:
    """Return a colored status badge"""
    colors = {
        "pending": "🟡",
        "running": "🔵",
        "validating": "🛡️",
        "validated": "✅",
        "invalid_input": "⚠️",
        "researching": "🔍",
        "debating": "⚔️",
        "writing": "✍️",
        "completed": "🟢",
        "failed": "🔴",
    }
    # Format status for display
    display_status = status.replace("_", " ").capitalize()
    return f"{colors.get(status, '⚪')} {display_status}"


def format_timestamp(dt: datetime | None) -> str:
    """Format a timestamp for display"""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

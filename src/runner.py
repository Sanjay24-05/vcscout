"""Job runner for executing the LangGraph analysis"""

import asyncio
import uuid
from datetime import datetime, timezone

from src.db.connection import get_session
from src.db.models import JobStatus
from src.db.repository import JobRepository, PivotHistoryRepository
from src.graph.builder import get_compiled_graph
from src.graph.state import create_initial_state


async def create_and_run_job(
    session_id: uuid.UUID,
    idea: str,
    progress_callback=None,
) -> dict:
    """
    Create a new job and run the analysis graph.
    
    Args:
        session_id: The session ID
        idea: The startup idea to analyze
        progress_callback: Optional callback for progress updates
        
    Returns:
        The final job details
    """
    # Create job in database
    async with get_session() as db:
        job_repo = JobRepository(db)
        job = await job_repo.create(session_id, idea)
        job_id = job.id
    
    # Update job status to running
    async with get_session() as db:
        job_repo = JobRepository(db)
        await job_repo.update_status(job_id, JobStatus.RUNNING)
    
    if progress_callback:
        progress_callback("Job created, starting analysis...")
    
    try:
        # Create initial state
        initial_state = create_initial_state(
            job_id=str(job_id),
            session_id=str(session_id),
            idea=idea,
        )
        
        # Get the compiled graph
        graph = get_compiled_graph()
        
        # Run the graph
        final_state = None
        async for state in graph.astream(initial_state):
            # state is a dict with node name as key
            for node_name, node_state in state.items():
                # Skip if node_state is None
                if node_state is None:
                    continue
                    
                if progress_callback:
                    status = node_state.get("status", "processing") if isinstance(node_state, dict) else "processing"
                    progress_callback(f"Completed: {node_name} (Status: {status})")
                
                # Track the latest state
                if isinstance(node_state, dict):
                    if final_state is None:
                        final_state = {**initial_state}
                    final_state.update(node_state)
        
        # Check for errors in final state
        if final_state and final_state.get("status") == "failed":
            error_msg = final_state.get("error", "Unknown error")
            async with get_session() as db:
                job_repo = JobRepository(db)
                await job_repo.update_status(job_id, JobStatus.FAILED, error_msg)
            return {"job_id": str(job_id), "status": "failed", "error": error_msg}
        
        # Save final report and pivot history
        if final_state:
            async with get_session() as db:
                job_repo = JobRepository(db)
                
                # Update current idea and pivot count
                await job_repo.update_current_idea(
                    job_id,
                    final_state.get("current_idea", idea),
                    final_state.get("pivot_attempts", 0),
                )
                
                # Save final report
                if final_state.get("final_report"):
                    # Replace timestamp placeholder
                    report = final_state["final_report"].replace(
                        "{timestamp}",
                        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    )
                    await job_repo.set_final_report(job_id, report)
                
                # Save pivot history
                pivot_history = final_state.get("pivot_history", [])
                if pivot_history:
                    pivot_repo = PivotHistoryRepository(db)
                    for pivot in pivot_history:
                        await pivot_repo.create(
                            job_id=job_id,
                            attempt_num=pivot["attempt_num"],
                            original_idea=pivot["original_idea"],
                            suggested_pivot=pivot["pivoted_idea"],
                            reason=pivot["reason"],
                            score=pivot["score"],
                        )
                
                # Mark as completed
                await job_repo.update_status(job_id, JobStatus.COMPLETED)
        
        if progress_callback:
            progress_callback("Analysis complete!")
        
        return {
            "job_id": str(job_id),
            "status": "completed",
            "report_type": final_state.get("report_type") if final_state else None,
        }
        
    except Exception as e:
        error_msg = str(e)
        async with get_session() as db:
            job_repo = JobRepository(db)
            await job_repo.update_status(job_id, JobStatus.FAILED, error_msg)
        
        if progress_callback:
            progress_callback(f"Error: {error_msg}")
        
        return {"job_id": str(job_id), "status": "failed", "error": error_msg}

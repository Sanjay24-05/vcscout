"""LangGraph node wrappers with persistence and error handling"""

import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from src.db.connection import get_session
from src.db.repository import JobStepRepository
from src.graph.state import AgentState


def create_node_wrapper(
    node_fn: Callable[[AgentState], Coroutine[Any, Any, dict]],
    node_name: str,
) -> Callable[[AgentState], Coroutine[Any, Any, dict]]:
    """
    Wrap a node function with persistence and error handling.
    
    This wrapper:
    1. Records the start time
    2. Executes the node function
    3. Saves the step to the database
    4. Handles errors gracefully
    """
    
    async def wrapped_node(state: AgentState) -> dict:
        start_time = time.time()
        job_id = state.get("job_id")
        pivot_attempt = state.get("pivot_attempts", 0)
        
        # Prepare minimal input state for logging (avoid huge payloads)
        input_state_log = {
            "current_idea": state.get("current_idea"),
            "pivot_attempts": pivot_attempt,
            "status": state.get("status"),
        }
        
        try:
            # Execute the actual node
            result = await node_fn(state)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Update timestamp
            result["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Save step to database
            if job_id:
                try:
                    async with get_session() as session:
                        step_repo = JobStepRepository(session)
                        await step_repo.create(
                            job_id=job_id,
                            node_name=node_name,
                            pivot_attempt=pivot_attempt,
                            input_state=input_state_log,
                            output_state=_sanitize_for_json(result),
                            duration_ms=duration_ms,
                        )
                except Exception as db_error:
                    # Don't fail the node if DB logging fails
                    print(f"Warning: Failed to save step to DB: {db_error}")
            
            return result
            
        except Exception as e:
            # Calculate duration even on error
            duration_ms = int((time.time() - start_time) * 1000)
            error_message = str(e)
            
            # Save error step to database
            if job_id:
                try:
                    async with get_session() as session:
                        step_repo = JobStepRepository(session)
                        await step_repo.create(
                            job_id=job_id,
                            node_name=node_name,
                            pivot_attempt=pivot_attempt,
                            input_state=input_state_log,
                            output_state={},
                            duration_ms=duration_ms,
                            error=error_message,
                        )
                except Exception as db_error:
                    print(f"Warning: Failed to save error step to DB: {db_error}")
            
            # Return error state instead of raising
            return {
                "status": "failed",
                "error": f"Node '{node_name}' failed: {error_message}",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
    
    return wrapped_node


def _sanitize_for_json(data: dict) -> dict:
    """Remove or truncate large fields for JSON storage"""
    result = {}
    for key, value in data.items():
        if isinstance(value, str) and len(value) > 5000:
            # Truncate very long strings
            result[key] = value[:5000] + "... [truncated]"
        elif isinstance(value, dict):
            result[key] = _sanitize_for_json(value)
        elif isinstance(value, list):
            # Truncate long lists
            if len(value) > 20:
                result[key] = value[:20] + ["... [truncated]"]
            else:
                result[key] = value
        else:
            result[key] = value
    return result

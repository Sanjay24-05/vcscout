"""Conditional edge logic for the LangGraph state machine"""

from datetime import datetime, timezone
from typing import Literal

from src.config import get_settings
from src.graph.state import AgentState


def should_pivot_or_proceed(
    state: AgentState,
) -> Literal["pivot", "write_success", "write_failure"]:
    """
    Determine the next step after Devil's Advocate evaluation.
    
    Returns:
    - "pivot": Score <= threshold AND pivots remaining → loop back to research
    - "write_success": Score > threshold → proceed to write investment memo
    - "write_failure": Score <= threshold AND no pivots remaining → write market reality report
    """
    settings = get_settings()
    
    # Check if there was an error in previous node
    if state.get("status") == "failed":
        return "write_failure"
    
    feedback = state.get("devils_advocate_feedback") or {}
    score = feedback.get("score", 0) if feedback else 0
    pivot_attempts = state.get("pivot_attempts", 0)
    
    # Check if the idea passed
    if score > settings.pivot_threshold:
        return "write_success"
    
    # Check if we can still pivot
    if pivot_attempts < settings.max_pivot_attempts:
        return "pivot"
    
    # No more pivots, generate market reality report
    return "write_failure"


def apply_pivot(state: AgentState) -> dict:
    """
    Apply a pivot to the current idea.
    
    This function:
    1. Extracts the suggested pivot from Devil's Advocate feedback
    2. Updates the current_idea
    3. Increments pivot_attempts
    4. Records the pivot in history
    """
    settings = get_settings()
    
    feedback = state.get("devils_advocate_feedback") or {}
    current_idea = state.get("current_idea", "")
    pivot_attempts = state.get("pivot_attempts", 0)
    
    # Get the suggested pivot
    suggested_pivot = feedback.get("suggested_pivot") if feedback else None
    if not suggested_pivot:
        # If no pivot suggested, use the pivot rationale or a generic refinement
        suggested_pivot = (feedback.get("pivot_rationale") if feedback else None) or f"Refined version of: {current_idea}"
    
    # Create pivot record
    pivot_record = {
        "attempt_num": pivot_attempts + 1,
        "original_idea": current_idea,
        "pivoted_idea": suggested_pivot,
        "reason": feedback.get("reason") or "Score below threshold",
        "score": feedback.get("score") or 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    return {
        "current_idea": suggested_pivot,
        "pivot_attempts": pivot_attempts + 1,
        "pivot_history": [pivot_record],  # Will be merged by reducer
        "status": "pivoting",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        # Clear previous research for fresh analysis
        "market_research": None,
        "competitor_analysis": None,
        "devils_advocate_feedback": None,
    }

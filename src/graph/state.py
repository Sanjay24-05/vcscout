"""Agent state and Pydantic models for the LangGraph state machine"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from typing_extensions import TypedDict


# ============================================================================
# Pydantic Models for Agent Outputs
# ============================================================================

class MarketResearchResult(BaseModel):
    """Output from the Market Researcher agent"""
    
    market_size_estimate: str = Field(
        description="Estimated TAM/SAM/SOM with sources"
    )
    growth_rate: str = Field(
        description="Market growth rate and trends"
    )
    key_trends: list[str] = Field(
        description="Top 3-5 market trends"
    )
    target_demographics: str = Field(
        description="Primary target market demographics"
    )
    market_maturity: Literal["emerging", "growing", "mature", "declining"] = Field(
        description="Current market lifecycle stage"
    )
    data_sources: list[str] = Field(
        description="URLs/sources used for research"
    )
    summary: str = Field(
        description="2-3 paragraph summary of market findings"
    )


class CompetitorProfile(BaseModel):
    """Profile of a single competitor"""
    
    name: str = Field(description="Company/product name")
    url: str = Field(description="Website URL")
    description: str = Field(description="Brief description of the company")
    key_features: list[str] = Field(description="Main features/offerings")
    pricing_model: str = Field(description="Pricing approach (free, freemium, subscription, etc.)")
    target_audience: str = Field(description="Who they target")
    strengths: list[str] = Field(description="Key strengths")
    weaknesses: list[str] = Field(description="Potential weaknesses or gaps")


class CompetitorAnalysisResult(BaseModel):
    """Output from the Competitor Analyst agent"""
    
    competitors: list[CompetitorProfile] = Field(
        description="List of analyzed competitors"
    )
    market_saturation: Literal["low", "medium", "high", "oversaturated"] = Field(
        description="Overall market saturation level"
    )
    differentiation_opportunities: list[str] = Field(
        description="Potential ways to differentiate"
    )
    barriers_to_entry: list[str] = Field(
        description="Key barriers to entering this market"
    )
    summary: str = Field(
        description="2-3 paragraph competitive landscape summary"
    )


class DevilsAdvocateFeedback(BaseModel):
    """Output from the Devil's Advocate agent"""
    
    score: int = Field(
        default=5,
        description="Viability score from 1 (terrible) to 10 (excellent)"
    )
    verdict: str = Field(
        default="pivot",
        description="Overall recommendation: invest, pivot, or reject"
    )
    reason: str = Field(
        default="Analysis incomplete",
        description="Detailed reasoning for the score/verdict"
    )
    key_risks: list[str] = Field(
        default_factory=list,
        description="Top risks identified"
    )
    key_opportunities: list[str] = Field(
        default_factory=list,
        description="Top opportunities identified"
    )
    suggested_pivot: str | None = Field(
        default=None,
        description="If score <= threshold, a specific pivot suggestion"
    )
    pivot_rationale: str | None = Field(
        default=None,
        description="Why this pivot would improve viability"
    )
    
    @field_validator('score', mode='before')
    @classmethod
    def clamp_score(cls, v):
        """Ensure score is within valid range"""
        if isinstance(v, str):
            try:
                v = int(v)
            except ValueError:
                return 5
        if v is None:
            return 5
        return max(1, min(10, int(v)))
    
    @field_validator('verdict', mode='before')
    @classmethod
    def normalize_verdict(cls, v):
        """Normalize verdict to valid values"""
        if v is None:
            return "pivot"
        v_lower = str(v).lower().strip()
        if "invest" in v_lower or "approve" in v_lower or "proceed" in v_lower:
            return "invest"
        elif "reject" in v_lower or "fail" in v_lower or "no" in v_lower:
            return "reject"
        return "pivot"


class InputValidationResult(BaseModel):
    """Output from the Input Validator agent"""
    
    is_valid: bool = Field(
        default=True,
        description="Whether the input is a valid startup idea"
    )
    rejection_reason: str | None = Field(
        default=None,
        description="If invalid, the reason for rejection"
    )
    suggested_reframe: str | None = Field(
        default=None,
        description="If valid but vague, a suggested more specific version"
    )


class DebateMessage(BaseModel):
    """A single message in the debate transcript"""
    
    speaker: str = Field(description="Agent name: Bull, Bear, or Synthesizer")
    content: str = Field(description="The message content")
    timestamp: str = Field(default="", description="When this was said")


class DebateResult(BaseModel):
    """Output from the Debate Panel - replaces DevilsAdvocateFeedback in debate mode"""
    
    # Final verdict
    score: int = Field(
        default=5,
        description="Final consensus score from 1 (reject) to 10 (strong invest)"
    )
    verdict: str = Field(
        default="pivot",
        description="Final verdict: invest, conditional_invest, or reject"
    )
    
    # The debated/refined idea (may be original or pivoted during debate)
    final_idea: str = Field(
        default="",
        description="The final idea after debate (may include refinements)"
    )
    idea_was_pivoted: bool = Field(
        default=False,
        description="Whether the debate resulted in a pivot"
    )
    
    # Debate summary
    bull_case: str = Field(
        default="",
        description="Summary of the Bull's arguments for investing"
    )
    bear_case: str = Field(
        default="",
        description="Summary of the Bear's arguments against"
    )
    synthesis: str = Field(
        default="",
        description="Synthesizer's balanced conclusion"
    )
    
    # Key insights from debate
    key_risks: list[str] = Field(
        default_factory=list,
        description="Top risks identified during debate"
    )
    key_opportunities: list[str] = Field(
        default_factory=list,
        description="Top opportunities identified during debate"
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations"
    )
    
    # Full transcript for transparency
    debate_transcript: list[DebateMessage] = Field(
        default_factory=list,
        description="Full debate transcript"
    )
    
    @field_validator('score', mode='before')
    @classmethod
    def clamp_score(cls, v):
        """Ensure score is within valid range"""
        if isinstance(v, str):
            try:
                v = int(v)
            except ValueError:
                return 5
        if v is None:
            return 5
        return max(1, min(10, int(v)))
    
    @field_validator('verdict', mode='before')
    @classmethod
    def normalize_verdict(cls, v):
        """Normalize verdict to valid values"""
        if v is None:
            return "conditional_invest"
        v_lower = str(v).lower().strip()
        if "strong" in v_lower or ("invest" in v_lower and "conditional" not in v_lower):
            return "invest"
        elif "reject" in v_lower or "fail" in v_lower or "no" in v_lower:
            return "reject"
        return "conditional_invest"


class PivotRecord(BaseModel):
    """Record of a pivot decision"""
    
    attempt_num: int
    original_idea: str
    pivoted_idea: str
    reason: str
    score: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# LangGraph State
# ============================================================================

def merge_pivot_history(
    existing: list[dict[str, Any]] | None,
    new: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Reducer for pivot_history - append new pivots"""
    existing = existing or []
    new = new or []
    return existing + new


class AgentState(TypedDict, total=False):
    """
    The shared state for the LangGraph state machine.
    
    This state is passed between all nodes and accumulates results
    from each agent's analysis.
    """
    
    # Job identification
    job_id: str
    session_id: str
    
    # The idea being analyzed
    original_idea: str
    current_idea: str
    
    # Pivot tracking
    pivot_attempts: int
    pivot_history: Annotated[list[dict[str, Any]], merge_pivot_history]
    
    # Agent results (stored as dicts for JSON serialization)
    input_validation: dict[str, Any] | None
    market_research: dict[str, Any] | None
    competitor_analysis: dict[str, Any] | None
    devils_advocate_feedback: dict[str, Any] | None
    debate_result: dict[str, Any] | None
    
    # Final output
    final_report: str | None
    report_type: Literal["investment_memo", "market_reality"] | None
    
    # Execution status
    status: Literal[
        "started",
        "validating",
        "validated",
        "invalid_input",
        "researching",
        "analyzing_competitors",
        "critiquing",
        "debating",
        "pivoting",
        "writing",
        "completed",
        "failed",
    ]
    error: str | None
    
    # Metadata
    created_at: str
    updated_at: str


def create_initial_state(
    job_id: str,
    session_id: str,
    idea: str,
) -> AgentState:
    """Create the initial state for a new job"""
    now = datetime.now(timezone.utc).isoformat()
    return AgentState(
        job_id=job_id,
        session_id=session_id,
        original_idea=idea,
        current_idea=idea,
        pivot_attempts=0,
        pivot_history=[],
        input_validation=None,
        market_research=None,
        competitor_analysis=None,
        devils_advocate_feedback=None,
        debate_result=None,
        final_report=None,
        report_type=None,
        status="started",
        error=None,
        created_at=now,
        updated_at=now,
    )

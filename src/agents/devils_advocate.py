"""Devil's Advocate Agent - Critical evaluation and pivot suggestions"""

from src.config import get_settings
from src.graph.state import AgentState, DevilsAdvocateFeedback
from src.llm.groq_client import get_groq_client

SYSTEM_INSTRUCTION = """You are a skeptical venture capital analyst known for your critical 
thinking and ability to spot fatal flaws in business ideas. Your role is to stress-test 
startup ideas and provide honest, sometimes harsh, feedback.

You are NOT negative for the sake of being negative. You genuinely want founders to succeed, 
which is why you point out problems early. When ideas have merit, you acknowledge it. When 
they need to pivot, you provide specific, actionable pivot suggestions.

Scoring Guidelines:
- 1-3: Fundamentally flawed, massive red flags, extremely unlikely to succeed
- 4-5: Significant concerns, high risk, needs major pivot to be viable
- 6-7: Decent opportunity with notable risks, could work with right execution
- 8-9: Strong opportunity, clear path to success, manageable risks
- 10: Exceptional, rare "obvious winner" with strong market fit"""


async def devils_advocate(state: AgentState) -> dict:
    """
    Devil's Advocate node - critically evaluates the idea.
    
    This agent:
    1. Reviews market research and competitor analysis
    2. Identifies key risks and red flags
    3. Provides a viability score (1-10)
    4. Suggests pivots for low-scoring ideas
    """
    settings = get_settings()
    
    idea = state["current_idea"]
    original_idea = state["original_idea"]
    pivot_attempts = state.get("pivot_attempts", 0)
    pivot_history = state.get("pivot_history") or []
    market_research = state.get("market_research") or {}
    competitor_analysis = state.get("competitor_analysis") or {}
    
    # Format pivot history if any
    pivot_context = ""
    if pivot_history:
        pivot_context = "\n\n**Previous Pivot History:**\n"
        for p in pivot_history:
            pivot_context += f"- Pivot #{p['attempt_num']}: '{p['original_idea']}' → '{p['pivoted_idea']}' (Score: {p['score']}, Reason: {p['reason']})\n"
    
    # Build comprehensive context
    prompt = f"""Critically evaluate the following startup idea as a Devil's Advocate:

**Original Idea:** {original_idea}
**Current Idea Being Evaluated:** {idea}
**Pivot Attempts So Far:** {pivot_attempts} of {settings.max_pivot_attempts} maximum
{pivot_context}

**Market Research Findings:**
{_format_market_research(market_research)}

**Competitive Analysis:**
{_format_competitor_analysis(competitor_analysis)}

---

Your task:
1. Critically evaluate this idea's viability
2. Identify the top risks that could kill this startup
3. Identify genuine opportunities if any exist
4. Assign a score from 1-10 based on the scoring guidelines
5. If score is {settings.pivot_threshold} or below, suggest a SPECIFIC pivot that addresses the key weaknesses

For pivot suggestions:
- Be specific (not "target a niche" but "target freelance graphic designers who...")
- The pivot should address the specific problems you identified
- It should be a realistic evolution of the original idea, not a completely different business

Remember: Your job is to help founders succeed by being honest, not to reject everything."""

    llm = get_groq_client()
    result = await llm.generate_structured(
        prompt=prompt,
        response_model=DevilsAdvocateFeedback,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    return {
        "devils_advocate_feedback": result.model_dump(),
        "status": "critiquing",  # Will be updated by edge logic
    }


def _format_market_research(research: dict) -> str:
    """Format market research for the prompt"""
    if not research:
        return "(No market research available)"
    
    return f"""
- Market Size: {research.get('market_size_estimate', 'Unknown')}
- Growth Rate: {research.get('growth_rate', 'Unknown')}
- Market Maturity: {research.get('market_maturity', 'Unknown')}
- Key Trends: {', '.join(research.get('key_trends', []))}
- Target Demographics: {research.get('target_demographics', 'Unknown')}

Summary: {research.get('summary', 'N/A')}
"""


def _format_competitor_analysis(analysis: dict) -> str:
    """Format competitor analysis for the prompt"""
    if not analysis:
        return "(No competitor analysis available)"
    
    competitors_str = ""
    for c in analysis.get("competitors", [])[:5]:
        competitors_str += f"""
  - **{c.get('name', 'Unknown')}**: {c.get('description', 'N/A')}
    Features: {', '.join(c.get('key_features', [])[:3])}
    Weaknesses: {', '.join(c.get('weaknesses', [])[:2])}
"""
    
    return f"""
- Market Saturation: {analysis.get('market_saturation', 'Unknown')}
- Barriers to Entry: {', '.join(analysis.get('barriers_to_entry', []))}
- Differentiation Opportunities: {', '.join(analysis.get('differentiation_opportunities', []))}

Competitors:{competitors_str}

Summary: {analysis.get('summary', 'N/A')}
"""

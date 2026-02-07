"""Writer Agent - Generates final investment memo or market reality report"""

from src.graph.state import AgentState
from src.llm.groq_client import get_groq_client

INVESTMENT_MEMO_INSTRUCTION = """You are an expert investment analyst writing a compelling 
investment memo for a venture capital fund. Your memos are data-driven, well-structured, 
and actionable. You highlight both opportunities and risks with appropriate weight.

Write in a professional but engaging tone. Use markdown formatting for readability."""

MARKET_REALITY_INSTRUCTION = """You are a thoughtful startup advisor writing a "Market Reality 
Report" for a founder whose idea faces significant challenges. Your goal is NOT to discourage 
them, but to educate them on the market dynamics and help them understand why this particular 
approach is difficult.

Be honest but constructive. Acknowledge their ambition while explaining the challenges. 
Provide clear takeaways they can learn from. Use markdown formatting for readability."""


async def writer(state: AgentState) -> dict:
    """
    Writer node - generates the final report.
    
    Generates either:
    - Investment Memo (score > threshold): Bullish analysis for promising ideas
    - Market Reality Report (exhausted pivots): Educational report explaining challenges
    """
    feedback = state.get("devils_advocate_feedback") or {}
    score = feedback.get("score", 0) if feedback else 0
    
    # Determine report type based on score and context
    # If we got here with score > threshold, it's an investment memo
    # If we got here after exhausting pivots, it's a market reality report
    pivot_attempts = state.get("pivot_attempts", 0)
    from src.config import get_settings
    settings = get_settings()
    
    if score > settings.pivot_threshold:
        return await _write_investment_memo(state)
    else:
        return await _write_market_reality_report(state)


async def _write_investment_memo(state: AgentState) -> dict:
    """Generate an investment memo for a promising idea"""
    
    idea = state["current_idea"]
    original_idea = state["original_idea"]
    market_research = state.get("market_research") or {}
    competitor_analysis = state.get("competitor_analysis") or {}
    feedback = state.get("devils_advocate_feedback") or {}
    pivot_history = state.get("pivot_history") or []
    
    # Build pivot narrative if applicable
    pivot_narrative = ""
    if pivot_history:
        pivot_narrative = "\n\n## Evolution of the Idea\n\n"
        pivot_narrative += f"The original idea was: **{original_idea}**\n\n"
        pivot_narrative += "Through iterative analysis, the idea evolved:\n\n"
        for p in pivot_history:
            pivot_narrative += f"- **Pivot #{p['attempt_num']}**: Shifted from '{p['original_idea']}' to '{p['pivoted_idea']}'\n"
            pivot_narrative += f"  - Reason: {p['reason']}\n"
        pivot_narrative += f"\nThe final validated idea is: **{idea}**\n"
    
    prompt = f"""Write a professional Investment Memo for the following startup idea:

**Startup Idea:** {idea}
**Viability Score:** {feedback.get('score', 'N/A')}/10
**Verdict:** {feedback.get('verdict', 'N/A')}

**Market Research:**
- Market Size: {market_research.get('market_size_estimate', 'N/A')}
- Growth Rate: {market_research.get('growth_rate', 'N/A')}
- Market Maturity: {market_research.get('market_maturity', 'N/A')}
- Key Trends: {', '.join(market_research.get('key_trends', []))}
- Target Demographics: {market_research.get('target_demographics', 'N/A')}

**Competitive Landscape:**
- Saturation Level: {competitor_analysis.get('market_saturation', 'N/A')}
- Key Competitors: {', '.join([c.get('name', '') for c in competitor_analysis.get('competitors', [])[:5]])}
- Differentiation Opportunities: {', '.join(competitor_analysis.get('differentiation_opportunities', []))}
- Barriers to Entry: {', '.join(competitor_analysis.get('barriers_to_entry', []))}

**Critical Analysis:**
- Key Risks: {', '.join(feedback.get('key_risks', []))}
- Key Opportunities: {', '.join(feedback.get('key_opportunities', []))}
- Reasoning: {feedback.get('reason', 'N/A')}

{pivot_narrative if pivot_history else ''}

---

Write a comprehensive Investment Memo with the following sections:
1. **Executive Summary** - One paragraph thesis
2. **The Opportunity** - Market size, trends, timing
3. **Competitive Advantage** - How to win against competitors
4. **Risks & Mitigations** - Key risks and how to address them
5. **Recommendation** - Final investment recommendation

Use markdown formatting. Be specific and data-driven."""

    llm = get_groq_client()
    report = await llm.generate(
        prompt=prompt,
        system_instruction=INVESTMENT_MEMO_INSTRUCTION,
    )
    
    # Add header
    full_report = f"""# 🟢 Investment Memo

**Idea:** {idea}
**Score:** {feedback.get('score', 'N/A')}/10
**Generated:** {{timestamp}}

---

{report}
"""
    
    return {
        "final_report": full_report,
        "report_type": "investment_memo",
        "status": "completed",
    }


async def _write_market_reality_report(state: AgentState) -> dict:
    """Generate a market reality report for a challenging idea"""
    
    idea = state["current_idea"]
    original_idea = state["original_idea"]
    market_research = state.get("market_research") or {}
    competitor_analysis = state.get("competitor_analysis") or {}
    feedback = state.get("devils_advocate_feedback") or {}
    pivot_history = state.get("pivot_history") or []
    
    # Build pivot journey narrative
    pivot_journey = ""
    if pivot_history:
        pivot_journey = "\n\n## The Pivot Journey\n\n"
        pivot_journey += "We attempted several pivots to find a viable angle:\n\n"
        for p in pivot_history:
            pivot_journey += f"### Pivot #{p['attempt_num']}: {p['pivoted_idea']}\n"
            pivot_journey += f"- **Previous idea:** {p['original_idea']}\n"
            pivot_journey += f"- **Score:** {p['score']}/10\n"
            pivot_journey += f"- **Why it didn't pass:** {p['reason']}\n\n"
    
    prompt = f"""Write a constructive "Market Reality Report" for the following startup idea:

**Original Idea:** {original_idea}
**Final Iteration:** {idea}
**Final Score:** {feedback.get('score', 'N/A')}/10
**Pivot Attempts:** {len(pivot_history)}

**Market Research:**
- Market Size: {market_research.get('market_size_estimate', 'N/A')}
- Growth Rate: {market_research.get('growth_rate', 'N/A')}
- Market Maturity: {market_research.get('market_maturity', 'N/A')}
- Market Summary: {market_research.get('summary', 'N/A')}

**Competitive Landscape:**
- Saturation Level: {competitor_analysis.get('market_saturation', 'N/A')}
- Number of Competitors: {len(competitor_analysis.get('competitors', []))}
- Barriers to Entry: {', '.join(competitor_analysis.get('barriers_to_entry', []))}
- Competitive Summary: {competitor_analysis.get('summary', 'N/A')}

**Critical Analysis:**
- Key Risks: {', '.join(feedback.get('key_risks', []))}
- Reasoning: {feedback.get('reason', 'N/A')}

{pivot_journey}

---

Write a constructive Market Reality Report with the following sections:
1. **Executive Summary** - Honest assessment of why this market is challenging
2. **The Market Reality** - Detailed explanation of market conditions (Red Ocean analysis)
3. **Why Traditional Approaches Fail** - Specific reasons this type of idea struggles
4. **Lessons Learned** - What the founder can take away from this analysis
5. **Alternative Directions** - 2-3 completely different approaches they might consider

The tone should be educational and respectful, not dismissive. Help them understand 
the market dynamics so they can make better decisions in the future."""

    llm = get_groq_client()
    report = await llm.generate(
        prompt=prompt,
        system_instruction=MARKET_REALITY_INSTRUCTION,
    )
    
    # Add header
    full_report = f"""# 🔴 Market Reality Report

**Original Idea:** {original_idea}
**Final Score:** {feedback.get('score', 'N/A')}/10
**Pivots Attempted:** {len(pivot_history)}
**Generated:** {{timestamp}}

---

{report}
"""
    
    return {
        "final_report": full_report,
        "report_type": "market_reality",
        "status": "completed",
    }

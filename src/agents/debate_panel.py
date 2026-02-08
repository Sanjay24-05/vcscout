"""
Debate Panel Agent - Multi-perspective analysis using Bull, Bear, and Synthesizer

This replaces the Devil's Advocate + pivot loop with a single debate that produces
either an approved idea or a collaboratively refined pivot.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any

from src.config import get_settings
from src.graph.state import AgentState, DebateResult, DebateMessage
from src.llm.groq_client import get_groq_client


# Agent system prompts
BULL_SYSTEM = """You are Bull, an optimistic venture capitalist evaluating startup ideas.

Your role in this debate:
- Find and articulate strong reasons to INVEST in this idea
- Identify market opportunities, growth potential, and competitive advantages
- Counter Bear's concerns with data-driven arguments
- Be enthusiastic but grounded in market realities

When the idea has flaws, suggest specific improvements that would make it investable.
Keep responses concise (2-3 paragraphs max). Focus on actionable insights.

You're in a debate with Bear (risk analyst). Read their arguments and respond thoughtfully."""

BEAR_SYSTEM = """You are Bear, a risk-focused analyst evaluating startup ideas.

Your role in this debate:
- Identify critical risks, market challenges, and fatal flaws
- Challenge Bull's optimism with realistic concerns
- Point out competition, barriers to entry, and execution risks
- Be constructive - explain WHY something is a risk, not just that it is

If the idea is truly terrible, be direct about it. If it has potential, acknowledge
what would need to change.
Keep responses concise (2-3 paragraphs max).

You're in a debate with Bull (VC optimist). Read their arguments and respond thoughtfully."""


def _get_synthesizer_system(pass_threshold: int) -> str:
    return f"""You are Synthesizer, a neutral moderator producing the final investment verdict.

You have listened to Bull (optimist) and Bear (skeptic) debate this startup idea.
Now you must produce a FINAL VERDICT.

Scoring guide:
- 1-3: REJECT - Fatal flaws, no viable path
- 4-{pass_threshold}: CONDITIONAL - Has potential but needs significant changes
- {pass_threshold + 1}-10: INVEST - Strong opportunity, proceed

If the score is {pass_threshold} or below AND the debate revealed a viable pivot:
- Set idea_was_pivoted=true
- Provide the refined idea in final_idea

You MUST respond with valid JSON matching this exact structure:
{{
    "score": <integer 1-10>,
    "verdict": "<invest|conditional_invest|reject>",
    "final_idea": "<the original idea OR a refined pivot based on debate>",
    "idea_was_pivoted": <true if you modified the idea, false otherwise>,
    "bull_case": "<2-3 sentence summary of Bull's investment thesis>",
    "bear_case": "<2-3 sentence summary of Bear's concerns>",
    "synthesis": "<your balanced 2-3 paragraph conclusion>",
    "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
    "key_opportunities": ["<opportunity 1>", "<opportunity 2>", "<opportunity 3>"],
    "recommended_next_steps": ["<step 1>", "<step 2>", "<step 3>"]
}}

Respond ONLY with the JSON object, no additional text."""


async def debate_panel(state: AgentState) -> dict:
    """
    Run a multi-agent debate to evaluate the startup idea.
    
    Flow:
    1. Bull presents investment case (given market research + competitor analysis)
    2. Bear challenges with risks and concerns
    3. Bull responds to Bear's concerns
    4. Bear responds to Bull's counter-arguments
    5. Synthesizer produces final verdict (potentially with collaborative pivot)
    
    Returns:
        dict with debate_result containing the final verdict
    """
    settings = get_settings()
    llm = get_groq_client()
    
    idea = state.get("current_idea", "")
    market_research = state.get("market_research") or {}
    competitor_analysis = state.get("competitor_analysis") or {}
    
    # Format context for the debate
    context = _format_research_context(idea, market_research, competitor_analysis)
    
    # Track the debate transcript
    transcript: list[DebateMessage] = []
    
    def add_to_transcript(speaker: str, content: str):
        transcript.append(DebateMessage(
            speaker=speaker,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
    
    # Round 1: Bull opens with investment case
    bull_r1_prompt = f"""{context}

As Bull, present your initial investment case for this startup idea.
Why should a VC invest? What's the opportunity?"""
    
    bull_r1 = await llm.generate(
        prompt=bull_r1_prompt,
        system_instruction=BULL_SYSTEM,
    )
    add_to_transcript("Bull", bull_r1)
    
    # Round 2: Bear challenges
    bear_r1_prompt = f"""{context}

Bull just presented their investment case:
---
{bull_r1}
---

As Bear, challenge this thesis. What are the critical risks and concerns?"""
    
    bear_r1 = await llm.generate(
        prompt=bear_r1_prompt,
        system_instruction=BEAR_SYSTEM,
    )
    add_to_transcript("Bear", bear_r1)
    
    # Round 3: Bull responds to concerns
    bull_r2_prompt = f"""{context}

Your initial case:
---
{bull_r1}
---

Bear's challenges:
---
{bear_r1}
---

Respond to Bear's concerns. Can you address these risks? What mitigations exist?
If some concerns are valid, acknowledge them and suggest how to address them."""
    
    bull_r2 = await llm.generate(
        prompt=bull_r2_prompt,
        system_instruction=BULL_SYSTEM,
    )
    add_to_transcript("Bull", bull_r2)
    
    # Round 4: Bear final response
    bear_r2_prompt = f"""{context}

The debate so far:

Bull (opening): {bull_r1[:500]}...

Your response: {bear_r1[:500]}...

Bull's counter:
---
{bull_r2}
---

Give your final assessment. Are Bull's mitigations sufficient? 
If the idea needs changes to be viable, what specific pivot would you suggest?"""
    
    bear_r2 = await llm.generate(
        prompt=bear_r2_prompt,
        system_instruction=BEAR_SYSTEM,
    )
    add_to_transcript("Bear", bear_r2)
    
    # Round 5: Synthesizer produces verdict
    synth_prompt = f"""{context}

=== DEBATE TRANSCRIPT ===

BULL (Opening Investment Case):
{bull_r1}

BEAR (Risk Analysis):
{bear_r1}

BULL (Response to Concerns):
{bull_r2}

BEAR (Final Assessment):
{bear_r2}

=== END TRANSCRIPT ===

Based on this debate, produce your final verdict as Synthesizer.
If score <= {settings.pass_threshold} but a viable pivot emerged from the debate, include it.

Remember: Respond ONLY with valid JSON."""
    
    synth_response = await llm.generate(
        prompt=synth_prompt,
        system_instruction=_get_synthesizer_system(settings.pass_threshold),
    )
    add_to_transcript("Synthesizer", synth_response)
    
    # Parse the synthesizer's response
    result = _parse_synthesizer_response(synth_response, idea, transcript)
    
    # Update current_idea if pivoted
    updates = {
        "debate_result": result.model_dump(),
        "status": "debating",
    }
    
    # Also populate devils_advocate_feedback for compatibility with existing code
    updates["devils_advocate_feedback"] = {
        "score": result.score,
        "verdict": result.verdict,
        "reason": result.synthesis,
        "key_risks": result.key_risks,
        "key_opportunities": result.key_opportunities,
        "suggested_pivot": result.final_idea if result.idea_was_pivoted else None,
        "pivot_rationale": result.synthesis if result.idea_was_pivoted else None,
    }
    
    # If pivoted, update current_idea
    if result.idea_was_pivoted and result.final_idea:
        updates["current_idea"] = result.final_idea
        updates["pivot_attempts"] = state.get("pivot_attempts", 0) + 1
        updates["pivot_history"] = [{
            "attempt_num": state.get("pivot_attempts", 0) + 1,
            "original_idea": idea,
            "pivoted_idea": result.final_idea,
            "reason": f"Debate consensus: {result.synthesis[:200]}...",
            "score": result.score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    
    return updates


def _format_research_context(idea: str, market_research: dict, competitor_analysis: dict) -> str:
    """Format the research context for debate agents"""
    
    market_summary = market_research.get("summary", "No market research available.")
    market_size = market_research.get("market_size_estimate", "Unknown")
    growth_rate = market_research.get("growth_rate", "Unknown")
    
    competitors = competitor_analysis.get("competitors", [])
    saturation = competitor_analysis.get("market_saturation", "unknown")
    differentiation = competitor_analysis.get("differentiation_opportunities", [])
    
    competitor_list = ""
    for c in competitors[:5]:
        if isinstance(c, dict):
            competitor_list += f"- {c.get('name', 'Unknown')}: {c.get('description', '')[:100]}\n"
    
    return f"""
=== STARTUP IDEA ===
{idea}

=== MARKET RESEARCH ===
Market Size: {market_size}
Growth Rate: {growth_rate}
Summary: {market_summary}

=== COMPETITIVE LANDSCAPE ===
Market Saturation: {saturation}
Key Competitors:
{competitor_list or "- No specific competitors identified"}

Differentiation Opportunities:
{chr(10).join('- ' + d for d in differentiation[:5]) if differentiation else "- None identified"}
"""


def _parse_synthesizer_response(
    response: str, 
    original_idea: str,
    transcript: list[DebateMessage]
) -> DebateResult:
    """Parse the Synthesizer's JSON response into DebateResult"""
    
    # Try to extract JSON from the response
    try:
        # Clean up response
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        if response.endswith("```"):
            response = response[:-3].strip()
        
        # Try to find JSON object in response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found")
        
        return DebateResult(
            score=data.get("score", 5),
            verdict=data.get("verdict", "conditional_invest"),
            final_idea=data.get("final_idea", original_idea),
            idea_was_pivoted=data.get("idea_was_pivoted", False),
            bull_case=data.get("bull_case", ""),
            bear_case=data.get("bear_case", ""),
            synthesis=data.get("synthesis", ""),
            key_risks=data.get("key_risks", []),
            key_opportunities=data.get("key_opportunities", []),
            recommended_next_steps=data.get("recommended_next_steps", []),
            debate_transcript=[m.model_dump() for m in transcript],
        )
        
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: try to extract key info from text
        score = 5
        score_match = re.search(r'score[:\s]*(\d+)', response, re.IGNORECASE)
        if score_match:
            score = int(score_match.group(1))
        
        verdict = "conditional_invest"
        if "reject" in response.lower():
            verdict = "reject"
        elif "invest" in response.lower() and "conditional" not in response.lower():
            verdict = "invest"
        
        return DebateResult(
            score=score,
            verdict=verdict,
            final_idea=original_idea,
            idea_was_pivoted=False,
            bull_case="(Parsing failed - see transcript)",
            bear_case="(Parsing failed - see transcript)",
            synthesis=response[:500],
            key_risks=[],
            key_opportunities=[],
            recommended_next_steps=[],
            debate_transcript=[m.model_dump() for m in transcript],
        )

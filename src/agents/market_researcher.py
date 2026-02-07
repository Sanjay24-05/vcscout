"""Market Researcher Agent - Analyzes TAM, trends, and market opportunity"""

from src.graph.state import AgentState, MarketResearchResult
from src.llm.groq_client import get_groq_client
from src.tools.search import get_search_tool

SYSTEM_INSTRUCTION = """You are an expert market researcher and analyst specializing in startup 
and venture capital due diligence. Your role is to gather and synthesize market data to help 
evaluate the viability of business ideas.

You provide factual, data-driven analysis based on the search results provided. When exact 
figures are not available, provide reasonable estimates with clear caveats. Always cite your 
sources."""


async def market_researcher(state: AgentState) -> dict:
    """
    Market Researcher node - gathers TAM, trends, and market data.
    
    This agent:
    1. Searches for market size and TAM data
    2. Identifies growth trends
    3. Analyzes target demographics
    4. Synthesizes findings into a structured report
    """
    idea = state["current_idea"]
    
    # Search for market data
    search_tool = get_search_tool()
    search_results = await search_tool.search_market_data(idea)
    
    # Format search results for the LLM
    search_context = "\n\n".join([
        f"**{r.title}**\nURL: {r.url}\n{r.snippet}"
        for r in search_results
    ])
    
    # Generate structured analysis
    prompt = f"""Analyze the market opportunity for the following startup idea:

**Idea:** {idea}

**Search Results:**
{search_context}

Based on these search results and your knowledge, provide a comprehensive market research analysis.
Focus on:
1. Market size (TAM/SAM/SOM) with specific numbers where available
2. Growth rate and trajectory
3. Key market trends
4. Target demographics and customer segments
5. Market maturity stage

Be specific and cite sources where possible. If exact data isn't available, provide reasonable 
estimates with clear caveats."""

    llm = get_groq_client()
    result = await llm.generate_structured(
        prompt=prompt,
        response_model=MarketResearchResult,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    return {
        "market_research": result.model_dump(),
        "status": "analyzing_competitors",
    }

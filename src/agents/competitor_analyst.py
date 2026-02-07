"""Competitor Analyst Agent - Analyzes competitive landscape"""

from src.graph.state import AgentState, CompetitorAnalysisResult
from src.llm.groq_client import get_groq_client
from src.tools.scraper import get_scraper_tool
from src.tools.search import get_search_tool

SYSTEM_INSTRUCTION = """You are an expert competitive intelligence analyst specializing in 
startup and venture capital due diligence. Your role is to analyze competitors and identify 
differentiation opportunities.

You provide objective, thorough analysis of competitive landscapes. You identify both 
strengths and weaknesses of existing players, and spot gaps in the market that new entrants 
could exploit."""


async def competitor_analyst(state: AgentState) -> dict:
    """
    Competitor Analyst node - analyzes competitive landscape.
    
    This agent:
    1. Searches for competitors in the space
    2. Scrapes competitor websites for detailed info
    3. Analyzes features, pricing, and positioning
    4. Identifies differentiation opportunities
    """
    idea = state["current_idea"]
    
    # Search for competitors
    search_tool = get_search_tool()
    competitor_results = await search_tool.search_competitors(idea)
    
    # Extract URLs to scrape (filter for likely company websites)
    urls_to_scrape = []
    for r in competitor_results:
        url = r.url
        # Skip common non-company sites
        skip_domains = [
            "wikipedia.org", "linkedin.com", "twitter.com", "facebook.com",
            "youtube.com", "reddit.com", "medium.com", "forbes.com",
            "techcrunch.com", "crunchbase.com", "g2.com", "capterra.com",
        ]
        if not any(domain in url for domain in skip_domains):
            urls_to_scrape.append(url)
    
    # Scrape competitor sites (with error handling - scraping is optional)
    scraped_pages = []
    try:
        scraper = get_scraper_tool()
        scraped_pages = await scraper.scrape_multiple(urls_to_scrape[:5])
    except Exception as e:
        print(f"Warning: Scraping failed: {e}. Continuing with search results only.")
    
    # Format search results
    search_context = "\n\n".join([
        f"**{r.title}**\nURL: {r.url}\n{r.snippet}"
        for r in competitor_results[:10]
    ])
    
    # Format scraped content (truncate to avoid token limits)
    scraped_context = ""
    for page in scraped_pages:
        if page.success and page.markdown_content:
            # Take first 2000 chars of each page
            content = page.markdown_content[:2000]
            scraped_context += f"\n\n---\n**{page.title}** ({page.url})\n{content}"
    
    # If no scraped content, note it
    if not scraped_context:
        scraped_context = "\n(Unable to scrape competitor websites - using search results only)"
    
    # Generate structured analysis
    prompt = f"""Analyze the competitive landscape for the following startup idea:

**Idea:** {idea}

**Search Results for Competitors:**
{search_context}

**Scraped Competitor Website Content:**
{scraped_context}

Based on this information, provide a comprehensive competitive analysis including:
1. Profile each major competitor (at least 3-5 if identifiable)
2. Assess market saturation level
3. Identify differentiation opportunities for a new entrant
4. List key barriers to entry

Be specific about each competitor's features, pricing (if available), target audience, 
and weaknesses that could be exploited."""

    llm = get_groq_client()
    result = await llm.generate_structured(
        prompt=prompt,
        response_model=CompetitorAnalysisResult,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    return {
        "competitor_analysis": result.model_dump(),
        "status": "critiquing",
    }

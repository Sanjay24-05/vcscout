"""DuckDuckGo search tool for market research"""

import asyncio
from dataclasses import dataclass

from duckduckgo_search import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings


@dataclass
class SearchResult:
    """A single search result"""
    title: str
    url: str
    snippet: str


class SearchTool:
    """DuckDuckGo search wrapper for market research"""
    
    def __init__(self):
        self.settings = get_settings()
        self._ddgs = DDGS()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _search_sync(
        self, 
        query: str, 
        num_results: int
    ) -> list[SearchResult]:
        """Synchronous search (DDG doesn't have native async)"""
        results = []
        raw_results = self._ddgs.text(
            query, 
            max_results=num_results,
            safesearch="moderate",
        )
        
        for r in raw_results:
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            ))
        
        return results
    
    async def search(
        self, 
        query: str, 
        num_results: int | None = None
    ) -> list[SearchResult]:
        """
        Search DuckDuckGo for market data.
        
        Args:
            query: The search query
            num_results: Number of results (default from settings)
            
        Returns:
            List of search results with title, url, and snippet
        """
        if num_results is None:
            num_results = self.settings.search_num_results
        
        # Run sync search in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._search_sync,
            query,
            num_results,
        )
    
    async def search_market_data(self, idea: str) -> list[SearchResult]:
        """Search for TAM, market size, and trends for an idea"""
        queries = [
            f"{idea} market size TAM 2025 2026",
            f"{idea} industry growth rate trends",
            f"{idea} target market demographics",
        ]
        
        all_results: list[SearchResult] = []
        for query in queries:
            results = await self.search(query, num_results=5)
            all_results.extend(results)
        
        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)
        
        return unique_results
    
    async def search_competitors(self, idea: str) -> list[SearchResult]:
        """Search for competitors in the space"""
        queries = [
            f"{idea} competitors companies startups",
            f"best {idea} apps services 2026",
            f"{idea} market leaders alternatives",
        ]
        
        all_results: list[SearchResult] = []
        for query in queries:
            results = await self.search(query, num_results=5)
            all_results.extend(results)
        
        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)
        
        return unique_results


# Singleton instance
_search_tool: SearchTool | None = None


def get_search_tool() -> SearchTool:
    """Get the search tool singleton"""
    global _search_tool
    if _search_tool is None:
        _search_tool = SearchTool()
    return _search_tool

"""Crawl4AI scraper tool for competitor analysis"""

import asyncio
from dataclasses import dataclass

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings


@dataclass
class ScrapedPage:
    """A scraped web page"""
    url: str
    title: str
    markdown_content: str
    success: bool
    error: str | None = None


class ScraperTool:
    """Crawl4AI wrapper for scraping competitor websites"""
    
    def __init__(self):
        self.settings = get_settings()
        self._crawler: AsyncWebCrawler | None = None
    
    async def _get_crawler(self) -> AsyncWebCrawler:
        """Get or create the crawler instance"""
        if self._crawler is None:
            browser_config = BrowserConfig(
                headless=True,
                verbose=False,
            )
            self._crawler = AsyncWebCrawler(config=browser_config)
            await self._crawler.start()
        return self._crawler
    
    async def close(self) -> None:
        """Close the crawler"""
        if self._crawler is not None:
            await self._crawler.close()
            self._crawler = None
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5),
    )
    async def _scrape_single(self, url: str) -> ScrapedPage:
        """Scrape a single URL"""
        try:
            crawler = await self._get_crawler()
            
            config = CrawlerRunConfig(
                word_count_threshold=50,
                remove_overlay_elements=True,
                process_iframes=False,
            )
            
            result = await asyncio.wait_for(
                crawler.arun(url=url, config=config),
                timeout=self.settings.scrape_timeout,
            )
            
            if result.success:
                return ScrapedPage(
                    url=url,
                    title=result.metadata.get("title", "") if result.metadata else "",
                    markdown_content=result.markdown or "",
                    success=True,
                )
            else:
                return ScrapedPage(
                    url=url,
                    title="",
                    markdown_content="",
                    success=False,
                    error=result.error_message or "Unknown error",
                )
                
        except asyncio.TimeoutError:
            return ScrapedPage(
                url=url,
                title="",
                markdown_content="",
                success=False,
                error=f"Timeout after {self.settings.scrape_timeout}s",
            )
        except Exception as e:
            return ScrapedPage(
                url=url,
                title="",
                markdown_content="",
                success=False,
                error=str(e),
            )
    
    async def scrape_url(self, url: str) -> ScrapedPage:
        """
        Scrape a URL and return clean markdown content.
        
        Args:
            url: The URL to scrape
            
        Returns:
            ScrapedPage with markdown content or error
        """
        return await self._scrape_single(url)
    
    async def scrape_multiple(
        self, 
        urls: list[str],
        max_concurrent: int = 3,
    ) -> list[ScrapedPage]:
        """
        Scrape multiple URLs with concurrency limit.
        
        Args:
            urls: List of URLs to scrape
            max_concurrent: Maximum concurrent scrapes
            
        Returns:
            List of ScrapedPage results
        """
        # Limit to max competitors setting
        urls = urls[:self.settings.max_competitors_to_scrape]
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url: str) -> ScrapedPage:
            async with semaphore:
                return await self._scrape_single(url)
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed ScrapedPage
        scraped_pages: list[ScrapedPage] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                scraped_pages.append(ScrapedPage(
                    url=urls[i],
                    title="",
                    markdown_content="",
                    success=False,
                    error=str(result),
                ))
            else:
                scraped_pages.append(result)
        
        return scraped_pages


# Singleton instance
_scraper_tool: ScraperTool | None = None


def get_scraper_tool() -> ScraperTool:
    """Get the scraper tool singleton"""
    global _scraper_tool
    if _scraper_tool is None:
        _scraper_tool = ScraperTool()
    return _scraper_tool


async def close_scraper() -> None:
    """Close the global scraper"""
    global _scraper_tool
    if _scraper_tool is not None:
        await _scraper_tool.close()
        _scraper_tool = None

import asyncio
import logging
from typing import Optional, Any
import urllib.parse
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import random
from model_url_cache import ModelURLCache

logger = logging.getLogger("uvicorn")

class ModelFinder:
    """Class to search for model files using Google Search via Playwright"""
    
    def __init__(self):
        self.cache = ModelURLCache()
        self._playwright: Any = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
    async def setup(self) -> None:
        """Initialize the browser if needed"""
        if not self._browser:
            logger.info("Starting browser...")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.8.0.12) Gecko/20070508 Firefox/1.5.0.12",
                viewport={"width": 1024, "height": 768},
                device_scale_factor=1,
                is_mobile=False,
                locale="en-US",
                timezone_id="America/Los_Angeles",
                color_scheme="light",
                java_script_enabled=False
            )
            self._page = await self._context.new_page()
            await self._page.goto("https://www.google.com", wait_until="networkidle")
            logger.info("Browser started and ready")
            
    async def cleanup(self) -> None:
        """Clean up browser resources"""
        try:
            if self._page:
                await self._page.close()
                self._page = None
                
            if self._context:
                await self._context.close()
                self._context = None
                
            if self._browser:
                await self._browser.close()
                self._browser = None
                
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
    async def find_model_online(self, filename: str) -> Optional[str]:
        """Search for a model file online"""
        # Check cache first
        if cached_url := self.cache.get(filename):
            logger.info(f"Found cached URL for {filename}")
            return cached_url
            
        # Fall back to web search
        try:
            if not self._page:
                return None
                
            query = f"huggingface \"{filename}\""
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            
            await self._page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(random.uniform(1.0, 2.0))  # Random delay
            
            # Find first valid HuggingFace link
            result_elements = await self._page.query_selector_all("a[href^='/url?q=']")
            for element in result_elements:
                if url := await self._extract_url(element):
                    if "huggingface.co" in url:
                        self.cache.put(filename, url)
                        return url
                    
            return None
            
        except Exception as e:
            logger.error(f"Error searching for model {filename}: {e}")
            return None
            
    async def _extract_url(self, element: Any) -> Optional[str]:
        """Extract URL from a search result element"""
        try:
            href = await element.get_attribute('href')
            if not href:
                return None
                
            parsed = urllib.parse.urlparse(href)
            return urllib.parse.parse_qs(parsed.query)['q'][0]
            
        except Exception as e:
            logger.error(f"Error extracting URL: {e}")
            return None

# Create a global instance
model_finder = ModelFinder()

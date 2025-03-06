import time
import hashlib
from pathlib import Path
from typing import Optional, Dict
import httpx
from datetime import datetime, timedelta
import logging
import re

CACHE_DIR = "cache"

logger = logging.getLogger(__name__)

class CachedRequest:
    """A request client with caching capabilities"""
    
    def __init__(self, rate_limit_delay: float = 0.1):
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.cache_dir = Path(CACHE_DIR)

        # mkdir if not exists (cache dir is a string)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_cache_path(self, url: str, params: Optional[Dict] = None) -> Path:
        """Get the cache file path for a URL and optional parameters"""
        # Create a hash of the URL and params
        key = url
        if params:
            key += "_" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
        safe_path = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
        hash_name = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{safe_path}_{hash_name}.txt"
        
    def _is_cache_valid(self, cache_path: Path, max_age_hours: int = 24) -> bool:
        """Check if the cache file is still valid"""
        if not cache_path.exists():
            return False
        file_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return (datetime.now() - file_mtime) < timedelta(hours=max_age_hours)
        
    def _load_cache(self, cache_path: Path) -> Optional[str]:
        """Load data from cache file"""
        try:
            return cache_path.read_text()
        except OSError as e:
            logger.warning(f"Failed to load cache from {cache_path}: {e}")
            return None
            
    def _save_cache(self, cache_path: Path, data: str) -> None:
        """Save data to cache file"""
        try:
            cache_path.write_text(data)
            logger.debug(f"Saved cache to {cache_path}")
        except OSError as e:
            logger.error(f"Failed to save cache to {cache_path}: {e}")
            
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests"""
        current_time = time.time()
        if current_time - self.last_request_time < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - (current_time - self.last_request_time))
        self.last_request_time = time.time()
        
    def get(self, url: str, params: Optional[Dict] = None, 
            headers: Optional[Dict] = None, cache: bool = True,
            max_age_hours: int = 24) -> httpx.Response:
        """Make a GET request with caching"""
        cache_path = self._get_cache_path(url, params)
        
        # Try to load from cache first
        if cache and self._is_cache_valid(cache_path, max_age_hours):
            if cached_text := self._load_cache(cache_path):
                logger.debug(f"Cache hit for {url}")
                return httpx.Response(
                    status_code=200,
                    content=cached_text.encode(),
                    request=httpx.Request("GET", url)
                )
                
        # Rate limit before making request
        self._rate_limit()
        
        # Make the request
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params, headers=headers)
                
                # Cache successful responses
                if cache and response.status_code == 200:
                    self._save_cache(cache_path, response.text)
                        
                return response
        except httpx.RequestError as e:
            return httpx.Response(
                status_code=500,
                content=str(e).encode(),
                request=httpx.Request("GET", url)
            ) 
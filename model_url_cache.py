import json
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger("uvicorn")

class ModelURLCache:
    """Simple cache for model URLs"""
    
    def __init__(self, cache_file: str = "cache/.model_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, str] = {}
        self._load_cache()
        
    def _load_cache(self) -> None:
        """Load cache from file if it exists"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
                self.cache = {}
                
    def _save_cache(self) -> None:
        """Save cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            
    def get(self, model_filename: str) -> Optional[str]:
        """Get URL for a model filename from cache"""
        return self.cache.get(model_filename)
        
    def put(self, model_filename: str, url: str) -> None:
        """Add or update URL for a model filename in cache"""
        self.cache[model_filename] = url
        self._save_cache() 
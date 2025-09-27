"""Simple in-memory cache for TTS and enrichment data to improve performance."""
import time
import threading
from typing import Dict, Any, Optional
from functools import wraps

class SimpleCache:
    """Thread-safe in-memory cache with TTL support."""
    
    def __init__(self, default_ttl: int = 3600):  # 1 hour default TTL
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if time.time() > entry['expires_at']:
                del self._cache[key]
                return None
            
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        with self._lock:
            ttl = ttl or self.default_ttl
            self._cache[key] = {
                'value': value,
                'expires_at': time.time() + ttl
            }
    
    def delete(self, key: str) -> None:
        """Delete key from cache."""
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        """Get number of cache entries."""
        with self._lock:
            return len(self._cache)

# Global cache instances
tts_cache = SimpleCache(default_ttl=7200)  # 2 hours for TTS
enrichment_cache = SimpleCache(default_ttl=3600)  # 1 hour for enrichment

def cached_tts(ttl: int = 7200):
    """Decorator to cache TTS results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"tts:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            cached_result = tts_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                tts_cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

def cached_enrichment(ttl: int = 3600):
    """Decorator to cache enrichment results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"enrich:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            cached_result = enrichment_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                enrichment_cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

def clear_tts_cache():
    """Clear TTS cache."""
    tts_cache.clear()

def clear_enrichment_cache():
    """Clear enrichment cache."""
    enrichment_cache.clear()

def get_cache_stats():
    """Get cache statistics."""
    return {
        'tts_cache_size': tts_cache.size(),
        'enrichment_cache_size': enrichment_cache.size()
    }

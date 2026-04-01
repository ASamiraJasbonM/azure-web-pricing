"""
Cache system for Azure pricing data
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry"""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)
    hits: int = 0
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def is_valid(self) -> bool:
        return not self.is_expired()


class MemoryCache:
    """In-memory cache implementation"""
    
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 1000):
        """
        Initialize memory cache
        
        Args:
            ttl_seconds: Time to live for cache entries
            max_size: Maximum number of entries
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, data: Any) -> str:
        """Generate cache key from data"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        
        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            return None
        
        entry.hits += 1
        self._hits += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
            del self._cache[oldest_key]
        
        expires_at = time.time() + (ttl or self.ttl_seconds)
        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            expires_at=expires_at
        )
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def cleanup(self) -> int:
        """Remove expired entries"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }


class FileCache:
    """File-based cache implementation"""
    
    def __init__(self, cache_dir: str = "./data/cache", ttl_seconds: int = 3600):
        """
        Initialize file cache
        
        Args:
            cache_dir: Directory to store cache files
            ttl_seconds: Time to live for cache entries
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key"""
        safe_key = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{safe_key}.json"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            
            # Check expiry
            if time.time() > data.get("expires_at", 0):
                cache_path.unlink()
                return None
            
            return data.get("value")
        except (json.JSONDecodeError, IOError):
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        cache_path = self._get_cache_path(key)
        expires_at = time.time() + (ttl or self.ttl_seconds)
        
        data = {
            "key": key,
            "value": value,
            "created_at": time.time(),
            "expires_at": expires_at,
        }
        
        try:
            with open(cache_path, "w") as f:
                json.dump(data, f)
        except IOError as e:
            logger.warning(f"Failed to write cache: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache"""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
    
    def cleanup(self) -> int:
        """Remove expired entries"""
        removed = 0
        current_time = time.time()
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                
                if current_time > data.get("expires_at", 0):
                    cache_file.unlink()
                    removed += 1
            except (json.JSONDecodeError, IOError):
                cache_file.unlink()
                removed += 1
        
        return removed
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_files = len(list(self.cache_dir.glob("*.json")))
        
        expired = 0
        current_time = time.time()
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                if current_time > data.get("expires_at", 0):
                    expired += 1
            except (json.JSONDecodeError, IOError):
                expired += 1
        
        return {
            "total_files": total_files,
            "expired_files": expired,
            "valid_files": total_files - expired,
        }


class CacheManager:
    """Unified cache manager with memory and file backing"""
    
    def __init__(
        self,
        use_memory: bool = True,
        use_file: bool = True,
        memory_ttl: int = 3600,
        file_ttl: int = 86400,
        cache_dir: str = "./data/cache",
    ):
        """
        Initialize cache manager
        
        Args:
            use_memory: Enable memory cache
            use_file: Enable file cache
            memory_ttl: Memory cache TTL in seconds
            file_ttl: File cache TTL in seconds
            cache_dir: Directory for file cache
        """
        self.use_memory = use_memory
        self.use_file = use_file
        
        if use_memory:
            self.memory_cache = MemoryCache(ttl_seconds=memory_ttl)
        
        if use_file:
            self.file_cache = FileCache(cache_dir=cache_dir, ttl_seconds=file_ttl)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        # Try memory first
        if self.use_memory:
            value = self.memory_cache.get(key)
            if value is not None:
                return value
        
        # Try file cache
        if self.use_file:
            value = self.file_cache.get(key)
            if value is not None:
                # Promote to memory
                if self.use_memory:
                    self.memory_cache.set(key, value)
                return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        if self.use_memory:
            self.memory_cache.set(key, value, ttl)
        
        if self.use_file:
            self.file_cache.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        deleted = False
        
        if self.use_memory:
            deleted = self.memory_cache.delete(key) or deleted
        
        if self.use_file:
            deleted = self.file_cache.delete(key) or deleted
        
        return deleted
    
    def clear(self) -> None:
        """Clear all caches"""
        if self.use_memory:
            self.memory_cache.clear()
        
        if self.use_file:
            self.file_cache.clear()
    
    def cleanup(self) -> int:
        """Clean up expired entries"""
        removed = 0
        
        if self.use_memory:
            removed += self.memory_cache.cleanup()
        
        if self.use_file:
            removed += self.file_cache.cleanup()
        
        return removed
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {}
        
        if self.use_memory:
            stats["memory"] = self.memory_cache.stats()
        
        if self.use_file:
            stats["file"] = self.file_cache.stats()
        
        return stats


# Global cache instance
_default_cache: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Get default cache instance"""
    global _default_cache
    if _default_cache is None:
        _default_cache = CacheManager()
    return _default_cache


def set_cache(cache: CacheManager) -> None:
    """Set default cache instance"""
    global _default_cache
    _default_cache = cache
import redis
from typing import Optional
import json
from app.config import REDIS_URL, CACHE_TTL

class RedisCache:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or REDIS_URL
        self.redis_client = redis.from_url(self.redis_url)
        self.default_ttl = CACHE_TTL

    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache"""
        try:
            value = self.redis_client.get(key)
            return value.decode('utf-8') if value else None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = None) -> bool:
        """Set a value in cache with optional TTL"""
        try:
            return self.redis_client.set(
                key,
                value,
                ex=ttl or self.default_ttl
            )
        except Exception as e:
            print(f"Redis set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False

    def generate_key(self, text: str) -> str:
        """Generate a cache key for the text suggestion"""
        # Use a prefix to avoid key collisions with other Redis uses
        return f"suggestion:{text}" 
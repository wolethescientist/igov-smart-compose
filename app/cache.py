import redis
from typing import Optional, List, Dict
import json
import time
from app.config import REDIS_URL, CACHE_TTL

class RedisCache:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or REDIS_URL
        self.redis_client = redis.from_url(self.redis_url)
        self.default_ttl = CACHE_TTL
        self.feedback_ttl = 60 * 60 * 24 * 30  # 30 days for feedback data

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

    async def store_user_feedback(self, user_id: str, context: str, selected_suggestion: str) -> bool:
        """Store user's selected suggestion for learning"""
        try:
            key = f"feedback:{user_id}"
            # Get existing feedback
            existing = self.redis_client.get(key)
            feedback_data = json.loads(existing) if existing else []
            
            # Add new feedback
            feedback_data.append({
                "context": context,
                "selected": selected_suggestion,
                "timestamp": time.time()
            })
            
            # Keep only last 100 selections to prevent unlimited growth
            if len(feedback_data) > 100:
                feedback_data = feedback_data[-100:]
            
            # Store updated feedback
            return self.redis_client.set(
                key,
                json.dumps(feedback_data),
                ex=self.feedback_ttl
            )
        except Exception as e:
            print(f"Redis feedback storage error: {e}")
            return False

    async def get_user_feedback(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get user's recent feedback for learning"""
        try:
            key = f"feedback:{user_id}"
            data = self.redis_client.get(key)
            if not data:
                return []
            
            feedback_data = json.loads(data)
            return feedback_data[-limit:]  # Return most recent feedback
        except Exception as e:
            print(f"Redis feedback retrieval error: {e}")
            return [] 
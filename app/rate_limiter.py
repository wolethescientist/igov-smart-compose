import time
from redis import Redis
from redis.exceptions import ConnectionError, TimeoutError
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class RedisRateLimiter:
    def __init__(self, redis_url: str = "redis://localhost:6379", max_retries: int = 3):
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.redis = None
        self.rate_limit = 20  # requests per window
        self.window = 60  # 1 minute window
        self._connect_to_redis()

    def _connect_to_redis(self) -> None:
        """Establish connection to Redis with retry logic"""
        retries = 0
        while retries < self.max_retries:
            try:
                self.redis = Redis.from_url(self.redis_url, decode_responses=True)
                # Test the connection
                self.redis.ping()
                logger.info("Successfully connected to Redis")
                break
            except (ConnectionError, TimeoutError) as e:
                retries += 1
                if retries == self.max_retries:
                    logger.error(f"Failed to connect to Redis after {self.max_retries} attempts: {e}")
                    raise
                logger.warning(f"Redis connection attempt {retries} failed, retrying...")
                time.sleep(1)  # Wait before retrying

    async def check_rate_limit(self, key: str) -> Tuple[bool, int]:
        """
        Check if rate limit is exceeded for the given key.
        Returns (is_allowed, remaining_requests)
        """
        try:
            if not self.redis or not self.redis.ping():
                logger.warning("Redis connection lost, attempting to reconnect...")
                self._connect_to_redis()

            pipe = self.redis.pipeline()
            now = time.time()
            window_start = now - self.window
            
            # Remove old requests
            pipe.zremrangebyscore(key, 0, window_start)
            # Count requests in current window
            pipe.zcard(key)
            # Add current request timestamp
            pipe.zadd(key, {str(now): now})
            # Set key expiration
            pipe.expire(key, self.window)
            
            _, request_count, *_ = pipe.execute()
            
            is_allowed = request_count <= self.rate_limit
            remaining = max(0, self.rate_limit - request_count)
            
            return is_allowed, remaining

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Redis operation failed: {e}")
            # In case of Redis failure, allow the request but log the error
            return True, self.rate_limit

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        redis_url: str = "redis://localhost:6379",
        prefix: str = "rate_limit"
    ):
        super().__init__(app)
        self.limiter = RedisRateLimiter(redis_url)
        self.prefix = prefix

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            # Get client IP
            client_ip = request.client.host
            key = f"{self.prefix}:{client_ip}"
            
            # Check rate limit
            is_allowed, remaining = await self.limiter.check_rate_limit(key)
            
            if not is_allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later."
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.limiter.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + self.limiter.window))
            
            return response

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # In case of unexpected errors, allow the request but log the error
            return await call_next(request) 
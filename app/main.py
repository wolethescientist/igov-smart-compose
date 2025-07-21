import os
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Body, Depends
from pydantic import BaseModel
from dotenv import load_dotenv
from app.rate_limiter import RateLimitMiddleware
from app.cache import RedisCache
import logging
from redis import Redis
from redis.exceptions import ConnectionError, TimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

COMPLETION_PROMPT = """You are a formal government text completion service. Provide ONLY the next few words to complete the text. Use formal, professional language and bureaucratic terminology. NO explanations or original text.

User's text: "{text}"

Completion:"""

app = FastAPI(
    title="Igov Smart Compose",
    description="An API that uses Google's Gemini to provide text suggestions, similar to Gmail's Smart Compose."
)

# Add Redis-based rate limiting middleware
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

@app.on_event("startup")
async def startup_event():
    # Test Redis connection on startup
    try:
        redis = Redis.from_url(redis_url, decode_responses=True)
        redis.ping()
        logger.info("✅ Successfully connected to Redis at %s", redis_url)
    except (ConnectionError, TimeoutError) as e:
        logger.error("❌ Failed to connect to Redis at %s: %s", redis_url, str(e))
    except Exception as e:
        logger.error("❌ Unexpected error while connecting to Redis: %s", str(e))

app.add_middleware(RateLimitMiddleware, redis_url=redis_url)

# Initialize Redis cache
redis_cache = RedisCache(redis_url)

class SuggestionRequest(BaseModel):
    current_text: str

class SuggestionResponse(BaseModel):
    suggestion: str
    cached: bool = False

async def get_suggestion_from_ai_model(text: str) -> str:
    try:
        response = await model.generate_content_async(COMPLETION_PROMPT.format(text=text))
        return response.text.strip()

    except Exception as e:
        print(f"Error calling the Gemini API: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/generate-suggestion", response_model=SuggestionResponse)
async def generate_suggestion(request: SuggestionRequest):
    if not request.current_text:
        return {"suggestion": "", "cached": False}

    try:
        # Try to get suggestion from cache first
        cache_key = redis_cache.generate_key(request.current_text)
        cached_suggestion = await redis_cache.get(cache_key)

        if cached_suggestion:
            return {"suggestion": cached_suggestion, "cached": True}

        # If not in cache, get from AI model
        ai_suggestion = await get_suggestion_from_ai_model(request.current_text)
        
        # Store in cache for future use
        await redis_cache.set(cache_key, ai_suggestion)
        
        return {"suggestion": ai_suggestion, "cached": False}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"An error occurred in the endpoint: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating the suggestion.")

@app.get("/")
def read_root():
    return {"message": "Suggestive Text API is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, workers=4) 
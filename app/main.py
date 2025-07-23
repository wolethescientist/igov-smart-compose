import os
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware  
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from app.rate_limiter import RateLimitMiddleware
from app.cache import RedisCache
import logging
from redis import Redis
from redis.exceptions import ConnectionError, TimeoutError
from typing import Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Load environment variables
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set")

# Configure allowed hosts
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

COMPLETION_PROMPT = """You are a smart compose assistant for a government organization. Your task is to provide concise, professional, and contextually relevant sentence completion suggestions for user inputs in forms, emails, or documents. Follow these guidelines:





Suggestions must be formal, clear, and adhere to government communication standards.



Use precise, inclusive, and neutral language, avoiding jargon unless contextually appropriate.



Prioritize clarity and brevity, keeping suggestions under 15 words.



Ensure suggestions align with the user's input context, tone, and intent.



Avoid sensitive or classified information; focus on general government-related topics (e.g., policy, services, compliance).



Provide 1 suggestions per input, ordered by relevance.





If the input is ambiguous, suggest safe, generic completions suitable for government use.

Example: Input: "We are committed to improving public services by..." Suggestions: enhancing accessibility and efficiency for all citizens. 

User's text: "{text}"

Completion:"""

app = FastAPI(
    title="Igov Smart Compose",
    description="An API that uses Google's Gemini to provide text suggestions, similar to Gmail's Smart Compose."
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Get Redis URL from environment variable
redis_url = os.getenv("REDIS_URL")
redis_cache = None
redis_available = False

@app.on_event("startup")
async def startup_event():
    global redis_cache, redis_available
    # Only try to connect to Redis if URL is provided
    if redis_url:
        try:
            redis = Redis.from_url(redis_url, decode_responses=True)
            redis.ping()
            redis_available = True
            redis_cache = RedisCache(redis_url)
            logger.info("Successfully connected to Redis at %s", redis_url)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(" Redis not available at %s: %s", redis_url, str(e))
        except Exception as e:
            logger.error(" Unexpected error while connecting to Redis: %s", str(e))
    else:
        logger.info(" No Redis URL provided, running without Redis features")

# Only add rate limiting middleware if Redis URL is provided
if redis_url:
    app.add_middleware(RateLimitMiddleware, redis_url=redis_url)

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

@app.post("/api/generate-suggestion", response_model=SuggestionResponse)
async def generate_suggestion(request: SuggestionRequest):
    if not request.current_text:
        return {"suggestion": "", "cached": False}

    try:
        # Only try cache if Redis is available
        if redis_cache and redis_available:
            try:
                # Try to get suggestion from cache first
                cache_key = redis_cache.generate_key(request.current_text)
                cached_suggestion = await redis_cache.get(cache_key)

                if cached_suggestion:
                    return {"suggestion": cached_suggestion, "cached": True}
            except Exception as e:
                logger.error(f"Cache operation failed: {e}")
                # Continue without cache if there's an error

        # Get from AI model
        ai_suggestion = await get_suggestion_from_ai_model(request.current_text)
        
        # Try to store in cache if Redis is available
        if redis_cache and redis_available:
            try:
                cache_key = redis_cache.generate_key(request.current_text)
                await redis_cache.set(cache_key, ai_suggestion)
            except Exception as e:
                logger.error(f"Failed to store in cache: {e}")
        
        return {"suggestion": ai_suggestion, "cached": False}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"An error occurred in the endpoint: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating the suggestion.")

# API health check endpoint
@app.get("/api/health")
def health_check():
    return {"message": "Suggestive Text API is running."}

# Mount static files AFTER defining API routes
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        workers=4,
        proxy_headers=True,
        forwarded_allow_ips="*",
        allowed_hosts=ALLOWED_HOSTS
    ) 
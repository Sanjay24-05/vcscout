"""Gemini 2.0 Flash LLM integration with rate limiting"""

import asyncio
import json
import time
from typing import Any, Type, TypeVar

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings

T = TypeVar("T", bound=BaseModel)


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, calls_per_minute: int = 10):
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self._last_call = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limit"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
            self._last_call = time.monotonic()


# Global rate limiter - Gemini free tier is 15 RPM, we use 10 to be safe
_rate_limiter = RateLimiter(calls_per_minute=10)


class GeminiClient:
    """Client for Google Gemini Flash with rate limiting"""
    
    def __init__(self):
        self.settings = get_settings()
        genai.configure(api_key=self.settings.gemini_api_key)
        
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=8192,
            ),
        )
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((ResourceExhausted, Exception)),
    )
    async def generate(
        self, 
        prompt: str,
        system_instruction: str | None = None,
    ) -> str:
        """
        Generate text response from Gemini.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            
        Returns:
            Generated text response
        """
        await _rate_limiter.acquire()
        
        if system_instruction:
            full_prompt = f"{system_instruction}\n\n{prompt}"
        else:
            full_prompt = prompt
        
        response = await self.model.generate_content_async(full_prompt)
        return response.text
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((ResourceExhausted, Exception)),
    )
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
    ) -> T:
        """
        Generate a structured response that conforms to a Pydantic model.
        
        Args:
            prompt: The user prompt
            response_model: Pydantic model class for the response
            system_instruction: Optional system instruction
            
        Returns:
            Parsed response as the specified Pydantic model
        """
        # Apply rate limiting
        await _rate_limiter.acquire()
        
        # Build schema instruction
        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)
        
        structured_prompt = f"""
{system_instruction or ""}

{prompt}

IMPORTANT: You must respond with ONLY valid JSON that matches this schema:
{schema_str}

Respond with the JSON object only, no markdown code blocks or additional text.
"""
        
        response = await self.model.generate_content_async(structured_prompt)
        response_text = response.text.strip()
        
        # Clean up response if it has markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (code block markers)
            response_text = "\n".join(lines[1:-1])
        
        # Parse JSON and validate with Pydantic
        data = json.loads(response_text)
        return response_model.model_validate(data)
    
    async def generate_stream(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ):
        """
        Stream text response from Gemini.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            
        Yields:
            Text chunks as they are generated
        """
        await _rate_limiter.acquire()
        
        if system_instruction:
            full_prompt = f"{system_instruction}\n\n{prompt}"
        else:
            full_prompt = prompt
        
        response = await self.model.generate_content_async(
            full_prompt,
            stream=True,
        )
        
        async for chunk in response:
            if chunk.text:
                yield chunk.text


# Singleton instance
_gemini_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    """Get the Gemini client singleton"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client

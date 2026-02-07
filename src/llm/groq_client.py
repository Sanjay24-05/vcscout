"""Groq LLM integration - Free tier with generous limits (30 RPM)"""

import asyncio
import json
import time
from typing import AsyncIterator, Type, TypeVar

from groq import AsyncGroq, RateLimitError
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
    
    def __init__(self, calls_per_minute: int = 25):
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


# Global rate limiter - Groq free tier is 30 RPM, we use 25 to be safe
_rate_limiter = RateLimiter(calls_per_minute=25)


class GroqClient:
    """Client for Groq API with Llama 3.3, Qwen, and Mixtral models"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncGroq(api_key=self.settings.groq_api_key)
        self.model = self.settings.llm_model
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((RateLimitError, Exception)),
    )
    async def generate(
        self, 
        prompt: str,
        system_instruction: str | None = None,
    ) -> str:
        """
        Generate text response from Groq.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            
        Returns:
            Generated text response
        """
        await _rate_limiter.acquire()
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
        )
        
        return response.choices[0].message.content
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((RateLimitError, Exception)),
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
        await _rate_limiter.acquire()
        
        # Build schema instruction
        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)
        
        json_instruction = f"""
IMPORTANT: You must respond with ONLY valid JSON that matches this schema:
{schema_str}

Respond with the JSON object only, no markdown code blocks or additional text.
"""
        
        messages = []
        system_content = (system_instruction or "") + "\n\n" + json_instruction
        messages.append({"role": "system", "content": system_content.strip()})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean up response if it has markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (code block markers)
            response_text = "\n".join(lines[1:-1])
        
        # Also handle ending code block marker if present
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()
        
        # Parse JSON and validate with Pydantic
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"Could not parse JSON from response: {response_text[:200]}")
        
        return response_model.model_validate(data)
    
    async def generate_stream(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream text response from Groq.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            
        Yields:
            Text chunks as they are generated
        """
        await _rate_limiter.acquire()
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Singleton instance
_groq_client: GroqClient | None = None


def get_groq_client() -> GroqClient:
    """Get the Groq client singleton"""
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client

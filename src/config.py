"""Configuration management using Pydantic Settings"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # LLM - Groq (free, fast, generous limits)
    groq_api_key: str
    llm_model: str = "llama-3.3-70b-versatile"  # or "qwen-qwq-32b", "mixtral-8x7b-32768"
    
    # Legacy Gemini (optional fallback)
    gemini_api_key: str = ""
    
    # Database
    neon_database_url: str
    
    # Pivoting Configuration
    max_pivot_attempts: int = 3
    pivot_threshold: int = 5
    
    # Agent Timeouts
    agent_timeout: int = 60
    
    # Search Settings
    search_num_results: int = 10
    
    # Scraper Settings
    scrape_timeout: int = 30
    max_competitors_to_scrape: int = 5
    
    # Session
    session_cookie_name: str = "vcscout_session"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

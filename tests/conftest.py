"""Test configuration for pytest"""

import pytest
import os

# Ensure we have dummy env vars for tests that might load settings
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GEMINI_API_KEY", "test-api-key")
os.environ.setdefault("NEON_DATABASE_URL", "postgresql://test:test@localhost/test")


@pytest.fixture
def mock_settings():
    """Fixture providing mock settings"""
    from unittest.mock import MagicMock
    
    settings = MagicMock()
    settings.groq_api_key = "test-groq-key"
    settings.llm_model = "llama-3.3-70b-versatile"
    settings.gemini_api_key = "test-key"
    settings.neon_database_url = "postgresql://test:test@localhost/test"
    settings.max_pivot_attempts = 3
    settings.pivot_threshold = 5
    settings.agent_timeout = 60
    settings.search_num_results = 10
    settings.scrape_timeout = 30
    settings.max_competitors_to_scrape = 5
    
    return settings

"""Input Validator Agent - Detects irrelevant/invalid inputs early to save API calls"""

import re
from src.graph.state import AgentState, InputValidationResult
from src.llm.groq_client import get_groq_client


SYSTEM_INSTRUCTION = """You are an input validator for a startup idea analysis system.

Your job is to determine if the user input is a valid startup/business idea that can be meaningfully analyzed.

VALID inputs (return is_valid=true):
- Product or service concepts (even if vague like "Uber for dogs")
- Business ideas with a clear value proposition
- App/platform concepts
- Technology solutions
- Single company names that imply a business model (e.g., "Airbnb for boats")

INVALID inputs (return is_valid=false):
- Gibberish or random characters ("asdfasdf", "xyz123")
- Off-topic queries ("what's the weather", "tell me a joke", "pizza recipe")
- Questions not about business ideas ("what is AI?", "how do I code?")
- Empty or extremely short inputs (less than 2 meaningful words)
- Explicit harmful or illegal business ideas

For borderline cases (single words like "Uber" or very vague ideas):
- Mark as valid but provide a suggested_reframe to make it more specific

Be LENIENT - if there's any chance it could be interpreted as a business idea, accept it.
Your goal is to catch obvious garbage, not to filter out creative ideas."""


async def input_validator(state: AgentState) -> dict:
    """
    Validate if the input is a legitimate startup idea.
    
    Returns:
        dict with input_validation containing:
        - is_valid: bool
        - rejection_reason: str | None  
        - suggested_reframe: str | None
    """
    idea = state.get("current_idea", "").strip()
    
    # Quick pre-checks (no LLM needed)
    
    # Check for empty or too short
    if not idea or len(idea) < 3:
        return {
            "input_validation": InputValidationResult(
                is_valid=False,
                rejection_reason="Input is too short. Please describe a startup idea.",
                suggested_reframe=None,
            ).model_dump(),
            "status": "invalid_input",
        }
    
    # Check for obvious gibberish (no vowels, all special chars, etc.)
    if _is_obvious_gibberish(idea):
        return {
            "input_validation": InputValidationResult(
                is_valid=False,
                rejection_reason="Input appears to be gibberish. Please enter a valid startup idea.",
                suggested_reframe=None,
            ).model_dump(),
            "status": "invalid_input",
        }
    
    # For very short inputs (1-3 words), use LLM to validate
    # For longer inputs that look like sentences, likely valid
    word_count = len(idea.split())
    
    if word_count >= 5 and _looks_like_business_idea(idea):
        # Likely valid, skip LLM call
        return {
            "input_validation": InputValidationResult(
                is_valid=True,
                rejection_reason=None,
                suggested_reframe=None,
            ).model_dump(),
            "status": "validated",
        }
    
    # Use LLM to validate ambiguous cases
    prompt = f"""Analyze this input and determine if it's a valid startup/business idea:

INPUT: "{idea}"

Respond with:
1. is_valid: true or false
2. rejection_reason: If invalid, explain why (keep it short and helpful)
3. suggested_reframe: If valid but vague, suggest a more specific version

Examples:
- "asdfasdf" → is_valid: false, rejection_reason: "This appears to be random text, not a business idea"
- "Uber" → is_valid: true, suggested_reframe: "Uber-like service for [specific industry/use case]"
- "AI tool for lawyers" → is_valid: true, no reframe needed
- "what is machine learning" → is_valid: false, rejection_reason: "This is a question, not a business idea"
"""

    llm = get_groq_client()
    result = await llm.generate_structured(
        prompt=prompt,
        response_model=InputValidationResult,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    return {
        "input_validation": result.model_dump(),
        "status": "validated" if result.is_valid else "invalid_input",
    }


def _is_obvious_gibberish(text: str) -> bool:
    """Quick heuristic check for obvious gibberish"""
    # Remove spaces and check
    clean = re.sub(r'\s+', '', text.lower())
    
    # All same character
    if len(set(clean)) <= 2 and len(clean) > 3:
        return True
    
    # No vowels at all (unlikely to be real words)
    vowels = set('aeiou')
    if len(clean) > 5 and not any(c in vowels for c in clean):
        return True
    
    # Mostly numbers/special chars
    alpha_count = sum(1 for c in clean if c.isalpha())
    if len(clean) > 3 and alpha_count / len(clean) < 0.5:
        return True
    
    return False


def _looks_like_business_idea(text: str) -> bool:
    """Heuristic check if text looks like a business concept"""
    text_lower = text.lower()
    
    # Common business/startup keywords
    keywords = [
        'app', 'platform', 'service', 'tool', 'software', 'saas',
        'marketplace', 'ai', 'automated', 'solution', 'startup',
        'business', 'company', 'product', 'subscription', 'b2b', 'b2c',
        'for', 'that', 'which', 'helps', 'enables', 'allows',
        'uber', 'airbnb', 'like', 'similar', 'alternative',
    ]
    
    return any(kw in text_lower for kw in keywords)

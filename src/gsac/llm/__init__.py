"""
gs-ai-crawl LLM集成模块
"""

from .prompts import (
    CLEAN_CONTENT_PROMPT,
    GENERATE_KEYWORDS_PROMPT,
    PARSE_INTENT_PROMPT,
    SUMMARIZE_RESULTS_PROMPT,
)
from .provider import get_anthropic_llm, get_llm, get_ollama_llm, get_openai_llm

__all__ = [
    "CLEAN_CONTENT_PROMPT",
    "GENERATE_KEYWORDS_PROMPT",
    "PARSE_INTENT_PROMPT",
    "SUMMARIZE_RESULTS_PROMPT",
    "get_anthropic_llm",
    "get_llm",
    "get_ollama_llm",
    "get_openai_llm",
]

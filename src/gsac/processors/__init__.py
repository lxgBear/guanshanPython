"""
gs-ai-crawl 处理器模块

提供结果去重、内容清洗和输出格式化功能
"""

from .cleaner import (
    CleanedContent,
    clean_content_basic,
    clean_content_with_llm,
    clean_contents_batch,
    clean_contents_batch_with_llm,
    extract_main_content,
    normalize_whitespace,
    remove_html_tags,
)
from .deduplicator import (
    calculate_similarity,
    deduplicate_results,
    merge_results,
    normalize_url,
)
from .formatter import (
    format_as_json,
    format_as_markdown,
    format_as_structured,
    format_results,
)

__all__ = [
    # cleaner
    "CleanedContent",
    "clean_content_basic",
    "clean_content_with_llm",
    "clean_contents_batch",
    "clean_contents_batch_with_llm",
    "extract_main_content",
    "normalize_whitespace",
    "remove_html_tags",
    # deduplicator
    "calculate_similarity",
    "deduplicate_results",
    "merge_results",
    "normalize_url",
    # formatter
    "format_as_json",
    "format_as_markdown",
    "format_as_structured",
    "format_results",
]

"""
结果去重处理器

实现URL去重和相似度过滤
"""

from difflib import SequenceMatcher
from urllib.parse import urlparse

from ..models.schemas import SearchResult


def normalize_url(url: str) -> str:
    """
    标准化URL用于比较

    移除协议、www前缀和尾部斜杠
    """
    parsed = urlparse(url.lower())
    netloc = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度

    使用SequenceMatcher算法
    """
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def deduplicate_results(
    results: list[SearchResult],
    similarity_threshold: float = 0.8,
) -> list[SearchResult]:
    """
    去重搜索结果

    Args:
        results: 原始搜索结果列表
        similarity_threshold: 标题相似度阈值(0.0-1.0)

    Returns:
        去重后的结果列表
    """
    if not results:
        return []

    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    unique_results: list[SearchResult] = []

    for result in results:
        # URL精确去重
        normalized_url = normalize_url(result.url)
        if normalized_url in seen_urls:
            continue

        # 标题相似度去重
        is_similar = False
        for seen_title in seen_titles:
            if calculate_similarity(result.title, seen_title) > similarity_threshold:
                is_similar = True
                break

        if is_similar:
            continue

        # 添加到结果
        seen_urls.add(normalized_url)
        seen_titles.append(result.title)
        unique_results.append(result)

    return unique_results


def merge_results(
    result_lists: list[list[SearchResult]],
    similarity_threshold: float = 0.8,
) -> list[SearchResult]:
    """
    合并多个结果列表并去重

    Args:
        result_lists: 多个搜索结果列表
        similarity_threshold: 相似度阈值

    Returns:
        合并去重后的结果列表
    """
    all_results: list[SearchResult] = []
    for results in result_lists:
        all_results.extend(results)

    return deduplicate_results(all_results, similarity_threshold)

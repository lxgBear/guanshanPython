"""
URL 规范化工具

用于标准化 URL 格式，提高去重效果。

功能:
- 移除 www 前缀
- 统一使用 HTTPS
- 移除尾部斜杠
- 移除跟踪参数（UTM 等）
- 转换为小写域名

作者: Claude (SuperClaude Framework)
日期: 2025-11-21
"""

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Set
import logging

logger = logging.getLogger(__name__)

# 需要移除的跟踪参数列表
DEFAULT_TRACKING_PARAMS: Set[str] = {
    'utm_source',
    'utm_medium',
    'utm_campaign',
    'utm_term',
    'utm_content',
    'utm_id',
    'utm_source_platform',
    'utm_creative_format',
    'utm_marketing_tactic',
    'gclid',  # Google Ads
    'fbclid',  # Facebook Ads
    'msclkid',  # Microsoft Ads
    'dclid',  # DoubleClick
    '_ga',  # Google Analytics
    'mc_cid',  # Mailchimp
    'mc_eid',  # Mailchimp
    'ref',  # Referrer
    'source',  # 通用来源参数
}


def normalize_url(url: str, remove_tracking: bool = True) -> str:
    """
    URL 规范化

    将各种 URL 变体标准化为统一格式，提高去重准确性。

    转换规则:
    - http://example.com → https://example.com
    - www.example.com → example.com
    - example.com/page/ → example.com/page
    - example.com/page?utm_source=xxx → example.com/page

    Args:
        url: 原始 URL
        remove_tracking: 是否移除跟踪参数（默认 True）

    Returns:
        规范化后的 URL

    Examples:
        >>> normalize_url("http://www.example.com/page/?utm_source=test")
        'https://example.com/page'

        >>> normalize_url("EXAMPLE.COM/Page")
        'https://example.com/Page'
    """
    if not url or not isinstance(url, str):
        return url

    try:
        # 如果 URL 不包含协议，添加 https://
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"

        parsed = urlparse(url)

        # 1. 转为小写域名（保持路径大小写）
        netloc = parsed.netloc.lower()

        # 2. 移除 www 前缀
        if netloc.startswith('www.'):
            netloc = netloc[4:]

        # 3. 移除尾部斜杠（但保留根路径的斜杠）
        path = parsed.path.rstrip('/') if parsed.path not in ('/', '') else ''

        # 4. 处理查询参数
        query = parsed.query
        if remove_tracking and query:
            query_params = parse_qs(query)
            # 移除跟踪参数
            cleaned_params = {
                k: v for k, v in query_params.items()
                if k not in DEFAULT_TRACKING_PARAMS
            }
            query = urlencode(cleaned_params, doseq=True) if cleaned_params else ''

        # 5. 强制使用 HTTPS（除非明确是本地开发）
        scheme = 'https'
        if netloc.startswith(('localhost', '127.0.0.1', '192.168.', '10.')):
            scheme = parsed.scheme  # 本地开发保留原始协议

        # 6. 重新组装 URL（忽略 fragment）
        normalized = urlunparse((scheme, netloc, path, '', query, ''))

        logger.debug(f"URL 规范化: {url} → {normalized}")
        return normalized

    except Exception as e:
        logger.warning(f"URL 规范化失败: {url}, 错误: {e}")
        # 失败时返回原始 URL
        return url


def is_same_url(url1: str, url2: str) -> bool:
    """
    判断两个 URL 是否实质相同（规范化后比较）

    Args:
        url1: 第一个 URL
        url2: 第二个 URL

    Returns:
        是否相同

    Examples:
        >>> is_same_url("http://www.example.com/", "https://example.com")
        True

        >>> is_same_url("example.com/page", "example.com/page?utm_source=test")
        True
    """
    return normalize_url(url1) == normalize_url(url2)


def add_tracking_param(param: str) -> None:
    """
    添加自定义跟踪参数到移除列表

    Args:
        param: 参数名称

    Examples:
        >>> add_tracking_param("my_campaign_id")
    """
    DEFAULT_TRACKING_PARAMS.add(param)
    logger.info(f"添加跟踪参数: {param}")


def get_domain(url: str) -> str:
    """
    提取 URL 的域名

    Args:
        url: URL 字符串

    Returns:
        域名（小写，不含 www）

    Examples:
        >>> get_domain("https://www.example.com/path")
        'example.com'
    """
    try:
        normalized = normalize_url(url)
        parsed = urlparse(normalized)
        return parsed.netloc
    except Exception as e:
        logger.warning(f"提取域名失败: {url}, 错误: {e}")
        return ""


def batch_normalize_urls(urls: list[str]) -> dict[str, str]:
    """
    批量规范化 URL

    Args:
        urls: URL 列表

    Returns:
        映射字典 {原始URL: 规范化URL}

    Examples:
        >>> batch_normalize_urls(["http://example.com", "www.example.com"])
        {'http://example.com': 'https://example.com',
         'www.example.com': 'https://example.com'}
    """
    return {url: normalize_url(url) for url in urls}

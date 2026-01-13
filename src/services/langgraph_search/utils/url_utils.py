"""URL 工具模块

提供 URL 规范化和域名提取功能，用于搜索结果去重和来源识别。
"""

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional
import re


def normalize_url(url: str) -> str:
    """规范化 URL 用于去重比较

    处理步骤:
    1. 转换为小写
    2. 移除 www. 前缀
    3. 移除尾部斜杠
    4. 移除常见追踪参数
    5. 排序查询参数

    Args:
        url: 原始 URL

    Returns:
        规范化后的 URL

    Example:
        >>> normalize_url("https://WWW.Example.com/path/?utm_source=google&id=1")
        'https://example.com/path?id=1'

        >>> normalize_url("https://example.com/article/")
        'https://example.com/article'
    """
    if not url:
        return ""

    # 转换为小写以便检测协议
    url_lower = url.lower()

    # 确保有协议
    if not url_lower.startswith(("http://", "https://")):
        url_lower = "https://" + url_lower

    try:
        parsed = urlparse(url_lower)
    except Exception:
        return url.lower()

    # 移除 www. 前缀
    netloc = parsed.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # 移除端口号 (如果是默认端口)
    if netloc.endswith(":80") or netloc.endswith(":443"):
        netloc = netloc.rsplit(":", 1)[0]

    # 规范化路径
    path = parsed.path
    # 移除尾部斜杠 (除非是根路径)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    # 空路径设为 /
    if not path:
        path = ""

    # 过滤追踪参数
    tracking_params = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid",
        "_ga", "_gl", "pk_campaign", "pk_kwd",
        "msclkid", "zanpid", "dclid",
    }

    # 解析并过滤查询参数
    if parsed.query:
        query_params = parse_qs(parsed.query, keep_blank_values=False)
        # 过滤追踪参数
        filtered_params = {
            k: v for k, v in query_params.items()
            if k.lower() not in tracking_params
        }
        # 排序并重建查询字符串
        if filtered_params:
            sorted_params = sorted(filtered_params.items())
            query = urlencode(sorted_params, doseq=True)
        else:
            query = ""
    else:
        query = ""

    # 重建 URL
    normalized = urlunparse((
        parsed.scheme,
        netloc,
        path,
        "",  # params
        query,
        ""   # fragment (移除)
    ))

    return normalized


def extract_domain(url: str) -> str:
    """从 URL 提取主域名

    Args:
        url: 完整 URL

    Returns:
        主域名 (不含 www.)

    Example:
        >>> extract_domain("https://www.reuters.com/world/article")
        'reuters.com'

        >>> extract_domain("https://api.example.co.uk/path")
        'example.co.uk'
    """
    if not url:
        return ""

    # 确保有协议
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
    except Exception:
        return ""

    # 移除端口号
    if ":" in domain:
        domain = domain.split(":")[0]

    # 移除 www. 前缀
    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def is_same_domain(url1: str, url2: str) -> bool:
    """检查两个 URL 是否属于同一域名

    Args:
        url1: 第一个 URL
        url2: 第二个 URL

    Returns:
        是否同一域名
    """
    return extract_domain(url1) == extract_domain(url2)


def get_root_domain(domain: str) -> str:
    """获取根域名 (去除子域名)

    Args:
        domain: 完整域名

    Returns:
        根域名

    Example:
        >>> get_root_domain("api.news.bbc.com")
        'bbc.com'

        >>> get_root_domain("whitehouse.gov")
        'whitehouse.gov'
    """
    if not domain:
        return ""

    # 常见的二级域名后缀
    second_level_tlds = {
        "co.uk", "co.jp", "co.kr", "co.nz", "co.za",
        "com.au", "com.br", "com.cn", "com.hk", "com.tw",
        "com.sg", "com.my", "com.ph",
        "org.uk", "org.au", "org.cn",
        "net.au", "net.cn",
        "gov.uk", "gov.au", "gov.cn",
        "edu.au", "edu.cn", "edu.hk",
        "ac.uk", "ac.jp", "ac.kr",
    }

    parts = domain.lower().split(".")

    if len(parts) <= 2:
        return domain

    # 检查是否是二级域名后缀
    possible_sld = ".".join(parts[-2:])
    if possible_sld in second_level_tlds:
        if len(parts) >= 3:
            return ".".join(parts[-3:])
        return domain

    return ".".join(parts[-2:])


def is_valid_url(url: str) -> bool:
    """检查 URL 是否有效

    Args:
        url: 待检查的 URL

    Returns:
        是否有效
    """
    if not url:
        return False

    # 基本格式检查
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )

    return bool(url_pattern.match(url))


def clean_url_for_display(url: str, max_length: int = 50) -> str:
    """清理 URL 用于显示

    Args:
        url: 原始 URL
        max_length: 最大显示长度

    Returns:
        适合显示的 URL

    Example:
        >>> clean_url_for_display("https://example.com/very/long/path/to/article", 30)
        'example.com/very/long/path...'
    """
    if not url:
        return ""

    # 移除协议
    display_url = re.sub(r'^https?://', '', url)

    # 移除 www.
    if display_url.startswith("www."):
        display_url = display_url[4:]

    # 移除尾部斜杠
    display_url = display_url.rstrip("/")

    # 截断
    if len(display_url) > max_length:
        display_url = display_url[:max_length - 3] + "..."

    return display_url

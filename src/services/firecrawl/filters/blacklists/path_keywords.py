"""
路径关键词黑名单

定义需要过滤的URL路径关键词,按类别组织,支持优先级配置。

数据来源: docs/MAP_API_URL_FILTERING_SOLUTION.md
版本: v1.0.0
"""

from typing import List, Dict, Set


# ==================== 类别1: 用户操作页面 ====================
USER_OPERATION_KEYWORDS = [
    'login', 'signin', 'signup', 'register', 'auth', 'logout',
    'forgot-password', 'reset-password', 'change-password',
    'profile', 'settings', 'account', 'dashboard',
    'cart', 'checkout', 'order', 'payment',
    'wishlist', 'favorites', 'bookmark'
]

# ==================== 类别2: 系统功能页面 ====================
SYSTEM_FUNCTION_KEYWORDS = [
    'admin', 'api', 'ajax', 'jsonp', 'rss', 'feed', 'sitemap',
    'robots.txt', 'search', 'filter', 'sort',
    'print', 'share', 'comment', 'reply',
    'subscribe', 'unsubscribe', 'newsletter'
]

# ==================== 类别3: 分页和排序 ====================
PAGINATION_SORTING_KEYWORDS = [
    'page=', 'p=', 'offset=', 'limit=',
    'sort=', 'order=', 'orderby=',
    'next=', 'prev=', 'previous='
]

# ==================== 类别4: 跟踪和分析 ====================
TRACKING_ANALYTICS_KEYWORDS = [
    'utm_', 'ref=', 'source=', 'medium=', 'campaign=',
    'track', 'analytics', 'pixel', 'beacon',
    'redirect', 'goto', 'out', 'away'
]

# ==================== 类别5: 存档和旧版本 ====================
ARCHIVE_OLD_VERSION_KEYWORDS = [
    'archive', 'old', 'legacy', 'deprecated', 'obsolete',
    'v1', 'v2', '/20', '/2019/', '/2020/', '/2021/', '/2022/',  # 旧年份
    'backup', 'temp', 'tmp', 'cache'
]

# ==================== 优先级配置 ====================
# 优先级: critical > high > medium > low
PRIORITY_CRITICAL_KEYWORDS = USER_OPERATION_KEYWORDS
PRIORITY_HIGH_KEYWORDS = SYSTEM_FUNCTION_KEYWORDS
PRIORITY_MEDIUM_KEYWORDS = PAGINATION_SORTING_KEYWORDS + TRACKING_ANALYTICS_KEYWORDS
PRIORITY_LOW_KEYWORDS = ARCHIVE_OLD_VERSION_KEYWORDS


def get_all_keywords() -> List[str]:
    """获取所有路径关键词黑名单

    Returns:
        List[str]: 所有黑名单关键词列表(去重)
    """
    all_keywords = (
        USER_OPERATION_KEYWORDS +
        SYSTEM_FUNCTION_KEYWORDS +
        PAGINATION_SORTING_KEYWORDS +
        TRACKING_ANALYTICS_KEYWORDS +
        ARCHIVE_OLD_VERSION_KEYWORDS
    )
    return list(set(all_keywords))  # 去重


def get_keywords_by_priority(priority: str) -> List[str]:
    """根据优先级获取关键词列表

    Args:
        priority: 优先级 ('critical', 'high', 'medium', 'low', 'all')

    Returns:
        List[str]: 对应优先级的关键词列表

    Raises:
        ValueError: 如果优先级无效
    """
    priority_map = {
        'critical': PRIORITY_CRITICAL_KEYWORDS,
        'high': PRIORITY_HIGH_KEYWORDS,
        'medium': PRIORITY_MEDIUM_KEYWORDS,
        'low': PRIORITY_LOW_KEYWORDS,
        'all': get_all_keywords()
    }

    if priority not in priority_map:
        raise ValueError(
            f"无效的优先级: {priority}. "
            f"有效值: {list(priority_map.keys())}"
        )

    return priority_map[priority]


def get_keywords_by_category(category: str) -> List[str]:
    """根据类别获取关键词列表

    Args:
        category: 类别名称

    Returns:
        List[str]: 对应类别的关键词列表

    Raises:
        ValueError: 如果类别无效
    """
    category_map = {
        'user_operation': USER_OPERATION_KEYWORDS,
        'system_function': SYSTEM_FUNCTION_KEYWORDS,
        'pagination_sorting': PAGINATION_SORTING_KEYWORDS,
        'tracking_analytics': TRACKING_ANALYTICS_KEYWORDS,
        'archive_old': ARCHIVE_OLD_VERSION_KEYWORDS
    }

    if category not in category_map:
        raise ValueError(
            f"无效的类别: {category}. "
            f"有效值: {list(category_map.keys())}"
        )

    return category_map[category]


def get_custom_blacklist(
    include_categories: List[str] = None,
    exclude_categories: List[str] = None,
    additional_keywords: List[str] = None
) -> Set[str]:
    """构建自定义黑名单

    Args:
        include_categories: 包含的类别列表
        exclude_categories: 排除的类别列表
        additional_keywords: 额外添加的关键词

    Returns:
        Set[str]: 自定义黑名单集合
    """
    all_categories = [
        'user_operation',
        'system_function',
        'pagination_sorting',
        'tracking_analytics',
        'archive_old'
    ]

    # 确定要包含的类别
    if include_categories:
        categories = [c for c in include_categories if c in all_categories]
    else:
        categories = all_categories

    # 排除指定类别
    if exclude_categories:
        categories = [c for c in categories if c not in exclude_categories]

    # 收集关键词
    keywords = set()
    for category in categories:
        keywords.update(get_keywords_by_category(category))

    # 添加额外关键词
    if additional_keywords:
        keywords.update(additional_keywords)

    return keywords


# ==================== 预设配置 ====================
DEFAULT_BLACKLIST = get_all_keywords()
CONSERVATIVE_BLACKLIST = get_keywords_by_priority('critical') + get_keywords_by_priority('high')
AGGRESSIVE_BLACKLIST = get_all_keywords()


# ==================== 统计信息 ====================
def get_statistics() -> Dict[str, int]:
    """获取黑名单统计信息

    Returns:
        Dict[str, int]: 统计信息字典
    """
    return {
        'total_keywords': len(get_all_keywords()),
        'user_operation': len(USER_OPERATION_KEYWORDS),
        'system_function': len(SYSTEM_FUNCTION_KEYWORDS),
        'pagination_sorting': len(PAGINATION_SORTING_KEYWORDS),
        'tracking_analytics': len(TRACKING_ANALYTICS_KEYWORDS),
        'archive_old': len(ARCHIVE_OLD_VERSION_KEYWORDS),
        'critical_priority': len(PRIORITY_CRITICAL_KEYWORDS),
        'high_priority': len(PRIORITY_HIGH_KEYWORDS),
        'medium_priority': len(PRIORITY_MEDIUM_KEYWORDS),
        'low_priority': len(PRIORITY_LOW_KEYWORDS)
    }

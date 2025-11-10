"""
文件扩展名黑名单

定义需要过滤的文件扩展名,按文件类型分类。

数据来源: docs/MAP_API_URL_FILTERING_SOLUTION.md
版本: v1.0.0
"""

from typing import List, Dict, Set


# ==================== 类别1: 文档文件 ====================
DOCUMENT_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.rtf', '.odt', '.ods', '.odp'
]

# ==================== 类别2: 压缩文件 ====================
ARCHIVE_EXTENSIONS = [
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz',
    '.dmg', '.pkg', '.deb', '.rpm'
]

# ==================== 类别3: 媒体文件 ====================
MEDIA_EXTENSIONS = [
    # 图片
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico', '.webp',
    # 视频
    '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm',
    # 音频
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'
]

# ==================== 类别4: 可执行文件 ====================
EXECUTABLE_EXTENSIONS = [
    '.exe', '.msi', '.app', '.bin', '.sh', '.bat', '.cmd',
    '.apk', '.ipa', '.jar'
]

# ==================== 类别5: 源代码文件 ====================
SOURCE_CODE_EXTENSIONS = [
    '.py', '.java', '.cpp', '.c', '.h', '.js', '.ts',
    '.rb', '.php', '.go', '.rs', '.swift', '.kt'
]

# ==================== 类别6: 配置和数据文件 ====================
CONFIG_DATA_EXTENSIONS = [
    '.xml', '.json', '.yml', '.yaml', '.ini', '.conf', '.cfg',
    '.csv', '.sql', '.db', '.sqlite'
]


def get_all_extensions() -> List[str]:
    """获取所有文件扩展名黑名单

    Returns:
        List[str]: 所有黑名单扩展名列表(去重)
    """
    all_extensions = (
        DOCUMENT_EXTENSIONS +
        ARCHIVE_EXTENSIONS +
        MEDIA_EXTENSIONS +
        EXECUTABLE_EXTENSIONS +
        SOURCE_CODE_EXTENSIONS +
        CONFIG_DATA_EXTENSIONS
    )
    return list(set(all_extensions))  # 去重


def get_extensions_by_category(category: str) -> List[str]:
    """根据类别获取扩展名列表

    Args:
        category: 类别名称

    Returns:
        List[str]: 对应类别的扩展名列表

    Raises:
        ValueError: 如果类别无效
    """
    category_map = {
        'document': DOCUMENT_EXTENSIONS,
        'archive': ARCHIVE_EXTENSIONS,
        'media': MEDIA_EXTENSIONS,
        'executable': EXECUTABLE_EXTENSIONS,
        'source_code': SOURCE_CODE_EXTENSIONS,
        'config_data': CONFIG_DATA_EXTENSIONS
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
    additional_extensions: List[str] = None
) -> Set[str]:
    """构建自定义黑名单

    Args:
        include_categories: 包含的类别列表
        exclude_categories: 排除的类别列表
        additional_extensions: 额外添加的扩展名

    Returns:
        Set[str]: 自定义黑名单集合
    """
    all_categories = [
        'document',
        'archive',
        'media',
        'executable',
        'source_code',
        'config_data'
    ]

    # 确定要包含的类别
    if include_categories:
        categories = [c for c in include_categories if c in all_categories]
    else:
        categories = all_categories

    # 排除指定类别
    if exclude_categories:
        categories = [c for c in categories if c not in exclude_categories]

    # 收集扩展名
    extensions = set()
    for category in categories:
        extensions.update(get_extensions_by_category(category))

    # 添加额外扩展名
    if additional_extensions:
        # 确保扩展名以 . 开头
        normalized_extensions = []
        for ext in additional_extensions:
            if not ext.startswith('.'):
                ext = '.' + ext
            normalized_extensions.append(ext.lower())
        extensions.update(normalized_extensions)

    return extensions


# ==================== 预设配置 ====================
DEFAULT_BLACKLIST = get_all_extensions()

CONSERVATIVE_BLACKLIST = (
    DOCUMENT_EXTENSIONS +
    ARCHIVE_EXTENSIONS +
    EXECUTABLE_EXTENSIONS
)

AGGRESSIVE_BLACKLIST = get_all_extensions()

# 仅过滤非HTML页面(保留HTML但过滤其他文件)
NON_HTML_BLACKLIST = (
    DOCUMENT_EXTENSIONS +
    ARCHIVE_EXTENSIONS +
    MEDIA_EXTENSIONS +
    EXECUTABLE_EXTENSIONS +
    SOURCE_CODE_EXTENSIONS +
    CONFIG_DATA_EXTENSIONS
)


# ==================== 统计信息 ====================
def get_statistics() -> Dict[str, int]:
    """获取黑名单统计信息

    Returns:
        Dict[str, int]: 统计信息字典
    """
    return {
        'total_extensions': len(get_all_extensions()),
        'document': len(DOCUMENT_EXTENSIONS),
        'archive': len(ARCHIVE_EXTENSIONS),
        'media': len(MEDIA_EXTENSIONS),
        'executable': len(EXECUTABLE_EXTENSIONS),
        'source_code': len(SOURCE_CODE_EXTENSIONS),
        'config_data': len(CONFIG_DATA_EXTENSIONS)
    }


def is_web_page(url: str) -> bool:
    """判断URL是否是网页

    Args:
        url: URL字符串

    Returns:
        bool: True表示是网页, False表示是文件
    """
    from urllib.parse import urlparse
    import os

    parsed = urlparse(url)
    path = parsed.path.lower()

    # 检查是否有文件扩展名
    _, ext = os.path.splitext(path)

    if not ext:
        # 没有扩展名,认为是网页
        return True

    # 常见网页扩展名
    web_extensions = {'.html', '.htm', '.php', '.asp', '.aspx', '.jsp', '.do'}

    return ext in web_extensions

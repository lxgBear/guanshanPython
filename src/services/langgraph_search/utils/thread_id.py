"""线程ID工具 - 多用户隔离支持

提供安全的 thread_id 生成和验证功能，确保多用户环境下的数据隔离。

Security:
- thread_id 包含用户标识，防止跨用户访问
- 支持所有权验证
- 支持从 thread_id 提取用户信息
"""

import uuid
from datetime import datetime
from typing import Optional


def generate_secure_thread_id(
    user_id: str,
    operation: str = "search",
    prefix: str = "user"
) -> str:
    """生成包含用户标识的安全 thread_id

    格式: {prefix}_{user_id}_{operation}_{timestamp}_{random}

    Args:
        user_id: 用户ID (雪花算法ID)
        operation: 操作类型 (search, resume, review, etc.)
        prefix: 前缀 (默认 "user")

    Returns:
        安全的 thread_id

    Raises:
        ValueError: 如果 user_id 为空

    Example:
        >>> generate_secure_thread_id("123456789", "search")
        'user_123456789_search_20250108120000_a1b2c3d4'

        >>> generate_secure_thread_id("123456789", "resume")
        'user_123456789_resume_20250108120001_e5f6g7h8'
    """
    if not user_id:
        raise ValueError("user_id is required for generating secure thread_id")

    # 清理 user_id 中的特殊字符
    safe_user_id = str(user_id).replace("_", "-")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_part = str(uuid.uuid4())[:8]

    return f"{prefix}_{safe_user_id}_{operation}_{timestamp}_{random_part}"


def validate_thread_id_ownership(
    thread_id: str,
    user_id: str,
    prefix: str = "user"
) -> bool:
    """验证 thread_id 是否属于指定用户

    通过检查 thread_id 的前缀部分是否包含指定的 user_id

    Args:
        thread_id: 待验证的 thread_id
        user_id: 当前用户ID
        prefix: 前缀 (默认 "user")

    Returns:
        是否归属当前用户

    Example:
        >>> validate_thread_id_ownership("user_123_search_20250108_abc", "123")
        True

        >>> validate_thread_id_ownership("user_456_search_20250108_abc", "123")
        False
    """
    if not thread_id or not user_id:
        return False

    # 清理 user_id 中的特殊字符 (与生成时保持一致)
    safe_user_id = str(user_id).replace("_", "-")
    expected_prefix = f"{prefix}_{safe_user_id}_"

    return thread_id.startswith(expected_prefix)


def extract_user_id_from_thread_id(
    thread_id: str,
    prefix: str = "user"
) -> str:
    """从 thread_id 中提取用户ID

    Args:
        thread_id: 格式为 {prefix}_{user_id}_{operation}_{...} 的 thread_id
        prefix: 前缀 (默认 "user")

    Returns:
        用户ID

    Raises:
        ValueError: 如果 thread_id 格式无效

    Example:
        >>> extract_user_id_from_thread_id("user_123456789_search_20250108_abc")
        '123456789'
    """
    if not thread_id:
        raise ValueError("thread_id is required")

    expected_start = f"{prefix}_"
    if not thread_id.startswith(expected_start):
        raise ValueError(f"Invalid thread_id format: must start with '{expected_start}'")

    # 移除前缀后分割
    without_prefix = thread_id[len(expected_start):]
    parts = without_prefix.split("_")

    if len(parts) < 2:
        raise ValueError(f"Invalid thread_id format: {thread_id}")

    # 第一部分是 user_id (可能包含连字符，需要还原)
    user_id = parts[0].replace("-", "_")

    return user_id


def parse_thread_id(thread_id: str, prefix: str = "user") -> dict:
    """解析 thread_id 的各个组成部分

    Args:
        thread_id: 完整的 thread_id
        prefix: 前缀 (默认 "user")

    Returns:
        包含各部分的字典:
        - prefix: 前缀
        - user_id: 用户ID
        - operation: 操作类型
        - timestamp: 时间戳字符串
        - random: 随机部分

    Raises:
        ValueError: 如果 thread_id 格式无效

    Example:
        >>> parse_thread_id("user_123_search_20250108120000_abcd1234")
        {
            'prefix': 'user',
            'user_id': '123',
            'operation': 'search',
            'timestamp': '20250108120000',
            'random': 'abcd1234'
        }
    """
    if not thread_id:
        raise ValueError("thread_id is required")

    parts = thread_id.split("_")

    if len(parts) < 5:
        raise ValueError(f"Invalid thread_id format: expected at least 5 parts, got {len(parts)}")

    if parts[0] != prefix:
        raise ValueError(f"Invalid thread_id prefix: expected '{prefix}', got '{parts[0]}'")

    return {
        "prefix": parts[0],
        "user_id": parts[1].replace("-", "_"),
        "operation": parts[2],
        "timestamp": parts[3],
        "random": parts[4] if len(parts) > 4 else "",
    }


def is_valid_thread_id_format(thread_id: str, prefix: str = "user") -> bool:
    """检查 thread_id 格式是否有效

    Args:
        thread_id: 待检查的 thread_id
        prefix: 期望的前缀

    Returns:
        格式是否有效
    """
    try:
        parse_thread_id(thread_id, prefix)
        return True
    except ValueError:
        return False

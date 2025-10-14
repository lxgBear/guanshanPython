"""
安全ID生成器模块

提供雪花算法等多种安全ID生成策略，解决简单ID带来的安全隐患。

特性：
- 高性能雪花算法实现
- 分布式系统支持
- 可配置的机器ID和数据中心ID
- 时间戳精度可调
- 线程安全
"""

from .snowflake import SnowflakeGenerator
from .factory import IDGeneratorFactory
from .config import SnowflakeConfig
from .types import IDGeneratorType

# 默认全局生成器实例
_default_generator = None

def get_default_generator() -> SnowflakeGenerator:
    """获取默认的ID生成器实例"""
    global _default_generator
    if _default_generator is None:
        _default_generator = IDGeneratorFactory.create_snowflake()
    return _default_generator

def generate_id() -> int:
    """生成一个安全的64位整数ID"""
    return get_default_generator().generate()

def generate_string_id() -> str:
    """生成一个安全的字符串ID"""
    return str(generate_id())

__all__ = [
    "SnowflakeGenerator",
    "IDGeneratorFactory", 
    "SnowflakeConfig",
    "IDGeneratorType",
    "get_default_generator",
    "generate_id",
    "generate_string_id"
]
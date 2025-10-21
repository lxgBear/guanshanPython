"""缓存基础设施模块"""

from .redis_client import redis_client, cache_key_gen

__all__ = ["redis_client", "cache_key_gen"]

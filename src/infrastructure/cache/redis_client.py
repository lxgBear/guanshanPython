"""Redis 缓存客户端

提供 Redis 连接管理和缓存操作的封装

功能:
- 单例模式管理 Redis 连接
- 异步操作支持
- 自动序列化/反序列化
- TTL 管理
- 缓存失效策略
"""

import json
from typing import Optional, Any, Union
from datetime import timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Redis 客户端（单例模式）"""

    _instance: Optional['RedisClient'] = None
    _redis: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self):
        """建立 Redis 连接"""
        if self._redis is not None:
            logger.debug("Redis 连接已存在")
            return

        try:
            # 从环境变量获取 Redis URL
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')

            self._redis = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10
            )

            # 测试连接
            await self._redis.ping()
            logger.info(f"✅ Redis 连接成功: {redis_url}")

        except Exception as e:
            logger.warning(f"⚠️ Redis 连接失败: {e}. 将使用无缓存模式")
            self._redis = None

    async def close(self):
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("✅ Redis 连接已关闭")

    def is_available(self) -> bool:
        """检查 Redis 是否可用"""
        return self._redis is not None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值（支持 dict, list, str, int, float, bool）
            ttl: 过期时间（秒或 timedelta 对象）

        Returns:
            bool: 是否设置成功
        """
        if not self.is_available():
            return False

        try:
            # 序列化值
            serialized_value = json.dumps(value, ensure_ascii=False)

            # 设置缓存
            if ttl:
                if isinstance(ttl, timedelta):
                    ttl = int(ttl.total_seconds())
                await self._redis.setex(key, ttl, serialized_value)
            else:
                await self._redis.set(key, serialized_value)

            logger.debug(f"✅ 缓存已设置: {key} (TTL: {ttl}s)")
            return True

        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"❌ 缓存设置失败: {key} - {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            Any: 缓存值（已反序列化），不存在则返回 None
        """
        if not self.is_available():
            return None

        try:
            value = await self._redis.get(key)
            if value is None:
                logger.debug(f"🔍 缓存未命中: {key}")
                return None

            # 反序列化值
            deserialized_value = json.loads(value)
            logger.debug(f"✅ 缓存命中: {key}")
            return deserialized_value

        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"❌ 缓存读取失败: {key} - {e}")
            return None

    async def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            bool: 是否删除成功
        """
        if not self.is_available():
            return False

        try:
            result = await self._redis.delete(key)
            logger.debug(f"🗑️ 缓存已删除: {key}")
            return result > 0

        except RedisError as e:
            logger.error(f"❌ 缓存删除失败: {key} - {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        删除匹配模式的所有缓存键

        Args:
            pattern: 键模式（支持通配符 *）

        Returns:
            int: 删除的键数量
        """
        if not self.is_available():
            return 0

        try:
            # 使用 SCAN 而不是 KEYS（更安全）
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self._redis.delete(*keys)
                logger.info(f"🗑️ 批量删除缓存: {pattern} ({deleted} 个键)")
                return deleted

            return 0

        except RedisError as e:
            logger.error(f"❌ 批量删除缓存失败: {pattern} - {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在

        Args:
            key: 缓存键

        Returns:
            bool: 是否存在
        """
        if not self.is_available():
            return False

        try:
            result = await self._redis.exists(key)
            return result > 0

        except RedisError as e:
            logger.error(f"❌ 缓存检查失败: {key} - {e}")
            return False

    async def ttl(self, key: str) -> Optional[int]:
        """
        获取缓存剩余过期时间

        Args:
            key: 缓存键

        Returns:
            int | None: 剩余秒数，-1 表示永不过期，-2 表示不存在
        """
        if not self.is_available():
            return None

        try:
            result = await self._redis.ttl(key)
            return result

        except RedisError as e:
            logger.error(f"❌ TTL 查询失败: {key} - {e}")
            return None

    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        原子递增计数器

        Args:
            key: 缓存键
            amount: 递增量（默认1）

        Returns:
            int | None: 递增后的值
        """
        if not self.is_available():
            return None

        try:
            result = await self._redis.incrby(key, amount)
            return result

        except RedisError as e:
            logger.error(f"❌ 计数器递增失败: {key} - {e}")
            return None


# 全局 Redis 客户端实例
redis_client = RedisClient()


# 缓存键生成器
class CacheKeyGenerator:
    """缓存键生成器"""

    PREFIX = "guanshan"  # 项目前缀

    @staticmethod
    def search_result(report_id: str, search_query: str, limit: int) -> str:
        """搜索结果缓存键"""
        # 使用哈希值以处理长查询字符串
        query_hash = hash(search_query)
        return f"{CacheKeyGenerator.PREFIX}:search:{report_id}:{query_hash}:{limit}"

    @staticmethod
    def report_pattern(report_id: str) -> str:
        """报告相关的所有缓存键模式"""
        return f"{CacheKeyGenerator.PREFIX}:*:{report_id}:*"

    @staticmethod
    def task_pattern(task_id: str) -> str:
        """任务相关的所有缓存键模式"""
        return f"{CacheKeyGenerator.PREFIX}:*:*:{task_id}*"


# 导出
cache_key_gen = CacheKeyGenerator()

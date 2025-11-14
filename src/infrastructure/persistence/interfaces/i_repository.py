"""
Repository 基础接口定义

定义通用的 Repository 接口层次，遵循接口隔离原则（ISP）。
每个接口只包含相关的方法，具体 Repository 可以选择实现需要的接口组合。

Version: v3.0.0 (模块化架构)
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Tuple, Dict, Any

# 泛型类型变量，代表领域实体类型
T = TypeVar('T')


class IBasicRepository(ABC, Generic[T]):
    """
    基础 Repository 接口

    提供标准的 CRUD 操作，是所有 Repository 的基础接口。
    遵循单一职责原则，只负责基本的数据访问操作。

    Type Parameters:
        T: 领域实体类型

    Example:
        class SearchTaskRepository(IBasicRepository[SearchTask]):
            async def create(self, entity: SearchTask) -> str:
                # 实现创建逻辑
                pass
    """

    @abstractmethod
    async def create(self, entity: T) -> str:
        """
        创建实体

        Args:
            entity: 要创建的领域实体

        Returns:
            str: 创建成功后的实体ID

        Raises:
            RepositoryException: 创建失败时抛出
        """
        pass

    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[T]:
        """
        根据ID获取实体

        Args:
            id: 实体ID

        Returns:
            Optional[T]: 实体对象，如果不存在则返回 None

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def update(self, entity: T) -> bool:
        """
        更新实体

        Args:
            entity: 要更新的领域实体（必须包含有效的 ID）

        Returns:
            bool: 更新是否成功

        Raises:
            RepositoryException: 更新失败时抛出
        """
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """
        删除实体

        Args:
            id: 要删除的实体ID

        Returns:
            bool: 删除是否成功

        Raises:
            RepositoryException: 删除失败时抛出
        """
        pass

    @abstractmethod
    async def exists(self, id: str) -> bool:
        """
        检查实体是否存在

        Args:
            id: 实体ID

        Returns:
            bool: 实体是否存在

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass


class IQueryableRepository(ABC, Generic[T]):
    """
    可查询 Repository 接口

    提供基于条件的查询功能。
    遵循接口隔离原则，只有需要查询功能的 Repository 才实现此接口。

    Type Parameters:
        T: 领域实体类型
    """

    @abstractmethod
    async def find_all(self, limit: Optional[int] = None) -> List[T]:
        """
        获取所有实体

        Args:
            limit: 可选的数量限制，防止查询过多数据

        Returns:
            List[T]: 实体列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        pass

    @abstractmethod
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """
        根据条件查询实体

        Args:
            criteria: 查询条件字典，键为字段名，值为期望的值
                     支持简单相等查询和部分 MongoDB 查询操作符

        Returns:
            List[T]: 符合条件的实体列表

        Raises:
            RepositoryException: 查询失败时抛出

        Example:
            criteria = {
                "status": "active",
                "created_at": {"$gte": start_date}
            }
            tasks = await repo.find_by_criteria(criteria)
        """
        pass

    @abstractmethod
    async def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """
        统计实体数量

        Args:
            criteria: 可选的查询条件，如果为 None 则统计全部

        Returns:
            int: 符合条件的实体数量

        Raises:
            RepositoryException: 统计失败时抛出
        """
        pass


class IPaginatableRepository(ABC, Generic[T]):
    """
    可分页 Repository 接口

    提供分页查询功能，适用于需要大量数据展示的场景。
    遵循接口隔离原则，只有需要分页的 Repository 才实现此接口。

    Type Parameters:
        T: 领域实体类型
    """

    @abstractmethod
    async def find_with_pagination(
        self,
        page: int,
        page_size: int,
        criteria: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc"
    ) -> Tuple[List[T], int]:
        """
        分页查询实体

        Args:
            page: 页码（从 1 开始）
            page_size: 每页大小
            criteria: 可选的查询条件
            sort_by: 可选的排序字段
            sort_order: 排序方向，"asc" 或 "desc"，默认降序

        Returns:
            Tuple[List[T], int]: (实体列表, 总数量)

        Raises:
            RepositoryException: 查询失败时抛出
            ValueError: 页码或页大小无效时抛出

        Example:
            tasks, total = await repo.find_with_pagination(
                page=1,
                page_size=20,
                criteria={"status": "active"},
                sort_by="created_at",
                sort_order="desc"
            )
        """
        pass


class IBulkOperationRepository(ABC, Generic[T]):
    """
    批量操作 Repository 接口

    提供批量创建、更新、删除功能，优化大量数据操作的性能。
    遵循接口隔离原则，只有需要批量操作的 Repository 才实现此接口。

    Type Parameters:
        T: 领域实体类型
    """

    @abstractmethod
    async def bulk_create(self, entities: List[T]) -> List[str]:
        """
        批量创建实体

        Args:
            entities: 要创建的实体列表

        Returns:
            List[str]: 创建成功的实体ID列表

        Raises:
            RepositoryException: 批量创建失败时抛出

        Note:
            如果部分实体创建失败，具体行为由实现决定：
            - 事务型：全部回滚
            - 非事务型：返回成功创建的ID
        """
        pass

    @abstractmethod
    async def bulk_update(self, entities: List[T]) -> int:
        """
        批量更新实体

        Args:
            entities: 要更新的实体列表（每个实体必须包含有效的 ID）

        Returns:
            int: 成功更新的数量

        Raises:
            RepositoryException: 批量更新失败时抛出
        """
        pass

    @abstractmethod
    async def bulk_delete(self, ids: List[str]) -> int:
        """
        批量删除实体

        Args:
            ids: 要删除的实体ID列表

        Returns:
            int: 成功删除的数量

        Raises:
            RepositoryException: 批量删除失败时抛出
        """
        pass

    @abstractmethod
    async def bulk_update_fields(
        self,
        criteria: Dict[str, Any],
        updates: Dict[str, Any]
    ) -> int:
        """
        批量更新字段

        根据条件批量更新指定字段，不需要加载完整实体。

        Args:
            criteria: 更新条件
            updates: 要更新的字段和值

        Returns:
            int: 成功更新的数量

        Raises:
            RepositoryException: 批量更新失败时抛出

        Example:
            count = await repo.bulk_update_fields(
                criteria={"status": "pending"},
                updates={"status": "processing", "updated_at": datetime.utcnow()}
            )
        """
        pass


class RepositoryException(Exception):
    """Repository 操作异常基类"""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception


class EntityNotFoundException(RepositoryException):
    """实体未找到异常"""
    pass


class DuplicateEntityException(RepositoryException):
    """实体重复异常"""
    pass


class InvalidCriteriaException(RepositoryException):
    """无效查询条件异常"""
    pass

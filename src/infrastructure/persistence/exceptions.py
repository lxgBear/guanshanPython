"""Repository 层统一异常定义

Version: v3.0.0 (模块化架构)

提供统一的异常处理体系，用于Repository层的错误处理。
"""


class RepositoryException(Exception):
    """Repository层基础异常

    所有Repository相关的异常都应该继承自此类。
    """
    pass


class EntityNotFoundException(RepositoryException):
    """实体未找到异常

    当查询的实体不存在时抛出此异常。
    """
    pass


class DuplicateEntityException(RepositoryException):
    """实体重复异常

    当尝试创建已存在的实体时抛出此异常。
    """
    pass


class ValidationException(RepositoryException):
    """数据验证异常

    当数据验证失败时抛出此异常。
    """
    pass


class ConcurrencyException(RepositoryException):
    """并发冲突异常

    当发生并发更新冲突时抛出此异常。
    """
    pass


class TransactionException(RepositoryException):
    """事务异常

    当事务操作失败时抛出此异常。
    """
    pass

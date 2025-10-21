"""基于游标的分页工具

相比传统的偏移分页（offset-based），游标分页有以下优势：
1. 性能更好：不需要 SKIP 操作，直接从游标位置开始查询
2. 数据一致性：避免偏移分页中的重复/丢失问题
3. 适合实时数据：支持流式数据场景

使用场景：
- 大数据集分页（>10000条）
- 实时数据流
- 移动端下拉加载
- 搜索结果分页
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import base64
import json
from pydantic import BaseModel


class CursorInfo(BaseModel):
    """游标信息模型"""
    field: str                    # 排序字段（如 created_at, _id）
    value: Any                    # 游标值
    direction: int = -1           # 排序方向（1: 升序, -1: 降序）


class PaginationMeta(BaseModel):
    """分页元数据"""
    has_next: bool                # 是否有下一页
    has_previous: bool            # 是否有上一页
    next_cursor: Optional[str]    # 下一页游标
    previous_cursor: Optional[str] # 上一页游标
    count: int                    # 当前页记录数
    total_count: Optional[int] = None  # 总记录数（可选，避免性能损耗）


class CursorPaginator:
    """游标分页器"""

    @staticmethod
    def encode_cursor(cursor_info: CursorInfo) -> str:
        """
        编码游标信息为Base64字符串

        Args:
            cursor_info: 游标信息

        Returns:
            str: Base64编码的游标字符串
        """
        cursor_dict = cursor_info.model_dump()
        # 处理 datetime 对象
        if isinstance(cursor_dict['value'], datetime):
            cursor_dict['value'] = cursor_dict['value'].isoformat()

        cursor_json = json.dumps(cursor_dict, ensure_ascii=False)
        cursor_bytes = cursor_json.encode('utf-8')
        return base64.urlsafe_b64encode(cursor_bytes).decode('utf-8')

    @staticmethod
    def decode_cursor(cursor_str: str) -> CursorInfo:
        """
        解码Base64游标字符串

        Args:
            cursor_str: Base64编码的游标字符串

        Returns:
            CursorInfo: 游标信息对象
        """
        try:
            cursor_bytes = base64.urlsafe_b64decode(cursor_str.encode('utf-8'))
            cursor_json = cursor_bytes.decode('utf-8')
            cursor_dict = json.loads(cursor_json)

            # 恢复 datetime 对象
            if cursor_dict['field'] in ['created_at', 'updated_at', 'added_at']:
                cursor_dict['value'] = datetime.fromisoformat(cursor_dict['value'])

            return CursorInfo(**cursor_dict)
        except Exception as e:
            raise ValueError(f"无效的游标: {e}")

    @staticmethod
    def build_mongo_query(
        base_filter: Dict[str, Any],
        cursor: Optional[str],
        sort_field: str = "created_at",
        direction: int = -1
    ) -> Dict[str, Any]:
        """
        构建MongoDB查询条件（包含游标过滤）

        Args:
            base_filter: 基础过滤条件
            cursor: 游标字符串（可选）
            sort_field: 排序字段
            direction: 排序方向（1: 升序, -1: 降序）

        Returns:
            dict: MongoDB查询条件
        """
        query = base_filter.copy()

        if cursor:
            cursor_info = CursorPaginator.decode_cursor(cursor)

            # 根据方向添加范围条件
            if cursor_info.direction == -1:  # 降序
                query[cursor_info.field] = {"$lt": cursor_info.value}
            else:  # 升序
                query[cursor_info.field] = {"$gt": cursor_info.value}

        return query

    @staticmethod
    async def paginate(
        collection,
        base_filter: Dict[str, Any],
        cursor: Optional[str] = None,
        limit: int = 20,
        sort_field: str = "created_at",
        direction: int = -1,
        include_total: bool = False
    ) -> Dict[str, Any]:
        """
        执行游标分页查询

        Args:
            collection: MongoDB集合
            base_filter: 基础过滤条件
            cursor: 当前游标
            limit: 每页记录数
            sort_field: 排序字段
            direction: 排序方向（1: 升序, -1: 降序）
            include_total: 是否包含总记录数（会影响性能）

        Returns:
            dict: 分页结果
                - items: 数据列表
                - meta: 分页元数据
        """
        # 构建查询条件
        query = CursorPaginator.build_mongo_query(
            base_filter, cursor, sort_field, direction
        )

        # 查询 limit+1 条记录，用于判断是否有下一页
        items = await collection.find(query).sort(
            sort_field, direction
        ).limit(limit + 1).to_list(limit + 1)

        # 判断是否有下一页
        has_next = len(items) > limit
        if has_next:
            items = items[:limit]  # 移除多余的记录

        # 生成下一页游标
        next_cursor = None
        if has_next and items:
            last_item = items[-1]
            next_cursor = CursorPaginator.encode_cursor(
                CursorInfo(
                    field=sort_field,
                    value=last_item.get(sort_field),
                    direction=direction
                )
            )

        # 计算总数（可选）
        total_count = None
        if include_total:
            total_count = await collection.count_documents(base_filter)

        # 构建分页元数据
        meta = PaginationMeta(
            has_next=has_next,
            has_previous=cursor is not None,
            next_cursor=next_cursor,
            previous_cursor=None,  # 单向游标不支持上一页
            count=len(items),
            total_count=total_count
        )

        return {
            "items": items,
            "meta": meta.model_dump()
        }

    @staticmethod
    async def paginate_aggregation(
        collection,
        pipeline: List[Dict[str, Any]],
        cursor: Optional[str] = None,
        limit: int = 20,
        sort_field: str = "created_at",
        direction: int = -1
    ) -> Dict[str, Any]:
        """
        执行聚合管道的游标分页

        Args:
            collection: MongoDB集合
            pipeline: 聚合管道（不包含 $sort 和 $limit）
            cursor: 当前游标
            limit: 每页记录数
            sort_field: 排序字段
            direction: 排序方向

        Returns:
            dict: 分页结果
        """
        # 复制管道避免修改原始数据
        paginated_pipeline = pipeline.copy()

        # 添加游标过滤
        if cursor:
            cursor_info = CursorPaginator.decode_cursor(cursor)
            match_stage = {
                "$match": {
                    cursor_info.field: {
                        "$lt" if cursor_info.direction == -1 else "$gt": cursor_info.value
                    }
                }
            }
            paginated_pipeline.append(match_stage)

        # 添加排序和限制
        paginated_pipeline.append({"$sort": {sort_field: direction}})
        paginated_pipeline.append({"$limit": limit + 1})

        # 执行聚合查询
        cursor_result = collection.aggregate(paginated_pipeline)
        items = await cursor_result.to_list(limit + 1)

        # 判断是否有下一页
        has_next = len(items) > limit
        if has_next:
            items = items[:limit]

        # 生成下一页游标
        next_cursor = None
        if has_next and items:
            last_item = items[-1]
            next_cursor = CursorPaginator.encode_cursor(
                CursorInfo(
                    field=sort_field,
                    value=last_item.get(sort_field),
                    direction=direction
                )
            )

        meta = PaginationMeta(
            has_next=has_next,
            has_previous=cursor is not None,
            next_cursor=next_cursor,
            previous_cursor=None,
            count=len(items),
            total_count=None
        )

        return {
            "items": items,
            "meta": meta.model_dump()
        }


# 全局实例
cursor_paginator = CursorPaginator()

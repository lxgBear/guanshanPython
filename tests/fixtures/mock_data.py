"""
测试模拟数据生成器

提供各种Mock数据生成函数,用于单元测试和集成测试。
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

from src.core.domain.entities.search_task import SearchTask, TaskStatus, ScheduleInterval
from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from src.core.domain.entities.search_config import UserSearchConfig


def create_mock_search_response(
    count: int = 10,
    include_markdown: bool = True,
    include_html: bool = True,
    api_version: str = "v2"
) -> Dict[str, Any]:
    """生成模拟的Firecrawl Search API响应

    Args:
        count: 结果数量
        include_markdown: 是否包含markdown内容
        include_html: 是否包含html内容
        api_version: API版本 (v0 或 v2)

    Returns:
        模拟的API响应字典
    """
    results = []

    for i in range(count):
        result = {
            "url": f"https://example.com/article/{i+1}",
            "title": f"测试文章标题 {i+1}",
            "description": f"这是第{i+1}篇文章的描述内容",
            "position": i + 1
        }

        if include_markdown:
            result["markdown"] = f"# 测试文章标题 {i+1}\n\n这是Markdown格式的文章内容..." * 50

        if include_html:
            result["html"] = f"<h1>测试文章标题 {i+1}</h1><p>这是HTML格式的文章内容...</p>" * 50

        result["metadata"] = {
            "language": "zh",
            "og:type": "article",
            "article:tag": ["科技", "AI"],
            "article:published_time": (datetime.utcnow() - timedelta(days=i)).isoformat(),
            "sourceURL": result["url"],
            "statusCode": 200
        }

        results.append(result)

    if api_version == "v2":
        return {
            "success": True,
            "data": {
                "web": results
            },
            "creditsUsed": 1
        }
    else:  # v0 format
        return {
            "success": True,
            "data": results,
            "credits_used": 1
        }


def create_mock_error_response(
    status_code: int = 500,
    message: str = "Internal Server Error",
    error_type: str = "ServerError"
) -> Dict[str, Any]:
    """生成模拟的错误响应

    Args:
        status_code: HTTP状态码
        message: 错误消息
        error_type: 错误类型

    Returns:
        模拟的错误响应字典
    """
    return {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code
        }
    }


def create_mock_search_task(
    task_id: Optional[str] = None,
    name: str = "测试任务",
    query: str = "Python async",
    schedule_interval: str = "HOURLY_1",
    is_active: bool = True,
    **kwargs
) -> SearchTask:
    """创建模拟的SearchTask实体

    Args:
        task_id: 任务ID (可选)
        name: 任务名称
        query: 搜索关键词
        schedule_interval: 调度间隔
        is_active: 是否活跃
        **kwargs: 其他自定义属性

    Returns:
        SearchTask实体
    """
    task = SearchTask.create_with_secure_id(
        name=name,
        query=query,
        description=kwargs.get("description", "测试任务描述"),
        search_config=kwargs.get("search_config", {"limit": 10}),
        schedule_interval=schedule_interval,
        is_active=is_active,
        created_by=kwargs.get("created_by", "test_user")
    )

    if task_id:
        task.id = task_id

    # 设置额外属性
    if "execution_count" in kwargs:
        task.execution_count = kwargs["execution_count"]
    if "success_count" in kwargs:
        task.success_count = kwargs["success_count"]
    if "failure_count" in kwargs:
        task.failure_count = kwargs["failure_count"]
    if "last_executed_at" in kwargs:
        task.last_executed_at = kwargs["last_executed_at"]

    return task


def create_mock_search_result(
    task_id: str = "test_task_123",
    result_id: Optional[str] = None,
    title: str = "测试结果标题",
    url: str = "https://example.com/test",
    content: str = "测试内容" * 100,
    **kwargs
) -> SearchResult:
    """创建模拟的SearchResult实体

    Args:
        task_id: 关联的任务ID
        result_id: 结果ID (可选)
        title: 标题
        url: URL
        content: 内容
        **kwargs: 其他自定义属性

    Returns:
        SearchResult实体
    """
    result = SearchResult(
        task_id=task_id,
        title=title,
        url=url,
        content=content,
        snippet=kwargs.get("snippet", content[:200]),
        source=kwargs.get("source", "web"),
        published_date=kwargs.get("published_date", datetime.utcnow()),
        author=kwargs.get("author"),
        language=kwargs.get("language", "zh"),
        markdown_content=kwargs.get("markdown_content", f"# {title}\n\n{content}"),
        html_content=kwargs.get("html_content", f"<h1>{title}</h1><p>{content}</p>"),
        article_tag=kwargs.get("article_tag"),
        article_published_time=kwargs.get("article_published_time"),
        source_url=kwargs.get("source_url", url),
        http_status_code=kwargs.get("http_status_code", 200),
        search_position=kwargs.get("search_position", 1),
        metadata=kwargs.get("metadata", {}),
        relevance_score=kwargs.get("relevance_score", 0.9),
        status=kwargs.get("status", ResultStatus.PROCESSED),
        is_test_data=kwargs.get("is_test_data", False)
    )

    if result_id:
        result.id = result_id

    return result


def create_mock_search_config(
    template_name: str = "default",
    **overrides
) -> UserSearchConfig:
    """创建模拟的UserSearchConfig

    Args:
        template_name: 模板名称
        **overrides: 覆盖配置

    Returns:
        UserSearchConfig实体
    """
    return UserSearchConfig(
        template_name=template_name,
        overrides=overrides
    )


def create_mock_result_batch(
    count: int = 10,
    success: bool = True,
    task_id: str = "test_task_123",
    query: str = "测试查询",
    **kwargs
) -> SearchResultBatch:
    """创建模拟的SearchResultBatch

    Args:
        count: 结果数量
        success: 是否成功
        task_id: 任务ID
        query: 搜索查询
        **kwargs: 其他自定义属性

    Returns:
        SearchResultBatch实体
    """
    batch = SearchResultBatch(
        task_id=task_id,
        query=query,
        search_config=kwargs.get("search_config", {"limit": count}),
        is_test_mode=kwargs.get("is_test_mode", False)
    )

    if success:
        # 生成结果
        for i in range(count):
            result = create_mock_search_result(
                task_id=task_id,
                title=f"测试结果 {i+1}",
                url=f"https://example.com/test/{i+1}",
                search_position=i+1
            )
            batch.add_result(result)

        batch.total_count = count
        batch.credits_used = 1
        batch.execution_time_ms = 1000
    else:
        # 设置错误
        error_msg = kwargs.get("error_message", "测试错误")
        batch.set_error(error_msg)

    return batch


def create_bulk_mock_tasks(count: int = 5) -> List[SearchTask]:
    """批量创建模拟任务

    Args:
        count: 任务数量

    Returns:
        SearchTask列表
    """
    tasks = []
    intervals = ["MINUTES_5", "MINUTES_30", "HOURLY_1", "DAILY", "WEEKLY"]

    for i in range(count):
        task = create_mock_search_task(
            name=f"批量测试任务 {i+1}",
            query=f"测试查询 {i+1}",
            schedule_interval=intervals[i % len(intervals)],
            is_active=i % 2 == 0  # 一半活跃,一半非活跃
        )
        tasks.append(task)

    return tasks


def create_bulk_mock_results(
    count: int = 20,
    task_id: str = "test_task_123"
) -> List[SearchResult]:
    """批量创建模拟搜索结果

    Args:
        count: 结果数量
        task_id: 任务ID

    Returns:
        SearchResult列表
    """
    results = []

    for i in range(count):
        result = create_mock_search_result(
            task_id=task_id,
            title=f"批量测试结果 {i+1}",
            url=f"https://example.com/bulk/{i+1}",
            search_position=i+1,
            relevance_score=1.0 - (i * 0.01)  # 递减相关性
        )
        results.append(result)

    return results

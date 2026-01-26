"""
搜索结果手动添加API端点 (v2.2.0)

提供手动添加数据和URL爬取功能：
- 手动添加搜索结果（用户输入标题、URL、内容等）
- URL爬取添加（用户输入URL，系统自动爬取内容）
- 数据来源类型标记（user_added/url_crawl/scheduled_crawl）
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.core.domain.entities.search_result import SearchResult, ResultStatus, DataSourceType
from src.infrastructure.id_generator import generate_string_id
from src.utils.logger import get_logger
from src.api.dependencies.auth import get_current_user
from src.core.domain.entities.auth import User

logger = get_logger(__name__)
router = APIRouter(prefix="/search-results", tags=["📝 手动添加数据"])


# ==========================================
# Pydantic模型定义
# ==========================================

class ManualAddRequest(BaseModel):
    """手动添加搜索结果请求"""
    task_id: str = Field(..., description="关联的任务ID")
    title: str = Field(..., description="标题", min_length=1, max_length=500)
    url: str = Field(..., description="URL链接")
    content: str = Field(..., description="内容", min_length=1)
    snippet: Optional[str] = Field(None, description="摘要（默认使用内容前200字符）")
    source: str = Field("web", description="来源类型（web/news/academic等）")
    author: Optional[str] = Field(None, description="作者")
    published_date: Optional[datetime] = Field(None, description="发布日期")
    language: Optional[str] = Field(None, description="语言")
    user_id: str = Field(..., description="用户ID")
    created_by: str = Field(..., description="创建者")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "1234567890123456789",
                "title": "Python异步编程最佳实践",
                "url": "https://example.com/python-async",
                "content": "本文介绍Python异步编程的最佳实践...",
                "source": "web",
                "language": "zh-CN",
                "user_id": "user123",
                "created_by": "user123"
            }
        }


class TranslatedContentRequest(BaseModel):
    """手动录入翻译内容请求

    用于用户直接录入翻译后的内容，无需关联已有任务。
    task_id 和 user_id 由后端自动生成/获取。
    """
    title: str = Field(..., description="标题", min_length=1, max_length=500)
    content: str = Field(..., description="翻译后的内容（完整保存）", min_length=1)
    url: Optional[str] = Field(None, description="来源URL")
    published_date: Optional[datetime] = Field(None, description="发布日期")
    primary_category: Optional[str] = Field(None, description="一级分类（大类）")
    secondary_category: Optional[str] = Field(None, description="二级分类（类别）")
    tertiary_category: Optional[str] = Field(None, description="三级分类（地域）")
    tags: Optional[List[str]] = Field(None, description="自定义标签")
    notes: Optional[str] = Field(None, description="备注")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "某国安全局发布年度威胁评估报告",
                "content": "根据最新发布的年度威胁评估报告，该国面临的主要安全威胁包括...",
                "url": "https://example.com/report",
                "primary_category": "安全情报",
                "secondary_category": "类别",
                "tertiary_category": "东亚",
                "tags": ["年度报告", "威胁评估"]
            }
        }


class UrlCrawlRequest(BaseModel):
    """URL爬取添加请求"""
    task_id: str = Field(..., description="关联的任务ID")
    url: HttpUrl = Field(..., description="要爬取的URL")
    source: str = Field("web", description="来源类型（web/news/academic等）")
    user_id: str = Field(..., description="用户ID")
    created_by: str = Field(..., description="创建者")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "1234567890123456789",
                "url": "https://example.com/article",
                "source": "web",
                "user_id": "user123",
                "created_by": "user123"
            }
        }


class ManualAddResponse(BaseModel):
    """手动添加响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
    data: Optional[dict] = Field(None, description="添加的数据")


# ==========================================
# 依赖注入
# ==========================================

async def get_db():
    """获取数据库实例"""
    return await get_mongodb_database()


async def get_crawler():
    """获取爬虫实例"""
    return FirecrawlAdapter()


# ==========================================
# 辅助函数
# ==========================================

async def validate_task_exists(db, task_id: str) -> bool:
    """验证任务是否存在"""
    task = await db.search_tasks.find_one({"_id": task_id})
    return task is not None


def search_result_to_dict(result: SearchResult) -> dict:
    """将SearchResult实体转换为字典"""
    return {
        "id": result.id,
        "task_id": result.task_id,
        "user_id": result.user_id,
        "created_by": result.created_by,
        "title": result.title,
        "url": result.url,
        "snippet": result.snippet,
        "source": result.source,
        "data_source_type": result.data_source_type.value,
        "status": result.status.value,
        "created_at": result.created_at.isoformat(),
    }


# ==========================================
# API端点
# ==========================================

@router.post(
    "/manual",
    response_model=ManualAddResponse,
    summary="手动添加搜索结果",
    description="用户手动输入标题、URL、内容等信息，添加到搜索结果表。数据来源标记为user_added。"
)
async def manual_add_search_result(
    request: ManualAddRequest,
    db = Depends(get_db)
):
    """手动添加搜索结果

    **功能说明：**
    - 用户手动输入数据
    - data_source_type 自动设置为 USER_ADDED
    - 自动生成 content_hash 用于去重
    - status 默认为 PENDING

    **数据流程：**
    1. 验证任务ID是否存在
    2. 创建SearchResult实体
    3. 生成content_hash
    4. 保存到数据库
    """
    try:
        # 验证任务是否存在
        task_exists = await validate_task_exists(db, request.task_id)
        if not task_exists:
            raise HTTPException(status_code=404, detail=f"任务不存在: {request.task_id}")

        # 检查URL是否已存在（去重）
        existing = await db.search_results.find_one({
            "url": request.url,
            "task_id": request.task_id,
            "status": {"$ne": "deleted"}
        })
        if existing:
            logger.warning(f"URL已存在: {request.url}")
            raise HTTPException(
                status_code=400,
                detail=f"该URL已存在于任务 {request.task_id} 中"
            )

        # 创建SearchResult实体
        result = SearchResult(
            id=generate_string_id(),
            task_id=request.task_id,
            user_id=request.user_id,
            created_by=request.created_by,
            title=request.title,
            url=request.url,
            snippet=request.snippet or (request.content[:200] + "..." if len(request.content) > 200 else request.content),
            source=request.source,
            author=request.author,
            published_date=request.published_date,
            language=request.language,
            markdown_content=request.content[:5000],  # 限制5000字符
            data_source_type=DataSourceType.USER_ADDED,  # 标记为用户手动添加
            status=ResultStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # 生成content_hash
        result.ensure_content_hash()

        # 保存到数据库
        await db.search_results.insert_one(result.__dict__)

        logger.info(f"手动添加搜索结果成功: id={result.id}, url={request.url}, user={request.created_by}")

        return ManualAddResponse(
            success=True,
            message="搜索结果添加成功",
            data=search_result_to_dict(result)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"手动添加搜索结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"添加失败: {str(e)}")


@router.post(
    "/crawl",
    response_model=ManualAddResponse,
    summary="URL爬取添加搜索结果",
    description="用户输入URL，系统自动爬取页面内容并添加到搜索结果表。数据来源标记为url_crawl。"
)
async def crawl_and_add_search_result(
    request: UrlCrawlRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db),
    crawler: FirecrawlAdapter = Depends(get_crawler)
):
    """URL爬取添加搜索结果

    **功能说明：**
    - 用户输入URL
    - 系统自动爬取页面内容
    - data_source_type 自动设置为 URL_CRAWL
    - 自动提取标题、内容等

    **数据流程：**
    1. 验证任务ID是否存在
    2. 调用爬虫爬取URL内容
    3. 创建SearchResult实体
    4. 保存到数据库
    """
    try:
        # 验证任务是否存在
        task_exists = await validate_task_exists(db, request.task_id)
        if not task_exists:
            raise HTTPException(status_code=404, detail=f"任务不存在: {request.task_id}")

        url_str = str(request.url)

        # 检查URL是否已存在（去重）
        existing = await db.search_results.find_one({
            "url": url_str,
            "task_id": request.task_id,
            "status": {"$ne": "deleted"}
        })
        if existing:
            logger.warning(f"URL已存在: {url_str}")
            raise HTTPException(
                status_code=400,
                detail=f"该URL已存在于任务 {request.task_id} 中"
            )

        # 调用爬虫爬取内容
        logger.info(f"开始爬取URL: {url_str}")
        crawl_result = await crawler.scrape(url_str)

        if not crawl_result or not crawl_result.content:
            raise HTTPException(
                status_code=400,
                detail=f"无法爬取URL内容: {url_str}"
            )

        # 从CrawlResult提取数据
        # 优先使用markdown，如果没有则使用content
        content_to_use = crawl_result.markdown or crawl_result.content or ""
        title_to_use = crawl_result.metadata.get("title") or crawl_result.metadata.get("pageTitle") or url_str

        # 创建SearchResult实体
        result = SearchResult(
            id=generate_string_id(),
            task_id=request.task_id,
            user_id=request.user_id,
            created_by=request.created_by,
            title=title_to_use,
            url=url_str,
            snippet=content_to_use[:200] if content_to_use else "",
            source=request.source,
            language=crawl_result.metadata.get("language") or crawl_result.metadata.get("lang"),
            markdown_content=content_to_use[:5000],
            html_content=crawl_result.raw_html or crawl_result.html,
            metadata={
                "crawled_at": datetime.utcnow().isoformat(),
                "http_status": crawl_result.metadata.get("statusCode") or crawl_result.metadata.get("status"),
                "content_length": len(content_to_use),
                "crawler": "firecrawl"
            },
            data_source_type=DataSourceType.URL_CRAWL,  # 标记为URL爬取
            status=ResultStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # 生成content_hash
        result.ensure_content_hash()

        # 保存到数据库
        await db.search_results.insert_one(result.__dict__)

        logger.info(f"URL爬取添加成功: id={result.id}, url={url_str}, user={request.created_by}")

        return ManualAddResponse(
            success=True,
            message="URL爬取并添加成功",
            data=search_result_to_dict(result)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL爬取添加失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"爬取添加失败: {str(e)}")


@router.post(
    "/manual/translated",
    response_model=ManualAddResponse,
    summary="手动录入翻译内容",
    description="用户录入翻译后的内容，入库到 news_results。task_id 自动生成，user_id 从 Token 获取。"
)
async def add_translated_content(
    request: TranslatedContentRequest,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """手动录入翻译内容

    **功能说明：**
    - 用户录入翻译后的内容
    - task_id 使用雪花算法自动生成
    - user_id/created_by 从 JWT Token 获取
    - content 完整保存到 snippet 和 markdown_content
    - 分类信息存入 metadata.category（兼容现有格式）

    **数据流程：**
    1. 从 Token 获取用户信息
    2. 生成 task_id（雪花算法）
    3. 构建 metadata（包含分类、标签、备注）
    4. 创建 SearchResult 实体
    5. 保存到数据库
    """
    try:
        # 生成 task_id（雪花算法）
        task_id = generate_string_id()

        # 构建 metadata（兼容现有分类格式）
        metadata = {
            "category": {
                "大类": request.primary_category,
                "类别": request.secondary_category,
                "地域": request.tertiary_category
            },
            "tags": request.tags or [],
            "notes": request.notes,
            "input_type": "translated"
        }

        # 创建 SearchResult 实体
        result = SearchResult(
            id=generate_string_id(),
            task_id=task_id,
            user_id=current_user.id,
            created_by=current_user.id,
            title=request.title,
            url=request.url or "",
            snippet=request.content,
            markdown_content=request.content,
            source="translated",
            language="zh-CN",
            published_date=request.published_date,
            data_source_type=DataSourceType.USER_ADDED,
            status=ResultStatus.PENDING,
            metadata=metadata,
            created_at=datetime.utcnow()
        )

        # 生成 content_hash
        result.ensure_content_hash()

        # 保存到数据库
        await db.search_results.insert_one(result.__dict__)

        logger.info(
            f"翻译内容录入成功: id={result.id}, title={request.title[:50]}, user={current_user.id}"
        )

        return ManualAddResponse(
            success=True,
            message="翻译内容录入成功",
            data=search_result_to_dict(result)
        )

    except Exception as e:
        logger.error(f"翻译内容录入失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"录入失败: {str(e)}")

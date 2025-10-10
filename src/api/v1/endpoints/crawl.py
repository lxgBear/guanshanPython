"""
爬取服务API端点
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl

from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.core.domain.interfaces.crawler_interface import CrawlException
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# === 请求/响应模型 ===

class ScrapeRequest(BaseModel):
    """爬取单页请求"""
    url: HttpUrl = Field(..., description="目标URL")
    wait_for: Optional[int] = Field(1000, description="等待时间（毫秒）")
    include_tags: Optional[List[str]] = Field(None, description="包含的HTML标签")
    exclude_tags: Optional[List[str]] = Field(
        default=["nav", "footer", "header"],
        description="排除的HTML标签"
    )
    actions: Optional[List[Dict[str, Any]]] = Field(None, description="页面交互动作")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "wait_for": 2000,
                "exclude_tags": ["nav", "footer", "ads"]
            }
        }


class ScrapeResponse(BaseModel):
    """爬取响应"""
    success: bool = Field(..., description="是否成功")
    url: str = Field(..., description="爬取的URL")
    content: str = Field(..., description="页面内容")
    markdown: Optional[str] = Field(None, description="Markdown格式内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    error: Optional[str] = Field(None, description="错误信息")


class CrawlRequest(BaseModel):
    """爬取网站请求"""
    url: HttpUrl = Field(..., description="起始URL")
    limit: int = Field(10, ge=1, le=100, description="最大页面数")
    max_depth: int = Field(3, ge=1, le=10, description="最大深度")
    include_paths: Optional[List[str]] = Field(None, description="包含的路径模式")
    exclude_paths: Optional[List[str]] = Field(None, description="排除的路径模式")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://docs.example.com",
                "limit": 20,
                "max_depth": 3,
                "include_paths": ["/docs/*"],
                "exclude_paths": ["/api/*"]
            }
        }


class MapRequest(BaseModel):
    """站点地图请求"""
    url: HttpUrl = Field(..., description="目标网站URL")
    limit: int = Field(100, ge=1, le=1000, description="最大URL数量")


class ExtractRequest(BaseModel):
    """数据提取请求"""
    url: HttpUrl = Field(..., description="目标URL")
    schema: Dict[str, Any] = Field(..., description="提取模式定义")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/article",
                "schema": {
                    "type": "object",
                    "description": "提取文章信息",
                    "properties": {
                        "title": {"type": "string", "description": "文章标题"},
                        "author": {"type": "string", "description": "作者"},
                        "content": {"type": "string", "description": "主要内容"},
                        "tags": {"type": "array", "description": "标签列表"}
                    }
                }
            }
        }


# === 依赖注入 ===

async def get_crawler() -> FirecrawlAdapter:
    """
    获取爬虫实例（依赖注入）
    
    Returns:
        FirecrawlAdapter: 爬虫适配器实例
    """
    return FirecrawlAdapter()


# === API端点 ===

@router.post("/scrape", response_model=ScrapeResponse, summary="爬取单个页面")
async def scrape_url(
    request: ScrapeRequest,
    crawler: FirecrawlAdapter = Depends(get_crawler)
):
    """
    爬取单个URL页面
    
    - **url**: 目标URL
    - **wait_for**: 等待时间（毫秒）
    - **include_tags**: 包含的HTML标签
    - **exclude_tags**: 排除的HTML标签
    - **actions**: 页面交互动作（点击、滚动等）
    """
    try:
        # 准备选项
        options = {
            "wait_for": request.wait_for,
            "include_tags": request.include_tags,
            "exclude_tags": request.exclude_tags,
            "actions": request.actions
        }
        
        # 执行爬取
        result = await crawler.scrape(str(request.url), **options)
        
        return ScrapeResponse(
            success=True,
            url=result.url,
            content=result.content[:5000],  # 限制返回内容长度
            markdown=result.markdown[:5000] if result.markdown else None,
            metadata=result.metadata or {}
        )
        
    except CrawlException as e:
        logger.error(f"爬取失败: {e}")
        return ScrapeResponse(
            success=False,
            url=str(request.url),
            content="",
            error=str(e)
        )
    except Exception as e:
        logger.error(f"未预期的错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl", summary="爬取整个网站")
async def crawl_website(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    crawler: FirecrawlAdapter = Depends(get_crawler)
):
    """
    爬取整个网站（异步任务）
    
    - **url**: 起始URL
    - **limit**: 最大页面数
    - **max_depth**: 最大爬取深度
    - **include_paths**: 包含的路径模式
    - **exclude_paths**: 排除的路径模式
    """
    try:
        # 准备选项
        options = {
            "max_depth": request.max_depth,
            "include_paths": request.include_paths,
            "exclude_paths": request.exclude_paths
        }
        
        # 执行爬取（实际应用中应该使用异步任务队列）
        results = await crawler.crawl(str(request.url), request.limit, **options)
        
        return {
            "success": True,
            "url": str(request.url),
            "pages_crawled": len(results),
            "results": [
                {
                    "url": r.url,
                    "content_length": len(r.content),
                    "has_markdown": r.markdown is not None
                }
                for r in results
            ]
        }
        
    except CrawlException as e:
        logger.error(f"网站爬取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"未预期的错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/map", summary="生成站点地图")
async def generate_sitemap(
    request: MapRequest,
    crawler: FirecrawlAdapter = Depends(get_crawler)
):
    """
    生成网站的URL地图
    
    - **url**: 目标网站URL
    - **limit**: 最大URL数量
    """
    try:
        urls = await crawler.map(str(request.url), request.limit)
        
        return {
            "success": True,
            "url": str(request.url),
            "total_urls": len(urls),
            "urls": urls
        }
        
    except CrawlException as e:
        logger.error(f"站点地图生成失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"未预期的错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract", summary="提取结构化数据")
async def extract_data(
    request: ExtractRequest,
    crawler: FirecrawlAdapter = Depends(get_crawler)
):
    """
    从页面提取结构化数据
    
    使用自然语言描述的schema来提取数据
    """
    try:
        data = await crawler.extract(str(request.url), request.schema)
        
        return {
            "success": True,
            "url": str(request.url),
            "extracted_data": data
        }
        
    except CrawlException as e:
        logger.error(f"数据提取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"未预期的错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test", summary="测试爬取服务")
async def test_crawl_service():
    """
    测试爬取服务是否正常
    """
    try:
        # 尝试创建爬虫实例
        crawler = FirecrawlAdapter()
        
        return {
            "status": "operational",
            "message": "爬取服务已就绪",
            "firecrawl_configured": True
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "firecrawl_configured": False
        }
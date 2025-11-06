"""
Firecrawl 工具 API 端点

提供 Firecrawl API 积分估算和定价信息查询功能
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from src.services.firecrawl.credits_calculator import FirecrawlCreditsCalculator


router = APIRouter(prefix="/firecrawl", tags=["Firecrawl Utils"])


# ==================== Response Models ====================

class CreditEstimateResponse(BaseModel):
    """积分估算响应"""
    total_credits: int = Field(..., description="总积分")
    breakdown: Dict[str, int] = Field(..., description="积分明细")
    description: str = Field(..., description="说明")


class PricingInfoResponse(BaseModel):
    """定价信息响应"""
    basic_operations: Dict[str, str] = Field(..., description="基础操作定价")
    additional_features: Dict[str, str] = Field(..., description="附加功能定价")
    note: str = Field(..., description="说明")
    reference_url: str = Field(..., description="参考链接")


# ==================== Endpoints ====================

@router.get(
    "/estimate/search",
    response_model=CreditEstimateResponse,
    summary="估算关键词搜索任务积分消耗",
    description="""
    根据搜索参数估算 Firecrawl API 积分消耗

    **计算规则**:
    - Search API 基础: 2积分/10条结果
    - 详情页爬取: 1积分/条
    - Stealth模式: +4积分/条
    - JSON模式: +4积分/条

    **示例**:
    - 搜索10条结果，爬取详情页: 2 + 10 = 12 积分
    - 搜索20条结果，爬取详情页: 4 + 20 = 24 积分
    - 搜索10条结果，不爬取详情页: 2 积分
    """
)
async def estimate_search_credits(
    num_results: int = Query(10, ge=1, le=100, description="搜索结果数量"),
    enable_detail_scrape: bool = Query(True, description="是否启用详情页爬取"),
    use_stealth_mode: bool = Query(False, description="是否使用Stealth代理模式"),
    use_json_mode: bool = Query(False, description="是否使用JSON模式")
):
    """估算关键词搜索任务的积分消耗"""
    estimate = FirecrawlCreditsCalculator.estimate_search_credits(
        num_results=num_results,
        enable_detail_scrape=enable_detail_scrape,
        use_stealth_mode=use_stealth_mode,
        use_json_mode=use_json_mode
    )

    return CreditEstimateResponse(**estimate.to_dict())


@router.get(
    "/estimate/crawl",
    response_model=CreditEstimateResponse,
    summary="估算网站爬取任务积分消耗",
    description="""
    根据爬取参数估算 Firecrawl API 积分消耗

    **计算规则**:
    - Crawl API: 1积分/页面

    **示例**:
    - 爬取10个页面: 10 积分
    - 爬取100个页面: 100 积分

    **注意**: 实际爬取页面数可能少于限制数，积分消耗按实际页面数计算
    """
)
async def estimate_crawl_credits(
    limit: int = Query(10, ge=1, le=500, description="最大页面数限制"),
    max_depth: int = Query(3, ge=1, le=10, description="最大爬取深度"),
    estimated_pages: Optional[int] = Query(None, ge=1, description="预估实际爬取页面数")
):
    """估算网站爬取任务的积分消耗"""
    estimate = FirecrawlCreditsCalculator.estimate_crawl_credits(
        limit=limit,
        max_depth=max_depth,
        estimated_pages=estimated_pages
    )

    return CreditEstimateResponse(**estimate.to_dict())


@router.get(
    "/estimate/scrape",
    response_model=CreditEstimateResponse,
    summary="估算单页面爬取任务积分消耗",
    description="""
    根据爬取参数估算 Firecrawl API 积分消耗

    **计算规则**:
    - Scrape API: 1积分/页面
    - PDF解析: +1积分/PDF页

    **示例**:
    - 爬取1个页面: 1 积分
    - 爬取1个页面，包含10页PDF: 1 + 10 = 11 积分
    """
)
async def estimate_scrape_credits(
    num_urls: int = Query(1, ge=1, le=100, description="URL数量"),
    has_pdf: bool = Query(False, description="是否包含PDF"),
    pdf_pages: int = Query(0, ge=0, le=1000, description="PDF页数")
):
    """估算单页面爬取任务的积分消耗"""
    estimate = FirecrawlCreditsCalculator.estimate_scrape_credits(
        num_urls=num_urls,
        has_pdf=has_pdf,
        pdf_pages=pdf_pages
    )

    return CreditEstimateResponse(**estimate.to_dict())


@router.get(
    "/pricing",
    response_model=PricingInfoResponse,
    summary="获取 Firecrawl API 积分定价信息",
    description="""
    返回 Firecrawl API v2 的积分定价规则

    **基础操作**:
    - Scrape API: 1积分/页面
    - Crawl API: 1积分/页面
    - Search API: 2积分/10条结果

    **附加功能**:
    - PDF解析: +1积分/PDF页
    - Stealth代理: +4积分/结果
    - JSON模式: +4积分/结果

    **数据来源**: 基于 Firecrawl 官方定价（2025年）
    """
)
async def get_pricing_info():
    """获取 Firecrawl API 积分定价信息"""
    pricing = FirecrawlCreditsCalculator.get_pricing_info()

    return PricingInfoResponse(
        basic_operations=pricing["基础操作"],
        additional_features=pricing["附加功能"],
        note=pricing["说明"],
        reference_url=pricing["参考链接"]
    )

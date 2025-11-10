"""
Firecrawl API 积分计算器

基于 Firecrawl v2 API 官方定价（2025年）:
https://www.firecrawl.dev/pricing

积分消耗规则:
1. Scrape API: 1 积分/页面
2. Crawl API: 1 积分/页面（发现的每个页面）
3. Search API:
   - 仅搜索（不爬取）: 2 积分/10条结果 (0.2积分/条)
   - 搜索+爬取: 2积分（搜索）+ 1积分/条（爬取）
4. 附加功能:
   - PDF解析: +1积分/PDF页
   - Stealth代理模式: +4积分/结果
   - JSON模式: +4积分/结果
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import math


@dataclass
class CreditEstimate:
    """积分估算结果"""
    total_credits: int  # 总积分
    breakdown: Dict[str, int]  # 明细
    description: str  # 说明

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_credits": self.total_credits,
            "breakdown": self.breakdown,
            "description": self.description
        }


class FirecrawlCreditsCalculator:
    """Firecrawl API 积分计算器"""

    # 基础积分消耗
    CREDIT_PER_SCRAPE = 1  # Scrape API: 1积分/页面
    CREDIT_PER_CRAWL_PAGE = 1  # Crawl API: 1积分/页面
    CREDIT_SEARCH_BASE = 2  # Search API 基础: 2积分/10条结果
    CREDIT_PER_SCRAPED_RESULT = 1  # 搜索结果爬取: 1积分/条
    CREDIT_MAP_API = 1  # Map API: 固定1积分（无论返回多少URL）

    # 附加功能积分消耗
    CREDIT_PDF_PER_PAGE = 1  # PDF解析: +1积分/PDF页
    CREDIT_STEALTH_MODE = 4  # Stealth代理: +4积分/结果
    CREDIT_JSON_MODE = 4  # JSON模式: +4积分/结果

    @classmethod
    def estimate_search_credits(
        cls,
        num_results: int = 10,
        enable_detail_scrape: bool = True,
        use_stealth_mode: bool = False,
        use_json_mode: bool = False
    ) -> CreditEstimate:
        """估算关键词搜索任务的积分消耗

        Args:
            num_results: 搜索结果数量
            enable_detail_scrape: 是否启用详情页爬取
            use_stealth_mode: 是否使用Stealth代理模式
            use_json_mode: 是否使用JSON模式

        Returns:
            CreditEstimate: 积分估算结果
        """
        breakdown = {}

        # 1. Search API 基础消耗（2积分/10条结果）
        search_credits = math.ceil(num_results / 10) * cls.CREDIT_SEARCH_BASE
        breakdown["search_api"] = search_credits

        # 2. 详情页爬取消耗（如果启用）
        scrape_credits = 0
        if enable_detail_scrape:
            scrape_credits = num_results * cls.CREDIT_PER_SCRAPED_RESULT
            breakdown["detail_scrape"] = scrape_credits

        # 3. 附加功能消耗
        extra_credits = 0
        if use_stealth_mode:
            stealth_credits = num_results * cls.CREDIT_STEALTH_MODE
            breakdown["stealth_mode"] = stealth_credits
            extra_credits += stealth_credits

        if use_json_mode:
            json_credits = num_results * cls.CREDIT_JSON_MODE
            breakdown["json_mode"] = json_credits
            extra_credits += json_credits

        # 计算总积分
        total_credits = search_credits + scrape_credits + extra_credits

        # 生成说明
        desc_parts = [
            f"搜索 {num_results} 条结果: {search_credits} 积分"
        ]
        if enable_detail_scrape:
            desc_parts.append(f"爬取详情页: {scrape_credits} 积分")
        if use_stealth_mode:
            desc_parts.append(f"Stealth模式: {breakdown['stealth_mode']} 积分")
        if use_json_mode:
            desc_parts.append(f"JSON模式: {breakdown['json_mode']} 积分")

        description = " + ".join(desc_parts) + f" = {total_credits} 积分"

        return CreditEstimate(
            total_credits=total_credits,
            breakdown=breakdown,
            description=description
        )

    @classmethod
    def estimate_crawl_credits(
        cls,
        limit: int = 10,
        max_depth: int = 3,
        estimated_pages: Optional[int] = None
    ) -> CreditEstimate:
        """估算网站爬取任务的积分消耗

        Args:
            limit: 最大页面数限制
            max_depth: 最大爬取深度
            estimated_pages: 预估实际爬取页面数（如果不提供，使用limit）

        Returns:
            CreditEstimate: 积分估算结果
        """
        # 实际爬取页面数
        actual_pages = estimated_pages if estimated_pages is not None else limit

        # Crawl API: 1积分/页面
        total_credits = actual_pages * cls.CREDIT_PER_CRAWL_PAGE

        breakdown = {
            "crawl_pages": total_credits
        }

        description = (
            f"爬取 {actual_pages} 个页面"
            f"（限制: {limit}, 深度: {max_depth}）= {total_credits} 积分"
        )

        return CreditEstimate(
            total_credits=total_credits,
            breakdown=breakdown,
            description=description
        )

    @classmethod
    def estimate_scrape_credits(
        cls,
        num_urls: int = 1,
        has_pdf: bool = False,
        pdf_pages: int = 0
    ) -> CreditEstimate:
        """估算单页面爬取任务的积分消耗

        Args:
            num_urls: URL数量
            has_pdf: 是否包含PDF
            pdf_pages: PDF页数（如果有）

        Returns:
            CreditEstimate: 积分估算结果
        """
        breakdown = {}

        # Scrape API: 1积分/页面
        scrape_credits = num_urls * cls.CREDIT_PER_SCRAPE
        breakdown["scrape_api"] = scrape_credits

        # PDF解析（如果有）
        pdf_credits = 0
        if has_pdf and pdf_pages > 0:
            pdf_credits = pdf_pages * cls.CREDIT_PDF_PER_PAGE
            breakdown["pdf_parsing"] = pdf_credits

        total_credits = scrape_credits + pdf_credits

        # 生成说明
        desc_parts = [f"爬取 {num_urls} 个页面: {scrape_credits} 积分"]
        if has_pdf:
            desc_parts.append(f"PDF解析 {pdf_pages} 页: {pdf_credits} 积分")

        description = " + ".join(desc_parts) + f" = {total_credits} 积分"

        return CreditEstimate(
            total_credits=total_credits,
            breakdown=breakdown,
            description=description
        )

    @classmethod
    def calculate_actual_credits(
        cls,
        operation: str,
        **kwargs
    ) -> int:
        """计算实际消耗的积分（用于记录实际执行结果）

        Args:
            operation: 操作类型 ("search", "crawl", "scrape")
            **kwargs: 操作相关参数

        Returns:
            int: 实际消耗积分

        Examples:
            >>> calculate_actual_credits("search", results_count=10, scraped_count=8)
            10  # 2 (search) + 8 (scrape)

            >>> calculate_actual_credits("crawl", pages_crawled=25)
            25

            >>> calculate_actual_credits("scrape", urls_scraped=1)
            1
        """
        if operation == "search":
            results_count = kwargs.get("results_count", 0)
            scraped_count = kwargs.get("scraped_count", 0)

            # Search API基础消耗
            search_credits = math.ceil(results_count / 10) * cls.CREDIT_SEARCH_BASE

            # 详情页爬取消耗
            scrape_credits = scraped_count * cls.CREDIT_PER_SCRAPED_RESULT

            return search_credits + scrape_credits

        elif operation == "crawl":
            pages_crawled = kwargs.get("pages_crawled", 0)
            return pages_crawled * cls.CREDIT_PER_CRAWL_PAGE

        elif operation == "scrape":
            urls_scraped = kwargs.get("urls_scraped", 1)
            pdf_pages = kwargs.get("pdf_pages", 0)

            scrape_credits = urls_scraped * cls.CREDIT_PER_SCRAPE
            pdf_credits = pdf_pages * cls.CREDIT_PDF_PER_PAGE

            return scrape_credits + pdf_credits

        else:
            raise ValueError(f"未知操作类型: {operation}")

    @classmethod
    def estimate_map_scrape_credits(
        cls,
        estimated_urls: int = 100,
        estimated_scraped: int = 50
    ) -> CreditEstimate:
        """估算 Map + Scrape 组合任务的积分消耗

        Args:
            estimated_urls: 预估 Map API 返回的URL数量
            estimated_scraped: 预估实际 Scrape 的页面数量

        Returns:
            CreditEstimate: 积分估算结果
        """
        breakdown = {}

        # 1. Map API 固定消耗
        map_credits = cls.CREDIT_MAP_API
        breakdown["map_api"] = map_credits

        # 2. Scrape API 消耗
        scrape_credits = estimated_scraped * cls.CREDIT_PER_SCRAPE
        breakdown["scrape_api"] = scrape_credits

        total_credits = map_credits + scrape_credits

        # 生成说明
        description = (
            f"Map API: {map_credits} 积分 + "
            f"Scrape {estimated_scraped} 页: {scrape_credits} 积分 = "
            f"{total_credits} 积分 "
            f"(发现 {estimated_urls} 个URL)"
        )

        return CreditEstimate(
            total_credits=total_credits,
            breakdown=breakdown,
            description=description
        )

    @classmethod
    def calculate_map_scrape_credits(
        cls,
        urls_discovered: int,
        pages_scraped: int
    ) -> int:
        """计算 Map + Scrape 实际消耗的积分

        Args:
            urls_discovered: Map API 发现的URL数量
            pages_scraped: 实际 Scrape 的页面数量

        Returns:
            int: 实际消耗积分
        """
        # Map API: 固定1积分
        map_credits = cls.CREDIT_MAP_API

        # Scrape API: 1积分/页面
        scrape_credits = pages_scraped * cls.CREDIT_PER_SCRAPE

        return map_credits + scrape_credits

    @classmethod
    def get_pricing_info(cls) -> Dict[str, Any]:
        """获取积分定价信息

        Returns:
            Dict: 积分定价规则详情
        """
        return {
            "基础操作": {
                "scrape_api": f"{cls.CREDIT_PER_SCRAPE} 积分/页面",
                "crawl_api": f"{cls.CREDIT_PER_CRAWL_PAGE} 积分/页面",
                "search_api_base": f"{cls.CREDIT_SEARCH_BASE} 积分/10条结果",
                "search_result_scrape": f"{cls.CREDIT_PER_SCRAPED_RESULT} 积分/条",
                "map_api": f"{cls.CREDIT_MAP_API} 积分/次（固定）"
            },
            "附加功能": {
                "pdf_parsing": f"+{cls.CREDIT_PDF_PER_PAGE} 积分/PDF页",
                "stealth_mode": f"+{cls.CREDIT_STEALTH_MODE} 积分/结果",
                "json_mode": f"+{cls.CREDIT_JSON_MODE} 积分/结果"
            },
            "组合模式": {
                "map_scrape": "Map API (1积分) + Scrape API (N积分)"
            },
            "说明": "基于 Firecrawl v2 API 官方定价（2025年）",
            "参考链接": "https://www.firecrawl.dev/pricing"
        }

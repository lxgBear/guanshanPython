"""
Firecrawl爬虫适配器实现
实现领域层定义的CrawlerInterface接口
"""
import asyncio
import hashlib
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions

from src.core.domain.interfaces.crawler_interface import (
    CrawlerInterface,
    CrawlResult,
    CrawlException
)
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FirecrawlAdapter(CrawlerInterface):
    """
    Firecrawl爬虫适配器
    将Firecrawl API适配为系统的CrawlerInterface
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Firecrawl适配器
        
        Args:
            api_key: Firecrawl API密钥，如果不提供则从配置中读取
        """
        self.api_key = api_key or settings.FIRECRAWL_API_KEY
        if not self.api_key:
            raise ValueError("Firecrawl API密钥未配置")

        # v4.6.0: 使用 Firecrawl (v2 API)
        self.client = Firecrawl(api_key=self.api_key)
        self.timeout = settings.FIRECRAWL_TIMEOUT
        self.max_retries = settings.FIRECRAWL_MAX_RETRIES

        logger.info("Firecrawl v2 适配器初始化成功")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def scrape(self, url: str, **options) -> CrawlResult:
        """
        爬取单个页面

        Args:
            url: 目标URL
            **options: 爬取选项
                - wait_for: 等待时间（毫秒），默认 1000
                - include_tags: 要包含的 HTML 标签列表
                - exclude_tags: 要排除的 HTML 标签列表，默认 None（不排除）
                - only_main_content: 只提取主要内容，默认 False（获取完整 HTML）
                - timeout: 超时时间（秒）

        Returns:
            CrawlResult: 爬取结果
        """
        try:
            logger.info(f"开始爬取URL: {url}")

            # Firecrawl v2 API: 使用命名参数
            formats = options.get('formats', ['markdown', 'html'])
            only_main_content = options.get('only_main_content', False)  # 默认 False 获取完整 HTML
            wait_for = options.get('wait_for', 1000)
            include_tags = options.get('include_tags')
            exclude_tags = options.get('exclude_tags')
            timeout = options.get('timeout', self.timeout)

            logger.info(f"爬取参数: formats={formats}, onlyMainContent={only_main_content}, waitFor={wait_for}ms")

            # v4.6.0: 使用 v2 API 的 scrape() 方法（同步）
            result = await asyncio.to_thread(
                self.client.scrape,
                url,
                formats=formats,
                only_main_content=only_main_content,
                wait_for=wait_for,
                include_tags=include_tags,
                exclude_tags=exclude_tags,
                timeout=timeout
            )

            # 处理结果（v2 返回 Document 对象）
            crawl_result = CrawlResult(
                url=url,
                content=getattr(result, 'content', '') or '',
                markdown=getattr(result, 'markdown', None),
                html=getattr(result, 'html', None),
                metadata=getattr(result, 'metadata', {}),
                screenshot=getattr(result, 'screenshot', None)
            )

            logger.info(f"成功爬取URL: {url}")
            return crawl_result

        except asyncio.TimeoutError:
            logger.error(f"爬取超时: {url}")
            raise CrawlException(f"爬取超时 ({self.timeout}秒)", url=url)
        except Exception as e:
            logger.error(f"爬取失败: {url}, 错误: {str(e)}")
            raise CrawlException(f"爬取失败: {str(e)}", url=url)
    
    async def crawl(self, url: str, limit: int = 10, **options) -> List[CrawlResult]:
        """
        爬取整个网站

        Args:
            url: 起始URL
            limit: 最大页面数
            **options: 爬取选项
                - prompt: 自然语言描述爬取意图（v2 API新增）
                - max_depth: 最大爬取深度
                - include_paths: 包含的URL路径模式
                - exclude_paths: 排除的URL路径模式
                - only_main_content: 只提取主要内容，默认 False（获取完整 HTML）
                - wait_for: 等待时间（毫秒）
                - exclude_tags: 排除的HTML标签，默认 None（不排除）

        Returns:
            List[CrawlResult]: 爬取结果列表
        """
        try:
            logger.info(f"开始爬取网站: {url}, 限制: {limit}页")

            # Firecrawl v2 API: 使用命名参数（不再使用 params 字典）
            max_depth = options.get('max_depth', 3)
            include_paths = options.get('include_paths', [])
            exclude_paths = options.get('exclude_paths', [])
            prompt = options.get('prompt')  # v2 API 新增: 自然语言描述

            # v2 API: 构建 scrape_options
            scrape_options = ScrapeOptions(
                formats=['markdown', 'html'],  # 格式列表
                only_main_content=options.get('only_main_content', False),  # 默认 False 获取完整 HTML
                wait_for=options.get('wait_for', 1000),
                exclude_tags=options.get('exclude_tags')  # 默认 None，不排除任何标签
            )

            if prompt:
                logger.info(f"🤖 使用 prompt 参数: {prompt}")
            logger.info(f"Firecrawl v2 爬取参数: limit={limit}, max_discovery_depth={max_depth}")

            # v4.6.0: 使用 v2 API 的 crawl() 方法（同步，返回 CrawlJob）
            # timeout=None 表示永不超时,让爬取任务完整执行
            crawl_params = {
                "url": url,
                "limit": limit,
                "max_discovery_depth": max_depth,
                "include_paths": include_paths,
                "exclude_paths": exclude_paths,
                "scrape_options": scrape_options,
                "poll_interval": 2,
                "timeout": None  # 永不超时
            }

            # 如果有 prompt，添加到参数中
            if prompt:
                crawl_params["prompt"] = prompt

            job = await asyncio.to_thread(
                self.client.crawl,
                **crawl_params
            )

            logger.info(f"Firecrawl v2 crawl 完成，job 类型: {type(job)}")

            # 处理 CrawlJob 结果
            results = []
            if hasattr(job, 'data') and job.data:
                for document in job.data:
                    result = CrawlResult(
                        url=getattr(document, 'url', '') or '',
                        content=getattr(document, 'content', '') or '',
                        markdown=getattr(document, 'markdown', None),
                        html=getattr(document, 'html', None),
                        metadata=getattr(document, 'metadata', {})
                    )
                    results.append(result)

            logger.info(f"成功爬取网站: {url}, 获得 {len(results)} 页")
            return results
            
        except Exception as e:
            logger.error(f"网站爬取失败: {url}, 错误: {str(e)}")
            raise CrawlException(f"网站爬取失败: {str(e)}", url=url)
    
    async def map(self, url: str, limit: int = 100) -> List[str]:
        """
        生成站点地图
        
        Args:
            url: 目标网站URL
            limit: 最大URL数量
        
        Returns:
            List[str]: URL列表
        """
        try:
            logger.info(f"生成站点地图: {url}, 限制: {limit}")
            
            result = await self.client.map(url, limit=limit)
            urls = result.get('urls', [])
            
            logger.info(f"成功生成站点地图: {url}, 发现 {len(urls)} 个URL")
            return urls
            
        except Exception as e:
            logger.error(f"站点地图生成失败: {url}, 错误: {str(e)}")
            raise CrawlException(f"站点地图生成失败: {str(e)}", url=url)
    
    async def extract(self, url: str, schema: Dict) -> Dict:
        """
        提取结构化数据
        
        Args:
            url: 目标URL
            schema: 提取模式
        
        Returns:
            Dict: 提取的结构化数据
        """
        try:
            logger.info(f"提取结构化数据: {url}")
            
            # Firecrawl的extract端点支持自然语言描述
            result = await self.client.extract(
                url=url,
                schema=schema,
                formats=['markdown']
            )
            
            extracted_data = result.get('data', {})
            logger.info(f"成功提取数据: {url}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"数据提取失败: {url}, 错误: {str(e)}")
            raise CrawlException(f"数据提取失败: {str(e)}", url=url)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=20),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def search(self, query: str, limit: int = 10) -> List[CrawlResult]:
        """
        搜索并爬取结果

        Args:
            query: 搜索查询
            limit: 结果数量限制（注意：Firecrawl v2可能不支持此参数）

        Returns:
            List[CrawlResult]: 搜索结果
        """
        try:
            logger.info(f"搜索查询: {query}, 期望限制: {limit}")

            # v2 API: 构建 scrape_options
            scrape_options = ScrapeOptions(
                formats=['markdown', 'html']
            )

            logger.info(f"Firecrawl v2 搜索参数: limit={limit}")

            # v4.6.0: 使用 v2 API 的 search() 方法（返回 SearchData）
            search_data = await asyncio.to_thread(
                self.client.search,
                query,
                limit=limit,
                scrape_options=scrape_options,
                timeout=self.timeout
            )

            # 处理 SearchData 结果
            results = []
            if hasattr(search_data, 'data') and search_data.data:
                for document in search_data.data[:limit]:
                    crawl_result = CrawlResult(
                        url=getattr(document, 'url', '') or '',
                        content=getattr(document, 'content', '') or getattr(document, 'markdown', '') or '',
                        markdown=getattr(document, 'markdown', None),
                        html=getattr(document, 'html', None),
                        metadata=getattr(document, 'metadata', {})
                    )
                    results.append(crawl_result)

            logger.info(f"搜索完成: {query}, 获得 {len(results)} 个结果")
            return results

        except asyncio.TimeoutError:
            error_msg = f"搜索超时 (超过{self.timeout}秒): {query}"
            logger.error(error_msg)
            raise CrawlException(error_msg)
        except Exception as e:
            error_msg = f"搜索失败: {query}, 错误类型: {type(e).__name__}, 详情: {str(e) or '无详细信息'}"
            logger.error(error_msg)
            raise CrawlException(error_msg)
    
    def _build_scrape_options(self, options: Dict) -> Dict:
        """
        构建Firecrawl爬取选项
        
        Args:
            options: 用户选项
        
        Returns:
            Dict: Firecrawl选项
        """
        scrape_options = {
            'formats': ['markdown', 'html'],
            'waitFor': options.get('wait_for', 1000)
        }
        
        # 添加包含/排除标签
        if 'include_tags' in options:
            scrape_options['includeTags'] = options['include_tags']
        if 'exclude_tags' in options:
            scrape_options['excludeTags'] = options.get('exclude_tags', ['nav', 'footer', 'header'])
        
        # 添加页面交互动作
        if 'actions' in options:
            scrape_options['actions'] = options['actions']
        
        return scrape_options
    
    def _process_scrape_result(self, url: str, result: Dict) -> CrawlResult:
        """
        处理爬取结果
        
        Args:
            url: 原始URL
            result: Firecrawl返回的结果
        
        Returns:
            CrawlResult: 标准化的爬取结果
        """
        return CrawlResult(
            url=url,
            content=result.get('content', ''),
            markdown=result.get('markdown'),
            html=result.get('html'),
            metadata=result.get('metadata', {}),
            screenshot=result.get('screenshot')
        )


class FirecrawlRateLimiter:
    """
    Firecrawl速率限制器
    管理API调用速率，避免触发限制
    """
    
    def __init__(self, max_requests_per_minute: int = 60):
        self.max_requests_per_minute = max_requests_per_minute
        self.request_times: List[float] = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """获取执行权限，必要时等待"""
        async with self.lock:
            import time
            now = time.time()
            
            # 清理一分钟前的记录
            self.request_times = [
                t for t in self.request_times
                if now - t < 60
            ]
            
            # 如果达到限制，等待
            if len(self.request_times) >= self.max_requests_per_minute:
                wait_time = 60 - (now - self.request_times[0])
                if wait_time > 0:
                    logger.warning(f"达到速率限制，等待 {wait_time:.2f} 秒")
                    await asyncio.sleep(wait_time)
            
            # 记录新请求
            self.request_times.append(now)
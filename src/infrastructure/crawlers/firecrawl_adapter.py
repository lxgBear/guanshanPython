"""
Firecrawl爬虫适配器实现
实现领域层定义的CrawlerInterface接口
"""
import asyncio
import hashlib
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from firecrawl import AsyncFirecrawl
except ImportError:
    # 如果Firecrawl未安装，使用模拟实现以便测试
    class AsyncFirecrawl:
        def __init__(self, api_key: str):
            self.api_key = api_key

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
        
        self.client = AsyncFirecrawl(api_key=self.api_key)
        self.timeout = settings.FIRECRAWL_TIMEOUT
        self.max_retries = settings.FIRECRAWL_MAX_RETRIES
        
        logger.info("Firecrawl适配器初始化成功")
    
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
        
        Returns:
            CrawlResult: 爬取结果
        """
        try:
            logger.info(f"开始爬取URL: {url}")
            
            # 构建Firecrawl选项
            scrape_options = self._build_scrape_options(options)
            
            # 执行爬取
            result = await asyncio.wait_for(
                self.client.scrape(url, **scrape_options),
                timeout=self.timeout
            )
            
            # 处理结果
            crawl_result = self._process_scrape_result(url, result)
            
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
        
        Returns:
            List[CrawlResult]: 爬取结果列表
        """
        try:
            logger.info(f"开始爬取网站: {url}, 限制: {limit}页")
            
            # 构建爬取选项
            crawl_options = {
                'limit': limit,
                'maxDepth': options.get('max_depth', 3),
                'includePaths': options.get('include_paths', []),
                'excludePaths': options.get('exclude_paths', []),
                'allowBackwardLinks': options.get('allow_backward_links', False)
            }
            
            # 启动爬取任务
            job = await self.client.crawl(url, **crawl_options)
            
            # 处理结果
            results = []
            if job.get('success'):
                for page_data in job.get('data', []):
                    result = CrawlResult(
                        url=page_data.get('url', ''),
                        content=page_data.get('content', ''),
                        markdown=page_data.get('markdown'),
                        html=page_data.get('html'),
                        metadata=page_data.get('metadata', {})
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
    
    async def search(self, query: str, limit: int = 10) -> List[CrawlResult]:
        """
        搜索并爬取结果
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
        
        Returns:
            List[CrawlResult]: 搜索结果
        """
        try:
            logger.info(f"搜索查询: {query}, 限制: {limit}")
            
            # Firecrawl的搜索功能
            result = await self.client.search(query, limit=limit)
            
            # 处理搜索结果
            results = []
            for item in result.get('results', []):
                crawl_result = CrawlResult(
                    url=item.get('url', ''),
                    content=item.get('content', ''),
                    markdown=item.get('markdown'),
                    metadata=item.get('metadata', {})
                )
                results.append(crawl_result)
            
            logger.info(f"搜索完成: {query}, 获得 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"搜索失败: {query}, 错误: {str(e)}")
            raise CrawlException(f"搜索失败: {str(e)}")
    
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
"""
Firecrawl 搜索服务适配器
"""

import asyncio
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from src.core.domain.entities.search_config import SearchConfigManager, UserSearchConfig
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FirecrawlSearchAdapter:
    """
Firecrawl 搜索API适配器
    """
    
    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY
        self.base_url = settings.FIRECRAWL_BASE_URL.rstrip('/')
        self.config_manager = SearchConfigManager()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # 优先从settings读取TEST_MODE，fallback到环境变量
        self.is_test_mode = getattr(settings, 'TEST_MODE',
                                     os.getenv("TEST_MODE", "false").lower() == "true")

        if self.is_test_mode:
            logger.info("🧪 Firecrawl适配器运行在测试模式 - 将生成模拟数据")
        else:
            logger.info(f"🌐 Firecrawl适配器运行在生产模式 - API Base URL: {self.base_url}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def search(self, 
                    query: str, 
                    user_config: Optional[UserSearchConfig] = None,
                    task_id: Optional[str] = None) -> SearchResultBatch:
        """
        执行搜索
        
        Args:
            query: 搜索查询字符串
            user_config: 用户搜索配置
            task_id: 任务ID
            
        Returns:
            SearchResultBatch: 搜索结果批次
        """
        start_time = datetime.utcnow()
        
        # 如果是测试模式，返回模拟数据
        if self.is_test_mode:
            logger.info(f"🧪 测试模式: 生成模拟搜索结果 - 查询: '{query}' (任务ID: {task_id})")
            return self._generate_test_results(query, task_id)
        
        # 获取最终配置
        if user_config is None:
            user_config = UserSearchConfig()
        
        config = self.config_manager.get_effective_config(user_config)
        
        # 构建请求体
        request_body = self._build_request_body(query, config)
        
        # 创建结果批次
        batch = SearchResultBatch(
            task_id=task_id if task_id else "",
            query=query,
            search_config=config,
            is_test_mode=False
        )
        
        try:
            # 配置httpx客户端 - 不使用系统代理以避免SOCKS问题
            # Firecrawl API不需要代理，直接连接
            client_config = {
                "proxies": None,  # 禁用代理
                "trust_env": False  # 不信任环境变量中的代理设置
            }

            logger.info(f"🔍 正在调用 Firecrawl API: {self.base_url}/v2/search")
            logger.info(f"📝 请求参数: {request_body}")

            # 发送请求
            async with httpx.AsyncClient(**client_config) as client:
                response = await client.post(
                    f"{self.base_url}/v2/search",
                    headers=self.headers,
                    json=request_body,
                    timeout=config.get('timeout', 30)
                )

                logger.info(f"📡 API 响应状态码: {response.status_code}")

                response.raise_for_status()

                # 解析响应
                data = response.json()
                logger.info(f"📦 响应数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")

                # 处理结果
                results = self._parse_search_results(data, task_id)
                logger.info(f"✅ 解析得到 {len(results)} 条搜索结果")

                # 添加到批次
                for result in results:
                    batch.add_result(result)

                batch.total_count = data.get('total', len(results))
                # v2使用creditsUsed, v0使用credits_used
                batch.credits_used = data.get('creditsUsed', data.get('credits_used', 1))

        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP {e.response.status_code}"
            try:
                error_body = e.response.json()
                error_detail += f": {error_body}"
            except:
                error_detail += f": {e.response.text[:200]}"

            logger.error(f"❌ 搜索请求失败: {error_detail}")
            batch.set_error(error_detail)

        except httpx.TimeoutException as e:
            error_msg = f"请求超时: {str(e)}"
            logger.error(f"❌ {error_msg}")
            batch.set_error(error_msg)

        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"❌ 搜索发生意外错误: {error_msg}")
            logger.error(f"堆栈信息:\n{traceback.format_exc()}")
            batch.set_error(error_msg)
        
        # 计算执行时间
        end_time = datetime.utcnow()
        batch.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return batch
    
    def _build_request_body(self, query: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """构建请求体"""
        body = {
            "query": query,
            "limit": config.get('limit', 20),
            "lang": config.get('language', 'zh')
        }

        # 添加scrapeOptions以获取完整网页内容
        # Firecrawl API v2: 默认search只返回元数据(title, url, description)
        # 需要scrapeOptions才能获取完整的markdown/html内容
        scrape_formats = config.get('scrape_formats', ['markdown', 'html', 'links'])
        if scrape_formats:
            body['scrapeOptions'] = {
                "formats": scrape_formats
            }
            # 可以添加更多scrape选项
            if config.get('only_main_content', True):
                body['scrapeOptions']['onlyMainContent'] = True

        # 添加可选参数
        if config.get('include_domains'):
            body['includeDomains'] = config['include_domains']

        if config.get('exclude_domains'):
            body['excludeDomains'] = config['exclude_domains']

        if config.get('time_range'):
            body['tbs'] = self._convert_time_range(config['time_range'])

        return body
    
    def _convert_time_range(self, time_range: str) -> str:
        """转换时间范围为Firecrawl格式"""
        mapping = {
            "day": "qdr:d",
            "week": "qdr:w",
            "month": "qdr:m",
            "year": "qdr:y"
        }
        return mapping.get(time_range, "")
    
    def _parse_search_results(self, data: Dict[str, Any], task_id: Optional[str]) -> List[SearchResult]:
        """解析搜索结果 - 支持Firecrawl API v2格式"""
        results = []

        # Firecrawl API v2 响应格式: data 是一个字典,包含 'web' 键
        # 例如: {"success": true, "data": {"web": [...]}, "creditsUsed": 1}
        data_content = data.get('data', {})

        # 处理v2格式: data.web 是结果列表
        if isinstance(data_content, dict) and 'web' in data_content:
            items = data_content.get('web', [])
        # 兼容v0格式: data 直接是结果列表
        elif isinstance(data_content, list):
            items = data_content
        else:
            logger.warning(f"未知的响应格式: data类型为 {type(data_content)}")
            items = []

        for item in items:
            # v2 API with scrapeOptions: markdown和html字段包含完整内容
            markdown = item.get('markdown', '')
            html = item.get('html', '')

            # content字段使用markdown内容，如果没有则使用html，最后fallback到空
            content = markdown if markdown else (html if html else item.get('content', ''))

            # 从原始数据的metadata中提取article字段
            item_metadata = item.get('metadata', {})

            # 处理article_tag：可能是字符串或列表
            article_tag_raw = item_metadata.get('article:tag')
            if isinstance(article_tag_raw, list):
                # 如果是列表，用逗号连接成字符串
                article_tag = ', '.join(str(tag) for tag in article_tag_raw) if article_tag_raw else None
            else:
                article_tag = article_tag_raw

            article_published_time = item_metadata.get('article:published_time')

            # 构建metadata，包含links
            metadata = item_metadata.copy() if item_metadata else {}
            if 'links' in item:
                metadata['extracted_links'] = item.get('links', [])

            result = SearchResult(
                task_id=task_id if task_id else "",
                title=item.get('title', ''),
                url=item.get('url', ''),
                content=content,  # 优先使用markdown/html内容
                snippet=item.get('description', item.get('snippet', '')),  # v2使用description
                source=item.get('source', 'web'),
                published_date=self._parse_date(item.get('publishedDate')),
                author=item.get('author'),
                language=item.get('language'),
                raw_data=item,
                markdown_content=markdown,  # 保存markdown格式
                html_content=html,  # 保存html格式为顶层字段
                article_tag=article_tag,  # 文章标签
                article_published_time=article_published_time,  # 文章发布时间
                metadata=metadata,  # 包含links的metadata
                relevance_score=item.get('score', 0.0),
                status=ResultStatus.PENDING
            )
            results.append(result)

        return results
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
        
        try:
            return datetime.fromisoformat(date_str)
        except:
            return None
    
    def _generate_test_results(self, query: str, task_id: Optional[str]) -> SearchResultBatch:
        """生成测试模式的模拟结果"""
        batch = SearchResultBatch(
            task_id=task_id if task_id else "",
            query=query,
            search_config={'limit': 10},
            is_test_mode=True,
            test_limit_applied=True
        )
        
        # 生成10条模拟结果
        for i in range(10):
            result = SearchResult(
                task_id=task_id if task_id else "",
                title=f"测试结果 {i+1}: {query}",
                url=f"https://example.com/test/{i+1}",
                content=f"这是关于'{query}'的测试内容 {i+1}。" * 10,
                snippet=f"测试摘要: {query} - 结果 {i+1}",
                source="test",
                published_date=datetime.utcnow(),
                relevance_score=0.9 - (i * 0.05),
                is_test_data=True,
                status=ResultStatus.PROCESSED
            )
            batch.add_result(result)
        
        batch.total_count = 10
        batch.credits_used = 0  # 测试模式不消耗积分
        batch.execution_time_ms = 100  # 模拟100ms响应时间
        
        return batch
    
    async def batch_search(self, 
                          queries: List[Dict[str, Any]]) -> List[SearchResultBatch]:
        """
        批量搜索
        
        Args:
            queries: 搜索查询列表，每个包含 query 和 config
            
        Returns:
            List[SearchResultBatch]: 搜索结果列表
        """
        tasks = [
            self.search(
                query=q['query'],
                user_config=UserSearchConfig.from_json(q.get('config', {})),
                task_id=q.get('task_id')
            )
            for q in queries
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        batches = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"批量搜索第{i}个查询失败: {result}")
                # 创建失败的批次
                batch = SearchResultBatch(
                    task_id=queries[i].get('task_id', ''),
                    query=queries[i]['query'],
                    search_config=queries[i].get('config', {})
                )
                batch.set_error(str(result))
                batches.append(batch)
            else:
                batches.append(result)
        
        return batches
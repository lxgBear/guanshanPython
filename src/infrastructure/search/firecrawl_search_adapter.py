"""
Firecrawl 搜索服务适配器
"""

import asyncio
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

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

    def _log_retry_attempt(self, retry_state):
        """记录重试尝试"""
        attempt_number = retry_state.attempt_number
        if attempt_number > 1:
            exception = retry_state.outcome.exception()
            logger.warning(
                f"🔄 搜索请求失败，第 {attempt_number - 1} 次重试 (共3次) | "
                f"错误: {type(exception).__name__}: {str(exception)[:100]} | "
                f"将在 8 分钟后重试..."
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(480),  # 8分钟 = 480秒
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        before_sleep=lambda retry_state: FirecrawlSearchAdapter._log_retry_attempt(None, retry_state)
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

        # 提取语言配置用于后置过滤
        language = config.get('language', 'zh')
        strict_filter = config.get('strict_language_filter', True)

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
            # 配置httpx客户端 - 显式禁用代理但保留DNS解析
            # Firecrawl API不需要代理，直接连接
            # 注意: trust_env=False会导致DNS解析问题,因此只显式设置proxies={}来禁用代理
            client_config = {
                "proxies": {},  # 空字典禁用代理,但不影响DNS
                "timeout": config.get('timeout', 30)
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

                # 语言后置过滤（如果启用严格语言过滤且设置language=en）
                if language == 'en' and strict_filter:
                    results = self._post_filter_by_language(results, 'en')
                    logger.info(f"🌐 语言后置过滤: 保留 {len(results)} 条英文结果")

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
        """构建请求体 - Firecrawl API v2格式 (增强版)"""
        # Firecrawl API v2: 使用site:操作符来限制域名,而不是includeDomains参数
        final_query = query

        # 智能语言过滤：如果设置language为en且启用strict_language_filter，自动排除中文域名
        language = config.get('language', 'zh')
        strict_filter = config.get('strict_language_filter', True)  # 默认启用严格语言过滤

        if language == 'en' and strict_filter:
            # 检测查询中是否包含中文字符
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in query)

            if has_chinese:
                # 如果查询包含中文但要求英文结果，自动添加域名过滤
                # 排除常见的中文域名后缀
                chinese_domains_exclusion = (
                    '-site:*.cn '
                    '-site:*.com.cn '
                    '-site:*.hk '
                    '-site:*.tw '
                    '-inurl:zh '
                    '-inurl:zh-cn '
                    '-inurl:zh-hans '
                    '-inurl:zh-hant'
                )
                final_query = f"{query} {chinese_domains_exclusion}"
                logger.info(f"🌍 语言过滤: 检测到中文查询+英文要求，已添加域名过滤")

        # 如果配置了include_domains,添加site:操作符到查询中
        if config.get('include_domains'):
            domains = config['include_domains']
            if domains:
                # 为每个域名添加site:操作符
                site_operators = ' OR '.join([f'site:{domain}' for domain in domains])
                final_query = f"({site_operators}) {final_query}"

        body = {
            "query": final_query,
            "limit": config.get('limit', 20),
            "lang": language
        }

        # 添加 sources 参数 (web, images, news)
        if config.get('sources'):
            body['sources'] = config['sources']
            logger.info(f"🔍 搜索来源: {config['sources']}")

        # 添加scrapeOptions以获取完整网页内容
        # Firecrawl API v2: 默认search只返回元数据(title, url, description)
        # 需要scrapeOptions才能获取完整的markdown/html内容
        scrape_formats = config.get('scrape_formats', ['markdown', 'html', 'links'])
        if scrape_formats:
            body['scrapeOptions'] = {
                "formats": scrape_formats
            }

            # HTML清理选项 - 完整支持
            if config.get('only_main_content', True):
                body['scrapeOptions']['onlyMainContent'] = True

            # 注意：remove_base64_images默认为False（保留正文图片）
            # 配合onlyMainContent和blockAds，可以保留正文图片同时移除广告/非主内容区域的图片
            if config.get('remove_base64_images', False):
                body['scrapeOptions']['removeBase64Images'] = True
                logger.info("🖼️  HTML清理: 已启用base64图片移除（性能优化模式）")
            else:
                logger.info("📷 图片保留: 保留正文图片（配合主内容提取和广告屏蔽）")

            if config.get('block_ads', True):
                body['scrapeOptions']['blockAds'] = True
                logger.info("🚫 HTML清理: 已启用广告屏蔽")

            # 标签过滤 - 精细化HTML控制
            if config.get('include_tags'):
                body['scrapeOptions']['includeTags'] = config['include_tags']
                logger.info(f"✅ HTML标签: 仅保留 {config['include_tags']}")

            if config.get('exclude_tags'):
                body['scrapeOptions']['excludeTags'] = config['exclude_tags']
                logger.info(f"❌ HTML标签: 排除 {config['exclude_tags']}")

            # 等待动态内容加载
            if config.get('wait_for'):
                body['scrapeOptions']['waitFor'] = config['wait_for']
                logger.info(f"⏱️  等待加载: {config['wait_for']}ms")

        # 添加可选参数
        # 注意: v2 API不支持includeDomains和excludeDomains参数
        # 域名过滤通过查询中的site:操作符实现(见上方final_query处理)

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
            # 1. 提取核心字段
            title = item.get('title', '')
            url = item.get('url', '')
            description = item.get('description', item.get('snippet', ''))

            # 2. 内容字段优化: 截断markdown(最大5000字符),存储html
            markdown_full = item.get('markdown', '')
            if len(markdown_full) > 5000:
                markdown_content = markdown_full[:5000]
                logger.debug(f"📏 截断markdown: {len(markdown_full)}字符 → 5000字符 (URL: {url[:50]}...)")
            else:
                markdown_content = markdown_full

            # 提取HTML内容
            html_content = item.get('html', '')

            # 使用截断后的markdown作为content,或使用description
            content = markdown_content if markdown_content else description

            # 3. 提取metadata字段
            item_metadata = item.get('metadata', {})

            # 4. 构建精简的metadata(只保留有用字段,过滤冗余字段)
            filtered_metadata = {
                'language': item_metadata.get('language'),
                'og_type': item_metadata.get('og:type'),
            }
            # 移除None值
            filtered_metadata = {k: v for k, v in filtered_metadata.items() if v is not None}

            # 5. 提取文章特定字段
            article_tag_raw = item_metadata.get('article:tag')
            if isinstance(article_tag_raw, list):
                # 如果是列表，用逗号连接成字符串
                article_tag = ', '.join(str(tag) for tag in article_tag_raw) if article_tag_raw else None
            else:
                article_tag = article_tag_raw

            article_published_time = item_metadata.get('article:published_time')

            # 6. 提取技术字段
            source_url = item_metadata.get('sourceURL')  # 原始URL(重定向场景)
            http_status_code = item_metadata.get('statusCode')
            search_position = item.get('position')

            # 7. 解析发布日期
            published_date = self._parse_date(item.get('publishedDate'))

            # 8. 创建搜索结果实体(已移除raw_data,保留html_content)
            result = SearchResult(
                task_id=task_id if task_id else "",
                title=title,
                url=url,
                content=content,
                snippet=description,
                source=item.get('source', 'web'),
                published_date=published_date,
                author=item.get('author'),
                language=item_metadata.get('language'),
                # 优化后的字段
                markdown_content=markdown_content,  # 截断版本(最大5000字符)
                html_content=html_content,  # HTML格式内容(用于富文本显示和分析)
                article_tag=article_tag,
                article_published_time=article_published_time,
                source_url=source_url,
                http_status_code=http_status_code,
                search_position=search_position,
                metadata=filtered_metadata,  # 精简版元数据(~200字节 vs 原来的2-5KB)
                # 不再存储: raw_data (~850KB)
                relevance_score=item.get('score', 0.0),
                status=ResultStatus.PENDING
            )

            logger.debug(f"✅ 解析结果: {title[:50]}... (content: {len(content)}字符, metadata: {len(str(filtered_metadata))}字节)")
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

    def _post_filter_by_language(self, results: List[SearchResult], target_language: str) -> List[SearchResult]:
        """后置语言过滤 - 根据URL、语言元数据和标题字符进行过滤

        Args:
            results: 原始搜索结果列表
            target_language: 目标语言（如 'en'）

        Returns:
            过滤后的结果列表
        """
        filtered_results = []

        for result in results:
            # 1. 检查URL中是否包含中文域名或路径标识
            url_lower = result.url.lower()
            chinese_url_indicators = [
                '.cn', '.com.cn', '.hk', '.tw',
                '/zh/', '/zh-cn/', '/zh-hans/', '/zh-hant/',
                'zhongwen', 'hans', 'hant'
            ]

            has_chinese_url = any(indicator in url_lower for indicator in chinese_url_indicators)

            # 2. 检查语言元数据
            language_metadata = result.language
            is_chinese_language = False
            if language_metadata:
                lang_lower = str(language_metadata).lower()
                is_chinese_language = any(zh in lang_lower for zh in ['zh', 'hans', 'hant', 'chinese'])

            # 3. 检查标题是否包含中文字符
            has_chinese_chars = any('\u4e00' <= char <= '\u9fff' for char in result.title)

            # 4. 过滤逻辑：如果是中文内容则跳过
            if has_chinese_url or is_chinese_language or has_chinese_chars:
                logger.debug(f"🚫 过滤中文结果: {result.title[:50]}... (URL: {result.url[:50]}...)")
                continue

            # 5. 保留英文结果
            filtered_results.append(result)

        return filtered_results
    
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
"""
GPT-5 Search API 适配器 (api.gpt.ge)
用于执行搜索查询并返回 URL 和标题列表

架构升级 v2.0:
- 使用 gpt-5-search-api 模型 (api.gpt.ge)
- 标准 OpenAI chat/completions 接口
- 支持测试模式（返回模拟数据）
- 异步 HTTP 客户端
- 重试机制和错误处理
- 结果过滤和排序
- URL annotations 解析
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

try:
    import httpx
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type
    )
except ImportError:
    httpx = None
    retry = None
    stop_after_attempt = None
    wait_exponential = None
    retry_if_exception_type = None

from src.services.nl_search.config import nl_search_config


logger = logging.getLogger(__name__)


class SearchResult:
    """搜索结果数据类"""

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str = "",
        position: int = 0,
        score: float = 0.0,
        source: str = "search"
    ):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.position = position
        self.score = score
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "position": self.position,
            "score": self.score,
            "source": self.source
        }


class GPT5SearchAdapter:
    """GPT-5 Search API 适配器 (api.gpt.ge)

    功能:
    - 使用 gpt-5-search-api 模型执行搜索查询
    - 返回 URL、标题和内容摘要
    - 支持测试模式和真实 API
    - 结果过滤和排序
    - 解析 URL annotations
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        test_mode: bool = False,
        timeout: int = 30
    ):
        """
        初始化搜索适配器

        Args:
            api_key: api.gpt.ge API Key（可选，默认使用配置）
            base_url: API Base URL（可选，默认使用配置）
            test_mode: 是否测试模式（返回模拟数据）
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key or nl_search_config.llm_api_key
        self.base_url = base_url or nl_search_config.llm_base_url
        self.test_mode = test_mode
        self.timeout = timeout
        self.max_results = nl_search_config.max_search_results
        self.search_model = nl_search_config.search_model
        self.max_tokens = nl_search_config.search_max_tokens

        # HTTP 客户端
        if httpx is None:
            logger.warning("httpx 包未安装，请运行: pip install httpx")
            self.client = None
        else:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )

        # API 端点 (标准 OpenAI chat/completions)
        self.search_api_url = f"{self.base_url}/chat/completions"

        logger.info(
            f"GPT5SearchAdapter initialized: model={self.search_model}, "
            f"url={self.search_api_url}, test_mode={self.test_mode}"
        )

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        language: str = "zh-cn"
    ) -> List[SearchResult]:
        """
        执行搜索查询

        Args:
            query: 搜索查询字符串
            max_results: 最大结果数（可选，默认使用配置）
            language: 搜索语言（默认中文）

        Returns:
            SearchResult 列表

        Raises:
            Exception: 搜索失败时抛出异常
        """
        if not query or not query.strip():
            logger.warning("搜索查询为空")
            return []

        max_results = max_results or self.max_results

        # 测试模式：返回模拟数据
        if self.test_mode:
            logger.info(f"[测试模式] 搜索查询: {query}")
            return self._generate_test_results(query, max_results)

        # 真实搜索
        if not self.api_key:
            logger.error("搜索 API Key 未配置")
            raise ValueError("搜索 API Key 未配置，无法执行搜索")

        if not self.client:
            logger.error("HTTP 客户端未初始化")
            raise RuntimeError("HTTP 客户端未初始化，无法执行搜索")

        try:
            # 调用搜索 API（带重试）
            results = await self._execute_search_with_retry(
                query=query,
                max_results=max_results,
                language=language
            )

            logger.info(f"搜索成功: {query} -> {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            raise

    async def _execute_search_with_retry(
        self,
        query: str,
        max_results: int,
        language: str
    ) -> List[SearchResult]:
        """
        执行搜索（带重试机制）

        使用 tenacity 库实现重试：
        - 最多重试 3 次
        - 指数退避（1s, 2s, 4s）
        - 仅对网络错误重试
        """
        if retry is None:
            # 如果 tenacity 未安装，直接执行
            return await self._execute_search(query, max_results, language)

        # 定义重试装饰器
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError
            )),
            reraise=True
        )
        async def _search_with_retry():
            return await self._execute_search(query, max_results, language)

        return await _search_with_retry()

    async def _execute_search(
        self,
        query: str,
        max_results: int,
        language: str
    ) -> List[SearchResult]:
        """
        执行搜索 API 调用 (gpt-5-search-api via chat/completions)
        """
        # 构建请求体 (OpenAI chat/completions format)
        payload = self._build_search_payload(query, language)

        # 发送请求
        logger.debug(f"发送搜索请求: {self.search_api_url}")
        logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)}")

        response = await self.client.post(self.search_api_url, json=payload)

        # 检查响应状态
        if response.status_code != 200:
            error_msg = f"搜索 API 返回错误: {response.status_code}, {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)

        # 解析响应
        try:
            data = response.json()
            results = self._parse_gpt5_search_response(data)

            # 结果过滤和排序
            results = self._filter_and_sort_results(results, max_results)

            logger.info(f"搜索成功解析: {len(results)} 个结果")

            # 控制台打印搜索结果
            self._print_search_results(query, results)

            return results

        except json.JSONDecodeError as e:
            logger.error(f"搜索结果解析失败: {e}")
            raise
        except Exception as e:
            logger.error(f"搜索结果处理失败: {e}", exc_info=True)
            raise

    def _build_search_payload(
        self,
        query: str,
        language: str
    ) -> Dict[str, Any]:
        """
        构建搜索 API 请求体 (OpenAI chat/completions format)

        参数:
        - model: gpt-5-search-api
        - messages: 用户查询
        - max_tokens: 最大响应 tokens
        """
        # 构建搜索提示词
        search_prompt = f"搜索: {query}"
        if language and language != "zh-cn":
            search_prompt = f"Search: {query}"

        return {
            "model": self.search_model,
            "messages": [
                {
                    "role": "user",
                    "content": search_prompt
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.3  # 搜索任务使用较低温度
        }

    def _parse_gpt5_search_response(self, data: Dict[str, Any]) -> List[SearchResult]:
        """
        解析 gpt-5-search-api 响应

        OpenAI chat/completions 响应格式:
        {
            "id": "chatcmpl-...",
            "object": "chat.completion",
            "model": "gpt-5-search-api-2025-10-14",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "搜索结果内容...",
                    "annotations": [{
                        "type": "url_citation",
                        "url_citation": {
                            "url": "https://example.com",
                            "title": "标题",
                            "start_index": 0,
                            "end_index": 100
                        }
                    }]
                }
            }]
        }
        """
        results = []

        try:
            # 提取 choice
            choices = data.get("choices", [])
            if not choices:
                logger.warning("响应中没有 choices")
                return results

            first_choice = choices[0]
            message = first_choice.get("message", {})

            # 提取主要内容
            content = message.get("content", "")

            # 提取 URL annotations
            annotations = message.get("annotations", [])

            # 解析每个 annotation
            for idx, annotation in enumerate(annotations):
                try:
                    if annotation.get("type") == "url_citation":
                        url_citation = annotation.get("url_citation", {})

                        # 提取 URL 和标题
                        url = url_citation.get("url", "")
                        title = url_citation.get("title", "")
                        start_idx = url_citation.get("start_index", 0)
                        end_idx = url_citation.get("end_index", 0)

                        # 提取内容片段作为 snippet
                        snippet = content[start_idx:end_idx] if start_idx < end_idx else ""

                        if url:
                            result = SearchResult(
                                title=title or url,
                                url=url,
                                snippet=snippet[:200],  # 限制摘要长度
                                position=idx + 1,
                                score=1.0 - (idx * 0.05),  # 分数递减
                                source="gpt-5-search-api"
                            )
                            results.append(result)

                except Exception as e:
                    logger.warning(f"解析 annotation 失败: {e}, annotation={annotation}")
                    continue

            # 如果没有 annotations,尝试从内容中提取
            if not results:
                logger.warning("响应中没有 URL annotations,使用内容作为单一结果")
                if content:
                    results.append(SearchResult(
                        title="搜索结果",
                        url="",
                        snippet=content[:500],
                        position=1,
                        score=1.0,
                        source="gpt-5-search-api"
                    ))

        except Exception as e:
            logger.error(f"解析 GPT-5 搜索响应失败: {e}, data={data}")
            raise

        return results

    def _filter_and_sort_results(
        self,
        results: List[SearchResult],
        max_results: int
    ) -> List[SearchResult]:
        """
        过滤和排序搜索结果

        策略:
        1. 去重（相同 URL）
        2. 按相关性评分排序
        3. 限制结果数量
        """
        # 1. 去重
        seen_urls = set()
        unique_results = []

        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        # 2. 排序（按 score 降序，再按 position 升序）
        unique_results.sort(key=lambda r: (-r.score, r.position))

        # 3. 限制数量
        return unique_results[:max_results]

    def _print_search_results(self, query: str, results: List[SearchResult]) -> None:
        """
        在控制台打印搜索结果

        Args:
            query: 搜索查询
            results: 搜索结果列表
        """
        print("\n" + "=" * 80)
        print(f"🔍 搜索查询: {query}")
        print(f"📊 找到 {len(results)} 个结果 (最多显示5条)")
        print("=" * 80)

        for idx, result in enumerate(results[:5], 1):
            print(f"\n[{idx}] {result.title}")
            print(f"    🔗 URL: {result.url}")
            if result.snippet:
                # 限制摘要显示长度
                snippet = result.snippet[:150] + "..." if len(result.snippet) > 150 else result.snippet
                print(f"    📝 摘要: {snippet}")
            print(f"    ⭐ 评分: {result.score:.2f} | 来源: {result.source}")

        print("\n" + "=" * 80 + "\n")

    def _generate_test_results(
        self,
        query: str,
        max_results: int
    ) -> List[SearchResult]:
        """
        生成测试模式的模拟结果

        根据查询关键词生成相关的模拟数据
        """
        # 模拟数据模板
        templates = [
            {
                "title": f"{query} - 最新技术解析",
                "url": f"https://example.com/article/{query.replace(' ', '-')}-1",
                "snippet": f"本文深入分析了{query}的最新发展趋势和技术突破...",
            },
            {
                "title": f"深入理解{query}：原理与实践",
                "url": f"https://example.com/tutorial/{query.replace(' ', '-')}-2",
                "snippet": f"从基础到高级，全面讲解{query}的核心原理和实战应用...",
            },
            {
                "title": f"{query}完整指南 - 2024版",
                "url": f"https://example.com/guide/{query.replace(' ', '-')}-3",
                "snippet": f"2024年最全面的{query}指南，涵盖最新技术和最佳实践...",
            },
            {
                "title": f"{query}案例研究与分析",
                "url": f"https://example.com/case/{query.replace(' ', '-')}-4",
                "snippet": f"通过真实案例分析{query}在生产环境中的应用和效果...",
            },
            {
                "title": f"{query}技术博客 - 官方文档",
                "url": f"https://docs.example.com/{query.replace(' ', '-')}",
                "snippet": f"官方提供的{query}技术文档、API参考和最佳实践...",
            },
            {
                "title": f"{query}社区讨论精选",
                "url": f"https://forum.example.com/topic/{query.replace(' ', '-')}",
                "snippet": f"社区专家分享的{query}使用经验和问题解答...",
            },
            {
                "title": f"{query}性能优化指南",
                "url": f"https://example.com/performance/{query.replace(' ', '-')}",
                "snippet": f"优化{query}性能的实用技巧和工具推荐...",
            },
            {
                "title": f"{query}常见问题与解决方案",
                "url": f"https://example.com/faq/{query.replace(' ', '-')}",
                "snippet": f"汇总{query}使用过程中的常见问题和解决方案...",
            },
            {
                "title": f"{query}开源项目推荐",
                "url": f"https://github.com/awesome/{query.replace(' ', '-')}",
                "snippet": f"优质的{query}相关开源项目和工具库...",
            },
            {
                "title": f"{query}最新动态 - 行业资讯",
                "url": f"https://news.example.com/{query.replace(' ', '-')}",
                "snippet": f"关于{query}的最新行业动态和技术资讯...",
            }
        ]

        # 生成结果
        results = []
        for i, template in enumerate(templates[:max_results]):
            result = SearchResult(
                title=template["title"],
                url=template["url"],
                snippet=template["snippet"],
                position=i + 1,
                score=1.0 - (i * 0.05),  # 分数递减
                source="test"
            )
            results.append(result)

        return results

    async def batch_search(
        self,
        queries: List[str],
        max_results_per_query: Optional[int] = None
    ) -> Dict[str, List[SearchResult]]:
        """
        批量搜索

        Args:
            queries: 搜索查询列表
            max_results_per_query: 每个查询的最大结果数

        Returns:
            字典: {query: [SearchResult]}
        """
        if not queries:
            return {}

        max_results = max_results_per_query or self.max_results

        # 并发执行所有搜索
        tasks = [
            self.search(query, max_results)
            for query in queries
        ]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 组装结果
        batch_results = {}
        for query, results in zip(queries, results_list):
            if isinstance(results, Exception):
                logger.error(f"批量搜索失败: {query} -> {results}")
                batch_results[query] = []
            else:
                batch_results[query] = results

        return batch_results

    async def close(self):
        """关闭 HTTP 客户端"""
        if self.client:
            await self.client.aclose()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

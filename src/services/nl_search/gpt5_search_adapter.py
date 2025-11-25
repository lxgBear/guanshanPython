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
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
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
        timeout: Optional[int] = None
    ):
        """
        初始化搜索适配器

        Args:
            api_key: api.gpt.ge API Key（可选，默认使用配置）
            base_url: API Base URL（可选，默认使用配置）
            test_mode: 是否测试模式（返回模拟数据）
            timeout: 请求超时时间（秒，可选，默认使用配置）
        """
        self.api_key = api_key or nl_search_config.llm_api_key
        self.base_url = base_url or nl_search_config.llm_base_url
        self.test_mode = test_mode
        self.timeout = timeout or nl_search_config.query_timeout  # 使用配置的超时时间
        self.max_results = nl_search_config.max_search_results
        self.search_model = nl_search_config.search_model
        self.max_tokens = nl_search_config.search_max_tokens
        self.reasoning_enabled = nl_search_config.reasoning_enabled
        self.reasoning_effort = nl_search_config.reasoning_effort
        self.use_responses_api = nl_search_config.use_responses_api

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

        # API 端点 (根据配置选择)
        if self.use_responses_api:
            self.search_api_url = f"{self.base_url}/responses"
            self.api_type = "responses"
        else:
            self.search_api_url = f"{self.base_url}/chat/completions"
            self.api_type = "chat_completions"

        logger.info(
            f"GPT5SearchAdapter initialized: model={self.search_model}, "
            f"api_type={self.api_type}, url={self.search_api_url}, "
            f"test_mode={self.test_mode}, reasoning={self.reasoning_enabled} "
            f"(effort={self.reasoning_effort})"
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

            # 保存原始JSON响应（临时功能，用于调试）
            self._save_search_response_json(query, data)

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
        构建搜索 API 请求体

        支持两种API格式:
        1. Responses API (/v1/responses): 官方推荐，支持完整reasoning功能
           - 使用 'input' 参数
           - reasoning格式: {"effort": "low|medium|high"}

        2. Chat Completions API (/v1/chat/completions): 兼容模式
           - 使用 'messages' 参数
           - reasoning格式: "reasoning_effort": "low|medium|high"
        """
        # 构建搜索提示词
        # 检查模型类型，为Gemini添加特殊指令
        if "gemini" in self.search_model.lower():
            # Gemini模型：要求在回答中引用来源URL
            search_prompt = f"""请搜索以下问题，并在回答中明确标注每个信息的来源URL：

{query}

要求：
1. 提供详细的回答
2. 在每个关键信息后用 [来源: URL] 的格式标注来源链接
3. 至少提供3-5个不同来源的URL"""
        else:
            # gpt-5-search-api 模型：直接使用查询文本
            search_prompt = query

        if self.use_responses_api:
            # ✅ Responses API 格式 (官方推荐)
            payload = {
                "model": self.search_model,
                "input": search_prompt,
                "max_tokens": self.max_tokens,
            }

            # 添加 reasoning 参数（嵌套对象）
            if self.reasoning_enabled:
                payload["reasoning"] = {
                    "effort": self.reasoning_effort
                }
                logger.debug(f"[Responses API] Reasoning: effort={self.reasoning_effort}")

        else:
            # ⚠️ Chat Completions API 格式 (兼容模式)
            payload = {
                "model": self.search_model,
                "messages": [
                    {
                        "role": "user",
                        "content": search_prompt
                    }
                ],
                "max_tokens": self.max_tokens,
                "temperature": 0.3
            }

            # 添加 reasoning_effort 参数（顶层字符串）
            if self.reasoning_enabled:
                payload["reasoning_effort"] = self.reasoning_effort
                logger.debug(f"[Chat Completions API] Reasoning: effort={self.reasoning_effort}")

        return payload

    def _should_filter_url(self, url: str) -> bool:
        """
        检查 URL 是否应该被过滤

        Args:
            url: 待检查的 URL

        Returns:
            bool: True 表示应该过滤（跳过），False 表示保留
        """
        if not nl_search_config.filter_pdf_urls:
            # 过滤功能已禁用
            return False

        # 转换为小写进行比较
        url_lower = url.lower()

        # 移除查询参数（?之后的部分）和锚点（#之后的部分）
        # 例如: https://example.com/file.pdf?param=value → https://example.com/file.pdf
        url_path = url_lower.split('?')[0].split('#')[0]

        # 检查是否以排除的扩展名结尾
        for ext in nl_search_config.excluded_url_extensions:
            if url_path.endswith(ext.lower()):
                logger.debug(f"过滤 {ext} 文件: {url}")
                return True

        return False

    def _parse_gpt5_search_response(self, data: Dict[str, Any]) -> List[SearchResult]:
        """
        解析搜索 API 响应，支持多种格式

        支持的格式:
        1. sonar-deep-research 格式 (Perplexity):
           {
               "search_results": [
                   {"title": "...", "url": "...", "snippet": "...", "source": "web"}
               ],
               "citations": ["https://..."]
           }

        2. gpt-5-search-api 格式 (OpenAI):
           {
               "choices": [{
                   "message": {
                       "content": "...",
                       "annotations": [{
                           "type": "url_citation",
                           "url_citation": {"url": "...", "title": "..."}
                       }]
                   }
               }]
           }
        """
        results = []
        filtered_count = 0  # 统计过滤的 URL 数量

        try:
            # ✅ 检测 sonar-deep-research 格式 (优先级最高)
            if "search_results" in data and isinstance(data["search_results"], list):
                logger.info(f"检测到 sonar-deep-research 格式响应: {len(data['search_results'])} 条结果")

                for idx, item in enumerate(data["search_results"]):
                    try:
                        url = item.get("url", "")
                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        source = item.get("source", "sonar-deep-research")

                        # 跳过无效结果
                        if not url or not url.startswith("http"):
                            logger.debug(f"跳过无效URL: {url}")
                            continue

                        # ✅ 过滤 PDF 等文件 URL
                        if self._should_filter_url(url):
                            filtered_count += 1
                            continue

                        result = SearchResult(
                            title=title or url,
                            url=url,
                            snippet=snippet[:200],  # 限制摘要长度
                            position=idx + 1,
                            score=1.0 - (idx * 0.01),  # 分数递减（sonar结果更多，递减更缓）
                            source=source
                        )
                        results.append(result)

                    except Exception as e:
                        logger.warning(f"解析 sonar 搜索结果失败: {e}, item={item}")
                        continue

                # 记录过滤统计
                if filtered_count > 0:
                    logger.info(f"✅ 过滤文件URL: {filtered_count} 条 ({', '.join(nl_search_config.excluded_url_extensions)})")

                logger.info(f"✅ sonar 格式解析完成: {len(results)} 条有效结果")
                return results

            # ⚠️ 检测 gpt-5-search-api 格式 (fallback)
            choices = data.get("choices", [])
            if not choices:
                logger.warning("响应中没有 choices 或 search_results")
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

                        # ✅ 过滤 PDF 等文件 URL
                        if url and self._should_filter_url(url):
                            logger.debug(f"GPT-5格式: 过滤文件URL: {url}")
                            filtered_count += 1
                            continue

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
            logger.error(f"解析搜索响应失败: {e}, data={data}")
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

    def _save_search_response_json(
        self,
        query: str,
        response_data: Dict[str, Any]
    ) -> None:
        """
        保存GPT5搜索API返回的原始JSON（临时功能，用于确定搜索数据是否符合预期）

        Args:
            query: 搜索查询
            response_data: API返回的原始JSON数据
        """
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()[:8]
            filename = f"{timestamp}_{query_hash}.json"

            # 保存路径
            save_dir = Path(__file__).parent.parent.parent.parent / "data" / "gpt5_search_responses"
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / filename

            # 保存JSON
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "query": query,
                    "timestamp": timestamp,
                    "response": response_data
                }, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ GPT5搜索响应已保存: {save_path}")

        except Exception as e:
            # 保存失败不影响主流程
            logger.warning(f"保存GPT5搜索响应失败: {e}")

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

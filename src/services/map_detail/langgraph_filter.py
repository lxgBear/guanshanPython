"""
LangGraph URL 判断工作流

使用 LLM 判断 URL 是否为详情页
"""

import json
import logging
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UrlFilterState(TypedDict, total=False):
    """URL 过滤状态"""
    urls: List[str]                  # 输入的 URL 列表
    detail_pages: List[str]          # 判断为详情页的 URL
    navigation_pages: List[str]      # 判断为导航页的 URL
    batch_index: int                 # 当前批次索引
    total_batches: int               # 总批次数
    error: Optional[str]             # 错误信息
    execution_time_ms: int           # 执行时间


# LLM Prompt 模板
DETAIL_PAGE_FILTER_PROMPT = """你是一个URL分类专家。请判断以下URL哪些是"详情页"，哪些是"导航页/列表页"。

【重要】这是一次100%准确的过滤任务，请严格区分：

详情页特征（必须包含具体内容的页面）：
- 包含文章ID、数字ID、日期格式(YYYY-MM-DD或YYYY/MM/DD)
- URL包含长slug（多个短横线分隔的描述性文本）
- 例如: /news/2024/01/article-title, /post/12345, /p/abc123, /articles/xyz, /blog/my-first-post
- 包含视频ID、产品ID等具体标识符

导航页/列表页特征（必须过滤）：
- 纯分类页：/news/, /blog/, /products/, /category/xxx, /tag/yyy
- 首页：/, /home, /index
- 分页：包含 ?page=, /page/2, /p/2 等分页参数
- 作者页：/author/xxx, /user/yyy
- 归档页：/archive/, /2024/, /2024/01/
- 搜索页：/search?q=xxx

请分析以下URL列表，返回JSON格式：
{{
    "detail_pages": ["url1", "url2", ...],
    "navigation_pages": ["url3", "url4", ...]
}}

URL列表：
{urls}
"""


class LLMClient:
    """LLM 客户端封装

    支持多种 LLM Provider：
    - openai: OpenAI GPT
    - claude: Anthropic Claude
    - custom_claude: 自定义 Claude API (第三方代理) - 使用 httpx 调用
    """

    def __init__(self):
        """初始化 LLM 客户端"""
        self.provider = settings.LLM_PROVIDER
        self._client = None
        self._model = None

        # 根据 provider 选择模型
        if self.provider == "openai":
            self._model = settings.OPENAI_MODEL or "gpt-4o-mini"
        elif self.provider == "claude" or self.provider == "custom_claude":
            self._model = settings.CLAUDE_MODEL or "claude-sonnet-4-20250514"

        logger.info(f"[LLMClient] 使用 provider={self.provider}, model={self._model}")

    def _get_client(self):
        """获取 LLM 客户端实例"""
        if self._client is not None:
            return self._client

        if self.provider == "openai":
            from openai import AsyncOpenAI
            # 支持自定义 base_url (用于第三方 OpenAI 兼容 API)
            client_kwargs = {"api_key": settings.OPENAI_API_KEY}
            if settings.OPENAI_BASE_URL:
                client_kwargs["base_url"] = settings.OPENAI_BASE_URL
            self._client = AsyncOpenAI(**client_kwargs)
        elif self.provider == "claude":
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)
        elif self.provider == "custom_claude":
            # custom_claude 使用 httpx 直接调用，不需要 SDK client
            # 返回 None，classify_urls 中会特殊处理
            self._client = None
        else:
            raise ValueError(f"不支持的 LLM provider: {self.provider}")

        return self._client

    async def _call_custom_claude(self, prompt: str) -> str:
        """使用 httpx 调用自定义 Claude API (第三方代理)
        
        与 src/infrastructure/llm/claude_client.py 的 ClaudeClient._call 方法保持一致
        """
        import httpx
        import os
        
        base_url = settings.ANTHROPIC_BASE_URL or os.getenv("ANTHROPIC_BASE_URL", "http://23.106.129.19:2828/api")
        api_key = settings.CLAUDE_API_KEY or os.getenv("ANTHROPIC_AUTH_TOKEN", "")
        
        if not api_key:
            raise ValueError("Claude API Key 未配置 (需要设置 CLAUDE_API_KEY 或 ANTHROPIC_AUTH_TOKEN)")
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        
        body = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        base_url = base_url.rstrip('/')
        
        logger.info(f"[LLMClient] 调用 custom_claude API: {base_url}/v1/messages")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/v1/messages",
                headers=headers,
                json=body
            )
            response.raise_for_status()
            data = response.json()
            
            if "content" in data and len(data["content"]) > 0:
                return data["content"][0].get("text", "")
            return ""

    async def classify_urls(self, urls: List[str]) -> Dict[str, List[str]]:
        """使用 LLM 分类 URL

        Args:
            urls: 待分类的 URL 列表

        Returns:
            {
                "detail_pages": [...],
                "navigation_pages": [...]
            }
        """
        if not urls:
            logger.info(f"[LLMClient] 输入 URL 列表为空")
            return {"detail_pages": [], "navigation_pages": []}

        # 构建 prompt
        urls_text = "\n".join(f"- {url}" for url in urls)
        prompt = DETAIL_PAGE_FILTER_PROMPT.format(urls=urls_text)

        logger.info(f"[LLMClient] ========== LLM 分类开始 ==========")
        logger.info(f"[LLMClient] Provider: {self.provider}, Model: {self._model}")
        logger.info(f"[LLMClient] 待分类 URL 数量: {len(urls)}")

        try:
            if self.provider == "custom_claude":
                # 使用 httpx 直接调用自定义 Claude API
                logger.info(f"[LLMClient] 使用 custom_claude 调用...")
                content = await self._call_custom_claude(prompt)
            elif self.provider == "openai":
                client = self._get_client()
                # OpenAI 调用
                logger.info(f"[LLMClient] 使用 OpenAI 调用: {self._model}")
                response = await client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": "你是一个URL分类专家，专门判断页面类型。请严格区分详情页和导航页。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,  # 降低温度以提高准确性
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                logger.debug(f"[LLMClient] OpenAI 响应 ID: {response.id}")
            else:
                # 标准 Claude 调用 (使用 Anthropic SDK)
                client = self._get_client()
                logger.info(f"[LLMClient] 使用 Anthropic Claude 调用: {self._model}")
                response = await client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    temperature=0.0,  # 降低温度以提高准确性
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                content = response.content[0].text
                logger.debug(f"[LLMClient] Claude 响应 ID: {response.id}")

            logger.info(f"[LLMClient] LLM 响应内容长度: {len(content)} 字符")
            logger.debug(f"[LLMClient] LLM 响应内容: {content[:500]}...")

            # 解析 JSON 结果
            # 处理可能的 markdown 代码块包装
            content_stripped = content.strip()
            if content_stripped.startswith("```json"):
                content_stripped = content_stripped[7:]
            if content_stripped.startswith("```"):
                content_stripped = content_stripped[3:]
            if content_stripped.endswith("```"):
                content_stripped = content_stripped[:-3]

            result = json.loads(content_stripped.strip())
            logger.debug(f"[LLMClient] 解析后的 JSON: {result}")

            # 验证结果格式
            detail_pages = result.get("detail_pages", [])
            navigation_pages = result.get("navigation_pages", [])

            # 确保 URL 在输入列表中（防御性检查）
            url_set = set(urls)
            detail_pages = [u for u in detail_pages if u in url_set]
            navigation_pages = [u for u in navigation_pages if u in url_set]

            # 检查是否有遗漏
            classified = set(detail_pages) | set(navigation_pages)
            unclassified = url_set - classified
            if unclassified:
                logger.warning(f"[LLMClient] LLM 未分类的 URL ({len(unclassified)}个): {list(unclassified)}")
                # 将未分类的 URL 保守地视为详情页
                detail_pages.extend(list(unclassified))

            logger.info(f"[LLMClient] ========== LLM 分类结果 ==========")
            logger.info(f"[LLMClient] 详情页: {len(detail_pages)} 个")
            for idx, url in enumerate(detail_pages, 1):
                logger.info(f"[LLMClient]   ✓ 详情页 [{idx}]: {url}")
            logger.info(f"[LLMClient] 导航页: {len(navigation_pages)} 个")
            for idx, url in enumerate(navigation_pages, 1):
                logger.info(f"[LLMClient]   ✗ 导航页 [{idx}]: {url}")
            logger.info(f"[LLMClient] 分类率: {len(classified)}/{len(urls)} = {len(classified)/len(urls)*100:.1f}%")

            return {
                "detail_pages": detail_pages,
                "navigation_pages": navigation_pages
            }

        except json.JSONDecodeError as e:
            logger.error(f"[LLMClient] JSON 解析失败: {e}", exc_info=True)
            logger.error(f"[LLMClient] 原始响应: {content}")
            # 失败时返回空结果，不过滤
            return {
                "detail_pages": urls,  # 保守策略：保留所有 URL
                "navigation_pages": []
            }
        except Exception as e:
            logger.error(f"[LLMClient] 分类失败: {e}", exc_info=True)
            # 失败时返回空结果，不过滤
            return {
                "detail_pages": urls,  # 保守策略：保留所有 URL
                "navigation_pages": []
            }


class LangGraphUrlFilter:
    """基于 LangGraph 的 URL 过滤器

    使用 LLM 判断 URL 是否为详情页
    """

    def __init__(self, batch_size: int = 50):
        """初始化过滤器

        Args:
            batch_size: 每批处理的 URL 数量
        """
        self.batch_size = batch_size
        self.llm_client = LLMClient()
        self.logger = get_logger(__name__)

    async def filter(self, urls: List[str]) -> tuple[List[str], List[str], Dict[str, Any]]:
        """过滤 URL 列表

        Args:
            urls: 待过滤的 URL 列表

        Returns:
            (详情页 URL 列表, 导航页 URL 列表, 统计信息)
        """
        start_time = datetime.utcnow()
        self.logger.info(f"[LangGraphUrlFilter] 开始过滤 {len(urls)} 个 URL")

        all_detail_pages: List[str] = []
        all_navigation_pages: List[str] = []

        # 分批处理
        total_batches = (len(urls) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(urls), self.batch_size):
            batch = urls[i:i + self.batch_size]
            batch_index = i // self.batch_size + 1

            self.logger.info(
                f"[LangGraphUrlFilter] 处理批次 {batch_index}/{total_batches}, "
                f"URL 数量: {len(batch)}"
            )

            try:
                result = await self.llm_client.classify_urls(batch)

                detail_pages = result.get("detail_pages", [])
                navigation_pages = result.get("navigation_pages", [])

                # 详细记录每个 URL 的分类结果
                for url in detail_pages:
                    self.logger.info(f"[LangGraphUrlFilter] ✓ {url} -> 详情页")
                for url in navigation_pages:
                    self.logger.info(f"[LangGraphUrlFilter] ✗ {url} -> 导航页")

                all_detail_pages.extend(detail_pages)
                all_navigation_pages.extend(navigation_pages)

                self.logger.info(
                    f"[LangGraphUrlFilter] 批次 {batch_index} 完成: "
                    f"详情页 {len(detail_pages)}, 导航页 {len(navigation_pages)}"
                )

            except Exception as e:
                self.logger.error(
                    f"[LangGraphUrlFilter] 批次 {batch_index} 失败: {e}"
                )
                # 批次失败时保留所有 URL
                for url in batch:
                    self.logger.warning(f"[LangGraphUrlFilter] {url} -> LLM失败，默认保留为详情页")
                all_detail_pages.extend(batch)

        # 计算执行时间
        end_time = datetime.utcnow()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # 统计信息
        stats = {
            "total_urls": len(urls),
            "detail_pages": len(all_detail_pages),
            "navigation_pages": len(all_navigation_pages),
            "detail_rate": len(all_detail_pages) / len(urls) * 100 if urls else 0,
            "execution_time_ms": execution_time_ms,
        }

        self.logger.info(
            f"[LangGraphUrlFilter] 过滤完成: 详情页 {len(all_detail_pages)}, "
            f"导航页 {len(all_navigation_pages)}, 耗时 {execution_time_ms}ms"
        )

        return all_detail_pages, all_navigation_pages, stats

    def reset(self):
        """重置过滤器状态"""
        pass  # 无状态过滤器


# 便捷函数
async def filter_urls_with_llm(
    urls: List[str],
    batch_size: int = 50
) -> tuple[List[str], List[str], Dict[str, Any]]:
    """使用 LLM 过滤 URL 的便捷函数

    Args:
        urls: 待过滤的 URL 列表
        batch_size: 每批处理的 URL 数量

    Returns:
        (详情页 URL 列表, 导航页 URL 列表, 统计信息)
    """
    filter_instance = LangGraphUrlFilter(batch_size=batch_size)
    return await filter_instance.filter(urls)

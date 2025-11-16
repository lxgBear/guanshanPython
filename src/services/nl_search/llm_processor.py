"""
LLM 处理器
用于自然语言查询的解析和精炼
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

try:
    from openai import AsyncOpenAI
    from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError
except ImportError:
    # 如果 openai 包未安装，定义占位符
    AsyncOpenAI = None
    APIError = Exception
    APIConnectionError = Exception
    RateLimitError = Exception
    APITimeoutError = Exception

from src.services.nl_search.config import nl_search_config
from src.services.nl_search.prompts import (
    get_query_parse_prompt,
    get_query_refine_prompt,
    get_query_parse_fallback_prompt
)


logger = logging.getLogger(__name__)


class LLMProcessor:
    """LLM 处理器，负责查询解析和精炼"""

    def __init__(self, config=None):
        """
        初始化 LLM 处理器

        Args:
            config: NLSearchConfig 配置对象（可选，默认使用全局配置）
        """
        self.config = config or nl_search_config

        # 验证配置
        if not self.config.llm_api_key:
            logger.warning("LLM API Key 未配置，LLM 功能将不可用")
            self.client = None
        else:
            if AsyncOpenAI is None:
                logger.error("openai 包未安装，请运行: pip install openai")
                self.client = None
            else:
                self.client = AsyncOpenAI(api_key=self.config.llm_api_key)

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1  # 秒

    async def parse_query(self, query_text: str) -> Optional[Dict[str, Any]]:
        """
        解析自然语言查询

        使用 LLM 分析用户查询，提取意图、关键词、实体等信息。

        Args:
            query_text: 用户原始查询

        Returns:
            解析结果字典，包含以下字段：
            - intent: 查询意图类型
            - keywords: 关键词列表
            - entities: 实体列表
            - time_range: 时间范围信息
            - category: 内容分类
            - confidence: 分析置信度

            如果解析失败，返回 None
        """
        if not self.client:
            logger.error("LLM 客户端未初始化，无法执行查询解析")
            return None

        if not query_text or not query_text.strip():
            logger.warning("查询文本为空，无法解析")
            return None

        # 构建 Prompt
        prompt = get_query_parse_prompt(query_text.strip())

        try:
            # 调用 LLM API
            response_text = await self._call_llm_with_retry(prompt)

            if not response_text:
                logger.error("LLM 返回空响应")
                return None

            # 解析 JSON 响应
            analysis = self._parse_json_response(response_text)

            if not analysis:
                # 使用 fallback prompt 重试一次
                logger.warning("首次解析失败，使用 fallback prompt 重试")
                fallback_prompt = get_query_parse_fallback_prompt(query_text.strip())
                response_text = await self._call_llm_with_retry(fallback_prompt)
                analysis = self._parse_json_response(response_text)

            if not analysis:
                logger.error(f"查询解析失败，无法获取有效的 JSON 响应: {response_text}")
                return None

            # 验证必需字段
            if not self._validate_analysis(analysis):
                logger.error(f"查询解析结果缺少必需字段: {analysis}")
                return None

            logger.info(f"查询解析成功: {query_text} -> intent={analysis.get('intent')}")
            return analysis

        except Exception as e:
            logger.error(f"查询解析异常: {e}", exc_info=True)
            return None

    async def refine_query(
        self,
        query_text: str,
        llm_analysis: Dict[str, Any]
    ) -> Optional[str]:
        """
        精炼查询为搜索关键词

        将自然语言查询转换为更精准的搜索查询。

        Args:
            query_text: 用户原始查询
            llm_analysis: 查询解析结果

        Returns:
            精炼后的搜索查询字符串

            如果精炼失败，返回原始查询
        """
        if not self.client:
            logger.warning("LLM 客户端未初始化，返回原始查询")
            return query_text

        if not query_text or not query_text.strip():
            logger.warning("查询文本为空，无法精炼")
            return query_text

        # 构建 Prompt
        prompt = get_query_refine_prompt(query_text.strip(), llm_analysis)

        try:
            # 调用 LLM API
            refined_query = await self._call_llm_with_retry(prompt)

            if not refined_query or not refined_query.strip():
                logger.warning("LLM 返回空的精炼查询，使用原始查询")
                return query_text

            # 清理响应（去除可能的 Markdown 代码块标记）
            refined_query = refined_query.strip()
            if refined_query.startswith("```") and refined_query.endswith("```"):
                refined_query = refined_query[3:-3].strip()

            # 长度检查
            if len(refined_query) > 100:
                logger.warning(f"精炼查询过长 ({len(refined_query)} 字符)，截断到 100 字符")
                refined_query = refined_query[:100]

            logger.info(f"查询精炼成功: '{query_text}' -> '{refined_query}'")
            return refined_query

        except Exception as e:
            logger.error(f"查询精炼异常: {e}", exc_info=True)
            return query_text  # 失败时返回原始查询

    async def _call_llm_with_retry(self, prompt: str) -> Optional[str]:
        """
        调用 LLM API（带重试机制）

        Args:
            prompt: 完整的 Prompt 字符串

        Returns:
            LLM 响应文本

        Raises:
            Exception: 重试次数耗尽后抛出异常
        """
        import asyncio

        for attempt in range(self.max_retries):
            try:
                # 调用 OpenAI API
                response = await self.client.chat.completions.create(
                    model=self.config.llm_model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的查询分析助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.llm_temperature,
                    max_tokens=self.config.llm_max_tokens,
                    timeout=30.0  # 30 秒超时
                )

                # 提取响应文本
                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    if content:
                        return content.strip()

                logger.warning(f"LLM API 返回空响应 (尝试 {attempt + 1}/{self.max_retries})")

            except RateLimitError as e:
                logger.warning(f"LLM API 限流 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

            except APITimeoutError as e:
                logger.warning(f"LLM API 超时 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise

            except (APIError, APIConnectionError) as e:
                logger.error(f"LLM API 错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise

            except Exception as e:
                logger.error(f"LLM 调用未知错误: {e}", exc_info=True)
                raise

        return None

    def _parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        解析 JSON 响应

        处理常见的 LLM 响应格式问题（如 Markdown 代码块）

        Args:
            response_text: LLM 响应文本

        Returns:
            解析后的 JSON 对象，如果解析失败返回 None
        """
        if not response_text:
            return None

        # 清理响应文本
        text = response_text.strip()

        # 处理 Markdown 代码块
        if text.startswith("```json"):
            text = text[7:]  # 去除 ```json
        elif text.startswith("```"):
            text = text[3:]   # 去除 ```

        if text.endswith("```"):
            text = text[:-3]  # 去除尾部 ```

        text = text.strip()

        try:
            # 尝试解析 JSON
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}, 响应文本: {text[:200]}")
            return None

    def _validate_analysis(self, analysis: Dict[str, Any]) -> bool:
        """
        验证解析结果是否包含必需字段

        Args:
            analysis: 解析结果字典

        Returns:
            True 表示验证通过，False 表示缺少必需字段
        """
        required_fields = ["intent", "keywords", "entities", "category", "confidence"]

        for field in required_fields:
            if field not in analysis:
                logger.warning(f"解析结果缺少字段: {field}")
                return False

        # 验证 keywords 是列表
        if not isinstance(analysis.get("keywords"), list):
            logger.warning(f"keywords 字段类型错误: {type(analysis.get('keywords'))}")
            return False

        # 验证 entities 是列表
        if not isinstance(analysis.get("entities"), list):
            logger.warning(f"entities 字段类型错误: {type(analysis.get('entities'))}")
            return False

        # 验证 confidence 范围
        confidence = analysis.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            logger.warning(f"confidence 值无效: {confidence}")
            return False

        return True

    def get_default_analysis(self, query_text: str) -> Dict[str, Any]:
        """
        获取默认的解析结果（当 LLM 不可用时）

        Args:
            query_text: 用户原始查询

        Returns:
            默认的解析结果字典
        """
        # 简单的关键词提取（基于空格和标点分词）
        import re
        words = re.findall(r'[\w]+', query_text)
        keywords = [w for w in words if len(w) > 1][:5]

        return {
            "intent": "general_info",
            "keywords": keywords,
            "entities": [],
            "time_range": {
                "type": "none",
                "from": None,
                "to": None
            },
            "category": "other",
            "confidence": 0.5  # 低置信度
        }

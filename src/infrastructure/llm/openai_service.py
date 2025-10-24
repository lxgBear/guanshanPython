"""OpenAI LLM服务实现

智能搜索系统的LLM集成服务，负责：
- 封装OpenAI API调用
- 实现查询分解的Prompt Engineering
- 处理响应验证和错误重试
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.domain.entities.query_decomposition import QueryDecomposition, DecomposedQuery
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMException(Exception):
    """LLM调用异常"""

    def __init__(self, message: str, model: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.model = model
        self.status_code = status_code


# Prompt模板定义
QUERY_DECOMPOSITION_SYSTEM_PROMPT = """
你是一个专业的搜索查询优化专家。你的任务是将用户的复杂查询分解为多个有针对性的子查询，以便通过搜索引擎获得更全面的结果。

分解原则：
1. 覆盖性：子查询应覆盖原始查询的所有关键方面
2. 独立性：每个子查询应该是独立的、可以单独搜索的
3. 针对性：每个子查询应该针对一个具体的信息需求
4. 简洁性：避免过度分解，通常2-5个子查询为宜
5. 可搜索性：子查询应该是搜索引擎友好的

输出格式（严格遵循JSON格式）：
{
  "decomposed_queries": [
    {
      "query": "子查询文本",
      "reasoning": "为什么需要这个子查询的解释",
      "focus": "关注的信息维度"
    }
  ],
  "overall_strategy": "整体分解策略说明"
}
"""

QUERY_DECOMPOSITION_USER_TEMPLATE = """
原始查询："{query}"

搜索上下文：
- 目标网站：{target_domains}
- 语言偏好：{language}
- 时间范围：{time_range}

请分解这个查询，返回有效的JSON格式结果。
"""


class LLMService:
    """
    LLM集成服务

    封装OpenAI API调用，提供查询分解等AI功能
    """

    def __init__(self):
        """初始化LLM服务"""
        self.api_key: str = os.getenv("OPENAI_API_KEY", "sk-lu0j5woxKtl1LXWmD511FcD1293c4bC7Ba26A0A654Bf355f")
        self.base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.gpt.ge/v1")
        self.model: str = os.getenv("OPENAI_MODEL", "gpt-4")
        self.timeout: int = int(os.getenv("OPENAI_TIMEOUT", "30"))
        self.max_retries: int = int(os.getenv("OPENAI_MAX_RETRIES", "3"))

        logger.info(
            f"LLMService初始化: model={self.model}, base_url={self.base_url}, timeout={self.timeout}s"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError))
    )
    async def decompose_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> QueryDecomposition:
        """
        分解复杂查询为多个子查询

        Args:
            query: 用户原始查询
            context: 搜索上下文（目标网站、语言、时间范围等）

        Returns:
            QueryDecomposition: 分解结果

        Raises:
            LLMException: LLM调用失败
        """
        try:
            logger.info(f"开始分解查询: {query}")

            # 构建上下文信息
            if context is None:
                context = {}

            target_domains = context.get("target_domains", "无限制")
            language = context.get("language", "中文或英文")
            time_range = context.get("time_range", "不限")

            # 构建用户消息
            user_message = QUERY_DECOMPOSITION_USER_TEMPLATE.format(
                query=query,
                target_domains=target_domains,
                language=language,
                time_range=time_range
            )

            # 构建消息列表
            messages = [
                {"role": "system", "content": QUERY_DECOMPOSITION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]

            # 调用GPT
            response = await self.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )

            # 解析响应
            decomposition_result = self._parse_decomposition_response(response)

            logger.info(
                f"查询分解完成: 生成 {len(decomposition_result.decomposed_queries)} 个子查询, "
                f"消耗 {decomposition_result.tokens_used} tokens"
            )

            return decomposition_result

        except Exception as e:
            error_msg = f"查询分解失败: {str(e)}"
            logger.error(error_msg)
            raise LLMException(error_msg, model=self.model)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        通用的GPT聊天完成调用

        Args:
            messages: 消息列表
            temperature: 温度参数（0-1）
            max_tokens: 最大token数

        Returns:
            API响应字典

        Raises:
            LLMException: API调用失败
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )

                # 检查HTTP状态码
                if response.status_code != 200:
                    error_msg = f"OpenAI API返回错误状态码: {response.status_code}, 响应: {response.text}"
                    logger.error(error_msg)
                    raise LLMException(error_msg, model=self.model, status_code=response.status_code)

                # 解析JSON响应
                result = response.json()

                # 检查是否有错误
                if "error" in result:
                    error_msg = f"OpenAI API返回错误: {result['error']}"
                    logger.error(error_msg)
                    raise LLMException(error_msg, model=self.model)

                return result

        except httpx.TimeoutException:
            error_msg = f"OpenAI API调用超时 (>{self.timeout}秒)"
            logger.error(error_msg)
            raise LLMException(error_msg, model=self.model)

        except httpx.HTTPError as e:
            error_msg = f"OpenAI API HTTP错误: {str(e)}"
            logger.error(error_msg)
            raise LLMException(error_msg, model=self.model)

        except Exception as e:
            error_msg = f"OpenAI API调用失败: {str(e)}"
            logger.error(error_msg)
            raise LLMException(error_msg, model=self.model)

    def _parse_decomposition_response(self, response: Dict[str, Any]) -> QueryDecomposition:
        """
        解析分解响应

        Args:
            response: OpenAI API响应

        Returns:
            QueryDecomposition: 分解结果

        Raises:
            LLMException: 解析失败
        """
        try:
            # 提取消息内容
            content = response["choices"][0]["message"]["content"]

            # 尝试解析JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取JSON块
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise LLMException(f"无法从响应中提取有效的JSON: {content}")

            # 验证必要字段
            if "decomposed_queries" not in data:
                raise LLMException(f"响应缺少decomposed_queries字段: {data}")

            if not isinstance(data["decomposed_queries"], list):
                raise LLMException(f"decomposed_queries必须是列表: {data}")

            if len(data["decomposed_queries"]) == 0:
                raise LLMException("分解结果为空，至少需要1个子查询")

            if len(data["decomposed_queries"]) > 10:
                logger.warning(f"子查询数量过多({len(data['decomposed_queries'])}个)，截取前10个")
                data["decomposed_queries"] = data["decomposed_queries"][:10]

            # 构建DecomposedQuery对象列表
            decomposed_queries = []
            for q in data["decomposed_queries"]:
                if not all(k in q for k in ["query", "reasoning", "focus"]):
                    logger.warning(f"子查询缺少必要字段，跳过: {q}")
                    continue

                decomposed_queries.append(DecomposedQuery(
                    query=q["query"],
                    reasoning=q["reasoning"],
                    focus=q["focus"]
                ))

            # 提取token使用量
            tokens_used = response.get("usage", {}).get("total_tokens", 0)

            # 构建QueryDecomposition对象
            return QueryDecomposition(
                decomposed_queries=decomposed_queries,
                overall_strategy=data.get("overall_strategy", ""),
                tokens_used=tokens_used,
                model=self.model
            )

        except KeyError as e:
            error_msg = f"响应格式错误，缺少字段: {str(e)}"
            logger.error(error_msg)
            raise LLMException(error_msg, model=self.model)

        except Exception as e:
            error_msg = f"解析分解响应失败: {str(e)}"
            logger.error(error_msg)
            raise LLMException(error_msg, model=self.model)

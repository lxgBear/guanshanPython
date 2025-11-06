"""Firecrawl 原始响应实体模型

⚠️ 临时表设计
用途：
1. 存储 Firecrawl API 的完整原始响应数据
2. 用于分析和提取新字段到现有数据模型
3. 用完后会删除此表

设计理念：
- 完整保存 API 响应 JSON
- 最小化字段设计
- 无复杂索引（临时用途）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from src.infrastructure.id_generator import generate_string_id


@dataclass
class FirecrawlRawResponse:
    """Firecrawl API 原始响应实体（临时）

    职责：
    1. 完整保存 Firecrawl API 返回的原始 JSON
    2. 关联到具体的搜索任务和执行
    3. 提供时间戳用于追踪和分析
    """
    # 主键
    id: str = field(default_factory=generate_string_id)

    # 关联信息
    task_id: str = ""                          # 关联的搜索任务ID
    search_execution_id: Optional[str] = None  # 搜索执行ID（如果有）
    result_url: str = ""                       # 结果URL（用于快速查找）

    # 原始数据
    raw_response: Dict[str, Any] = field(default_factory=dict)  # 完整的 Firecrawl API 响应

    # API 元信息
    api_endpoint: str = ""                     # 调用的 API 端点（search/scrape）
    api_version: str = "v1"                    # API 版本
    response_status_code: int = 200            # HTTP 状态码
    response_time_ms: int = 0                  # 响应时间（毫秒）

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于MongoDB存储）"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "search_execution_id": self.search_execution_id,
            "result_url": self.result_url,
            "raw_response": self.raw_response,
            "api_endpoint": self.api_endpoint,
            "api_version": self.api_version,
            "response_status_code": self.response_status_code,
            "response_time_ms": self.response_time_ms,
            "created_at": self.created_at
        }


def create_firecrawl_raw_response(
    task_id: str,
    result_url: str,
    raw_data: Dict[str, Any],
    api_endpoint: str = "search",
    search_execution_id: Optional[str] = None,
    response_time_ms: int = 0
) -> FirecrawlRawResponse:
    """创建 Firecrawl 原始响应实体

    Args:
        task_id: 搜索任务ID
        result_url: 结果URL
        raw_data: Firecrawl API 返回的原始数据
        api_endpoint: API 端点类型
        search_execution_id: 搜索执行ID（可选）
        response_time_ms: API 响应时间

    Returns:
        FirecrawlRawResponse 实例
    """
    return FirecrawlRawResponse(
        task_id=task_id,
        search_execution_id=search_execution_id,
        result_url=result_url,
        raw_response=raw_data,
        api_endpoint=api_endpoint,
        response_time_ms=response_time_ms
    )

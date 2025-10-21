"""即时搜索结果映射实体模型

v1.3.0 架构的核心组件：
- 实现搜索任务与结果的多对多关系
- 支持跨搜索结果可见性
- 记录每次发现事件的完整元数据

架构优势：
- 一个结果可以被多次搜索发现（多对多关系）
- 完整追溯：记录哪次搜索、什么时间、什么排名发现了该结果
- 高效查询：支持按搜索执行ID、结果ID、任务ID快速检索
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

# 导入雪花算法ID生成器
from src.infrastructure.id_generator import generate_string_id


@dataclass
class InstantSearchResultMapping:
    """
    即时搜索结果映射实体

    作用：
    - 记录"哪次搜索发现了哪个结果"的关系
    - 解决跨搜索结果共享问题
    - 提供完整的发现历史追溯

    示例场景：
    - A搜索找到结果R，创建映射：(search_execution_id_A, result_id_R)
    - B搜索也找到结果R（去重命中），创建映射：(search_execution_id_B, result_id_R)
    - 查询B的结果时，通过映射表JOIN返回R，实现跨搜索可见性
    """
    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 关联关系（核心字段）
    search_execution_id: str = ""  # 搜索执行ID（哪次搜索）
    result_id: str = ""  # 结果ID（找到了哪个结果）
    task_id: str = ""  # 任务ID（冗余字段，便于按任务查询）

    # 发现元数据
    found_at: datetime = field(default_factory=datetime.utcnow)  # 发现时间
    search_position: int = 0  # 在该次搜索中的排名（1表示第一个结果）
    relevance_score: float = 0.0  # 该次搜索的相关性分数

    # 统计标记
    is_first_discovery: bool = False  # 是否是首次发现该结果

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应和数据库存储）"""
        return {
            "id": self.id,
            "search_execution_id": self.search_execution_id,
            "result_id": self.result_id,
            "task_id": self.task_id,
            "found_at": self.found_at.isoformat() if self.found_at else None,
            "search_position": self.search_position,
            "relevance_score": self.relevance_score,
            "is_first_discovery": self.is_first_discovery,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def create_result_mapping(
    search_execution_id: str,
    result_id: str,
    task_id: str,
    search_position: int = 0,
    relevance_score: float = 0.0,
    is_first_discovery: bool = False
) -> InstantSearchResultMapping:
    """
    创建结果映射记录的工厂函数

    Args:
        search_execution_id: 搜索执行ID
        result_id: 结果ID
        task_id: 任务ID
        search_position: 搜索结果排名
        relevance_score: 相关性分数
        is_first_discovery: 是否首次发现

    Returns:
        InstantSearchResultMapping 实例
    """
    return InstantSearchResultMapping(
        search_execution_id=search_execution_id,
        result_id=result_id,
        task_id=task_id,
        search_position=search_position,
        relevance_score=relevance_score,
        is_first_discovery=is_first_discovery
    )

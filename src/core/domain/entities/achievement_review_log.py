"""审核日志实体模型

记录每一次审核操作，用于：
- 审核流程追溯
- 审核人员工作量统计
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any

from src.infrastructure.id_generator import generate_string_id


class ReviewAction(Enum):
    """审核操作类型"""
    SUBMIT = "submit"                          # 提交审核
    APPROVE = "approve"                        # 通过（流程结束）
    FORWARD = "forward"                        # 转交下一级
    RETURN_TO_AUTHOR = "return_to_author"      # 退回提交人
    RETURN_TO_PREVIOUS = "return_to_previous"  # 退回上一级
    VOID = "void"                              # 作废
    RESUBMIT = "resubmit"                      # 重新提交（退回后）


@dataclass
class AchievementReviewLog:
    """审核日志实体

    记录每一次审核操作的详细信息
    """
    # === 主键 ===
    id: str = field(default_factory=generate_string_id)

    # === 关联 ===
    achievement_id: str = ""          # 关联的 achievement_draft ID

    # === 操作信息 ===
    action: ReviewAction = ReviewAction.SUBMIT
    review_level: int = 0             # 审核层级（1, 2, 3...）

    # === 操作人 ===
    operator_id: str = ""             # 操作人ID
    operator_name: str = ""           # 操作人姓名

    # === 流转信息 ===
    from_user_id: str = ""            # 来自谁（上一个处理人）
    to_user_id: str = ""              # 转给谁（下一个处理人，可为空）
    to_user_name: str = ""            # 下一个处理人姓名

    # === 审核意见 ===
    comment: str = ""                 # 审核意见/备注

    # === 时间 ===
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 API 响应）"""
        return {
            "id": self.id,
            "achievement_id": self.achievement_id,
            "action": self.action.value,
            "review_level": self.review_level,
            "operator_id": self.operator_id,
            "operator_name": self.operator_name,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "to_user_name": self.to_user_name,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def review_log_to_mongo_doc(log: AchievementReviewLog) -> Dict[str, Any]:
    """将 AchievementReviewLog 转换为 MongoDB 文档"""
    return {
        "_id": log.id,
        "achievement_id": log.achievement_id,
        "action": log.action.value,
        "review_level": log.review_level,
        "operator_id": log.operator_id,
        "operator_name": log.operator_name,
        "from_user_id": log.from_user_id,
        "to_user_id": log.to_user_id,
        "to_user_name": log.to_user_name,
        "comment": log.comment,
        "created_at": log.created_at,
    }


def mongo_doc_to_review_log(doc: Dict[str, Any]) -> AchievementReviewLog:
    """将 MongoDB 文档转换为 AchievementReviewLog"""
    # Safe action parsing
    try:
        action = ReviewAction(doc.get("action", "submit"))
    except ValueError:
        action = ReviewAction.SUBMIT

    return AchievementReviewLog(
        id=str(doc.get("_id", "")),
        achievement_id=doc.get("achievement_id", ""),
        action=action,
        review_level=doc.get("review_level", 0),
        operator_id=doc.get("operator_id", ""),
        operator_name=doc.get("operator_name", ""),
        from_user_id=doc.get("from_user_id", ""),
        to_user_id=doc.get("to_user_id", ""),
        to_user_name=doc.get("to_user_name", ""),
        comment=doc.get("comment", ""),
        created_at=doc.get("created_at") or datetime.utcnow(),
    )

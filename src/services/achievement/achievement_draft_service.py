"""AchievementDraft 服务层

提供草稿的 CRUD 和审核流程控制
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from src.core.domain.entities.achievement_draft import (
    AchievementDraft,
    AchievementStatus,
)
from src.core.domain.entities.achievement_review_log import (
    AchievementReviewLog,
    ReviewAction,
)
from src.infrastructure.persistence.repositories.mongo.achievement_draft_repository import (
    achievement_draft_repository,
)
from src.infrastructure.persistence.repositories.mongo.achievement_review_log_repository import (
    achievement_review_log_repository,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AchievementDraftService:
    """AchievementDraft 服务"""

    def __init__(self):
        self.draft_repo = achievement_draft_repository
        self.log_repo = achievement_review_log_repository

    # ==================== CRUD ====================

    async def create(
        self,
        source_entry_ids: List[str],
        title: str,
        author_id: str,
        author_name: str,
        description: str = "",
        summary: str = "",
        combined_content: str = "",
        tags: Optional[List[str]] = None,
        primary_category: str = "",
        secondary_category: str = "",
        tertiary_category: str = "",
    ) -> AchievementDraft:
        """创建草稿"""
        draft = AchievementDraft(
            source_entry_ids=source_entry_ids,
            title=title,
            description=description,
            summary=summary,
            combined_content=combined_content,
            tags=tags or [],
            primary_category=primary_category,
            secondary_category=secondary_category,
            tertiary_category=tertiary_category,
            author_id=author_id,
            author_name=author_name,
            status=AchievementStatus.DRAFT,
        )

        result = await self.draft_repo.create(draft)
        logger.info(f"创建成果草稿成功: id={result.id}, title={title}, author={author_name}")
        return result

    async def get_by_id(self, draft_id: str) -> Optional[AchievementDraft]:
        """获取草稿"""
        return await self.draft_repo.get_by_id(draft_id)

    async def update(
        self,
        draft_id: str,
        user_id: str,
        **updates,
    ) -> AchievementDraft:
        """更新草稿（仅 DRAFT/RETURNED 状态可用）"""
        draft = await self.draft_repo.get_by_id(draft_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")

        if not draft.can_edit(user_id):
            raise ValueError("无权限编辑此草稿或当前状态不允许编辑")

        # 更新允许的字段
        allowed_fields = [
            "title", "description", "summary", "combined_content",
            "tags", "primary_category", "secondary_category", "tertiary_category",
            "source_entry_ids",
        ]

        for field in allowed_fields:
            if field in updates:
                setattr(draft, field, updates[field])

        # 更新 raw_data_count
        if "source_entry_ids" in updates:
            draft.update_raw_data_count()

        result = await self.draft_repo.update(draft)
        logger.info(f"更新成果草稿成功: id={draft_id}")
        return result

    async def delete(self, draft_id: str, user_id: str) -> bool:
        """删除草稿（仅 DRAFT 状态且是作者可删除）"""
        draft = await self.draft_repo.get_by_id(draft_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")

        if draft.author_id != user_id:
            raise ValueError("无权限删除此草稿")

        if draft.status != AchievementStatus.DRAFT:
            raise ValueError("只能删除草稿状态的记录")

        result = await self.draft_repo.delete(draft_id)
        if result:
            logger.info(f"删除成果草稿成功: id={draft_id}")
        return result

    # ==================== 查询 ====================

    async def list_by_author(
        self,
        author_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出作者的草稿"""
        status_enum = AchievementStatus(status) if status else None
        items, total = await self.draft_repo.list_by_author(author_id, status_enum, page, page_size)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_by_reviewer(
        self,
        reviewer_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出审核员的待审核草稿"""
        items, total = await self.draft_repo.list_by_reviewer(reviewer_id, page, page_size)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_all(
        self,
        status: Optional[str] = None,
        primary_category: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出所有草稿（管理员）"""
        status_enum = AchievementStatus(status) if status else None
        items, total = await self.draft_repo.list_all(status_enum, primary_category, keyword, page, page_size)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ==================== 审核流程 ====================

    async def submit_for_review(
        self,
        draft_id: str,
        user_id: str,
        reviewer_id: str,
        reviewer_name: str,
    ) -> AchievementDraft:
        """提交审核"""
        draft = await self.draft_repo.get_by_id(draft_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")

        if not draft.can_submit(user_id):
            raise ValueError("无权限提交或当前状态不允许提交")

        # 记录审核日志
        is_resubmit = draft.status == AchievementStatus.RETURNED

        draft.submit_for_review(reviewer_id, reviewer_name)
        await self.draft_repo.update(draft)

        # 创建审核日志
        log = AchievementReviewLog(
            achievement_id=draft_id,
            action=ReviewAction.RESUBMIT if is_resubmit else ReviewAction.SUBMIT,
            review_level=draft.current_review_level,
            operator_id=user_id,
            operator_name=draft.author_name,
            from_user_id=user_id,
            to_user_id=reviewer_id,
            to_user_name=reviewer_name,
            comment="",
        )
        await self.log_repo.create(log)

        logger.info(f"提交审核成功: id={draft_id}, reviewer={reviewer_name}, is_resubmit={is_resubmit}")
        return draft

    async def review(
        self,
        draft_id: str,
        reviewer_id: str,
        reviewer_name: str,
        action: str,
        comment: str = "",
        to_user_id: str = "",
        to_user_name: str = "",
    ) -> AchievementDraft:
        """执行审核操作"""
        draft = await self.draft_repo.get_by_id(draft_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")

        if not draft.can_review(reviewer_id):
            raise ValueError("无权限审核或当前状态不允许审核")

        action_enum = ReviewAction(action)
        current_level = draft.current_review_level

        # 执行操作
        if action_enum == ReviewAction.APPROVE:
            draft.approve()
            logger.info(f"审核通过: id={draft_id}, reviewer={reviewer_name}")

        elif action_enum == ReviewAction.FORWARD:
            if not to_user_id or not to_user_name:
                raise ValueError("转交操作必须指定下一级审核员")
            draft.forward(to_user_id, to_user_name)
            logger.info(f"转交审核: id={draft_id}, from={reviewer_name}, to={to_user_name}")

        elif action_enum == ReviewAction.RETURN_TO_AUTHOR:
            draft.return_to_author()
            logger.info(f"退回提交人: id={draft_id}, reviewer={reviewer_name}")

        elif action_enum == ReviewAction.RETURN_TO_PREVIOUS:
            if current_level <= 1:
                raise ValueError("当前是第一级审核，无法退回上一级")

            # 获取上一级审核员信息
            prev_info = await self.log_repo.get_previous_reviewer(draft_id, current_level)
            if not prev_info:
                raise ValueError("找不到上一级审核员信息")

            draft.return_to_previous(
                prev_info["reviewer_id"],
                prev_info["reviewer_name"],
                prev_info["level"],
            )
            to_user_id = prev_info["reviewer_id"]
            to_user_name = prev_info["reviewer_name"]
            logger.info(f"退回上一级: id={draft_id}, from={reviewer_name}, to={to_user_name}")

        elif action_enum == ReviewAction.VOID:
            draft.void()
            logger.info(f"作废: id={draft_id}, reviewer={reviewer_name}")

        else:
            raise ValueError(f"不支持的审核操作: {action}")

        await self.draft_repo.update(draft)

        # 创建审核日志
        log = AchievementReviewLog(
            achievement_id=draft_id,
            action=action_enum,
            review_level=current_level,
            operator_id=reviewer_id,
            operator_name=reviewer_name,
            from_user_id=reviewer_id,
            to_user_id=to_user_id,
            to_user_name=to_user_name,
            comment=comment,
        )
        await self.log_repo.create(log)

        return draft

    # ==================== 审核日志 ====================

    async def get_review_logs(self, draft_id: str) -> List[AchievementReviewLog]:
        """获取审核日志"""
        return await self.log_repo.get_by_achievement_id(draft_id)

    async def get_review_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """获取审核统计"""
        return await self.log_repo.get_review_stats(start_date, end_date)


# 单例
achievement_draft_service = AchievementDraftService()

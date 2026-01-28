"""审批流程MongoDB仓储 v2.8.0"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.review_flow import (
    ReviewFlow,
    ReviewFlowInDB,
    ReviewFlowStatus,
    ReviewFlowDetail,
    ReviewStep,
    ReviewAction,
    ReviewTargetType,
)
from src.infrastructure.id_generator import generate_string_id

logger = logging.getLogger(__name__)

COLLECTION_NAME = "review_flows"


class ReviewFlowRepository:
    """审批流程仓储"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[COLLECTION_NAME]

    async def create(
        self,
        target_id: str,
        target_type: ReviewTargetType,
        submitter_id: str,
        submitter_name: str,
        reviewer_id: str,
        reviewer_name: str,
        title: Optional[str] = None,
    ) -> ReviewFlow:
        """创建审批流程"""
        flow_id = generate_string_id()
        now = datetime.utcnow()

        # 创建第一个审批步骤
        first_step = ReviewStep(
            step=1,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            status=ReviewFlowStatus.PENDING,
            assigned_at=now,
        )

        flow_data = {
            "_id": flow_id,
            "target_id": target_id,
            "target_type": target_type.value,
            "title": title,
            "review_chain": [first_step.model_dump()],
            "current_step": 1,
            "status": ReviewFlowStatus.PENDING.value,
            "submitter_id": submitter_id,
            "submitter_name": submitter_name,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }

        await self.collection.insert_one(flow_data)
        logger.info(f"创建审批流程: flow_id={flow_id}, target_id={target_id}, reviewer={reviewer_name}")

        return self._doc_to_model(flow_data)

    async def get_by_id(self, flow_id: str) -> Optional[ReviewFlow]:
        """根据ID获取审批流程"""
        doc = await self.collection.find_one({"_id": flow_id})
        if doc:
            return self._doc_to_model(doc)
        return None

    async def get_by_target(self, target_id: str, target_type: ReviewTargetType) -> Optional[ReviewFlow]:
        """根据目标对象获取审批流程"""
        doc = await self.collection.find_one({
            "target_id": target_id,
            "target_type": target_type.value,
        })
        if doc:
            return self._doc_to_model(doc)
        return None

    async def get_pending_by_reviewer(
        self,
        reviewer_id: str,
        target_type: Optional[ReviewTargetType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReviewFlowDetail], int]:
        """获取某审核员的待审批列表"""
        query = {
            "status": ReviewFlowStatus.PENDING.value,
            "review_chain": {
                "$elemMatch": {
                    "reviewer_id": reviewer_id,
                    "status": ReviewFlowStatus.PENDING.value,
                }
            }
        }

        if target_type:
            query["target_type"] = target_type.value

        # 获取总数
        total = await self.collection.count_documents(query)

        # 分页查询
        skip = (page - 1) * page_size
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)

        items = []
        async for doc in cursor:
            flow = self._doc_to_detail_model(doc)
            items.append(flow)

        logger.info(f"查询待审批列表: reviewer_id={reviewer_id}, total={total}")
        return items, total

    async def get_history_by_reviewer(
        self,
        reviewer_id: str,
        target_type: Optional[ReviewTargetType] = None,
        status: Optional[ReviewFlowStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReviewFlowDetail], int]:
        """获取某审核员的审批历史"""
        query = {
            "review_chain": {
                "$elemMatch": {
                    "reviewer_id": reviewer_id,
                    "status": {"$ne": ReviewFlowStatus.PENDING.value},  # 已处理过的
                }
            }
        }

        if target_type:
            query["target_type"] = target_type.value

        if status:
            query["status"] = status.value

        # 获取总数
        total = await self.collection.count_documents(query)

        # 分页查询
        skip = (page - 1) * page_size
        cursor = self.collection.find(query).sort("updated_at", -1).skip(skip).limit(page_size)

        items = []
        async for doc in cursor:
            flow = self._doc_to_detail_model(doc)
            items.append(flow)

        logger.info(f"查询审批历史: reviewer_id={reviewer_id}, total={total}")
        return items, total

    async def get_by_submitter(
        self,
        submitter_id: str,
        target_type: Optional[ReviewTargetType] = None,
        status: Optional[ReviewFlowStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReviewFlowDetail], int]:
        """获取某提交人的审批流程列表"""
        query = {"submitter_id": submitter_id}

        if target_type:
            query["target_type"] = target_type.value

        if status:
            query["status"] = status.value

        # 获取总数
        total = await self.collection.count_documents(query)

        # 分页查询
        skip = (page - 1) * page_size
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)

        items = []
        async for doc in cursor:
            flow = self._doc_to_detail_model(doc)
            items.append(flow)

        return items, total

    async def approve(
        self,
        flow_id: str,
        reviewer_id: str,
        action: ReviewAction,
        comment: Optional[str] = None,
        next_reviewer_id: Optional[str] = None,
        next_reviewer_name: Optional[str] = None,
    ) -> Optional[ReviewFlow]:
        """审批通过"""
        now = datetime.utcnow()

        # 获取当前流程
        flow = await self.get_by_id(flow_id)
        if not flow:
            return None

        # 找到当前待审批的步骤
        current_step_idx = None
        for idx, step in enumerate(flow.review_chain):
            if step.reviewer_id == reviewer_id and step.status == ReviewFlowStatus.PENDING:
                current_step_idx = idx
                break

        if current_step_idx is None:
            logger.warning(f"未找到待审批步骤: flow_id={flow_id}, reviewer_id={reviewer_id}")
            return None

        # 更新当前步骤
        update_data = {
            f"review_chain.{current_step_idx}.status": ReviewFlowStatus.APPROVED.value,
            f"review_chain.{current_step_idx}.action": action.value,
            f"review_chain.{current_step_idx}.comment": comment,
            f"review_chain.{current_step_idx}.reviewed_at": now,
            "updated_at": now,
        }

        if action == ReviewAction.PASS_AND_END:
            # 通过并结束
            update_data["status"] = ReviewFlowStatus.APPROVED.value
            update_data["completed_at"] = now
        elif action == ReviewAction.PASS_AND_CONTINUE and next_reviewer_id:
            # 通过并继续，添加下一步骤
            new_step = ReviewStep(
                step=flow.current_step + 1,
                reviewer_id=next_reviewer_id,
                reviewer_name=next_reviewer_name or "",
                status=ReviewFlowStatus.PENDING,
                assigned_at=now,
            )
            update_data["current_step"] = flow.current_step + 1

            await self.collection.update_one(
                {"_id": flow_id},
                {
                    "$set": update_data,
                    "$push": {"review_chain": new_step.model_dump()},
                }
            )
            logger.info(f"审批通过并继续: flow_id={flow_id}, next_reviewer={next_reviewer_name}")
            return await self.get_by_id(flow_id)

        await self.collection.update_one({"_id": flow_id}, {"$set": update_data})
        logger.info(f"审批通过: flow_id={flow_id}, action={action.value}")
        return await self.get_by_id(flow_id)

    async def reject(
        self,
        flow_id: str,
        reviewer_id: str,
        comment: Optional[str] = None,
    ) -> Optional[ReviewFlow]:
        """审批拒绝"""
        now = datetime.utcnow()

        # 获取当前流程
        flow = await self.get_by_id(flow_id)
        if not flow:
            return None

        # 找到当前待审批的步骤
        current_step_idx = None
        for idx, step in enumerate(flow.review_chain):
            if step.reviewer_id == reviewer_id and step.status == ReviewFlowStatus.PENDING:
                current_step_idx = idx
                break

        if current_step_idx is None:
            logger.warning(f"未找到待审批步骤: flow_id={flow_id}, reviewer_id={reviewer_id}")
            return None

        # 更新
        update_data = {
            f"review_chain.{current_step_idx}.status": ReviewFlowStatus.REJECTED.value,
            f"review_chain.{current_step_idx}.action": ReviewAction.REJECT.value,
            f"review_chain.{current_step_idx}.comment": comment,
            f"review_chain.{current_step_idx}.reviewed_at": now,
            "status": ReviewFlowStatus.REJECTED.value,
            "completed_at": now,
            "updated_at": now,
        }

        await self.collection.update_one({"_id": flow_id}, {"$set": update_data})
        logger.info(f"审批拒绝: flow_id={flow_id}, comment={comment}")
        return await self.get_by_id(flow_id)

    async def delete(self, flow_id: str) -> bool:
        """删除审批流程"""
        result = await self.collection.delete_one({"_id": flow_id})
        return result.deleted_count > 0

    def _doc_to_model(self, doc: dict) -> ReviewFlow:
        """文档转模型"""
        # 转换 review_chain
        review_chain = []
        for step_data in doc.get("review_chain", []):
            step = ReviewStep(
                step=step_data["step"],
                reviewer_id=step_data["reviewer_id"],
                reviewer_name=step_data["reviewer_name"],
                status=ReviewFlowStatus(step_data["status"]),
                action=ReviewAction(step_data["action"]) if step_data.get("action") else None,
                comment=step_data.get("comment"),
                assigned_at=step_data["assigned_at"],
                reviewed_at=step_data.get("reviewed_at"),
            )
            review_chain.append(step)

        return ReviewFlow(
            id=str(doc["_id"]),
            target_id=doc["target_id"],
            target_type=ReviewTargetType(doc["target_type"]),
            title=doc.get("title"),
            review_chain=review_chain,
            current_step=doc["current_step"],
            status=ReviewFlowStatus(doc["status"]),
            submitter_id=doc["submitter_id"],
            submitter_name=doc["submitter_name"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
            completed_at=doc.get("completed_at"),
        )

    def _doc_to_detail_model(self, doc: dict) -> ReviewFlowDetail:
        """文档转详情模型"""
        flow = self._doc_to_model(doc)
        return ReviewFlowDetail(
            **flow.model_dump(),
            target_title=doc.get("target_title"),
            target_summary=doc.get("target_summary"),
        )


async def create_review_flow_indexes(db: AsyncIOMotorDatabase):
    """创建审批流程索引"""
    collection = db[COLLECTION_NAME]

    # 目标对象索引
    await collection.create_index([("target_id", 1), ("target_type", 1)])

    # 状态索引
    await collection.create_index([("status", 1)])

    # 提交人索引
    await collection.create_index([("submitter_id", 1), ("created_at", -1)])

    # 审核员查询索引（复合索引用于待审批查询）
    await collection.create_index([
        ("review_chain.reviewer_id", 1),
        ("review_chain.status", 1),
        ("status", 1),
    ])

    # 时间索引
    await collection.create_index([("created_at", -1)])
    await collection.create_index([("updated_at", -1)])

    logger.info("✅ 审批流程索引创建完成")

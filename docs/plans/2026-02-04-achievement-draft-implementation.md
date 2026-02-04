# Achievement Draft (整编成果) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现整编成果功能，支持从已发布成果创建草稿，并支持动态链式多级审核流程。

**Architecture:** 分层架构 - Entity → Repository → Service → API。先实现 `achievement_draft` 表和基础 CRUD，再实现 `achievement_review_log` 审核日志，最后实现审核流程控制。

**Tech Stack:** Python 3.11+, FastAPI, MongoDB (motor), Pydantic, dataclasses

---

## Task 1: 创建 AchievementDraft 实体

**Files:**
- Create: `src/core/domain/entities/achievement_draft.py`

**Step 1: 创建实体文件**

```python
"""成果草稿实体模型

支持动态链式多级审核流程：
- 提交人创建草稿 → 提交审核（选择审核员）
- 审核员可：通过、转交、退回提交人、退回上一级、作废
- 退回后重新提交，直接回到退回的审核员
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from src.infrastructure.id_generator import generate_string_id


class AchievementStatus(Enum):
    """成果草稿状态"""
    DRAFT = "draft"                    # 草稿（可编辑）
    PENDING_REVIEW = "pending_review"  # 待审核（提交人不可编辑）
    RETURNED = "returned"              # 已退回（提交人可编辑）
    APPROVED = "approved"              # 已通过（流程结束）
    VOIDED = "voided"                  # 已作废（流程终止，不可编辑）


@dataclass
class AchievementDraft:
    """成果草稿实体

    用于存储整编成果草稿，支持多级审核流程
    """
    # === 主键 ===
    id: str = field(default_factory=generate_string_id)

    # === 内容字段 ===
    title: str = ""
    description: str = ""
    summary: str = ""
    combined_content: str = ""        # 整编内容（HTML/JSON）

    # === 分类与标签 ===
    tags: List[str] = field(default_factory=list)
    primary_category: str = ""        # 大类
    secondary_category: str = ""      # 类别
    tertiary_category: str = ""       # 地域

    # === 来源引用 ===
    source_entry_ids: List[str] = field(default_factory=list)  # 关联的 published_entries IDs
    raw_data_count: int = 0           # 原始数据数量

    # === 提交人信息 ===
    author_id: str = ""               # 创建/提交人ID
    author_name: str = ""             # 创建/提交人姓名

    # === 状态管理 ===
    status: AchievementStatus = AchievementStatus.DRAFT

    # === 当前审核信息 ===
    current_reviewer_id: str = ""     # 当前审核员ID
    current_reviewer_name: str = ""   # 当前审核员姓名
    current_review_level: int = 0     # 当前审核层级（0=未提交, 1, 2, 3...）

    # === 退回时记录的审核员（用于重新提交时直接回到该审核员）===
    returned_by_reviewer_id: str = ""
    returned_by_reviewer_name: str = ""
    returned_at_level: int = 0

    # === 时间戳 ===
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None   # 提交审核时间
    completed_at: Optional[datetime] = None   # 流程完成时间（通过/作废）

    def __post_init__(self):
        """初始化后处理"""
        self.raw_data_count = len(self.source_entry_ids)

    def can_edit(self, user_id: str) -> bool:
        """检查用户是否可以编辑"""
        if self.author_id != user_id:
            return False
        return self.status in [AchievementStatus.DRAFT, AchievementStatus.RETURNED]

    def can_submit(self, user_id: str) -> bool:
        """检查用户是否可以提交审核"""
        if self.author_id != user_id:
            return False
        return self.status in [AchievementStatus.DRAFT, AchievementStatus.RETURNED]

    def can_review(self, user_id: str) -> bool:
        """检查用户是否可以审核"""
        if self.status != AchievementStatus.PENDING_REVIEW:
            return False
        return self.current_reviewer_id == user_id

    def submit_for_review(self, reviewer_id: str, reviewer_name: str) -> None:
        """提交审核"""
        if self.status == AchievementStatus.RETURNED:
            # 退回后重新提交，回到退回的审核员
            self.current_reviewer_id = self.returned_by_reviewer_id
            self.current_reviewer_name = self.returned_by_reviewer_name
            self.current_review_level = self.returned_at_level
        else:
            # 首次提交
            self.current_reviewer_id = reviewer_id
            self.current_reviewer_name = reviewer_name
            self.current_review_level = 1

        self.status = AchievementStatus.PENDING_REVIEW
        self.submitted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        # 清除退回记录
        self.returned_by_reviewer_id = ""
        self.returned_by_reviewer_name = ""
        self.returned_at_level = 0

    def approve(self) -> None:
        """通过审核"""
        self.status = AchievementStatus.APPROVED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def forward(self, next_reviewer_id: str, next_reviewer_name: str) -> None:
        """转交下一级"""
        self.current_reviewer_id = next_reviewer_id
        self.current_reviewer_name = next_reviewer_name
        self.current_review_level += 1
        self.updated_at = datetime.utcnow()

    def return_to_author(self) -> None:
        """退回提交人"""
        self.returned_by_reviewer_id = self.current_reviewer_id
        self.returned_by_reviewer_name = self.current_reviewer_name
        self.returned_at_level = self.current_review_level

        self.status = AchievementStatus.RETURNED
        self.current_reviewer_id = ""
        self.current_reviewer_name = ""
        self.updated_at = datetime.utcnow()

    def return_to_previous(self, prev_reviewer_id: str, prev_reviewer_name: str, prev_level: int) -> None:
        """退回上一级审核员"""
        self.current_reviewer_id = prev_reviewer_id
        self.current_reviewer_name = prev_reviewer_name
        self.current_review_level = prev_level
        self.updated_at = datetime.utcnow()

    def void(self) -> None:
        """作废"""
        self.status = AchievementStatus.VOIDED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 API 响应）"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "summary": self.summary,
            "combined_content": self.combined_content,
            "tags": self.tags,
            "primary_category": self.primary_category,
            "secondary_category": self.secondary_category,
            "tertiary_category": self.tertiary_category,
            "source_entry_ids": self.source_entry_ids,
            "raw_data_count": self.raw_data_count,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "status": self.status.value,
            "current_reviewer_id": self.current_reviewer_id,
            "current_reviewer_name": self.current_reviewer_name,
            "current_review_level": self.current_review_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def achievement_draft_to_mongo_doc(draft: AchievementDraft) -> Dict[str, Any]:
    """将 AchievementDraft 转换为 MongoDB 文档"""
    return {
        "_id": draft.id,
        "title": draft.title,
        "description": draft.description,
        "summary": draft.summary,
        "combined_content": draft.combined_content,
        "tags": draft.tags,
        "primary_category": draft.primary_category,
        "secondary_category": draft.secondary_category,
        "tertiary_category": draft.tertiary_category,
        "source_entry_ids": draft.source_entry_ids,
        "raw_data_count": draft.raw_data_count,
        "author_id": draft.author_id,
        "author_name": draft.author_name,
        "status": draft.status.value,
        "current_reviewer_id": draft.current_reviewer_id,
        "current_reviewer_name": draft.current_reviewer_name,
        "current_review_level": draft.current_review_level,
        "returned_by_reviewer_id": draft.returned_by_reviewer_id,
        "returned_by_reviewer_name": draft.returned_by_reviewer_name,
        "returned_at_level": draft.returned_at_level,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
        "submitted_at": draft.submitted_at,
        "completed_at": draft.completed_at,
    }


def mongo_doc_to_achievement_draft(doc: Dict[str, Any]) -> AchievementDraft:
    """将 MongoDB 文档转换为 AchievementDraft"""
    return AchievementDraft(
        id=str(doc.get("_id", "")),
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        summary=doc.get("summary", ""),
        combined_content=doc.get("combined_content", ""),
        tags=doc.get("tags", []),
        primary_category=doc.get("primary_category", ""),
        secondary_category=doc.get("secondary_category", ""),
        tertiary_category=doc.get("tertiary_category", ""),
        source_entry_ids=doc.get("source_entry_ids", []),
        raw_data_count=doc.get("raw_data_count", 0),
        author_id=doc.get("author_id", ""),
        author_name=doc.get("author_name", ""),
        status=AchievementStatus(doc.get("status", "draft")),
        current_reviewer_id=doc.get("current_reviewer_id", ""),
        current_reviewer_name=doc.get("current_reviewer_name", ""),
        current_review_level=doc.get("current_review_level", 0),
        returned_by_reviewer_id=doc.get("returned_by_reviewer_id", ""),
        returned_by_reviewer_name=doc.get("returned_by_reviewer_name", ""),
        returned_at_level=doc.get("returned_at_level", 0),
        created_at=doc.get("created_at") or datetime.utcnow(),
        updated_at=doc.get("updated_at") or datetime.utcnow(),
        submitted_at=doc.get("submitted_at"),
        completed_at=doc.get("completed_at"),
    )
```

**Step 2: 验证导入**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -c "from src.core.domain.entities.achievement_draft import AchievementDraft, AchievementStatus; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add src/core/domain/entities/achievement_draft.py
git commit -m "feat(entity): add AchievementDraft entity with multi-level review support"
```

---

## Task 2: 创建 AchievementReviewLog 实体

**Files:**
- Create: `src/core/domain/entities/achievement_review_log.py`

**Step 1: 创建实体文件**

```python
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
    return AchievementReviewLog(
        id=str(doc.get("_id", "")),
        achievement_id=doc.get("achievement_id", ""),
        action=ReviewAction(doc.get("action", "submit")),
        review_level=doc.get("review_level", 0),
        operator_id=doc.get("operator_id", ""),
        operator_name=doc.get("operator_name", ""),
        from_user_id=doc.get("from_user_id", ""),
        to_user_id=doc.get("to_user_id", ""),
        to_user_name=doc.get("to_user_name", ""),
        comment=doc.get("comment", ""),
        created_at=doc.get("created_at") or datetime.utcnow(),
    )
```

**Step 2: 验证导入**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -c "from src.core.domain.entities.achievement_review_log import AchievementReviewLog, ReviewAction; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add src/core/domain/entities/achievement_review_log.py
git commit -m "feat(entity): add AchievementReviewLog entity for audit trail"
```

---

## Task 3: 创建 AchievementDraft Repository

**Files:**
- Create: `src/infrastructure/persistence/repositories/mongo/achievement_draft_repository.py`

**Step 1: 创建仓储文件**

```python
"""AchievementDraft MongoDB 仓储实现"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.achievement_draft import (
    AchievementDraft,
    AchievementStatus,
    achievement_draft_to_mongo_doc,
    mongo_doc_to_achievement_draft,
)


class AchievementDraftRepository:
    """AchievementDraft MongoDB 仓储"""

    COLLECTION_NAME = "achievement_drafts"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.COLLECTION_NAME]

    async def create(self, draft: AchievementDraft) -> AchievementDraft:
        """创建草稿"""
        collection = await self._get_collection()
        doc = achievement_draft_to_mongo_doc(draft)
        await collection.insert_one(doc)
        return draft

    async def get_by_id(self, draft_id: str) -> Optional[AchievementDraft]:
        """根据ID获取草稿"""
        collection = await self._get_collection()
        doc = await collection.find_one({"_id": draft_id})
        if doc:
            return mongo_doc_to_achievement_draft(doc)
        return None

    async def update(self, draft: AchievementDraft) -> AchievementDraft:
        """更新草稿"""
        collection = await self._get_collection()
        draft.updated_at = datetime.utcnow()
        doc = achievement_draft_to_mongo_doc(draft)
        await collection.replace_one({"_id": draft.id}, doc)
        return draft

    async def delete(self, draft_id: str) -> bool:
        """删除草稿"""
        collection = await self._get_collection()
        result = await collection.delete_one({"_id": draft_id})
        return result.deleted_count > 0

    async def list_by_author(
        self,
        author_id: str,
        status: Optional[AchievementStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """根据作者ID列出草稿"""
        collection = await self._get_collection()

        query: Dict[str, Any] = {"author_id": author_id}
        if status:
            query["status"] = status.value

        total = await collection.count_documents(query)

        cursor = collection.find(query).sort("created_at", -1)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        items = []
        async for doc in cursor:
            items.append(mongo_doc_to_achievement_draft(doc))

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
        """根据当前审核员ID列出待审核草稿"""
        collection = await self._get_collection()

        query = {
            "current_reviewer_id": reviewer_id,
            "status": AchievementStatus.PENDING_REVIEW.value,
        }

        total = await collection.count_documents(query)

        cursor = collection.find(query).sort("submitted_at", -1)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        items = []
        async for doc in cursor:
            items.append(mongo_doc_to_achievement_draft(doc))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_all(
        self,
        status: Optional[AchievementStatus] = None,
        primary_category: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出所有草稿（管理员）"""
        collection = await self._get_collection()

        query: Dict[str, Any] = {}
        if status:
            query["status"] = status.value
        if primary_category:
            query["primary_category"] = primary_category
        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
            ]

        total = await collection.count_documents(query)

        cursor = collection.find(query).sort("created_at", -1)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        items = []
        async for doc in cursor:
            items.append(mongo_doc_to_achievement_draft(doc))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }


# 单例
achievement_draft_repository = AchievementDraftRepository()
```

**Step 2: 验证导入**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -c "from src.infrastructure.persistence.repositories.mongo.achievement_draft_repository import achievement_draft_repository; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add src/infrastructure/persistence/repositories/mongo/achievement_draft_repository.py
git commit -m "feat(repo): add AchievementDraft repository"
```

---

## Task 4: 创建 AchievementReviewLog Repository

**Files:**
- Create: `src/infrastructure/persistence/repositories/mongo/achievement_review_log_repository.py`

**Step 1: 创建仓储文件**

```python
"""AchievementReviewLog MongoDB 仓储实现"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.achievement_review_log import (
    AchievementReviewLog,
    ReviewAction,
    review_log_to_mongo_doc,
    mongo_doc_to_review_log,
)


class AchievementReviewLogRepository:
    """AchievementReviewLog MongoDB 仓储"""

    COLLECTION_NAME = "achievement_review_logs"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.COLLECTION_NAME]

    async def create(self, log: AchievementReviewLog) -> AchievementReviewLog:
        """创建审核日志"""
        collection = await self._get_collection()
        doc = review_log_to_mongo_doc(log)
        await collection.insert_one(doc)
        return log

    async def get_by_achievement_id(
        self,
        achievement_id: str,
    ) -> List[AchievementReviewLog]:
        """获取某个草稿的所有审核日志"""
        collection = await self._get_collection()

        cursor = collection.find({"achievement_id": achievement_id}).sort("created_at", 1)

        logs = []
        async for doc in cursor:
            logs.append(mongo_doc_to_review_log(doc))

        return logs

    async def get_latest_by_achievement_id(
        self,
        achievement_id: str,
    ) -> Optional[AchievementReviewLog]:
        """获取某个草稿的最新审核日志"""
        collection = await self._get_collection()

        doc = await collection.find_one(
            {"achievement_id": achievement_id},
            sort=[("created_at", -1)]
        )

        if doc:
            return mongo_doc_to_review_log(doc)
        return None

    async def get_previous_reviewer(
        self,
        achievement_id: str,
        current_level: int,
    ) -> Optional[Dict[str, Any]]:
        """获取上一级审核员信息（用于退回上一级）"""
        collection = await self._get_collection()

        # 查找上一级的审核记录（forward 或 submit 操作）
        doc = await collection.find_one(
            {
                "achievement_id": achievement_id,
                "review_level": current_level - 1,
                "action": {"$in": [ReviewAction.FORWARD.value, ReviewAction.SUBMIT.value]},
            },
            sort=[("created_at", -1)]
        )

        if doc:
            return {
                "reviewer_id": doc.get("operator_id", ""),
                "reviewer_name": doc.get("operator_name", ""),
                "level": current_level - 1,
            }
        return None

    async def count_by_operator(
        self,
        operator_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        actions: Optional[List[ReviewAction]] = None,
    ) -> int:
        """统计审核员的审核数量"""
        collection = await self._get_collection()

        query: Dict[str, Any] = {"operator_id": operator_id}

        if actions:
            query["action"] = {"$in": [a.value for a in actions]}
        else:
            # 默认统计所有审核操作（排除 submit 和 resubmit）
            query["action"] = {"$in": [
                ReviewAction.APPROVE.value,
                ReviewAction.FORWARD.value,
                ReviewAction.RETURN_TO_AUTHOR.value,
                ReviewAction.RETURN_TO_PREVIOUS.value,
                ReviewAction.VOID.value,
            ]}

        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lt"] = end_date

        return await collection.count_documents(query)

    async def get_review_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """获取审核统计（按审核员分组）"""
        collection = await self._get_collection()

        match_stage: Dict[str, Any] = {
            "action": {"$in": [
                ReviewAction.APPROVE.value,
                ReviewAction.FORWARD.value,
                ReviewAction.RETURN_TO_AUTHOR.value,
                ReviewAction.RETURN_TO_PREVIOUS.value,
                ReviewAction.VOID.value,
            ]}
        }

        if start_date or end_date:
            match_stage["created_at"] = {}
            if start_date:
                match_stage["created_at"]["$gte"] = start_date
            if end_date:
                match_stage["created_at"]["$lt"] = end_date

        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": {
                    "operator_id": "$operator_id",
                    "operator_name": "$operator_name",
                },
                "total": {"$sum": 1},
                "approved": {"$sum": {"$cond": [{"$eq": ["$action", "approve"]}, 1, 0]}},
                "forwarded": {"$sum": {"$cond": [{"$eq": ["$action", "forward"]}, 1, 0]}},
                "returned": {"$sum": {"$cond": [{"$in": ["$action", ["return_to_author", "return_to_previous"]]}, 1, 0]}},
                "voided": {"$sum": {"$cond": [{"$eq": ["$action", "void"]}, 1, 0]}},
            }},
            {"$sort": {"total": -1}},
        ]

        results = []
        async for doc in collection.aggregate(pipeline):
            results.append({
                "operator_id": doc["_id"]["operator_id"],
                "operator_name": doc["_id"]["operator_name"],
                "total": doc["total"],
                "approved": doc["approved"],
                "forwarded": doc["forwarded"],
                "returned": doc["returned"],
                "voided": doc["voided"],
            })

        return results


# 单例
achievement_review_log_repository = AchievementReviewLogRepository()
```

**Step 2: 验证导入**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -c "from src.infrastructure.persistence.repositories.mongo.achievement_review_log_repository import achievement_review_log_repository; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add src/infrastructure/persistence/repositories/mongo/achievement_review_log_repository.py
git commit -m "feat(repo): add AchievementReviewLog repository with stats support"
```

---

## Task 5: 创建 AchievementDraft Service

**Files:**
- Create: `src/services/achievement/__init__.py`
- Create: `src/services/achievement/achievement_draft_service.py`

**Step 1: 创建 __init__.py**

```python
"""Achievement 服务模块"""

from src.services.achievement.achievement_draft_service import achievement_draft_service

__all__ = ["achievement_draft_service"]
```

**Step 2: 创建服务文件**

```python
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

        return await self.draft_repo.create(draft)

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
            draft.raw_data_count = len(draft.source_entry_ids)

        return await self.draft_repo.update(draft)

    async def delete(self, draft_id: str, user_id: str) -> bool:
        """删除草稿（仅 DRAFT 状态且是作者可删除）"""
        draft = await self.draft_repo.get_by_id(draft_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")

        if draft.author_id != user_id:
            raise ValueError("无权限删除此草稿")

        if draft.status != AchievementStatus.DRAFT:
            raise ValueError("只能删除草稿状态的记录")

        return await self.draft_repo.delete(draft_id)

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
        return await self.draft_repo.list_by_author(author_id, status_enum, page, page_size)

    async def list_by_reviewer(
        self,
        reviewer_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出审核员的待审核草稿"""
        return await self.draft_repo.list_by_reviewer(reviewer_id, page, page_size)

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
        return await self.draft_repo.list_all(status_enum, primary_category, keyword, page, page_size)

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

        elif action_enum == ReviewAction.FORWARD:
            if not to_user_id or not to_user_name:
                raise ValueError("转交操作必须指定下一级审核员")
            draft.forward(to_user_id, to_user_name)

        elif action_enum == ReviewAction.RETURN_TO_AUTHOR:
            draft.return_to_author()

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

        elif action_enum == ReviewAction.VOID:
            draft.void()

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
```

**Step 3: 验证导入**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -c "from src.services.achievement import achievement_draft_service; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add src/services/achievement/
git commit -m "feat(service): add AchievementDraft service with review workflow"
```

---

## Task 6: 创建 API 端点

**Files:**
- Create: `src/api/v1/endpoints/achievement_drafts.py`
- Modify: `src/api/v1/router.py`

**Step 1: 创建 API 端点文件**

```python
"""
成果草稿 API

提供成果草稿的 CRUD 和审核流程 API
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from src.api.dependencies.auth import get_current_user, require_permissions
from src.services.achievement import achievement_draft_service


router = APIRouter(
    prefix="/achievement-drafts",
    # tags 由 router.py 统一管理
)


# ==================== 请求/响应模型 ====================

class CreateDraftRequest(BaseModel):
    """创建草稿请求"""
    source_entry_ids: List[str] = Field(..., description="关联的 published_entries IDs")
    title: str = Field(..., description="标题")
    description: str = Field("", description="描述")
    summary: str = Field("", description="摘要")
    combined_content: str = Field("", description="整编内容")
    tags: List[str] = Field(default_factory=list, description="标签")
    primary_category: str = Field("", description="大类")
    secondary_category: str = Field("", description="类别")
    tertiary_category: str = Field("", description="地域")


class UpdateDraftRequest(BaseModel):
    """更新草稿请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    combined_content: Optional[str] = None
    tags: Optional[List[str]] = None
    primary_category: Optional[str] = None
    secondary_category: Optional[str] = None
    tertiary_category: Optional[str] = None
    source_entry_ids: Optional[List[str]] = None


class SubmitReviewRequest(BaseModel):
    """提交审核请求"""
    reviewer_id: str = Field(..., description="审核员ID")
    reviewer_name: str = Field(..., description="审核员姓名")


class ReviewActionRequest(BaseModel):
    """审核操作请求"""
    action: str = Field(..., description="操作类型: approve|forward|return_to_author|return_to_previous|void")
    comment: str = Field("", description="审核意见")
    to_user_id: str = Field("", description="下一级审核员ID（转交时必填）")
    to_user_name: str = Field("", description="下一级审核员姓名（转交时必填）")


class DraftResponse(BaseModel):
    """草稿响应"""
    id: str
    title: str
    description: str
    summary: str
    combined_content: str
    tags: List[str]
    primary_category: str
    secondary_category: str
    tertiary_category: str
    source_entry_ids: List[str]
    raw_data_count: int
    author_id: str
    author_name: str
    status: str
    current_reviewer_id: str
    current_reviewer_name: str
    current_review_level: int
    created_at: Optional[str]
    updated_at: Optional[str]
    submitted_at: Optional[str]
    completed_at: Optional[str]


class ReviewLogResponse(BaseModel):
    """审核日志响应"""
    id: str
    achievement_id: str
    action: str
    review_level: int
    operator_id: str
    operator_name: str
    from_user_id: str
    to_user_id: str
    to_user_name: str
    comment: str
    created_at: Optional[str]


class ReviewStatsResponse(BaseModel):
    """审核统计响应"""
    operator_id: str
    operator_name: str
    total: int
    approved: int
    forwarded: int
    returned: int
    voided: int


# ==================== API 端点 ====================

@router.post(
    "/",
    response_model=DraftResponse,
    summary="创建草稿",
    description="从已选的 published_entries 创建成果草稿",
)
async def create_draft(
    request: CreateDraftRequest,
    current_user: dict = Depends(get_current_user),
):
    """创建草稿"""
    try:
        draft = await achievement_draft_service.create(
            source_entry_ids=request.source_entry_ids,
            title=request.title,
            author_id=current_user["id"],
            author_name=current_user["name"],
            description=request.description,
            summary=request.summary,
            combined_content=request.combined_content,
            tags=request.tags,
            primary_category=request.primary_category,
            secondary_category=request.secondary_category,
            tertiary_category=request.tertiary_category,
        )
        return DraftResponse(**draft.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/",
    summary="列出草稿",
    description="根据角色列出草稿",
)
async def list_drafts(
    status: Optional[str] = Query(None, description="状态筛选"),
    primary_category: Optional[str] = Query(None, description="大类筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """列出草稿"""
    try:
        # TODO: 根据用户角色决定查询范围
        # 暂时返回用户自己的草稿
        result = await achievement_draft_service.list_by_author(
            author_id=current_user["id"],
            status=status,
            page=page,
            page_size=page_size,
        )

        return {
            "items": [DraftResponse(**d.to_dict()) for d in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pending-review",
    summary="列出待审核草稿",
    description="列出当前用户需要审核的草稿",
)
async def list_pending_review(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """列出待审核草稿"""
    try:
        result = await achievement_draft_service.list_by_reviewer(
            reviewer_id=current_user["id"],
            page=page,
            page_size=page_size,
        )

        return {
            "items": [DraftResponse(**d.to_dict()) for d in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{draft_id}",
    response_model=DraftResponse,
    summary="获取草稿详情",
)
async def get_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取草稿详情"""
    draft = await achievement_draft_service.get_by_id(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return DraftResponse(**draft.to_dict())


@router.put(
    "/{draft_id}",
    response_model=DraftResponse,
    summary="更新草稿",
    description="更新草稿（仅 DRAFT/RETURNED 状态可用）",
)
async def update_draft(
    draft_id: str,
    request: UpdateDraftRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新草稿"""
    try:
        updates = request.dict(exclude_none=True)
        draft = await achievement_draft_service.update(
            draft_id=draft_id,
            user_id=current_user["id"],
            **updates,
        )
        return DraftResponse(**draft.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{draft_id}",
    summary="删除草稿",
    description="删除草稿（仅 DRAFT 状态可删除）",
)
async def delete_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除草稿"""
    try:
        success = await achievement_draft_service.delete(draft_id, current_user["id"])
        return {"success": success, "message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{draft_id}/submit",
    response_model=DraftResponse,
    summary="提交审核",
    description="提交草稿进行审核，需指定审核员",
)
async def submit_for_review(
    draft_id: str,
    request: SubmitReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    """提交审核"""
    try:
        draft = await achievement_draft_service.submit_for_review(
            draft_id=draft_id,
            user_id=current_user["id"],
            reviewer_id=request.reviewer_id,
            reviewer_name=request.reviewer_name,
        )
        return DraftResponse(**draft.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{draft_id}/review",
    response_model=DraftResponse,
    summary="执行审核操作",
    description="执行审核操作：通过、转交、退回提交人、退回上一级、作废",
)
async def review_draft(
    draft_id: str,
    request: ReviewActionRequest,
    current_user: dict = Depends(get_current_user),
):
    """执行审核操作"""
    try:
        draft = await achievement_draft_service.review(
            draft_id=draft_id,
            reviewer_id=current_user["id"],
            reviewer_name=current_user["name"],
            action=request.action,
            comment=request.comment,
            to_user_id=request.to_user_id,
            to_user_name=request.to_user_name,
        )
        return DraftResponse(**draft.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{draft_id}/logs",
    response_model=List[ReviewLogResponse],
    summary="获取审核日志",
    description="获取草稿的审核历史",
)
async def get_review_logs(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取审核日志"""
    logs = await achievement_draft_service.get_review_logs(draft_id)
    return [ReviewLogResponse(**log.to_dict()) for log in logs]


@router.get(
    "/stats/review",
    response_model=List[ReviewStatsResponse],
    summary="获取审核统计",
    description="获取审核员的审核统计",
)
async def get_review_stats(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """获取审核统计"""
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None

        stats = await achievement_draft_service.get_review_stats(start, end)
        return [ReviewStatsResponse(**s) for s in stats]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 2: 验证导入**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -c "from src.api.v1.endpoints.achievement_drafts import router; print('OK')"`

Expected: `OK`

**Step 3: 修改 router.py 注册路由**

查看现有 router.py 结构，添加新路由：

```python
# 在 router.py 中添加：
from src.api.v1.endpoints import achievement_drafts

# 在路由注册部分添加：
router.include_router(
    achievement_drafts.router,
    tags=["📝 成果草稿"]
)
```

**Step 4: Commit**

```bash
git add src/api/v1/endpoints/achievement_drafts.py src/api/v1/router.py
git commit -m "feat(api): add achievement drafts API endpoints"
```

---

## Task 7: 添加单元测试

**Files:**
- Create: `tests/unit/test_achievement_draft_entity.py`

**Step 1: 创建测试文件**

```python
"""AchievementDraft 实体单元测试"""

import pytest
from datetime import datetime

from src.core.domain.entities.achievement_draft import (
    AchievementDraft,
    AchievementStatus,
    achievement_draft_to_mongo_doc,
    mongo_doc_to_achievement_draft,
)


class TestAchievementDraft:
    """AchievementDraft 实体测试"""

    def test_create_draft(self):
        """测试创建草稿"""
        draft = AchievementDraft(
            title="测试标题",
            description="测试描述",
            author_id="user_123",
            author_name="张三",
            source_entry_ids=["entry_1", "entry_2"],
        )

        assert draft.title == "测试标题"
        assert draft.status == AchievementStatus.DRAFT
        assert draft.raw_data_count == 2
        assert draft.current_review_level == 0

    def test_can_edit_draft_status(self):
        """测试草稿状态下的编辑权限"""
        draft = AchievementDraft(author_id="user_123")

        assert draft.can_edit("user_123") is True
        assert draft.can_edit("other_user") is False

    def test_can_edit_pending_review_status(self):
        """测试待审核状态下的编辑权限"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        assert draft.can_edit("user_123") is False

    def test_can_edit_returned_status(self):
        """测试退回状态下的编辑权限"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        assert draft.can_edit("user_123") is True

    def test_submit_for_review(self):
        """测试提交审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        assert draft.status == AchievementStatus.PENDING_REVIEW
        assert draft.current_reviewer_id == "reviewer_1"
        assert draft.current_review_level == 1
        assert draft.submitted_at is not None

    def test_approve(self):
        """测试通过审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        assert draft.status == AchievementStatus.APPROVED
        assert draft.completed_at is not None

    def test_forward(self):
        """测试转交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")

        assert draft.status == AchievementStatus.PENDING_REVIEW
        assert draft.current_reviewer_id == "reviewer_2"
        assert draft.current_review_level == 2

    def test_return_to_author(self):
        """测试退回提交人"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        assert draft.status == AchievementStatus.RETURNED
        assert draft.returned_by_reviewer_id == "reviewer_1"
        assert draft.returned_at_level == 1

    def test_resubmit_after_return(self):
        """测试退回后重新提交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()
        draft.submit_for_review("reviewer_2", "审核员B")  # 这个参数会被忽略

        # 应该回到退回的审核员
        assert draft.current_reviewer_id == "reviewer_1"
        assert draft.current_review_level == 1

    def test_void(self):
        """测试作废"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.void()

        assert draft.status == AchievementStatus.VOIDED
        assert draft.completed_at is not None

    def test_to_dict(self):
        """测试转换为字典"""
        draft = AchievementDraft(
            title="测试",
            author_id="user_123",
            author_name="张三",
        )

        d = draft.to_dict()
        assert d["title"] == "测试"
        assert d["status"] == "draft"

    def test_mongo_doc_conversion(self):
        """测试 MongoDB 文档转换"""
        draft = AchievementDraft(
            title="测试",
            author_id="user_123",
            author_name="张三",
            source_entry_ids=["entry_1"],
        )

        doc = achievement_draft_to_mongo_doc(draft)
        restored = mongo_doc_to_achievement_draft(doc)

        assert restored.title == draft.title
        assert restored.author_id == draft.author_id
        assert restored.source_entry_ids == draft.source_entry_ids
```

**Step 2: 运行测试**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -m pytest tests/unit/test_achievement_draft_entity.py -v`

Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/unit/test_achievement_draft_entity.py
git commit -m "test: add unit tests for AchievementDraft entity"
```

---

## Task 8: 最终验证和合并准备

**Step 1: 运行所有新增测试**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -m pytest tests/unit/test_achievement_draft_entity.py -v`

Expected: All tests PASS

**Step 2: 验证所有导入**

Run:
```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && python -c "
from src.core.domain.entities.achievement_draft import AchievementDraft
from src.core.domain.entities.achievement_review_log import AchievementReviewLog
from src.infrastructure.persistence.repositories.mongo.achievement_draft_repository import achievement_draft_repository
from src.infrastructure.persistence.repositories.mongo.achievement_review_log_repository import achievement_review_log_repository
from src.services.achievement import achievement_draft_service
from src.api.v1.endpoints.achievement_drafts import router
print('All imports OK')
"
```

Expected: `All imports OK`

**Step 3: 查看提交历史**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && git log --oneline -10`

**Step 4: 推送分支**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-achievement-draft && git push -u origin feature/achievement-draft`

---

## 文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/core/domain/entities/achievement_draft.py` | 新增 | 草稿实体 |
| `src/core/domain/entities/achievement_review_log.py` | 新增 | 审核日志实体 |
| `src/infrastructure/persistence/repositories/mongo/achievement_draft_repository.py` | 新增 | 草稿仓储 |
| `src/infrastructure/persistence/repositories/mongo/achievement_review_log_repository.py` | 新增 | 日志仓储 |
| `src/services/achievement/__init__.py` | 新增 | 服务模块 |
| `src/services/achievement/achievement_draft_service.py` | 新增 | 草稿服务 |
| `src/api/v1/endpoints/achievement_drafts.py` | 新增 | API 端点 |
| `src/api/v1/router.py` | 修改 | 注册路由 |
| `tests/unit/test_achievement_draft_entity.py` | 新增 | 单元测试 |

# 用户精选内容工作流需求分析与接口设计方案

**文档版本**: v1.0.0
**创建日期**: 2025-11-17
**需求来源**: 项目需求 #11 - 用户编辑search_results功能

---

## 一、需求背景

### 1.1 完整工作流描述

```
用户自然搜索
  ↓
LLM分解查询
  ↓
GPT-5搜索返回URL列表
  ↓
FirecrawlAPI爬取URL内容
  ↓
存入search_results (processed_results表)
  ↓
AI服务分析整理 (不归我们负责)
  ↓
返回news_results表
  ↓
【新增】用户查看AI分析结果
  ↓
【新增】用户编辑字段修正AI错误
  ↓
【新增】用户勾选编辑好的条目
  ↓
【新增】保存到新的精选表
```

### 1.2 核心需求

1. **用户编辑能力**: 允许用户修改news_results中的特定字段以修正AI错误
2. **精选机制**: 用户可勾选满意的条目进行保存
3. **独立存储**: 用户精选的内容需要保存到新的独立表中
4. **接口支持**: 需要新增/修改API接口支持完整工作流

---

## 二、现有系统分析

### 2.1 news_results表结构 (ProcessedResult实体)

**当前字段分类** (共43+字段):

#### 原始搜索结果字段 (17个)
```python
title                  # 原始标题
url                    # URL
content                # 原始内容
snippet                # 摘要
markdown_content       # Markdown格式内容
html_content           # HTML格式内容
author                 # 作者
published_date         # 发布日期
language               # 语言
source                 # 来源
metadata               # 元数据
quality_score          # 质量评分
relevance_score        # 相关性评分
search_position        # 搜索位置
...
```

#### AI处理字段 (11个)
```python
content_zh             # 中文翻译内容
title_generated        # AI生成的标题
cls_results            # 分类结果
html_ctx_llm          # LLM提取的HTML上下文
html_ctx_regex        # 正则提取的上下文
article_published_time # AI识别的发布时间
article_tag           # AI标签
...
```

#### AI增强字段 - news_results嵌套对象 (v2.0.2+)
```python
news_results = {
    "title": str,              # 翻译后的标题
    "published_at": datetime,  # 发布时间
    "source": str,             # 来源域名
    "content": str,            # 翻译后的内容
    "category": {              # 分类信息
        "大类": str,
        "类别": str,
        "地域": str
    },
    "media_urls": List[str]    # 媒体URL列表 (v2.0.3)
}
```

#### 用户操作字段 (3个)
```python
status                 # ProcessedStatus枚举
user_rating           # 用户评分
user_notes            # 用户备注
```

### 2.2 现有API接口

**当前提供的7个接口** (search_results_frontend.py):

```python
GET    /search-tasks/{task_id}/results              # 列表查询+分页
GET    /search-tasks/{task_id}/results/stats        # 统计数据
GET    /search-tasks/{task_id}/results/summary      # 摘要信息
GET    /search-tasks/{task_id}/results/{result_id}  # 详情查询
POST   /search-tasks/{task_id}/results/{result_id}/archive  # 归档
POST   /search-tasks/{task_id}/results/{result_id}/delete   # 软删除
POST   /search-tasks/{task_id}/results/{result_id}/rating   # 评分
```

**现有的用户操作方法** (ProcessedResultRepository):
```python
async def update_user_action(
    result_id: str,
    status: Optional[ProcessedStatus],
    user_rating: Optional[int],
    user_notes: Optional[str]
) -> bool
```

---

## 三、需求分析

### 3.1 可编辑字段识别

**建议允许用户编辑的字段**:

#### 核心内容字段 (用户最需要修正)
```python
✅ title_generated          # AI生成的标题 - 可能需要修正
✅ content_zh               # 中文翻译内容 - 可能有翻译错误
✅ news_results.title       # 最终标题 - 需要精炼
✅ news_results.content     # 最终内容 - 需要修正
✅ news_results.category    # 分类信息 - AI可能分类错误
✅ article_tag              # 文章标签 - 需要调整
```

#### 元数据字段 (辅助修正)
```python
✅ author                   # 作者信息可能识别错误
✅ published_date           # 发布日期可能不准确
✅ news_results.published_at # 最终发布时间
✅ news_results.source      # 来源信息
```

#### 质量评估字段
```python
✅ user_rating              # 用户评分 (已支持)
✅ user_notes               # 用户备注 (已支持)
⚠️  quality_score           # 建议只读，由系统计算
⚠️  relevance_score         # 建议只读，由系统计算
```

**不建议编辑的字段**:
```python
❌ url                      # 原始URL不应修改
❌ content                  # 原始内容不应修改
❌ html_content             # 原始HTML不应修改
❌ ai_model                 # AI元数据不应修改
❌ processing_status        # 处理状态由系统管理
❌ created_at               # 时间戳由系统管理
```

### 3.2 精选表设计需求

**新表目的**: 存储用户审核、编辑后的高质量精选内容

**设计考虑**:
1. **完整性**: 需要保留原始结果的引用关系
2. **版本控制**: 记录用户的修改历史
3. **审核状态**: 支持多级审核流程（如果需要）
4. **独立性**: 与原始结果解耦，方便独立使用

---

## 四、技术方案设计

### 4.1 新表Schema设计

**表名**: `curated_search_results` (用户精选结果表)

```python
# src/core/domain/entities/curated_search_result.py

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

class CurationStatus(str, Enum):
    """精选状态"""
    DRAFT = "draft"              # 草稿 - 用户正在编辑
    SUBMITTED = "submitted"      # 已提交 - 等待审核
    APPROVED = "approved"        # 已批准 - 审核通过
    REJECTED = "rejected"        # 已拒绝 - 审核未通过
    PUBLISHED = "published"      # 已发布 - 对外可见

class CategoryInfo(BaseModel):
    """分类信息"""
    major: str = Field(..., alias="大类", description="大类分类")
    category: str = Field(..., alias="类别", description="具体类别")
    region: str = Field(..., alias="地域", description="地域分类")

class CuratedSearchResult(BaseModel):
    """用户精选搜索结果实体"""

    # ========== 主键 ==========
    id: str = Field(..., description="精选记录ID (雪花算法)")

    # ========== 关联引用 ==========
    original_result_id: str = Field(..., description="原始结果ID (关联processed_results)")
    task_id: str = Field(..., description="任务ID")
    nl_search_log_id: Optional[str] = Field(None, description="NL搜索日志ID (如果来自NL搜索)")

    # ========== 核心内容字段 (用户编辑) ==========
    title: str = Field(..., description="精选标题 (用户编辑后)")
    content: str = Field(..., description="精选内容 (用户编辑后)")
    summary: Optional[str] = Field(None, description="内容摘要")

    # ========== 元数据字段 (用户可编辑) ==========
    author: Optional[str] = Field(None, description="作者")
    published_at: Optional[datetime] = Field(None, description="发布时间")
    source: str = Field(..., description="来源域名")
    language: str = Field(default="zh", description="语言")

    # ========== 分类与标签 (用户编辑) ==========
    category: CategoryInfo = Field(..., description="分类信息")
    tags: List[str] = Field(default_factory=list, description="标签列表")

    # ========== 质量评估 ==========
    user_rating: Optional[int] = Field(None, ge=1, le=5, description="用户评分 (1-5)")
    quality_score: Optional[float] = Field(None, description="质量分数")

    # ========== 媒体资源 ==========
    media_urls: List[str] = Field(default_factory=list, description="媒体URL列表")
    featured_image: Optional[str] = Field(None, description="封面图片URL")

    # ========== 精选管理 ==========
    curation_status: CurationStatus = Field(
        default=CurationStatus.DRAFT,
        description="精选状态"
    )
    curator_id: str = Field(..., description="精选人ID")
    curator_notes: Optional[str] = Field(None, description="精选备注")

    # ========== 审核信息 (如果需要审核流程) ==========
    reviewed_by: Optional[str] = Field(None, description="审核人ID")
    reviewed_at: Optional[datetime] = Field(None, description="审核时间")
    review_notes: Optional[str] = Field(None, description="审核意见")

    # ========== 修改历史 ==========
    edit_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="编辑历史记录"
    )
    version: int = Field(default=1, description="版本号")

    # ========== 原始数据快照 ==========
    original_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="原始AI处理结果的快照"
    )

    # ========== 时间戳 ==========
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    curated_at: Optional[datetime] = Field(None, description="精选完成时间")

    # ========== 额外元数据 ==========
    metadata: Dict[str, Any] = Field(default_factory=dict, description="其他元数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        allow_population_by_field_name = True
```

**MongoDB索引设计**:
```python
# curated_search_results集合索引

# 1. 任务查询索引
{"task_id": 1, "created_at": -1}

# 2. 状态查询索引
{"curation_status": 1, "created_at": -1}

# 3. 用户精选索引
{"curator_id": 1, "created_at": -1}

# 4. 原始结果关联索引
{"original_result_id": 1}

# 5. NL搜索关联索引
{"nl_search_log_id": 1, "created_at": -1}

# 6. 分类查询索引
{"category.major": 1, "category.category": 1, "created_at": -1}

# 7. 全文搜索索引
{"title": "text", "content": "text", "tags": "text"}
```

### 4.2 Repository层设计

**新增Repository**: `src/infrastructure/database/curated_result_repository.py`

```python
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.domain.entities.curated_search_result import (
    CuratedSearchResult,
    CurationStatus
)
from src.infrastructure.database.mongodb_client import get_database
from src.utils.snowflake import generate_id

class CuratedResultRepository:
    """用户精选结果Repository"""

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        self.db = db or get_database()
        self.collection = self.db.curated_search_results

    # ========== CRUD操作 ==========

    async def create(self, entity: CuratedSearchResult) -> str:
        """创建精选记录"""
        if not entity.id:
            entity.id = generate_id()

        document = entity.dict(by_alias=True)
        await self.collection.insert_one(document)
        return entity.id

    async def get_by_id(self, id: str) -> Optional[CuratedSearchResult]:
        """根据ID获取精选记录"""
        document = await self.collection.find_one({"_id": id})
        if not document:
            return None
        return CuratedSearchResult(**document)

    async def update(self, entity: CuratedSearchResult) -> bool:
        """更新精选记录"""
        entity.updated_at = datetime.utcnow()
        entity.version += 1

        result = await self.collection.update_one(
            {"_id": entity.id},
            {"$set": entity.dict(exclude={"id"}, by_alias=True)}
        )
        return result.modified_count > 0

    async def delete(self, id: str) -> bool:
        """删除精选记录"""
        result = await self.collection.delete_one({"_id": id})
        return result.deleted_count > 0

    # ========== 业务查询方法 ==========

    async def get_by_task(
        self,
        task_id: str,
        status: Optional[CurationStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[CuratedSearchResult], int]:
        """根据任务ID获取精选记录（分页）"""
        query = {"task_id": task_id}
        if status:
            query["curation_status"] = status.value

        total = await self.collection.count_documents(query)

        cursor = self.collection.find(query)\
            .sort("created_at", -1)\
            .skip((page - 1) * page_size)\
            .limit(page_size)

        results = []
        async for doc in cursor:
            results.append(CuratedSearchResult(**doc))

        return results, total

    async def get_by_curator(
        self,
        curator_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[CuratedSearchResult], int]:
        """获取用户的精选记录"""
        query = {"curator_id": curator_id}

        total = await self.collection.count_documents(query)

        cursor = self.collection.find(query)\
            .sort("created_at", -1)\
            .skip((page - 1) * page_size)\
            .limit(page_size)

        results = []
        async for doc in cursor:
            results.append(CuratedSearchResult(**doc))

        return results, total

    async def update_status(
        self,
        id: str,
        new_status: CurationStatus,
        reviewer_id: Optional[str] = None,
        review_notes: Optional[str] = None
    ) -> bool:
        """更新精选状态"""
        update_data = {
            "curation_status": new_status.value,
            "updated_at": datetime.utcnow()
        }

        if reviewer_id:
            update_data["reviewed_by"] = reviewer_id
            update_data["reviewed_at"] = datetime.utcnow()

        if review_notes:
            update_data["review_notes"] = review_notes

        if new_status == CurationStatus.APPROVED:
            update_data["curated_at"] = datetime.utcnow()

        result = await self.collection.update_one(
            {"_id": id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def add_edit_history(
        self,
        id: str,
        editor_id: str,
        changes: Dict[str, Any]
    ) -> bool:
        """添加编辑历史记录"""
        history_entry = {
            "editor_id": editor_id,
            "timestamp": datetime.utcnow().isoformat(),
            "changes": changes
        }

        result = await self.collection.update_one(
            {"_id": id},
            {
                "$push": {"edit_history": history_entry},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    async def get_statistics_by_task(
        self,
        task_id: str
    ) -> Dict[str, int]:
        """获取任务的精选统计数据"""
        pipeline = [
            {"$match": {"task_id": task_id}},
            {
                "$group": {
                    "_id": "$curation_status",
                    "count": {"$sum": 1}
                }
            }
        ]

        cursor = self.collection.aggregate(pipeline)
        stats = {status.value: 0 for status in CurationStatus}

        async for doc in cursor:
            stats[doc["_id"]] = doc["count"]

        stats["total"] = sum(stats.values())
        return stats

    async def create_indexes(self):
        """创建索引"""
        await self.collection.create_index(
            [("task_id", 1), ("created_at", -1)],
            name="task_created_idx"
        )
        await self.collection.create_index(
            [("curation_status", 1), ("created_at", -1)],
            name="status_created_idx"
        )
        await self.collection.create_index(
            [("curator_id", 1), ("created_at", -1)],
            name="curator_created_idx"
        )
        await self.collection.create_index(
            [("original_result_id", 1)],
            name="original_ref_idx"
        )
        await self.collection.create_index(
            [("nl_search_log_id", 1), ("created_at", -1)],
            name="nl_search_idx"
        )
        await self.collection.create_index(
            [
                ("category.major", 1),
                ("category.category", 1),
                ("created_at", -1)
            ],
            name="category_idx"
        )
        await self.collection.create_index(
            [("title", "text"), ("content", "text"), ("tags", "text")],
            name="fulltext_idx"
        )

# 全局单例
curated_result_repository = CuratedResultRepository()
```

### 4.3 Service层设计

**新增Service**: `src/services/curation_service.py`

```python
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.core.domain.entities.curated_search_result import (
    CuratedSearchResult,
    CurationStatus,
    CategoryInfo
)
from src.infrastructure.database.curated_result_repository import curated_result_repository
from src.infrastructure.persistence.repositories.mongo.processed_result_repository import (
    mongo_processed_result_repository
)

logger = logging.getLogger(__name__)

class CurationService:
    """用户精选服务"""

    def __init__(self):
        self.curated_repo = curated_result_repository
        self.processed_repo = mongo_processed_result_repository

    async def create_curated_result(
        self,
        original_result_id: str,
        curator_id: str,
        edited_data: Dict[str, Any],
        nl_search_log_id: Optional[str] = None
    ) -> CuratedSearchResult:
        """
        从原始结果创建精选记录

        Args:
            original_result_id: 原始结果ID
            curator_id: 精选人ID
            edited_data: 用户编辑的数据
            nl_search_log_id: NL搜索日志ID（可选）

        Returns:
            创建的精选记录
        """
        # 1. 获取原始结果
        original = await self.processed_repo.get_by_id(original_result_id)
        if not original:
            raise ValueError(f"原始结果不存在: {original_result_id}")

        # 2. 提取news_results数据
        news_results = original.news_results or {}

        # 3. 构建精选记录
        curated = CuratedSearchResult(
            id="",  # 将由repository生成
            original_result_id=original_result_id,
            task_id=original.task_id,
            nl_search_log_id=nl_search_log_id,
            curator_id=curator_id,

            # 核心内容 - 优先使用用户编辑的数据
            title=edited_data.get("title") or news_results.get("title") or original.title,
            content=edited_data.get("content") or news_results.get("content") or original.content_zh or original.content,
            summary=edited_data.get("summary") or original.snippet,

            # 元数据
            author=edited_data.get("author") or original.author,
            published_at=edited_data.get("published_at") or news_results.get("published_at") or original.published_date,
            source=edited_data.get("source") or news_results.get("source") or original.source,
            language=edited_data.get("language", "zh"),

            # 分类与标签
            category=self._parse_category(edited_data.get("category") or news_results.get("category", {})),
            tags=edited_data.get("tags", []) or self._extract_tags(original),

            # 质量评估
            user_rating=edited_data.get("user_rating") or original.user_rating,
            quality_score=original.quality_score,

            # 媒体资源
            media_urls=edited_data.get("media_urls") or news_results.get("media_urls", []),
            featured_image=edited_data.get("featured_image"),

            # 精选管理
            curation_status=CurationStatus.DRAFT,
            curator_notes=edited_data.get("curator_notes"),

            # 原始数据快照
            original_data={
                "id": original.id,
                "title": original.title,
                "content_zh": original.content_zh,
                "news_results": news_results,
                "quality_score": original.quality_score,
                "relevance_score": original.relevance_score
            },

            # 编辑历史
            edit_history=[{
                "editor_id": curator_id,
                "timestamp": datetime.utcnow().isoformat(),
                "action": "created",
                "changes": edited_data
            }]
        )

        # 4. 保存到数据库
        curated_id = await self.curated_repo.create(curated)
        curated.id = curated_id

        logger.info(f"创建精选记录: curated_id={curated_id}, original_id={original_result_id}")
        return curated

    async def update_curated_result(
        self,
        curated_id: str,
        editor_id: str,
        updates: Dict[str, Any]
    ) -> CuratedSearchResult:
        """
        更新精选记录

        Args:
            curated_id: 精选记录ID
            editor_id: 编辑人ID
            updates: 更新的字段

        Returns:
            更新后的精选记录
        """
        # 1. 获取现有记录
        curated = await self.curated_repo.get_by_id(curated_id)
        if not curated:
            raise ValueError(f"精选记录不存在: {curated_id}")

        # 2. 记录变更
        changes = {}
        for key, new_value in updates.items():
            if hasattr(curated, key):
                old_value = getattr(curated, key)
                if old_value != new_value:
                    changes[key] = {
                        "old": old_value,
                        "new": new_value
                    }
                    setattr(curated, key, new_value)

        # 3. 添加编辑历史
        if changes:
            await self.curated_repo.add_edit_history(
                curated_id,
                editor_id,
                changes
            )

        # 4. 更新记录
        await self.curated_repo.update(curated)

        logger.info(f"更新精选记录: curated_id={curated_id}, changes={len(changes)}")
        return curated

    async def submit_for_review(
        self,
        curated_id: str,
        curator_id: str
    ) -> bool:
        """提交精选记录进行审核"""
        return await self.curated_repo.update_status(
            curated_id,
            CurationStatus.SUBMITTED
        )

    async def approve_curated_result(
        self,
        curated_id: str,
        reviewer_id: str,
        review_notes: Optional[str] = None
    ) -> bool:
        """批准精选记录"""
        return await self.curated_repo.update_status(
            curated_id,
            CurationStatus.APPROVED,
            reviewer_id=reviewer_id,
            review_notes=review_notes
        )

    async def reject_curated_result(
        self,
        curated_id: str,
        reviewer_id: str,
        review_notes: str
    ) -> bool:
        """拒绝精选记录"""
        return await self.curated_repo.update_status(
            curated_id,
            CurationStatus.REJECTED,
            reviewer_id=reviewer_id,
            review_notes=review_notes
        )

    async def publish_curated_result(
        self,
        curated_id: str
    ) -> bool:
        """发布精选记录"""
        return await self.curated_repo.update_status(
            curated_id,
            CurationStatus.PUBLISHED
        )

    async def get_curated_results_by_task(
        self,
        task_id: str,
        status: Optional[CurationStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取任务的精选记录列表"""
        results, total = await self.curated_repo.get_by_task(
            task_id,
            status=status,
            page=page,
            page_size=page_size
        )

        return {
            "results": [r.dict() for r in results],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    async def get_curation_statistics(
        self,
        task_id: str
    ) -> Dict[str, int]:
        """获取精选统计数据"""
        return await self.curated_repo.get_statistics_by_task(task_id)

    # ========== 辅助方法 ==========

    def _parse_category(self, category_data: Dict[str, str]) -> CategoryInfo:
        """解析分类信息"""
        return CategoryInfo(
            major=category_data.get("大类", ""),
            category=category_data.get("类别", ""),
            region=category_data.get("地域", "")
        )

    def _extract_tags(self, processed_result) -> List[str]:
        """从原始结果提取标签"""
        tags = []

        # 从article_tag提取
        if processed_result.article_tag:
            tags.extend(processed_result.article_tag)

        # 从分类提取
        if processed_result.news_results and processed_result.news_results.get("category"):
            cat = processed_result.news_results["category"]
            if cat.get("大类"):
                tags.append(cat["大类"])
            if cat.get("类别"):
                tags.append(cat["类别"])

        return list(set(tags))  # 去重

# 全局单例
curation_service = CurationService()
```

### 4.4 API层设计

**新增API Router**: `src/api/v1/endpoints/curation.py`

```python
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from src.services.curation_service import curation_service
from src.core.domain.entities.curated_search_result import CurationStatus

router = APIRouter(
    prefix="/curation",
    tags=["curation"]
)

# ========== 请求/响应模型 ==========

class CreateCuratedResultRequest(BaseModel):
    """创建精选记录请求"""
    original_result_id: str = Field(..., description="原始结果ID")
    curator_id: str = Field(..., description="精选人ID")
    nl_search_log_id: Optional[str] = Field(None, description="NL搜索日志ID")

    # 可编辑字段
    title: Optional[str] = Field(None, description="标题")
    content: Optional[str] = Field(None, description="内容")
    summary: Optional[str] = Field(None, description="摘要")
    author: Optional[str] = Field(None, description="作者")
    published_at: Optional[datetime] = Field(None, description="发布时间")
    source: Optional[str] = Field(None, description="来源")
    category: Optional[Dict[str, str]] = Field(None, description="分类")
    tags: Optional[List[str]] = Field(None, description="标签")
    user_rating: Optional[int] = Field(None, ge=1, le=5, description="用户评分")
    media_urls: Optional[List[str]] = Field(None, description="媒体URL")
    featured_image: Optional[str] = Field(None, description="封面图")
    curator_notes: Optional[str] = Field(None, description="精选备注")

class UpdateCuratedResultRequest(BaseModel):
    """更新精选记录请求"""
    editor_id: str = Field(..., description="编辑人ID")

    # 可更新字段
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    source: Optional[str] = None
    category: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    media_urls: Optional[List[str]] = None
    featured_image: Optional[str] = None
    curator_notes: Optional[str] = None

class CuratedResultResponse(BaseModel):
    """精选记录响应"""
    id: str
    original_result_id: str
    task_id: str
    nl_search_log_id: Optional[str]

    title: str
    content: str
    summary: Optional[str]
    author: Optional[str]
    published_at: Optional[datetime]
    source: str

    category: Dict[str, str]
    tags: List[str]

    user_rating: Optional[int]
    quality_score: Optional[float]

    media_urls: List[str]
    featured_image: Optional[str]

    curation_status: CurationStatus
    curator_id: str
    curator_notes: Optional[str]

    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]

    version: int
    created_at: datetime
    updated_at: datetime
    curated_at: Optional[datetime]

class CuratedResultListResponse(BaseModel):
    """精选记录列表响应"""
    results: List[CuratedResultResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class CurationStatisticsResponse(BaseModel):
    """精选统计响应"""
    total: int
    draft: int
    submitted: int
    approved: int
    rejected: int
    published: int

# ========== API端点 ==========

@router.post(
    "/results",
    response_model=CuratedResultResponse,
    summary="创建精选记录",
    description="从原始搜索结果创建用户精选记录"
)
async def create_curated_result(
    request: CreateCuratedResultRequest
):
    """
    创建精选记录

    工作流:
    1. 用户在news_results列表中选择一条记录
    2. 编辑字段修正AI错误
    3. 提交创建精选记录
    """
    try:
        # 构建编辑数据
        edited_data = {
            k: v for k, v in request.dict(exclude={"original_result_id", "curator_id", "nl_search_log_id"}).items()
            if v is not None
        }

        # 创建精选记录
        curated = await curation_service.create_curated_result(
            original_result_id=request.original_result_id,
            curator_id=request.curator_id,
            edited_data=edited_data,
            nl_search_log_id=request.nl_search_log_id
        )

        return CuratedResultResponse(**curated.dict())

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建精选记录失败: {str(e)}")

@router.patch(
    "/results/{curated_id}",
    response_model=CuratedResultResponse,
    summary="更新精选记录",
    description="更新用户精选记录的内容"
)
async def update_curated_result(
    curated_id: str,
    request: UpdateCuratedResultRequest
):
    """
    更新精选记录

    允许用户继续编辑已保存的精选记录
    """
    try:
        # 提取更新字段
        updates = {
            k: v for k, v in request.dict(exclude={"editor_id"}).items()
            if v is not None
        }

        # 更新记录
        curated = await curation_service.update_curated_result(
            curated_id=curated_id,
            editor_id=request.editor_id,
            updates=updates
        )

        return CuratedResultResponse(**curated.dict())

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新精选记录失败: {str(e)}")

@router.get(
    "/tasks/{task_id}/results",
    response_model=CuratedResultListResponse,
    summary="获取任务的精选记录",
    description="分页获取任务的精选记录列表"
)
async def get_curated_results_by_task(
    task_id: str,
    status: Optional[CurationStatus] = Query(None, description="精选状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取任务的精选记录列表

    支持按状态筛选和分页
    """
    try:
        result = await curation_service.get_curated_results_by_task(
            task_id=task_id,
            status=status,
            page=page,
            page_size=page_size
        )

        return CuratedResultListResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取精选记录失败: {str(e)}")

@router.get(
    "/results/{curated_id}",
    response_model=CuratedResultResponse,
    summary="获取精选记录详情",
    description="获取单个精选记录的详细信息"
)
async def get_curated_result(
    curated_id: str
):
    """获取精选记录详情"""
    try:
        curated = await curation_service.curated_repo.get_by_id(curated_id)

        if not curated:
            raise HTTPException(status_code=404, detail="精选记录不存在")

        return CuratedResultResponse(**curated.dict())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取精选记录失败: {str(e)}")

@router.post(
    "/results/{curated_id}/submit",
    summary="提交审核",
    description="提交精选记录进行审核"
)
async def submit_for_review(
    curated_id: str,
    curator_id: str = Query(..., description="精选人ID")
):
    """提交精选记录进行审核"""
    try:
        success = await curation_service.submit_for_review(curated_id, curator_id)

        if not success:
            raise HTTPException(status_code=400, detail="提交失败")

        return {"message": "提交成功", "curated_id": curated_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")

@router.post(
    "/results/{curated_id}/approve",
    summary="批准精选",
    description="批准精选记录"
)
async def approve_curated_result(
    curated_id: str,
    reviewer_id: str = Query(..., description="审核人ID"),
    review_notes: Optional[str] = Query(None, description="审核意见")
):
    """批准精选记录"""
    try:
        success = await curation_service.approve_curated_result(
            curated_id,
            reviewer_id,
            review_notes
        )

        if not success:
            raise HTTPException(status_code=400, detail="批准失败")

        return {"message": "批准成功", "curated_id": curated_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批准失败: {str(e)}")

@router.post(
    "/results/{curated_id}/reject",
    summary="拒绝精选",
    description="拒绝精选记录"
)
async def reject_curated_result(
    curated_id: str,
    reviewer_id: str = Query(..., description="审核人ID"),
    review_notes: str = Query(..., description="拒绝原因")
):
    """拒绝精选记录"""
    try:
        success = await curation_service.reject_curated_result(
            curated_id,
            reviewer_id,
            review_notes
        )

        if not success:
            raise HTTPException(status_code=400, detail="拒绝失败")

        return {"message": "拒绝成功", "curated_id": curated_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拒绝失败: {str(e)}")

@router.post(
    "/results/{curated_id}/publish",
    summary="发布精选",
    description="发布精选记录对外可见"
)
async def publish_curated_result(
    curated_id: str
):
    """发布精选记录"""
    try:
        success = await curation_service.publish_curated_result(curated_id)

        if not success:
            raise HTTPException(status_code=400, detail="发布失败")

        return {"message": "发布成功", "curated_id": curated_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发布失败: {str(e)}")

@router.get(
    "/tasks/{task_id}/statistics",
    response_model=CurationStatisticsResponse,
    summary="获取精选统计",
    description="获取任务的精选统计数据"
)
async def get_curation_statistics(
    task_id: str
):
    """获取精选统计数据"""
    try:
        stats = await curation_service.get_curation_statistics(task_id)
        return CurationStatisticsResponse(**stats)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")

@router.delete(
    "/results/{curated_id}",
    summary="删除精选记录",
    description="删除精选记录"
)
async def delete_curated_result(
    curated_id: str
):
    """删除精选记录"""
    try:
        success = await curation_service.curated_repo.delete(curated_id)

        if not success:
            raise HTTPException(status_code=404, detail="精选记录不存在")

        return {"message": "删除成功", "curated_id": curated_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
```

**注册Router到主应用** (修改 `src/api/v1/router.py`):

```python
from src.api.v1.endpoints import curation

# 在router.py中添加
api_router.include_router(
    curation.router,
    prefix="/curation",
    tags=["curation"]
)
```

---

## 五、完整工作流示例

### 5.1 前端操作流程

```
1. 用户查看AI分析结果
   GET /api/v1/search-tasks/{task_id}/results
   → 返回news_results列表

2. 用户选择一条记录进行编辑
   → 前端展示编辑表单，预填AI生成的内容

3. 用户修改字段
   - 修正标题
   - 调整内容翻译
   - 修正分类
   - 添加/修改标签

4. 用户保存编辑
   POST /api/v1/curation/results
   Body: {
     "original_result_id": "123456",
     "curator_id": "user_789",
     "title": "修正后的标题",
     "content": "修正后的内容",
     "category": {
       "大类": "科技",
       "类别": "人工智能",
       "地域": "美国"
     },
     "tags": ["GPT-5", "AI突破"],
     "user_rating": 5
   }
   → 创建精选记录，状态为DRAFT

5. 用户继续编辑（可选）
   PATCH /api/v1/curation/results/{curated_id}
   Body: {
     "editor_id": "user_789",
     "content": "进一步修正的内容"
   }
   → 更新精选记录，记录编辑历史

6. 用户提交审核（如果需要审核流程）
   POST /api/v1/curation/results/{curated_id}/submit
   → 状态变更为SUBMITTED

7. 审核人员批准
   POST /api/v1/curation/results/{curated_id}/approve
   → 状态变更为APPROVED

8. 发布精选内容
   POST /api/v1/curation/results/{curated_id}/publish
   → 状态变更为PUBLISHED，对外可见
```

### 5.2 批量精选流程

```
1. 用户勾选多条记录
   前端维护选中列表: [result_id_1, result_id_2, result_id_3]

2. 批量创建精选记录
   for result_id in selected_ids:
       POST /api/v1/curation/results
       Body: {
         "original_result_id": result_id,
         "curator_id": "user_789",
         ...编辑的数据...
       }

3. 查看精选列表
   GET /api/v1/curation/tasks/{task_id}/results?status=draft
   → 返回所有草稿状态的精选记录

4. 批量发布
   for curated_id in curated_ids:
       POST /api/v1/curation/results/{curated_id}/publish
```

---

## 六、数据库迁移脚本

**新建文件**: `scripts/create_curation_indexes.py`

```python
#!/usr/bin/env python3
"""
用户精选表索引创建脚本

版本: v1.0.0
日期: 2025-11-17
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.curated_result_repository import curated_result_repository

async def create_indexes():
    """创建精选表索引"""
    print("=" * 60)
    print("用户精选表索引创建工具")
    print("=" * 60)
    print()

    try:
        print("📋 创建 curated_search_results 集合索引...")
        await curated_result_repository.create_indexes()
        print("✅ curated_search_results 索引创建完成")
        print()

        print("=" * 60)
        print("✅ 所有索引创建成功！")
        print("=" * 60)
        print()
        print("创建的索引列表:")
        print()
        print("curated_search_results 集合:")
        print("  1. task_created_idx - 任务+创建时间复合索引")
        print("  2. status_created_idx - 状态+创建时间复合索引")
        print("  3. curator_created_idx - 精选人+创建时间复合索引")
        print("  4. original_ref_idx - 原始结果引用索引")
        print("  5. nl_search_idx - NL搜索关联索引")
        print("  6. category_idx - 分类查询索引")
        print("  7. fulltext_idx - 全文搜索索引")
        print()

    except Exception as e:
        print(f"❌ 索引创建失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """主函数"""
    try:
        asyncio.run(create_indexes())
    except KeyboardInterrupt:
        print("\n\n⚠️  索引创建被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 七、测试脚本

**新建文件**: `scripts/test_curation_workflow.py`

```python
#!/usr/bin/env python3
"""
用户精选工作流集成测试脚本

版本: v1.0.0
日期: 2025-11-17
"""
import asyncio
import sys
import os
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.curation_service import curation_service
from src.core.domain.entities.curated_search_result import CurationStatus

class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_section(title: str):
    """打印章节标题"""
    print()
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print()

def print_success(message: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")

def print_error(message: str):
    """打印错误消息"""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")

def print_info(message: str):
    """打印信息消息"""
    print(f"{Colors.YELLOW}ℹ️  {message}{Colors.RESET}")

async def test_create_curated_result(original_result_id: str) -> str:
    """测试创建精选记录"""
    print_section("测试 1: 创建精选记录")

    try:
        print_info(f"从原始结果创建精选记录: {original_result_id}")

        edited_data = {
            "title": "【测试】修正后的标题 - GPT-5技术突破",
            "content": "这是修正后的内容，修正了AI翻译的错误...",
            "category": {
                "大类": "科技",
                "类别": "人工智能",
                "地域": "美国"
            },
            "tags": ["GPT-5", "AI", "技术突破"],
            "user_rating": 5,
            "curator_notes": "这是一条高质量的技术新闻"
        }

        curated = await curation_service.create_curated_result(
            original_result_id=original_result_id,
            curator_id="test_curator_123",
            edited_data=edited_data,
            nl_search_log_id="test_nl_search_log_456"
        )

        print_success("精选记录创建成功")
        print(f"   精选记录ID: {curated.id}")
        print(f"   标题: {curated.title}")
        print(f"   状态: {curated.curation_status.value}")
        print(f"   版本: {curated.version}")

        return curated.id

    except Exception as e:
        print_error(f"创建精选记录失败: {e}")
        raise

async def test_update_curated_result(curated_id: str):
    """测试更新精选记录"""
    print_section("测试 2: 更新精选记录")

    try:
        print_info(f"更新精选记录: {curated_id}")

        updates = {
            "content": "这是进一步修正的内容，添加了更多细节...",
            "tags": ["GPT-5", "AI", "技术突破", "深度学习"]
        }

        curated = await curation_service.update_curated_result(
            curated_id=curated_id,
            editor_id="test_editor_789",
            updates=updates
        )

        print_success("精选记录更新成功")
        print(f"   版本: {curated.version}")
        print(f"   编辑历史数量: {len(curated.edit_history)}")

    except Exception as e:
        print_error(f"更新精选记录失败: {e}")
        raise

async def test_submit_and_approve(curated_id: str):
    """测试提交审核和批准"""
    print_section("测试 3: 提交审核和批准")

    try:
        # 提交审核
        print_info("提交审核...")
        await curation_service.submit_for_review(
            curated_id=curated_id,
            curator_id="test_curator_123"
        )
        print_success("提交审核成功")

        # 批准
        print_info("批准精选...")
        await curation_service.approve_curated_result(
            curated_id=curated_id,
            reviewer_id="test_reviewer_456",
            review_notes="内容质量优秀，批准发布"
        )
        print_success("批准成功")

        # 发布
        print_info("发布精选...")
        await curation_service.publish_curated_result(curated_id)
        print_success("发布成功")

    except Exception as e:
        print_error(f"审核流程失败: {e}")
        raise

async def test_get_curated_results(task_id: str):
    """测试获取精选记录列表"""
    print_section("测试 4: 获取精选记录列表")

    try:
        print_info(f"获取任务的精选记录: {task_id}")

        result = await curation_service.get_curated_results_by_task(
            task_id=task_id,
            page=1,
            page_size=10
        )

        print_success("获取精选记录列表成功")
        print(f"   总数: {result['total']}")
        print(f"   当前页: {result['page']}")
        print(f"   每页数量: {result['page_size']}")

    except Exception as e:
        print_error(f"获取精选记录失败: {e}")
        raise

async def test_get_statistics(task_id: str):
    """测试获取统计数据"""
    print_section("测试 5: 获取精选统计")

    try:
        print_info(f"获取统计数据: {task_id}")

        stats = await curation_service.get_curation_statistics(task_id)

        print_success("获取统计数据成功")
        print(f"   总数: {stats['total']}")
        print(f"   草稿: {stats['draft']}")
        print(f"   已提交: {stats['submitted']}")
        print(f"   已批准: {stats['approved']}")
        print(f"   已发布: {stats['published']}")

    except Exception as e:
        print_error(f"获取统计数据失败: {e}")
        raise

async def run_all_tests():
    """运行所有测试"""
    print_section("用户精选工作流集成测试")

    # 注意：这里需要一个真实的原始结果ID
    # 在实际测试中，应该先创建一个测试用的processed_result
    original_result_id = "test_result_123456"  # 替换为真实ID
    task_id = "test_task_789"

    try:
        # 测试 1: 创建精选记录
        curated_id = await test_create_curated_result(original_result_id)

        # 测试 2: 更新精选记录
        await test_update_curated_result(curated_id)

        # 测试 3: 提交审核和批准
        await test_submit_and_approve(curated_id)

        # 测试 4: 获取精选记录列表
        await test_get_curated_results(task_id)

        # 测试 5: 获取统计数据
        await test_get_statistics(task_id)

        # 测试总结
        print_section("测试完成")
        print_success("所有测试通过！✨")
        print()
        print("测试覆盖:")
        print("  ✅ 创建精选记录")
        print("  ✅ 更新精选记录")
        print("  ✅ 提交审核")
        print("  ✅ 批准精选")
        print("  ✅ 发布精选")
        print("  ✅ 获取精选列表")
        print("  ✅ 获取统计数据")
        print()

        return True

    except Exception as e:
        print_section("测试失败")
        print_error(f"发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print()
        print_error("测试被用户中断")
        sys.exit(1)

    except Exception as e:
        print()
        print_error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 八、实施计划

### 8.1 开发阶段

**阶段1: 数据模型与Repository (2-3天)**
- [ ] 创建 `curated_search_result.py` 实体
- [ ] 创建 `curated_result_repository.py`
- [ ] 创建索引脚本并执行
- [ ] 单元测试Repository方法

**阶段2: Service层 (1-2天)**
- [ ] 创建 `curation_service.py`
- [ ] 实现核心业务逻辑
- [ ] 单元测试Service方法

**阶段3: API层 (2-3天)**
- [ ] 创建 `curation.py` Router
- [ ] 实现所有API端点
- [ ] API集成测试

**阶段4: 集成测试 (1天)**
- [ ] 创建集成测试脚本
- [ ] 完整工作流测试
- [ ] 性能测试

**阶段5: 文档与部署 (1天)**
- [ ] API文档更新
- [ ] 部署文档
- [ ] 用户操作手册

### 8.2 预计工作量

- **开发**: 7-9个工作日
- **测试**: 2-3个工作日
- **文档**: 1个工作日
- **总计**: 10-13个工作日

---

## 九、风险与注意事项

### 9.1 技术风险

1. **数据一致性**:
   - 原始结果被删除时，精选记录如何处理？
   - **建议**: 保留原始数据快照，soft delete原始结果

2. **并发编辑**:
   - 多人同时编辑同一条记录
   - **建议**: 使用乐观锁（version字段）

3. **存储成本**:
   - 保留编辑历史可能导致数据膨胀
   - **建议**: 定期归档旧版本历史

### 9.2 业务风险

1. **审核流程复杂度**:
   - 是否需要多级审核？
   - **建议**: 先实现单级审核，后续扩展

2. **权限管理**:
   - 谁可以创建/编辑/审核/发布？
   - **建议**: 集成现有权限系统

3. **质量控制**:
   - 如何保证精选内容质量？
   - **建议**: 添加质量评分机制和审核标准

---

## 十、总结

本文档详细设计了**用户精选内容工作流**的完整技术方案，包括:

✅ **新表设计**: `curated_search_results` 表schema
✅ **Repository层**: 完整的数据访问实现
✅ **Service层**: 核心业务逻辑
✅ **API层**: 11个RESTful端点
✅ **数据库脚本**: 索引创建脚本
✅ **测试脚本**: 集成测试脚本
✅ **实施计划**: 10-13个工作日

该方案完全满足需求：
- ✅ 用户可以编辑news_results字段修正AI错误
- ✅ 用户可以勾选编辑好的条目
- ✅ 精选内容保存到新的独立表
- ✅ 提供完整的API接口支持

**下一步行动**:
1. 评审本技术方案
2. 确认审核流程需求
3. 开始阶段1实施（数据模型与Repository）

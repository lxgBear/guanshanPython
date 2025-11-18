# NL Search 功能实现指南

**文档版本**: v1.0
**创建日期**: 2025-11-17
**目标**: 完善 NL Search 核心功能，实现完整闭环
**估算工作量**: 3-5 天

---

## 📋 目录

1. [功能概述](#功能概述)
2. [技术架构分析](#技术架构分析)
3. [实现方案 1: GET /{log_id}/results](#实现方案-1-get-log_idresults)
4. [实现方案 2: POST /{log_id}/select](#实现方案-2-post-log_idselect)
5. [数据库设计](#数据库设计)
6. [测试方案](#测试方案)
7. [部署清单](#部署清单)

---

## 功能概述

### 当前 NL Search 架构状态

**已实现功能** (70%):
- ✅ 搜索记录创建 (`POST /nl-search`)
- ✅ 搜索记录查询 (`GET /nl-search/{log_id}`)
- ✅ 搜索历史列表 (`GET /nl-search`)
- ✅ MongoDB 迁移完成
- ✅ 档案管理功能

**未实现功能** (30%):
- ❌ 搜索结果查询 (`GET /nl-search/{log_id}/results`)
- ❌ 用户选择记录 (`POST /nl-search/{log_id}/select`)

### 核心问题分析

**问题 1: 搜索结果存储在哪里？**

当前 `NLSearchService.create_search()` 方法执行流程:
```python
# src/services/nl_search/nl_search_service.py:50-137
async def create_search(self, query_text, user_id):
    # 1. 创建搜索记录 (保存到 nl_search_logs)
    log_id = await self.repository.create(query_text, llm_analysis=None)

    # 2. LLM 解析查询
    analysis = await self.llm_processor.parse_query(query_text)

    # 3. 更新分析结果
    await self.repository.update_llm_analysis(log_id, analysis)

    # 4. 精炼查询
    refined_query = await self.llm_processor.refine_query(query_text)

    # 5. 执行搜索 (GPT5SearchAdapter)
    search_results = await self.gpt5_adapter.search(refined_query, max_results)

    # 6. 返回结果 (仅在响应中返回，未持久化)
    return {
        "log_id": log_id,
        "results": [r.to_dict() for r in search_results],  # ⚠️ 仅内存中
        ...
    }
```

**关键发现**:
- ✅ 搜索记录保存到 `nl_search_logs` 集合
- ❌ 搜索结果 **未保存** 到数据库
- ⚠️ 搜索结果仅通过 API 响应返回给前端，未持久化

**问题 2: 搜索结果数据结构**

`SearchResult` 类定义:
```python
# src/services/nl_search/gpt5_search_adapter.py:39-67
class SearchResult:
    def __init__(self, title, url, snippet, position, score, source):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.position = position
        self.score = score
        self.source = source  # "serpapi", "test" 等

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "position": self.position,
            "score": self.score,
            "source": self.source
        }
```

**数据特征**:
- 轻量级结构 (URL + 标题 + 摘要)
- 无完整网页内容 (需后续爬取)
- 与 `news_results` 集合 **不同**

---

## 技术架构分析

### 架构决策: 搜索结果存储方案

#### 方案 A: 内嵌存储 (推荐)

**设计**: 将搜索结果直接存储在 `nl_search_logs` 文档中

**优点**:
- ✅ 简单直接，无需新建集合
- ✅ 查询效率高 (单次查询获取所有数据)
- ✅ 数据一致性强 (原子操作)
- ✅ 适合轻量级搜索结果

**缺点**:
- ⚠️ 文档大小可能增大 (MongoDB 文档限制 16MB)
- ⚠️ 不适合大量搜索结果 (>100条)

**文档结构**:
```javascript
// nl_search_logs 集合
{
    "_id": "248728141926559744",
    "query_text": "最近AI技术突破",
    "llm_analysis": { ... },
    "search_results": [  // 新增字段
        {
            "title": "GPT-5 重磅发布",
            "url": "https://example.com/gpt5",
            "snippet": "OpenAI 发布最新...",
            "position": 1,
            "score": 0.95,
            "source": "serpapi"
        },
        // ... 更多结果
    ],
    "results_count": 10,
    "status": "completed",
    "created_at": ISODate(...),
    "updated_at": ISODate(...)
}
```

#### 方案 B: 独立集合存储

**设计**: 创建 `nl_search_results` 集合，通过 `log_id` 关联

**优点**:
- ✅ 适合大量搜索结果
- ✅ 支持结果单独查询和过滤
- ✅ 文档大小不受限制

**缺点**:
- ⚠️ 需要额外的集合和索引
- ⚠️ 查询需要 JOIN 操作 (MongoDB $lookup)
- ⚠️ 增加系统复杂度

**文档结构**:
```javascript
// nl_search_results 集合
{
    "_id": "result_001",
    "log_id": "248728141926559744",  // 关联搜索记录
    "title": "GPT-5 重磅发布",
    "url": "https://example.com/gpt5",
    "snippet": "OpenAI 发布最新...",
    "position": 1,
    "score": 0.95,
    "source": "serpapi",
    "created_at": ISODate(...)
}
```

### 推荐方案: 方案 A (内嵌存储)

**理由**:
1. NL Search 搜索结果数量可控 (默认 10-20 条)
2. 结果数据轻量 (无完整内容)
3. 简化查询逻辑，提升性能
4. 符合 MongoDB 最佳实践 (内嵌文档)

---

## 实现方案 1: GET /{log_id}/results

### 1.1 数据模型定义

```python
# src/api/v1/endpoints/nl_search.py

class SearchResultItem(BaseModel):
    """搜索结果条目"""
    title: str = Field(..., description="结果标题")
    url: str = Field(..., description="结果URL")
    snippet: str = Field("", description="结果摘要")
    position: int = Field(..., description="结果位置")
    score: float = Field(0.0, description="相关性评分")
    source: str = Field("search", description="搜索来源")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "GPT-5 重磅发布",
                "url": "https://example.com/gpt5",
                "snippet": "OpenAI 发布最新大语言模型 GPT-5...",
                "position": 1,
                "score": 0.95,
                "source": "serpapi"
            }
        }


class SearchResultsResponse(BaseModel):
    """搜索结果响应"""
    log_id: str = Field(..., description="搜索记录ID")
    query_text: str = Field(..., description="用户查询")
    total_count: int = Field(..., description="结果总数")
    results: List[SearchResultItem] = Field(..., description="搜索结果列表")
    llm_analysis: Optional[Dict[str, Any]] = Field(None, description="LLM分析结果")
    status: str = Field(..., description="搜索状态")
    created_at: str = Field(..., description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "log_id": "248728141926559744",
                "query_text": "最近AI技术突破",
                "total_count": 10,
                "results": [
                    {
                        "title": "GPT-5 发布",
                        "url": "https://example.com/gpt5",
                        "snippet": "...",
                        "position": 1,
                        "score": 0.95,
                        "source": "serpapi"
                    }
                ],
                "llm_analysis": {
                    "intent": "technology_news",
                    "keywords": ["AI", "技术突破"]
                },
                "status": "completed",
                "created_at": "2025-11-17T10:00:00Z"
            }
        }
```

### 1.2 Repository 层扩展

```python
# src/infrastructure/database/mongo_nl_search_repository.py

class MongoNLSearchLogRepository:
    # ... 现有方法 ...

    async def update_search_results(
        self,
        log_id: str,
        search_results: List[Dict[str, Any]],
        results_count: int
    ) -> bool:
        """
        更新搜索结果

        Args:
            log_id: 日志ID
            search_results: 搜索结果列表 (字典格式)
            results_count: 结果数量

        Returns:
            bool: 更新是否成功

        Example:
            >>> await repo.update_search_results(
            ...     log_id="248728141926559744",
            ...     search_results=[
            ...         {
            ...             "title": "GPT-5",
            ...             "url": "https://...",
            ...             "snippet": "...",
            ...             "position": 1,
            ...             "score": 0.95,
            ...             "source": "serpapi"
            ...         }
            ...     ],
            ...     results_count=10
            ... )
        """
        collection = await self._get_collection()

        # 更新文档
        result = await collection.update_one(
            {"_id": log_id},
            {
                "$set": {
                    "search_results": search_results,
                    "results_count": results_count,
                    "status": "completed",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        success = result.modified_count > 0
        if success:
            logger.info(f"更新搜索结果成功: log_id={log_id}, count={results_count}")
        else:
            logger.warning(f"更新搜索结果失败: log_id={log_id}")

        return success

    async def get_search_results(
        self,
        log_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取搜索结果

        Args:
            log_id: 日志ID

        Returns:
            Optional[List[Dict]]: 搜索结果列表，不存在时返回 None

        Example:
            >>> results = await repo.get_search_results("248728141926559744")
            >>> if results:
            ...     for r in results:
            ...         print(r["title"], r["url"])
        """
        collection = await self._get_collection()

        # 查询文档，仅返回搜索结果字段
        document = await collection.find_one(
            {"_id": log_id},
            {"search_results": 1, "_id": 0}
        )

        if not document:
            logger.debug(f"搜索记录不存在: log_id={log_id}")
            return None

        # 返回搜索结果数组
        return document.get("search_results", [])
```

### 1.3 Service 层实现

```python
# src/services/nl_search/nl_search_service.py

class NLSearchService:
    # ... 现有方法 ...

    async def create_search(
        self,
        query_text: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建自然语言搜索 (修改版本 - 持久化搜索结果)
        """
        # 验证输入
        if not query_text or not query_text.strip():
            raise ValueError("查询文本不能为空")

        query_text = query_text.strip()
        logger.info(f"开始处理自然语言搜索: {query_text[:50]}...")

        try:
            # 1. 创建搜索记录
            log_id = await self.repository.create(
                query_text=query_text,
                llm_analysis=None
            )

            # 2-4. LLM 解析和分析 (保持不变)
            analysis = await self.llm_processor.parse_query(query_text)
            await self.repository.update_llm_analysis(log_id, analysis)
            refined_query = await self.llm_processor.refine_query(query_text)

            # 5. 执行搜索
            search_results = await self.gpt5_adapter.search(
                query=refined_query,
                max_results=nl_search_config.max_results_per_query
            )
            logger.info(f"搜索完成: 获得{len(search_results)}个结果")

            # 🆕 6. 保存搜索结果到数据库
            results_dict = [r.to_dict() for r in search_results]
            await self.repository.update_search_results(
                log_id=log_id,
                search_results=results_dict,
                results_count=len(search_results)
            )
            logger.info(f"搜索结果已保存: log_id={log_id}")

            # 7. 构建返回结果
            result = {
                "log_id": log_id,
                "query_text": query_text,
                "analysis": analysis,
                "refined_query": refined_query,
                "results": results_dict,
                "created_at": datetime.now().isoformat()
            }

            return result

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            raise

    async def get_search_results(
        self,
        log_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        获取搜索结果

        Args:
            log_id: 搜索记录ID
            limit: 返回数量限制 (可选)
            offset: 分页偏移量 (默认 0)

        Returns:
            Optional[Dict]: 搜索结果数据，不存在时返回 None

        Example:
            >>> result = await service.get_search_results("248728141926559744")
            >>> print(f"共 {result['total_count']} 条结果")
            >>> for item in result['results']:
            ...     print(item['title'])
        """
        logger.info(f"获取搜索结果: log_id={log_id}")

        try:
            # 1. 获取搜索记录 (包含基本信息)
            log = await self.repository.get_by_id(log_id)
            if not log:
                logger.warning(f"搜索记录不存在: log_id={log_id}")
                return None

            # 2. 获取搜索结果
            search_results = await self.repository.get_search_results(log_id)
            if search_results is None:
                logger.warning(f"搜索结果不存在: log_id={log_id}")
                return None

            # 3. 分页处理
            total_count = len(search_results)
            if limit is not None:
                search_results = search_results[offset:offset + limit]

            # 4. 构建响应
            return {
                "log_id": log_id,
                "query_text": log["query_text"],
                "total_count": total_count,
                "results": search_results,
                "llm_analysis": log.get("llm_analysis"),
                "status": log.get("status", "completed"),
                "created_at": log["created_at"].isoformat() if log.get("created_at") else None
            }

        except Exception as e:
            logger.error(f"获取搜索结果失败: {e}", exc_info=True)
            raise
```

### 1.4 API 端点实现

```python
# src/api/v1/endpoints/nl_search.py

@router.get(
    "/{log_id}/results",
    response_model=SearchResultsResponse,
    summary="获取搜索结果",
    description="获取自然语言搜索的所有结果"
)
async def get_search_results(
    log_id: str,
    limit: Optional[int] = Query(None, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="分页偏移量")
):
    """
    获取搜索结果

    **功能**: ✅ 完整实现

    **功能**:
    - 获取某次搜索的所有结果
    - 支持分页查询
    - 包含 LLM 分析结果

    Args:
        log_id (str): 搜索记录ID（雪花算法ID字符串）
        limit (Optional[int]): 返回数量限制 (1-100)
        offset (int): 分页偏移量

    Returns:
        SearchResultsResponse: 搜索结果详情

    Raises:
        HTTPException:
            - 503: 功能未启用
            - 404: 搜索记录不存在
            - 500: 内部错误

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search/248728141926559744/results?limit=10"
        ```
    """
    # 检查功能开关
    if not nl_search_config.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "功能未启用",
                "message": "自然语言搜索功能已关闭。设置环境变量 NL_SEARCH_ENABLED=true 启用此功能。",
                "status": "disabled"
            }
        )

    try:
        logger.info(f"获取搜索结果: log_id={log_id}, limit={limit}, offset={offset}")

        # 调用服务层
        result = await nl_search_service.get_search_results(
            log_id=log_id,
            limit=limit,
            offset=offset
        )

        if not result:
            logger.warning(f"搜索记录或结果不存在: log_id={log_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "记录不存在",
                    "message": f"未找到搜索记录或结果: log_id={log_id}",
                    "log_id": log_id
                }
            )

        # 构建响应
        return SearchResultsResponse(
            log_id=result["log_id"],
            query_text=result["query_text"],
            total_count=result["total_count"],
            results=[SearchResultItem(**r) for r in result["results"]],
            llm_analysis=result.get("llm_analysis"),
            status=result["status"],
            created_at=result["created_at"]
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"获取搜索结果失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "获取搜索结果失败，请稍后重试",
                "log_id": log_id
            }
        )
```

---

## 实现方案 2: POST /{log_id}/select

### 2.1 数据模型定义

```python
# src/api/v1/endpoints/nl_search.py

class UserSelectionRequest(BaseModel):
    """用户选择请求"""
    result_url: str = Field(..., description="选中的结果URL")
    action_type: str = Field(
        "click",
        description="操作类型: click, bookmark, archive",
        regex="^(click|bookmark|archive)$"
    )
    user_id: Optional[str] = Field(None, description="用户ID（可选）")

    class Config:
        json_schema_extra = {
            "example": {
                "result_url": "https://example.com/gpt5",
                "action_type": "click",
                "user_id": "user_123"
            }
        }


class UserSelectionResponse(BaseModel):
    """用户选择响应"""
    event_id: str = Field(..., description="事件ID")
    log_id: str = Field(..., description="搜索记录ID")
    result_url: str = Field(..., description="选中的结果URL")
    action_type: str = Field(..., description="操作类型")
    recorded_at: str = Field(..., description="记录时间")
    message: str = Field(..., description="响应消息")

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "event_123456789",
                "log_id": "248728141926559744",
                "result_url": "https://example.com/gpt5",
                "action_type": "click",
                "recorded_at": "2025-11-17T10:00:00Z",
                "message": "用户选择已记录"
            }
        }
```

### 2.2 MongoDB 集合设计

```javascript
// user_selection_events 集合
{
    "_id": "event_123456789",
    "log_id": "248728141926559744",  // 关联搜索记录
    "result_url": "https://example.com/gpt5",  // 选中的结果URL
    "action_type": "click",  // 操作类型
    "user_id": "user_123",  // 用户ID（可选）
    "selected_at": ISODate("2025-11-17T10:00:00Z"),  // 选择时间
    "user_agent": "Mozilla/5.0...",  // 用户代理（可选）
    "ip_address": "192.168.1.1"  // IP地址（可选）
}

// 索引
db.user_selection_events.createIndex({ "log_id": 1, "selected_at": -1 })
db.user_selection_events.createIndex({ "user_id": 1, "selected_at": -1 })
db.user_selection_events.createIndex({ "selected_at": -1 })
```

### 2.3 Repository 层实现

```python
# src/infrastructure/database/user_selection_repository.py (新建文件)

"""
用户选择事件仓储
记录用户对搜索结果的选择行为
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

logger = logging.getLogger(__name__)


class UserSelectionEventRepository:
    """用户选择事件仓储"""

    def __init__(self):
        self.db = None
        self.collection_name = "user_selection_events"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        if self.db is None:
            self.db = await get_mongodb_database()
        return self.db[self.collection_name]

    async def create(
        self,
        log_id: str,
        result_url: str,
        action_type: str,
        user_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        创建用户选择事件

        Args:
            log_id: 搜索记录ID
            result_url: 选中的结果URL
            action_type: 操作类型 (click, bookmark, archive)
            user_id: 用户ID（可选）
            user_agent: 用户代理（可选）
            ip_address: IP地址（可选）

        Returns:
            str: 事件ID

        Example:
            >>> event_id = await repo.create(
            ...     log_id="248728141926559744",
            ...     result_url="https://example.com/gpt5",
            ...     action_type="click",
            ...     user_id="user_123"
            ... )
        """
        collection = await self._get_collection()

        # 生成事件ID
        event_id = generate_string_id()

        # 准备文档
        document = {
            "_id": event_id,
            "log_id": log_id,
            "result_url": result_url,
            "action_type": action_type,
            "user_id": user_id,
            "selected_at": datetime.utcnow(),
            "user_agent": user_agent,
            "ip_address": ip_address
        }

        # 插入文档
        await collection.insert_one(document)

        logger.info(
            f"创建用户选择事件: event_id={event_id}, "
            f"log_id={log_id}, action={action_type}"
        )

        return event_id

    async def get_by_log_id(
        self,
        log_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取某次搜索的所有用户选择事件

        Args:
            log_id: 搜索记录ID
            limit: 返回数量限制

        Returns:
            List[Dict]: 事件列表

        Example:
            >>> events = await repo.get_by_log_id("248728141926559744")
            >>> for event in events:
            ...     print(event["result_url"], event["action_type"])
        """
        collection = await self._get_collection()

        # 查询事件（按时间倒序）
        cursor = collection.find(
            {"log_id": log_id}
        ).sort("selected_at", -1).limit(limit)

        events = await cursor.to_list(length=limit)
        return events

    async def get_by_user_id(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取某用户的所有选择事件

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            List[Dict]: 事件列表
        """
        collection = await self._get_collection()

        # 查询事件
        cursor = collection.find(
            {"user_id": user_id}
        ).sort("selected_at", -1).skip(offset).limit(limit)

        events = await cursor.to_list(length=limit)
        return events

    async def count_by_log_id(self, log_id: str) -> int:
        """统计某次搜索的选择次数"""
        collection = await self._get_collection()
        return await collection.count_documents({"log_id": log_id})

    async def create_indexes(self):
        """创建索引"""
        collection = await self._get_collection()

        # 1. log_id + 时间索引
        await collection.create_index(
            [("log_id", 1), ("selected_at", -1)],
            name="log_time_idx"
        )

        # 2. user_id + 时间索引
        await collection.create_index(
            [("user_id", 1), ("selected_at", -1)],
            name="user_time_idx"
        )

        # 3. 时间索引
        await collection.create_index(
            [("selected_at", -1)],
            name="time_idx"
        )

        logger.info("用户选择事件索引创建完成")


# 全局实例
user_selection_repository = UserSelectionEventRepository()
```

### 2.4 Service 层实现

```python
# src/services/nl_search/nl_search_service.py

# 导入新的仓储
from src.infrastructure.database.user_selection_repository import user_selection_repository

class NLSearchService:
    def __init__(self):
        # ... 现有初始化代码 ...
        self.selection_repository = user_selection_repository

    async def record_user_selection(
        self,
        log_id: str,
        result_url: str,
        action_type: str,
        user_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        记录用户选择事件

        Args:
            log_id: 搜索记录ID
            result_url: 选中的结果URL
            action_type: 操作类型
            user_id: 用户ID（可选）
            user_agent: 用户代理（可选）
            ip_address: IP地址（可选）

        Returns:
            str: 事件ID

        Raises:
            ValueError: 搜索记录不存在

        Example:
            >>> event_id = await service.record_user_selection(
            ...     log_id="248728141926559744",
            ...     result_url="https://example.com/gpt5",
            ...     action_type="click"
            ... )
        """
        logger.info(
            f"记录用户选择: log_id={log_id}, "
            f"url={result_url}, action={action_type}"
        )

        try:
            # 1. 验证搜索记录存在
            log = await self.repository.get_by_id(log_id)
            if not log:
                raise ValueError(f"搜索记录不存在: log_id={log_id}")

            # 2. 创建选择事件
            event_id = await self.selection_repository.create(
                log_id=log_id,
                result_url=result_url,
                action_type=action_type,
                user_id=user_id,
                user_agent=user_agent,
                ip_address=ip_address
            )

            logger.info(f"用户选择已记录: event_id={event_id}")
            return event_id

        except Exception as e:
            logger.error(f"记录用户选择失败: {e}", exc_info=True)
            raise

    async def get_selection_statistics(
        self,
        log_id: str
    ) -> Dict[str, Any]:
        """
        获取用户选择统计

        Args:
            log_id: 搜索记录ID

        Returns:
            Dict: 统计数据

        Example:
            >>> stats = await service.get_selection_statistics("248728141926559744")
            >>> print(f"总点击数: {stats['total_clicks']}")
        """
        logger.info(f"获取选择统计: log_id={log_id}")

        try:
            # 获取所有选择事件
            events = await self.selection_repository.get_by_log_id(log_id)

            # 统计数据
            total_count = len(events)
            click_count = sum(1 for e in events if e["action_type"] == "click")
            bookmark_count = sum(1 for e in events if e["action_type"] == "bookmark")
            archive_count = sum(1 for e in events if e["action_type"] == "archive")

            # 统计 URL 点击次数
            url_clicks = {}
            for event in events:
                url = event["result_url"]
                url_clicks[url] = url_clicks.get(url, 0) + 1

            return {
                "log_id": log_id,
                "total_count": total_count,
                "click_count": click_count,
                "bookmark_count": bookmark_count,
                "archive_count": archive_count,
                "top_urls": sorted(
                    url_clicks.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]  # 前5个最热门URL
            }

        except Exception as e:
            logger.error(f"获取选择统计失败: {e}", exc_info=True)
            raise
```

### 2.5 API 端点实现

```python
# src/api/v1/endpoints/nl_search.py

@router.post(
    "/{log_id}/select",
    response_model=UserSelectionResponse,
    summary="用户选择结果",
    description="记录用户对搜索结果的选择"
)
async def select_search_result(
    log_id: str,
    request: UserSelectionRequest,
    user_agent: Optional[str] = Header(None, alias="User-Agent"),
    x_forwarded_for: Optional[str] = Header(None, alias="X-Forwarded-For")
):
    """
    记录用户选择结果

    **功能**: ✅ 完整实现

    **用途**:
    - 收集用户反馈
    - 优化LLM理解
    - 个性化推荐

    Args:
        log_id (str): 搜索记录ID
        request (UserSelectionRequest): 选择请求
        user_agent (str): 用户代理 (自动从 Header 获取)
        x_forwarded_for (str): 客户端IP (自动从 Header 获取)

    Returns:
        UserSelectionResponse: 选择记录响应

    Raises:
        HTTPException:
            - 503: 功能未启用
            - 404: 搜索记录不存在
            - 400: 输入验证失败
            - 500: 内部错误

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/nl-search/248728141926559744/select" \\
          -H "Content-Type: application/json" \\
          -d '{
            "result_url": "https://example.com/gpt5",
            "action_type": "click",
            "user_id": "user_123"
          }'
        ```
    """
    # 检查功能开关
    if not nl_search_config.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "功能未启用",
                "message": "自然语言搜索功能已关闭。",
                "status": "disabled"
            }
        )

    try:
        logger.info(
            f"记录用户选择: log_id={log_id}, "
            f"url={request.result_url}, action={request.action_type}"
        )

        # 获取客户端IP
        ip_address = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else None

        # 调用服务层
        event_id = await nl_search_service.record_user_selection(
            log_id=log_id,
            result_url=request.result_url,
            action_type=request.action_type,
            user_id=request.user_id,
            user_agent=user_agent,
            ip_address=ip_address
        )

        # 构建响应
        return UserSelectionResponse(
            event_id=event_id,
            log_id=log_id,
            result_url=request.result_url,
            action_type=request.action_type,
            recorded_at=datetime.utcnow().isoformat(),
            message="用户选择已记录"
        )

    except ValueError as e:
        # 输入验证错误 (如搜索记录不存在)
        logger.warning(f"输入验证失败: {e}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "记录不存在",
                "message": str(e),
                "log_id": log_id
            }
        )

    except Exception as e:
        logger.error(f"记录用户选择失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "记录用户选择失败，请稍后重试",
                "log_id": log_id
            }
        )
```

---

## 数据库设计

### 索引创建脚本

```python
# scripts/create_nl_search_indexes.py (新建文件)

"""
NL Search 索引创建脚本
"""
import asyncio
import logging
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.mongo_nl_search_repository import mongo_nl_search_repository
from src.infrastructure.database.user_selection_repository import user_selection_repository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_all_indexes():
    """创建所有索引"""
    logger.info("开始创建 NL Search 索引...")

    try:
        # 1. nl_search_logs 集合索引
        await mongo_nl_search_repository.create_indexes()
        logger.info("✅ nl_search_logs 索引创建完成")

        # 2. user_selection_events 集合索引
        await user_selection_repository.create_indexes()
        logger.info("✅ user_selection_events 索引创建完成")

        logger.info("🎉 所有索引创建完成！")

    except Exception as e:
        logger.error(f"❌ 索引创建失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(create_all_indexes())
```

---

## 测试方案

### 集成测试脚本

```python
# scripts/test_nl_search_complete.py (新建文件)

"""
NL Search 完整功能测试
测试搜索结果查询和用户选择记录功能
"""
import asyncio
import logging
from src.services.nl_search.nl_search_service import nl_search_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_complete_flow():
    """测试完整流程"""
    logger.info("=" * 60)
    logger.info("NL Search 完整功能测试")
    logger.info("=" * 60)

    try:
        # 测试 1: 创建搜索 (包含结果保存)
        logger.info("\n测试 1: 创建搜索并保存结果")
        result = await nl_search_service.create_search(
            query_text="最近有哪些AI技术突破",
            user_id="test_user_001"
        )
        log_id = result["log_id"]
        logger.info(f"✅ 搜索创建成功: log_id={log_id}")
        logger.info(f"   搜索结果数: {len(result['results'])}")

        # 测试 2: 获取搜索结果
        logger.info(f"\n测试 2: 获取搜索结果 (log_id={log_id})")
        search_results = await nl_search_service.get_search_results(log_id)
        if search_results:
            logger.info(f"✅ 获取搜索结果成功")
            logger.info(f"   查询文本: {search_results['query_text']}")
            logger.info(f"   结果总数: {search_results['total_count']}")
            logger.info(f"   前3个结果:")
            for i, r in enumerate(search_results['results'][:3], 1):
                logger.info(f"     {i}. {r['title']} - {r['url']}")
        else:
            logger.error("❌ 获取搜索结果失败")
            return

        # 测试 3: 记录用户选择
        logger.info(f"\n测试 3: 记录用户选择")
        if search_results['results']:
            first_result = search_results['results'][0]
            event_id = await nl_search_service.record_user_selection(
                log_id=log_id,
                result_url=first_result['url'],
                action_type="click",
                user_id="test_user_001"
            )
            logger.info(f"✅ 用户选择已记录: event_id={event_id}")

            # 再次记录 (不同操作类型)
            event_id_2 = await nl_search_service.record_user_selection(
                log_id=log_id,
                result_url=first_result['url'],
                action_type="bookmark",
                user_id="test_user_001"
            )
            logger.info(f"✅ 书签记录已保存: event_id={event_id_2}")

        # 测试 4: 获取选择统计
        logger.info(f"\n测试 4: 获取选择统计")
        stats = await nl_search_service.get_selection_statistics(log_id)
        logger.info(f"✅ 统计数据:")
        logger.info(f"   总操作数: {stats['total_count']}")
        logger.info(f"   点击数: {stats['click_count']}")
        logger.info(f"   书签数: {stats['bookmark_count']}")
        if stats['top_urls']:
            logger.info(f"   热门URL:")
            for url, count in stats['top_urls']:
                logger.info(f"     {url} ({count}次)")

        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试通过！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
```

---

## 部署清单

### 部署步骤

```bash
# 1. 创建索引
python scripts/create_nl_search_indexes.py

# 2. 运行集成测试
python scripts/test_nl_search_complete.py

# 3. 启动服务
# (uvicorn 已在运行，无需额外操作)

# 4. API 测试
# 测试搜索结果获取
curl -X GET "http://localhost:8000/api/v1/nl-search/248728141926559744/results?limit=10"

# 测试用户选择记录
curl -X POST "http://localhost:8000/api/v1/nl-search/248728141926559744/select" \
  -H "Content-Type: application/json" \
  -d '{
    "result_url": "https://example.com/gpt5",
    "action_type": "click",
    "user_id": "user_123"
  }'
```

### 文件清单

**需要修改的文件**:
1. `src/api/v1/endpoints/nl_search.py` - API 端点实现
2. `src/services/nl_search/nl_search_service.py` - Service 层逻辑
3. `src/infrastructure/database/mongo_nl_search_repository.py` - Repository 扩展

**需要新建的文件**:
1. `src/infrastructure/database/user_selection_repository.py` - 用户选择仓储
2. `scripts/create_nl_search_indexes.py` - 索引创建脚本
3. `scripts/test_nl_search_complete.py` - 集成测试脚本

### 环境变量

```bash
# .env 文件
NL_SEARCH_ENABLED=true  # 启用 NL Search 功能
```

---

## 总结

### 实现工作量估算

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| 搜索结果查询 (`GET /{log_id}/results`) | 2-3 天 | 🔥 高 |
| 用户选择记录 (`POST /{log_id}/select`) | 1-2 天 | 🟡 中 |
| 索引创建和测试 | 0.5 天 | 🟡 中 |
| **总计** | **3.5-5.5 天** | |

### 关键技术决策

1. ✅ **搜索结果内嵌存储**: 简化查询，提升性能
2. ✅ **用户选择独立集合**: 支持行为分析和统计
3. ✅ **完整的索引设计**: 优化查询性能
4. ✅ **详细的测试方案**: 保证功能质量

### 后续优化方向

1. **行为分析系统**: 基于用户选择数据优化 LLM 理解
2. **推荐系统**: 基于历史行为提供个性化推荐
3. **A/B 测试**: 不同搜索策略的效果对比
4. **实时统计**: WebSocket 推送热门搜索结果

---

**文档版本**: v1.0
**最后更新**: 2025-11-17
**作者**: Claude Code (Backend Architect + Backend Engineer)

"""
统一结果仓储层 (v4.27.0)

聚合多个数据源的搜索结果，支持服务端筛选、排序、分页。

数据源：
- search_results: 定时任务结果 (scheduled) + 手动录入 (user_added)
- instant_search_results: 智能搜索结果 (smart-search)
- langgraph_search_results: Chat搜索结果 (chat-search)
- file_uploads: 文档上传 (upload) [v4.26.0 从 data_sources 改为 file_uploads]

v4.27.0 更新：
- 添加 TipTap JSON 纯文本提取支持
- 新增 snippet_text 字段：纯文本摘要，用于列表显示
- 新增 original_content_text 字段：纯文本原文，用于详情显示
- 保留原始 snippet 和 original_content 字段，用于编辑时的 TipTap JSON 渲染
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import re
import json

from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_text_from_tiptap(content: str) -> str:
    """从 TipTap JSON 格式中提取纯文本

    TipTap 格式示例:
    {"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"内容"}]}]}
    """
    if not content:
        return ""

    # 如果不是 JSON 格式，直接返回原内容
    if not content.strip().startswith("{"):
        return content

    try:
        data = json.loads(content)
        texts = []

        def extract_texts(node):
            """递归提取文本节点"""
            if isinstance(node, dict):
                if node.get("type") == "text" and "text" in node:
                    texts.append(node["text"])
                for value in node.values():
                    extract_texts(value)
            elif isinstance(node, list):
                for item in node:
                    extract_texts(item)

        extract_texts(data)
        return "\n".join(texts) if texts else content
    except (json.JSONDecodeError, TypeError):
        # 解析失败，返回原内容
        return content


class UnifiedResultRepository:
    """统一结果仓储 - 聚合多个数据源"""

    # 数据源映射
    SOURCE_TYPE_MAP = {
        "scheduled": {
            "collection": "search_results",
            "name": "定时任务",
            "task_collection": "search_tasks"
        },
        "smart-search": {
            "collection": "instant_search_results",
            "name": "智能搜索",
            "task_collection": "instant_search_tasks"
        },
        "chat-search": {
            "collection": "langgraph_search_results",
            "name": "智能搜索",  # Chat搜索也显示为智能搜索
            "task_collection": "chat_v2_tasks"
        },
        "upload": {
            "collection": "file_uploads",
            "name": "文档上传",
            "task_collection": None
        }
    }

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    def _get_time_range_filter(
        self,
        time_range: str,
        date_start: Optional[datetime] = None,
        date_end: Optional[datetime] = None
    ) -> Optional[Dict]:
        """获取时间范围过滤条件"""
        now = datetime.utcnow()
        today = datetime(now.year, now.month, now.day)

        if time_range == "today":
            return {"$gte": today, "$lte": now}
        elif time_range == "week":
            week_start = today - timedelta(days=today.weekday())
            return {"$gte": week_start, "$lte": now}
        elif time_range == "month":
            month_start = datetime(today.year, today.month, 1)
            return {"$gte": month_start, "$lte": now}
        elif time_range == "custom" and (date_start or date_end):
            filter_dict = {}
            if date_start:
                filter_dict["$gte"] = date_start
            if date_end:
                # 结束日期包含当天
                filter_dict["$lte"] = date_end + timedelta(days=1)
            return filter_dict if filter_dict else None

        return None

    async def _get_task_names(self, task_ids: List[str], task_collection: str) -> Dict[str, str]:
        """批量获取任务名称

        Args:
            task_ids: 任务ID列表
            task_collection: 任务集合名称

        Returns:
            {task_id: task_name} 映射字典
        """
        if not task_ids or not task_collection:
            return {}

        try:
            collection = self.db[task_collection]
            task_names = {}

            # 方法1: 使用 id 字段查询（雪花算法ID，SearchTask/InstantSearchTask 使用）
            cursor = collection.find(
                {"id": {"$in": task_ids}},
                {"id": 1, "name": 1, "keyword": 1, "query": 1}
            )
            async for doc in cursor:
                tid = doc.get("id", "")
                # 优先使用 name，其次是 keyword，最后是 query
                name = doc.get("name") or doc.get("keyword") or doc.get("query") or ""
                if tid and name:
                    task_names[tid] = name

            # 方法2: 使用 _id 字段直接查询（字符串格式，search_tasks 使用雪花ID作为_id）
            remaining_ids = [tid for tid in task_ids if tid not in task_names]
            if remaining_ids:
                cursor = collection.find(
                    {"_id": {"$in": remaining_ids}},
                    {"_id": 1, "name": 1, "keyword": 1, "query": 1}
                )
                async for doc in cursor:
                    tid = str(doc.get("_id", ""))
                    name = doc.get("name") or doc.get("keyword") or doc.get("query") or ""
                    if tid and name:
                        task_names[tid] = name

            # 方法3: 尝试用 task_id 字段查询（某些集合可能使用 task_id）
            remaining_ids = [tid for tid in task_ids if tid not in task_names]
            if remaining_ids:
                cursor = collection.find(
                    {"task_id": {"$in": remaining_ids}},
                    {"task_id": 1, "name": 1, "keyword": 1, "query": 1}
                )
                async for doc in cursor:
                    tid = doc.get("task_id", "")
                    name = doc.get("name") or doc.get("keyword") or doc.get("query") or ""
                    if tid and name:
                        task_names[tid] = name

            # 方法4: 尝试用 _id 字段查询（ObjectId 格式，兼容旧数据）
            remaining_ids = [tid for tid in task_ids if tid not in task_names]
            if remaining_ids:
                from bson import ObjectId
                valid_oids = []
                oid_to_str = {}
                for tid in remaining_ids:
                    try:
                        oid = ObjectId(tid)
                        valid_oids.append(oid)
                        oid_to_str[oid] = tid
                    except Exception:
                        pass

                if valid_oids:
                    cursor = collection.find(
                        {"_id": {"$in": valid_oids}},
                        {"_id": 1, "name": 1, "keyword": 1, "query": 1}
                    )
                    async for doc in cursor:
                        oid = doc.get("_id")
                        tid = oid_to_str.get(oid, str(oid))
                        name = doc.get("name") or doc.get("keyword") or doc.get("query") or ""
                        if tid and name:
                            task_names[tid] = name

            logger.debug(f"获取任务名称: collection={task_collection}, ids={task_ids}, found={list(task_names.keys())}")
            return task_names
        except Exception as e:
            logger.warning(f"获取任务名称失败: {e}")
            return {}

    def _extract_domain(self, url: str) -> str:
        """从URL提取域名（仅作为后备方案）"""
        if not url:
            return ""
        try:
            # 简单提取域名
            match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if match:
                return match.group(1)
            return url
        except Exception:
            return url

    async def _query_search_results(
        self,
        user_id: str,
        keyword: Optional[str] = None,
        time_filter: Optional[Dict] = None,
        task_id: Optional[str] = None,
        time_field: str = "created_at"
    ) -> List[Dict]:
        """查询定时任务结果 (search_results)"""
        collection = self.db.search_results

        query: Dict[str, Any] = {
            "user_id": user_id,
            "status": {"$nin": ["deleted"]}
        }

        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"snippet": {"$regex": keyword, "$options": "i"}}
            ]

        if time_filter:
            # 根据 time_field 选择筛选字段
            query[time_field] = time_filter

        if task_id:
            query["task_id"] = task_id

        cursor = collection.find(query)
        results = []

        async for doc in cursor:
            # 根据数据来源类型判断 origin_site 和 source_type
            data_source_type = doc.get("data_source_type", "")
            source = doc.get("source", "")

            # 判断数据来源类型
            if data_source_type == "url_crawl":
                # v4.29.0: 智能爬取（URL爬取）
                origin_site = "智能爬取"
                source_type = "url-crawl"
                source_type_name = "智能爬取"
            elif data_source_type == "user_added" or source == "translated":
                origin_site = "手动录入"
                source_type = "manual"
                source_type_name = "手动录入"
            else:
                origin_site = "定时任务"
                source_type = "scheduled"
                source_type_name = "定时任务"

            # 获取原始内容
            raw_content = doc.get("markdown_content") or doc.get("snippet", "")

            # v4.32.0: 从 news_results 嵌套字段获取翻译内容
            news_results = doc.get("news_results", {}) or {}
            translated_content = (
                news_results.get("content_zh", "") or
                news_results.get("content", "") or
                doc.get("translated_content", "")
            )
            # v4.33.0: 从 news_results 获取翻译后的标题
            translated_title = (
                news_results.get("title_zh", "") or
                news_results.get("title", "") or
                doc.get("translated_title", "")
            )

            results.append({
                "id": str(doc.get("_id") or doc.get("id", "")),
                "title": doc.get("title", ""),
                "translated_title": translated_title or None,
                "url": doc.get("url", ""),
                "snippet": doc.get("snippet", ""),  # 原始格式（可能是 TipTap JSON）
                "snippet_text": extract_text_from_tiptap(doc.get("snippet", "")),  # 纯文本，用于列表显示
                "source_type": source_type,
                "source_type_name": source_type_name,
                "origin_site": origin_site,
                "task_id": str(doc.get("task_id", "")),
                # v4.28.0: 优先使用冗余存储的 task_name
                "task_name": doc.get("task_name", ""),
                "published_date": doc.get("published_date").isoformat() if doc.get("published_date") else None,
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "original_content": raw_content,  # 原始格式（TipTap JSON），用于编辑
                "original_content_text": extract_text_from_tiptap(raw_content),  # 纯文本，用于显示
                "translated_content": translated_content,  # v4.32.0: 优先从 news_results 获取
                "_sort_date": doc.get("created_at")
            })

        return results

    async def _query_instant_search_results(
        self,
        user_id: str,
        keyword: Optional[str] = None,
        time_filter: Optional[Dict] = None,
        task_id: Optional[str] = None,
        time_field: str = "created_at"
    ) -> List[Dict]:
        """查询智能搜索结果 (instant_search_results)"""
        collection = self.db.instant_search_results

        query: Dict[str, Any] = {
            "status": {"$nin": ["deleted"]}
        }

        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"snippet": {"$regex": keyword, "$options": "i"}}
            ]

        if time_filter:
            # instant_search_results 表使用 first_found_at 作为采集时间
            db_time_field = "first_found_at" if time_field == "created_at" else time_field
            query[db_time_field] = time_filter

        if task_id:
            query["task_id"] = task_id

        cursor = collection.find(query)
        results = []

        async for doc in cursor:
            # origin_site: 直接使用数据库中的 source 字段
            origin_site = doc.get("source", "")
            snippet = doc.get("snippet", "")
            raw_content = doc.get("markdown_content") or doc.get("content") or snippet
            # v4.33.0: 翻译后的标题
            translated_title = doc.get("translated_title", "")
            results.append({
                "id": str(doc.get("_id") or doc.get("id", "")),
                "title": doc.get("title", ""),
                "translated_title": translated_title or None,
                "url": doc.get("url", ""),
                "snippet": snippet,  # 原始格式
                "snippet_text": extract_text_from_tiptap(snippet),  # 纯文本，用于列表显示
                "source_type": "smart-search",
                "source_type_name": "智能搜索",
                "origin_site": origin_site,
                "task_id": str(doc.get("task_id", "")),
                # v4.28.0: 优先使用冗余存储的 task_name
                "task_name": doc.get("task_name", ""),
                "published_date": doc.get("published_date").isoformat() if isinstance(doc.get("published_date"), datetime) else doc.get("published_date"),
                "created_at": doc.get("first_found_at").isoformat() if doc.get("first_found_at") else None,
                "original_content": raw_content,  # 原始格式（TipTap JSON），用于编辑
                "original_content_text": extract_text_from_tiptap(raw_content),  # 纯文本，用于显示
                "translated_content": doc.get("translated_content", ""),
                "_sort_date": doc.get("first_found_at")
            })

        return results

    async def _query_langgraph_results(
        self,
        user_id: str,
        keyword: Optional[str] = None,
        time_filter: Optional[Dict] = None,
        task_id: Optional[str] = None,
        time_field: str = "created_at"
    ) -> List[Dict]:
        """查询Chat搜索结果 (langgraph_search_results)"""
        collection = self.db.langgraph_search_results

        query: Dict[str, Any] = {
            "user_id": user_id,
            "status": {"$nin": ["deleted"]}
        }

        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"snippet": {"$regex": keyword, "$options": "i"}}
            ]

        if time_filter:
            # 根据 time_field 选择筛选字段
            query[time_field] = time_filter

        if task_id:
            query["task_id"] = task_id

        cursor = collection.find(query)
        results = []

        async for doc in cursor:
            # origin_site: 直接使用数据库中的 source 字段
            origin_site = doc.get("source", "")
            snippet = doc.get("snippet", "")
            raw_content = doc.get("markdown_content") or doc.get("content") or snippet

            # v4.34.0: 从 translator_dict 中提取翻译内容（与 langgraph_search_result 实体结构保持一致）
            translator_dict = doc.get("translator_dict", {}) or {}
            translated_title = translator_dict.get("title_zh", "")
            translated_content = translator_dict.get("content_zh", "")

            results.append({
                "id": str(doc.get("_id") or doc.get("id", "")),
                "title": doc.get("title", ""),
                "translated_title": translated_title or None,
                "url": doc.get("url", ""),
                "snippet": snippet,  # 原始格式
                "snippet_text": extract_text_from_tiptap(snippet),  # 纯文本，用于列表显示
                "source_type": "chat-search",
                "source_type_name": "智能搜索",  # 显示名称统一为智能搜索
                "origin_site": origin_site,
                "task_id": str(doc.get("task_id", "")),
                # v4.28.0: 优先使用冗余存储的 task_name
                "task_name": doc.get("task_name", ""),
                "published_date": doc.get("published_date").isoformat() if isinstance(doc.get("published_date"), datetime) else doc.get("published_date"),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "original_content": raw_content,  # 原始格式（TipTap JSON），用于编辑
                "original_content_text": extract_text_from_tiptap(raw_content),  # 纯文本，用于显示
                "translated_content": translated_content,
                "_sort_date": doc.get("created_at")
            })

        return results

    async def _query_file_uploads(
        self,
        user_id: str,
        keyword: Optional[str] = None,
        time_filter: Optional[Dict] = None,
        task_id: Optional[str] = None,
        time_field: str = "created_at"
    ) -> List[Dict]:
        """查询文件上传数据 (file_uploads)

        v4.26.0: 替换 _query_data_sources，直接查询 file_uploads 集合
        """
        collection = self.db.file_uploads

        query: Dict[str, Any] = {
            "uploaded_by": user_id,
            "status": {"$nin": ["deleted", "failed"]}
        }

        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"original_filename": {"$regex": keyword, "$options": "i"}},
                {"content": {"$regex": keyword, "$options": "i"}}
            ]

        if time_filter:
            # 文件上传没有 published_date，只使用 created_at
            query["created_at"] = time_filter

        cursor = collection.find(query)
        results = []

        async for doc in cursor:
            file_id = doc.get("file_id", "")
            # 标题优先使用 title，其次是 display_name，最后是 original_filename
            title = doc.get("title") or doc.get("display_name") or doc.get("original_filename", "")
            # 摘要：截取 content 前 500 字符
            content = doc.get("content", "")
            snippet = content[:500] + "..." if len(content) > 500 else content

            results.append({
                "id": file_id,
                "title": title,
                "translated_title": None,  # 文件上传不涉及翻译
                "url": doc.get("storage_url", ""),
                "snippet": snippet,  # 原始格式
                "snippet_text": extract_text_from_tiptap(snippet),  # 纯文本，用于列表显示
                "source_type": "upload",
                "source_type_name": "文档上传",
                "origin_site": "本地上传",
                "task_id": file_id,  # 使用 file_id 作为 task_id
                # v4.28.0: 文件上传使用文件标题作为 task_name
                "task_name": title,
                "published_date": None,
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "original_content": content,  # 原始格式（TipTap JSON），用于编辑
                "original_content_text": extract_text_from_tiptap(content),  # 纯文本，用于显示
                "translated_content": "",
                "_sort_date": doc.get("created_at")
            })

        return results

    async def get_by_ids(
        self,
        user_id: str,
        ids: List[str]
    ) -> List[Dict]:
        """
        按 ID 列表批量获取统一结果

        遍历所有数据源集合，按 ID 匹配。
        """
        if not ids:
            return []

        results_map: Dict[str, Dict] = {}

        # 1. search_results (scheduled) - ID 来自 _id 或 id
        try:
            collection = self.db.search_results
            cursor = collection.find({
                "$or": [
                    {"_id": {"$in": ids}},
                    {"id": {"$in": ids}}
                ]
            })
            async for doc in cursor:
                doc_id = str(doc.get("_id") or doc.get("id", ""))
                if doc_id in ids and doc_id not in results_map:
                    translated_title = doc.get("translated_title", "")
                    content = doc.get("markdown_content", "") or doc.get("content", "")
                    snippet = doc.get("snippet", "") or (content[:500] + "..." if len(content) > 500 else content)
                    results_map[doc_id] = {
                        "id": doc_id,
                        "title": doc.get("title", ""),
                        "translated_title": translated_title or None,
                        "url": doc.get("url", ""),
                        "snippet": snippet,
                        "snippet_text": extract_text_from_tiptap(snippet),
                        "source_type": "scheduled",
                        "source_type_name": "定时任务",
                        "origin_site": doc.get("origin_site", ""),
                        "task_id": str(doc.get("task_id", "")),
                        "task_name": None,
                        "published_date": doc.get("published_date").isoformat() if doc.get("published_date") else None,
                        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                        "original_content": content,
                        "original_content_text": extract_text_from_tiptap(content),
                        "translated_content": doc.get("translated_content", ""),
                    }
        except Exception as e:
            logger.warning(f"[BatchGet] search_results 查询失败: {e}")

        remaining = [i for i in ids if i not in results_map]
        if not remaining:
            return [results_map[i] for i in ids if i in results_map]

        # 2. instant_search_results (smart-search) - ID 来自 _id 或 id
        try:
            collection = self.db.instant_search_results
            cursor = collection.find({
                "$or": [
                    {"_id": {"$in": remaining}},
                    {"id": {"$in": remaining}}
                ]
            })
            async for doc in cursor:
                doc_id = str(doc.get("_id") or doc.get("id", ""))
                if doc_id in remaining and doc_id not in results_map:
                    translated_title = doc.get("translated_title", "")
                    content = doc.get("markdown_content", "") or doc.get("content", "")
                    snippet = doc.get("snippet", "") or (content[:500] + "..." if len(content) > 500 else content)
                    results_map[doc_id] = {
                        "id": doc_id,
                        "title": doc.get("title", ""),
                        "translated_title": translated_title or None,
                        "url": doc.get("url", ""),
                        "snippet": snippet,
                        "snippet_text": extract_text_from_tiptap(snippet),
                        "source_type": "smart-search",
                        "source_type_name": "智能搜索",
                        "origin_site": doc.get("origin_site", ""),
                        "task_id": str(doc.get("task_id", "")),
                        "task_name": None,
                        "published_date": doc.get("published_date").isoformat() if doc.get("published_date") else None,
                        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                        "original_content": content,
                        "original_content_text": extract_text_from_tiptap(content),
                        "translated_content": doc.get("translated_content", ""),
                    }
        except Exception as e:
            logger.warning(f"[BatchGet] instant_search_results 查询失败: {e}")

        remaining = [i for i in ids if i not in results_map]
        if not remaining:
            return [results_map[i] for i in ids if i in results_map]

        # 3. langgraph_search_results (chat-search)
        try:
            collection = self.db.langgraph_search_results
            cursor = collection.find({
                "$or": [
                    {"_id": {"$in": remaining}},
                    {"id": {"$in": remaining}}
                ]
            })
            async for doc in cursor:
                doc_id = str(doc.get("_id") or doc.get("id", ""))
                if doc_id in remaining and doc_id not in results_map:
                    translated_title = doc.get("translated_title", "")
                    translator_dict = doc.get("translator", {}) or {}
                    translated_content = translator_dict.get("content_zh", "")
                    content = doc.get("markdown_content", "") or doc.get("content", "")
                    snippet = doc.get("snippet", "") or (content[:500] + "..." if len(content) > 500 else content)
                    results_map[doc_id] = {
                        "id": doc_id,
                        "title": doc.get("title", ""),
                        "translated_title": translated_title or None,
                        "url": doc.get("url", ""),
                        "snippet": snippet,
                        "snippet_text": extract_text_from_tiptap(snippet),
                        "source_type": "chat-search",
                        "source_type_name": "对话搜索",
                        "origin_site": doc.get("origin_site", ""),
                        "task_id": str(doc.get("task_id", "") or doc.get("session_id", "")),
                        "task_name": None,
                        "published_date": doc.get("published_date").isoformat() if doc.get("published_date") else None,
                        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                        "original_content": content,
                        "original_content_text": extract_text_from_tiptap(content),
                        "translated_content": translated_content,
                    }
        except Exception as e:
            logger.warning(f"[BatchGet] langgraph_search_results 查询失败: {e}")

        remaining = [i for i in ids if i not in results_map]
        if not remaining:
            return [results_map[i] for i in ids if i in results_map]

        # 4. file_uploads (upload) - ID 来自 file_id
        try:
            collection = self.db.file_uploads
            cursor = collection.find({
                "file_id": {"$in": remaining},
                "uploaded_by": user_id,
                "status": {"$nin": ["deleted", "failed"]}
            })
            async for doc in cursor:
                file_id = doc.get("file_id", "")
                if file_id in remaining and file_id not in results_map:
                    title = doc.get("title") or doc.get("display_name") or doc.get("original_filename", "")
                    content = doc.get("content", "")
                    snippet = content[:500] + "..." if len(content) > 500 else content
                    results_map[file_id] = {
                        "id": file_id,
                        "title": title,
                        "translated_title": None,
                        "url": doc.get("storage_url", ""),
                        "snippet": snippet,
                        "snippet_text": extract_text_from_tiptap(snippet),
                        "source_type": "upload",
                        "source_type_name": "文档上传",
                        "origin_site": "本地上传",
                        "task_id": file_id,
                        "task_name": title,
                        "published_date": None,
                        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                        "original_content": content,
                        "original_content_text": extract_text_from_tiptap(content),
                        "translated_content": "",
                    }
        except Exception as e:
            logger.warning(f"[BatchGet] file_uploads 查询失败: {e}")

        # 按原始 ID 顺序返回
        return [results_map[i] for i in ids if i in results_map]

    async def query_unified_results(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        source_type: str = "all",
        time_range: str = "all",
        date_start: Optional[datetime] = None,
        date_end: Optional[datetime] = None,
        task_id: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        time_field: str = "created_at"
    ) -> Tuple[List[Dict], int, Dict[str, int]]:
        """
        统一查询多个数据源的结果

        Args:
            user_id: 用户ID
            page: 页码
            page_size: 每页数量
            keyword: 关键词搜索
            source_type: 数据源类型 (all/scheduled/smart-search/chat-search/upload)
            time_range: 时间范围 (all/today/week/month/custom)
            date_start: 自定义开始日期
            date_end: 自定义结束日期
            task_id: 任务ID筛选
            sort_by: 排序字段 (created_at/published_date)
            sort_order: 排序方向 (asc/desc)
            time_field: 时间筛选字段 (created_at=采集时间/published_date=发布时间)

        Returns:
            (items, total, statistics)
        """
        logger.info(f"查询统一结果: user_id={user_id}, source_type={source_type}, keyword={keyword}")

        # 计算时间过滤条件
        time_filter = self._get_time_range_filter(time_range, date_start, date_end)

        # 根据source_type决定查询哪些数据源
        all_results: List[Dict] = []
        statistics: Dict[str, int] = {
            "scheduled": 0,
            "smart-search": 0,
            "chat-search": 0,
            "upload": 0,
            "url-crawl": 0,
            "manual": 0
        }

        # 确定要查询的数据源
        # url-crawl 和 manual 都在 search_results 表中，需要查询 scheduled 然后按 source_type 筛选
        sources_to_query = []
        post_filter_source_type = None  # 后处理筛选（用于 url-crawl 和 manual）

        if source_type == "all":
            sources_to_query = ["scheduled", "smart-search", "chat-search", "upload"]
        elif source_type == "smart-search":
            # 智能搜索包含 smart-search 和 chat-search
            sources_to_query = ["smart-search", "chat-search"]
        elif source_type in ["url-crawl", "manual"]:
            # url-crawl 和 manual 都在 search_results 表中
            sources_to_query = ["scheduled"]
            post_filter_source_type = source_type
        else:
            sources_to_query = [source_type]

        # 并行查询各数据源
        for src in sources_to_query:
            try:
                if src == "scheduled":
                    results = await self._query_search_results(user_id, keyword, time_filter, task_id, time_field)
                    # 更新统计：按 source_type 分类
                    for r in results:
                        st = r.get("source_type", "scheduled")
                        if st in statistics:
                            statistics[st] += 1
                        else:
                            statistics["scheduled"] += 1
                    all_results.extend(results)
                elif src == "smart-search":
                    results = await self._query_instant_search_results(user_id, keyword, time_filter, task_id, time_field)
                    statistics["smart-search"] = len(results)
                    all_results.extend(results)
                elif src == "chat-search":
                    results = await self._query_langgraph_results(user_id, keyword, time_filter, task_id, time_field)
                    statistics["chat-search"] = len(results)
                    all_results.extend(results)
                elif src == "upload":
                    results = await self._query_file_uploads(user_id, keyword, time_filter, task_id, time_field)
                    statistics["upload"] = len(results)
                    all_results.extend(results)
            except Exception as e:
                logger.warning(f"查询数据源 {src} 失败: {e}")
                continue

        # v4.29.0: 后处理筛选（用于 url-crawl 和 manual）
        if post_filter_source_type:
            all_results = [r for r in all_results if r.get("source_type") == post_filter_source_type]

        # 排序
        reverse = sort_order == "desc"
        if sort_by == "published_date":
            all_results.sort(
                key=lambda x: x.get("published_date") or "",
                reverse=reverse
            )
        else:  # created_at
            all_results.sort(
                key=lambda x: x.get("_sort_date") or datetime.min,
                reverse=reverse
            )

        # 总数
        total = len(all_results)

        # 分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = all_results[start_idx:end_idx]

        # v4.28.0: 优先使用结果表中冗余存储的 task_name，仅对缺失的进行回退查询
        # 收集需要回退查询的 task_id（按 source_type 分组）
        task_ids_by_source: Dict[str, List[str]] = {}
        for item in paginated_results:
            # 如果已有 task_name，跳过
            if item.get("task_name"):
                continue

            src_type = item.get("source_type", "")
            task_id = item.get("task_id", "")
            if src_type and task_id:
                if src_type not in task_ids_by_source:
                    task_ids_by_source[src_type] = []
                if task_id not in task_ids_by_source[src_type]:
                    task_ids_by_source[src_type].append(task_id)

        # 仅对缺失 task_name 的记录进行回退查询
        all_task_names: Dict[str, str] = {}
        if task_ids_by_source:
            for src_type, task_ids in task_ids_by_source.items():
                task_collection = self.SOURCE_TYPE_MAP.get(src_type, {}).get("task_collection")
                if task_collection:
                    names = await self._get_task_names(task_ids, task_collection)
                    all_task_names.update(names)

        # 填充任务名称（仅对缺失的）并移除内部排序字段
        for item in paginated_results:
            item.pop("_sort_date", None)
            # v4.28.0: 仅在 task_name 为空时使用回退查询结果
            if not item.get("task_name"):
                task_id = item.get("task_id", "")
                item["task_name"] = all_task_names.get(task_id, "")

        logger.info(f"查询完成: total={total}, page={page}, returned={len(paginated_results)}")

        return paginated_results, total, statistics

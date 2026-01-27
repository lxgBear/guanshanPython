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
            # 尝试不同的ID字段名（不同集合可能使用不同的字段）
            task_names = {}

            # 先尝试用 task_id 字段查询
            cursor = collection.find(
                {"task_id": {"$in": task_ids}},
                {"task_id": 1, "name": 1, "keyword": 1, "query": 1}
            )
            async for doc in cursor:
                tid = doc.get("task_id", "")
                # 优先使用 name，其次是 keyword，最后是 query
                name = doc.get("name") or doc.get("keyword") or doc.get("query") or ""
                if tid and name:
                    task_names[tid] = name

            # 如果没找到，尝试用 _id 字段查询（ObjectId 转字符串）
            if not task_names:
                from bson import ObjectId
                valid_oids = []
                for tid in task_ids:
                    try:
                        valid_oids.append(ObjectId(tid))
                    except Exception:
                        pass

                if valid_oids:
                    cursor = collection.find(
                        {"_id": {"$in": valid_oids}},
                        {"_id": 1, "name": 1, "keyword": 1, "query": 1}
                    )
                    async for doc in cursor:
                        tid = str(doc.get("_id", ""))
                        name = doc.get("name") or doc.get("keyword") or doc.get("query") or ""
                        if tid and name:
                            task_names[tid] = name

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
        task_id: Optional[str] = None
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
            query["created_at"] = time_filter

        if task_id:
            query["task_id"] = task_id

        cursor = collection.find(query)
        results = []

        async for doc in cursor:
            # 根据数据来源类型判断 origin_site 和 source_type
            data_source_type = doc.get("data_source_type", "")
            source = doc.get("source", "")

            # 判断是手动录入还是定时任务
            if data_source_type == "user_added" or source == "translated":
                origin_site = "手动录入"
                source_type = "manual"
                source_type_name = "手动录入"
            else:
                origin_site = "定时任务"
                source_type = "scheduled"
                source_type_name = "定时任务"

            # 获取原始内容
            raw_content = doc.get("markdown_content") or doc.get("snippet", "")

            results.append({
                "id": str(doc.get("_id") or doc.get("id", "")),
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "snippet": doc.get("snippet", ""),  # 原始格式（可能是 TipTap JSON）
                "snippet_text": extract_text_from_tiptap(doc.get("snippet", "")),  # 纯文本，用于列表显示
                "source_type": source_type,
                "source_type_name": source_type_name,
                "origin_site": origin_site,
                "task_id": str(doc.get("task_id", "")),
                "published_date": doc.get("published_date").isoformat() if doc.get("published_date") else None,
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "original_content": raw_content,  # 原始格式（TipTap JSON），用于编辑
                "original_content_text": extract_text_from_tiptap(raw_content),  # 纯文本，用于显示
                "translated_content": doc.get("translated_content", ""),
                "_sort_date": doc.get("created_at")
            })

        return results

    async def _query_instant_search_results(
        self,
        user_id: str,
        keyword: Optional[str] = None,
        time_filter: Optional[Dict] = None,
        task_id: Optional[str] = None
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
            query["first_found_at"] = time_filter

        if task_id:
            query["task_id"] = task_id

        cursor = collection.find(query)
        results = []

        async for doc in cursor:
            # origin_site: 直接使用数据库中的 source 字段
            origin_site = doc.get("source", "")
            snippet = doc.get("snippet", "")
            raw_content = doc.get("markdown_content") or doc.get("content") or snippet
            results.append({
                "id": str(doc.get("_id") or doc.get("id", "")),
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "snippet": snippet,  # 原始格式
                "snippet_text": extract_text_from_tiptap(snippet),  # 纯文本，用于列表显示
                "source_type": "smart-search",
                "source_type_name": "智能搜索",
                "origin_site": origin_site,
                "task_id": str(doc.get("task_id", "")),
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
        task_id: Optional[str] = None
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
            query["created_at"] = time_filter

        if task_id:
            query["task_id"] = task_id

        cursor = collection.find(query)
        results = []

        async for doc in cursor:
            # origin_site: 直接使用数据库中的 source 字段
            origin_site = doc.get("source", "")
            snippet = doc.get("snippet", "")
            raw_content = doc.get("markdown_content") or doc.get("content") or snippet
            results.append({
                "id": str(doc.get("_id") or doc.get("id", "")),
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "snippet": snippet,  # 原始格式
                "snippet_text": extract_text_from_tiptap(snippet),  # 纯文本，用于列表显示
                "source_type": "chat-search",
                "source_type_name": "智能搜索",  # 显示名称统一为智能搜索
                "origin_site": origin_site,
                "task_id": str(doc.get("task_id", "")),
                "published_date": doc.get("published_date").isoformat() if isinstance(doc.get("published_date"), datetime) else doc.get("published_date"),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "original_content": raw_content,  # 原始格式（TipTap JSON），用于编辑
                "original_content_text": extract_text_from_tiptap(raw_content),  # 纯文本，用于显示
                "translated_content": doc.get("translated_content", ""),
                "_sort_date": doc.get("created_at")
            })

        return results

    async def _query_file_uploads(
        self,
        user_id: str,
        keyword: Optional[str] = None,
        time_filter: Optional[Dict] = None,
        task_id: Optional[str] = None
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
                "url": doc.get("storage_url", ""),
                "snippet": snippet,  # 原始格式
                "snippet_text": extract_text_from_tiptap(snippet),  # 纯文本，用于列表显示
                "source_type": "upload",
                "source_type_name": "文档上传",
                "origin_site": "本地上传",
                "task_id": file_id,  # 使用 file_id 作为 task_id
                "published_date": None,
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "original_content": content,  # 原始格式（TipTap JSON），用于编辑
                "original_content_text": extract_text_from_tiptap(content),  # 纯文本，用于显示
                "translated_content": "",
                "_sort_date": doc.get("created_at")
            })

        return results

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
        sort_order: str = "desc"
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
            "upload": 0
        }

        # 确定要查询的数据源
        sources_to_query = []
        if source_type == "all":
            sources_to_query = ["scheduled", "smart-search", "chat-search", "upload"]
        elif source_type == "smart-search":
            # 智能搜索包含 smart-search 和 chat-search
            sources_to_query = ["smart-search", "chat-search"]
        else:
            sources_to_query = [source_type]

        # 并行查询各数据源
        for src in sources_to_query:
            try:
                if src == "scheduled":
                    results = await self._query_search_results(user_id, keyword, time_filter, task_id)
                    statistics["scheduled"] = len(results)
                    all_results.extend(results)
                elif src == "smart-search":
                    results = await self._query_instant_search_results(user_id, keyword, time_filter, task_id)
                    statistics["smart-search"] = len(results)
                    all_results.extend(results)
                elif src == "chat-search":
                    results = await self._query_langgraph_results(user_id, keyword, time_filter, task_id)
                    statistics["chat-search"] = len(results)
                    all_results.extend(results)
                elif src == "upload":
                    results = await self._query_file_uploads(user_id, keyword, time_filter, task_id)
                    statistics["upload"] = len(results)
                    all_results.extend(results)
            except Exception as e:
                logger.warning(f"查询数据源 {src} 失败: {e}")
                continue

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

        # 批量获取任务名称
        # 按 source_type 分组收集 task_id
        task_ids_by_source: Dict[str, List[str]] = {}
        for item in paginated_results:
            src_type = item.get("source_type", "")
            task_id = item.get("task_id", "")
            if src_type and task_id:
                if src_type not in task_ids_by_source:
                    task_ids_by_source[src_type] = []
                if task_id not in task_ids_by_source[src_type]:
                    task_ids_by_source[src_type].append(task_id)

        # 查询各数据源的任务名称
        all_task_names: Dict[str, str] = {}
        for src_type, task_ids in task_ids_by_source.items():
            task_collection = self.SOURCE_TYPE_MAP.get(src_type, {}).get("task_collection")
            if task_collection:
                names = await self._get_task_names(task_ids, task_collection)
                all_task_names.update(names)

        # 填充任务名称并移除内部排序字段
        for item in paginated_results:
            item.pop("_sort_date", None)
            task_id = item.get("task_id", "")
            item["task_name"] = all_task_names.get(task_id, "")

        logger.info(f"查询完成: total={total}, page={page}, returned={len(paginated_results)}")

        return paginated_results, total, statistics

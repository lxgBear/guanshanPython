"""
MongoDB LangGraph 搜索结果 Repository 实现

v4.5.2 新增：专门用于 LangGraph 智能搜索系统的数据访问实现

与 MongoResultRepository 的关系：
- 使用独立的 MongoDB 集合：langgraph_search_results
- 支持 LangGraph 特定字段：layer, layer_name, source_tier, category
- 实现与 search_results 的数据隔离

v4.8.0: 移除评分字段存储 - 评分在内存中计算，不需要持久化
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from src.core.domain.entities.langgraph_search_result import (
    LangGraphSearchResult,
    LangGraphSearchResultBatch,
    ResultStatus,
    LangGraphResultStatus  # v4.7.0: 结果处理状态枚举
)
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoLangGraphResultRepository:
    """MongoDB LangGraph 搜索结果 Repository 实现

    v4.5.2 新增：专门用于存储 LangGraph 智能搜索结果

    特点：
    - 独立集合：langgraph_search_results
    - 支持 LangGraph 特定字段
    - 基于 content_hash 去重

    v4.28.0 更新：
    - 保存时自动从 chat_conversations 获取 task_name
    """

    def __init__(self):
        self.collection_name = "langgraph_search_results"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    async def _get_task_name_from_conversation(self, conversation_id: str) -> Optional[str]:
        """从 chat_conversations 获取任务名称

        v4.28.0 新增：用于冗余存储 task_name

        Args:
            conversation_id: 对话会话 ID

        Returns:
            任务名称（对话标题），如果不存在则返回 None
        """
        if not conversation_id:
            return None

        try:
            db = await get_mongodb_database()
            collection = db["chat_conversations"]
            doc = await collection.find_one(
                {"_id": conversation_id},
                {"title": 1}  # chat_conversations 使用 title 字段
            )
            if doc:
                return doc.get("title")
            return None
        except Exception as e:
            logger.warning(f"获取 conversation title 失败: {e}")
            return None

    def _result_to_dict(self, result: LangGraphSearchResult) -> Dict[str, Any]:
        """将 LangGraph 结果实体转换为 MongoDB 文档

        v4.8.0: 移除评分字段存储 - relevance_score, quality_score, credibility_score,
                final_score, multi_source_bonus, recency_bonus, layer_weight 不再存入数据库
        """
        # 继承父类的基础字段
        base_dict = {
            "_id": str(result.id),
            "task_id": str(result.task_id),
            # v4.28.0: 任务名称冗余存储（来自 chat_conversations.name）
            "task_name": result.task_name,
            # v4.6.0: 关联对话会话（用于前端查询历史会话的搜索结果）
            "conversation_id": result.conversation_id,
            "user_id": str(result.user_id),
            "created_by": str(result.created_by),
            "title": result.title,
            "url": result.url,
            "snippet": result.snippet,
            "source": result.source,
            "published_date": result.published_date,
            "author": result.author,
            "language": result.language,
            "markdown_content": result.markdown_content,
            # v4.9.2: 移除 html_content 字段
            "article_tag": result.article_tag,
            "article_published_time": result.article_published_time,
            "source_url": result.source_url,
            "http_status_code": result.http_status_code,
            "search_position": result.search_position,
            "content_hash": result.content_hash,
            "metadata": result.metadata,
            # v4.8.0: 移除评分字段存储
            "status": result.status.value if isinstance(result.status, ResultStatus) else result.status,
            "created_at": result.created_at,
            "processed_at": result.processed_at,
            "is_test_data": result.is_test_data,
            # LangGraph 特定字段
            "layer": result.layer,
            "layer_name": result.layer_name,
            "source_tier": result.source_tier,
            # v4.8.0: 移除评分字段存储
            "category": result.category,
            # v4.5.3: 数据来源分类
            "data_source_type": result.data_source_type,
            # v4.5.3: AI 处理状态标记
            "ai_processed": result.ai_processed,
            "ai_processed_at": result.ai_processed_at,
            "ai_model": result.ai_model,
            # v4.5.5: AI 翻译状态与内容
            "translator_status": result.translator_status,
            "translator_dict": result.translator_dict,
            # v4.5.5: 数据转移标记
            "transferred_to_news": result.transferred_to_news,
            "transferred_at": result.transferred_at,
            # v4.7.0: 结果处理状态
            "langgraph_status": result.langgraph_status,
        }
        return base_dict

    def _dict_to_result(self, data: Dict[str, Any]) -> LangGraphSearchResult:
        """将 MongoDB 文档转换为 LangGraph 结果实体

        v4.8.0: 评分字段从数据库读取时使用默认值（向后兼容旧数据）
        """
        # 处理状态
        status_value = data.get("status", "pending")
        try:
            status = ResultStatus(status_value)
        except ValueError:
            logger.warning(f"⚠️ 检测到未知状态值 '{status_value}'，使用 PENDING")
            status = ResultStatus.PENDING

        # 处理 article_tag
        article_tag_raw = data.get("article_tag")
        if isinstance(article_tag_raw, list):
            article_tag = ', '.join(str(tag) for tag in article_tag_raw) if article_tag_raw else None
        else:
            article_tag = article_tag_raw

        return LangGraphSearchResult(
            id=str(data.get("_id", data.get("id", ""))),
            task_id=str(data.get("task_id", "")),
            # v4.28.0: 任务名称冗余存储（来自 chat_conversations.name）
            task_name=data.get("task_name"),
            # v4.6.0: 关联对话会话
            conversation_id=data.get("conversation_id"),
            user_id=str(data.get("user_id", "")),
            created_by=str(data.get("created_by", "")),
            title=data.get("title", ""),
            url=data.get("url", ""),
            snippet=data.get("snippet"),
            source=data.get("source", "web"),
            published_date=data.get("published_date"),
            author=data.get("author"),
            language=data.get("language"),
            markdown_content=data.get("markdown_content"),
            # v4.9.2: 移除 html_content 字段（旧数据读取时忽略）
            article_tag=article_tag,
            article_published_time=data.get("article_published_time"),
            source_url=data.get("source_url"),
            http_status_code=data.get("http_status_code"),
            search_position=data.get("search_position"),
            content_hash=data.get("content_hash"),
            metadata=data.get("metadata", {}),
            # v4.8.1: 评分字段已删除，不再从数据库读取
            status=status,
            created_at=data.get("created_at", datetime.utcnow()),
            processed_at=data.get("processed_at"),
            is_test_data=data.get("is_test_data", False),
            # LangGraph 特定字段
            layer=data.get("layer", 0),
            layer_name=data.get("layer_name", ""),
            source_tier=data.get("source_tier", 1),
            # v4.8.1: LangGraph 评分字段已删除，不再从数据库读取
            category=data.get("category"),
            # v4.5.3: 数据来源分类
            data_source_type=data.get("data_source_type", "langgraph"),
            # v4.5.3: AI 处理状态标记
            ai_processed=data.get("ai_processed", False),
            ai_processed_at=data.get("ai_processed_at"),
            ai_model=data.get("ai_model"),
            # v4.5.5: AI 翻译状态与内容
            translator_status=data.get("translator_status"),
            translator_dict=data.get("translator_dict"),
            # v4.5.5: 数据转移标记
            transferred_to_news=data.get("transferred_to_news", False),
            transferred_at=data.get("transferred_at"),
            # v4.7.0: 结果处理状态
            langgraph_status=data.get("langgraph_status", "pending"),
        )

    # ==================== 基础 CRUD 方法 ====================

    async def create(self, entity: LangGraphSearchResult) -> str:
        """创建搜索结果"""
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(entity)

            await collection.insert_one(result_dict)
            logger.info(f"✅ 创建 LangGraph 搜索结果: {entity.title[:50]} (ID: {entity.id}, layer: {entity.layer})")

            return str(entity.id)

        except Exception as e:
            logger.error(f"❌ 创建 LangGraph 搜索结果失败: {e}")
            raise

    async def get_by_id(self, id: str) -> Optional[LangGraphSearchResult]:
        """根据 ID 获取搜索结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取 LangGraph 搜索结果失败 (ID: {id}): {e}")
            raise

    async def update(self, entity: LangGraphSearchResult) -> bool:
        """更新搜索结果"""
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(entity)
            result_dict.pop("_id")

            result = await collection.update_one(
                {"_id": str(entity.id)},
                {"$set": result_dict}
            )

            if result.matched_count > 0:
                logger.info(f"✅ 更新 LangGraph 搜索结果: {entity.title[:50]} (ID: {entity.id})")
                return result.modified_count > 0

            return False

        except Exception as e:
            logger.error(f"❌ 更新 LangGraph 搜索结果失败: {e}")
            raise

    async def delete(self, id: str) -> bool:
        """删除搜索结果"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": id})

            if result.deleted_count > 0:
                logger.info(f"✅ 删除 LangGraph 搜索结果: {id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 删除 LangGraph 搜索结果失败: {e}")
            raise

    # ==================== v4.7.0: 部分更新方法 ====================

    async def update_partial(
        self,
        result_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """部分更新搜索结果字段

        v4.7.0 新增：支持只更新指定字段，而不是整个实体

        Args:
            result_id: 结果 ID
            updates: 要更新的字段字典，支持的字段包括：
                - title: 标题
                - snippet: 摘要
                - markdown_content: Markdown 内容
                - langgraph_status: 处理状态 (pending/transferred/discarded)
                - category: 分类信息

        Returns:
            是否更新成功（找到并修改了记录返回 True）

        Raises:
            ValueError: 如果 updates 为空或包含不允许更新的字段
        """
        if not updates:
            logger.warning("⚠️ update_partial 调用但 updates 为空")
            return False

        # 允许更新的字段白名单
        allowed_fields = {
            "title", "snippet", "markdown_content",
            "langgraph_status", "category"
        }

        # 验证字段
        invalid_fields = set(updates.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"不允许更新的字段: {invalid_fields}")

        # 验证 langgraph_status 值
        if "langgraph_status" in updates:
            status_value = updates["langgraph_status"]
            valid_statuses = {s.value for s in LangGraphResultStatus}
            if status_value not in valid_statuses:
                raise ValueError(
                    f"无效的 langgraph_status 值: {status_value}, "
                    f"有效值: {valid_statuses}"
                )

        try:
            collection = await self._get_collection()

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": updates}
            )

            if result.matched_count > 0:
                updated_fields = list(updates.keys())
                logger.info(
                    f"✅ 部分更新 LangGraph 结果 (ID: {result_id}): "
                    f"更新字段 {updated_fields}"
                )
                return result.modified_count > 0

            logger.warning(f"⚠️ 未找到要更新的结果 (ID: {result_id})")
            return False

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ 部分更新 LangGraph 结果失败 (ID: {result_id}): {e}")
            raise

    async def batch_update_status(
        self,
        result_ids: List[str],
        langgraph_status: str
    ) -> Dict[str, Any]:
        """批量更新结果处理状态

        v4.7.0 新增：支持批量修改多个结果的处理状态

        Args:
            result_ids: 结果 ID 列表 (最多 100 条)
            langgraph_status: 新状态 (pending/transferred/discarded)

        Returns:
            更新结果统计: {
                "success": True/False,
                "updated": 更新成功数量,
                "failed": 更新失败数量,
                "total": 总请求数量,
                "updated_ids": 成功更新的 ID 列表,
                "failed_ids": 失败的 ID 列表
            }

        Raises:
            ValueError: 如果 result_ids 为空、超过 100 条或状态值无效
        """
        # 参数验证
        if not result_ids:
            raise ValueError("result_ids 不能为空")

        if len(result_ids) > 100:
            raise ValueError(f"批量更新最多支持 100 条，当前请求 {len(result_ids)} 条")

        # 验证状态值
        valid_statuses = {s.value for s in LangGraphResultStatus}
        if langgraph_status not in valid_statuses:
            raise ValueError(
                f"无效的 langgraph_status 值: {langgraph_status}, "
                f"有效值: {valid_statuses}"
            )

        try:
            collection = await self._get_collection()

            # 批量更新
            result = await collection.update_many(
                {"_id": {"$in": result_ids}},
                {"$set": {"langgraph_status": langgraph_status}}
            )

            updated_count = result.modified_count
            matched_count = result.matched_count

            # 如果 matched_count < len(result_ids)，说明有些 ID 不存在
            failed_count = len(result_ids) - matched_count

            # 获取实际更新的 ID（简化处理：假设匹配的都更新了）
            # 注意：MongoDB update_many 不返回具体哪些 ID 被更新
            # 如需精确追踪，需要逐条更新或额外查询
            updated_ids = []
            failed_ids = []

            if matched_count > 0:
                # 查询确认哪些 ID 存在且状态已更新
                async for doc in collection.find(
                    {"_id": {"$in": result_ids}, "langgraph_status": langgraph_status},
                    {"_id": 1}
                ):
                    updated_ids.append(doc["_id"])

            # 计算失败的 ID
            updated_set = set(updated_ids)
            failed_ids = [rid for rid in result_ids if rid not in updated_set]

            logger.info(
                f"✅ 批量更新 LangGraph 结果状态为 '{langgraph_status}': "
                f"成功 {len(updated_ids)}/{len(result_ids)} 条"
            )

            return {
                "success": len(updated_ids) > 0,
                "updated": len(updated_ids),
                "failed": len(failed_ids),
                "total": len(result_ids),
                "updated_ids": updated_ids,
                "failed_ids": failed_ids
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ 批量更新 LangGraph 结果状态失败: {e}")
            raise

    # ==================== 查询方法 ====================

    async def find_by_task_id(
        self,
        task_id: str,
        limit: Optional[int] = None
    ) -> List[LangGraphSearchResult]:
        """根据任务 ID 查询搜索结果"""
        try:
            collection = await self._get_collection()
            query = {"task_id": task_id}
            cursor = collection.find(query)

            if limit:
                cursor = cursor.limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 按任务 ID 查询 LangGraph 搜索结果失败: {e}")
            raise

    async def find_by_task_and_layer(
        self,
        task_id: str,
        layer: int,
        limit: Optional[int] = None
    ) -> List[LangGraphSearchResult]:
        """根据任务 ID 和层级查询搜索结果"""
        try:
            collection = await self._get_collection()
            query = {"task_id": task_id, "layer": layer}
            cursor = collection.find(query)

            if limit:
                cursor = cursor.limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 按任务 ID 和层级查询失败: {e}")
            raise

    async def find_by_user(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[LangGraphSearchResult]:
        """根据用户 ID 查询搜索结果"""
        try:
            collection = await self._get_collection()
            cursor = collection.find({"user_id": user_id}).sort("created_at", -1)

            if limit:
                cursor = cursor.limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 按用户 ID 查询 LangGraph 搜索结果失败: {e}")
            raise

    async def count_by_task(self, task_id: str) -> int:
        """统计任务的搜索结果数量"""
        try:
            collection = await self._get_collection()
            return await collection.count_documents({"task_id": task_id})

        except Exception as e:
            logger.error(f"❌ 统计任务 LangGraph 搜索结果数量失败: {e}")
            raise

    async def count_by_task_and_layer(self, task_id: str) -> Dict[int, int]:
        """统计任务各层级的搜索结果数量

        Returns:
            {0: 5, 1: 10, 2: 3, ...}
        """
        try:
            collection = await self._get_collection()

            pipeline = [
                {"$match": {"task_id": task_id}},
                {"$group": {"_id": "$layer", "count": {"$sum": 1}}}
            ]

            layer_counts = {}
            async for doc in collection.aggregate(pipeline):
                layer_counts[doc["_id"]] = doc["count"]

            return layer_counts

        except Exception as e:
            logger.error(f"❌ 统计任务各层级结果数量失败: {e}")
            raise

    # ==================== 批量操作 ====================

    async def save_results(
        self,
        results: List[LangGraphSearchResult],
        enable_dedup: bool = True
    ) -> Dict[str, int]:
        """批量保存 LangGraph 搜索结果（支持去重）

        Args:
            results: LangGraph 搜索结果列表
            enable_dedup: 是否启用去重（默认 True）

        Returns:
            保存统计信息: {"saved": 10, "duplicates": 2, "total": 12, "skipped_no_title": 1, "url_duplicates": 3}

        v4.28.0 更新：
            - 自动从 chat_conversations 获取 task_name 并设置到结果中
        """
        if not results:
            return {"saved": 0, "duplicates": 0, "total": 0, "skipped_no_title": 0, "url_duplicates": 0}

        try:
            collection = await self._get_collection()

            # v4.28.0: 批量获取 task_name（按 conversation_id 分组以减少查询次数）
            conversation_ids = set(r.conversation_id for r in results if r.conversation_id and not r.task_name)
            task_name_cache: Dict[str, Optional[str]] = {}
            for conv_id in conversation_ids:
                task_name_cache[conv_id] = await self._get_task_name_from_conversation(conv_id)

            # 设置 task_name
            for result in results:
                if not result.task_name and result.conversation_id:
                    result.task_name = task_name_cache.get(result.conversation_id)

            # v4.5.3: 过滤掉 title 为空的记录
            valid_results = []
            skipped_no_title = 0

            for result in results:
                if not result.title or not result.title.strip():
                    skipped_no_title += 1
                    logger.debug(f"跳过无标题记录: {result.url}")
                else:
                    valid_results.append(result)

            if skipped_no_title > 0:
                logger.info(f"⚠️ 跳过 {skipped_no_title} 条无标题记录")

            if not valid_results:
                logger.info("没有有效记录可保存（全部无标题）")
                return {"saved": 0, "duplicates": 0, "total": len(results), "skipped_no_title": skipped_no_title, "url_duplicates": 0}

            # 如果不启用去重，直接批量插入
            if not enable_dedup:
                result_dicts = [self._result_to_dict(result) for result in valid_results]
                await collection.insert_many(result_dicts)
                logger.info(f"保存 LangGraph 搜索结果成功（未去重）: {len(valid_results)}条")
                return {
                    "saved": len(valid_results),
                    "duplicates": 0,
                    "total": len(results),
                    "skipped_no_title": skipped_no_title,
                    "url_duplicates": 0
                }

            # ==================== v4.22.0: URL 去重逻辑 ====================
            # 1. 提取所有 URL
            urls = [result.url for result in valid_results if result.url]

            # 2. 查询数据库中已存在的 URL
            existing_urls = set()
            if urls:
                async for doc in collection.find(
                    {"url": {"$in": urls}},
                    {"url": 1}
                ):
                    existing_urls.add(doc.get("url"))

            # 3. 过滤出 URL 不存在的结果
            url_new_results = []
            url_duplicate_count = 0

            for result in valid_results:
                if result.url in existing_urls:
                    url_duplicate_count += 1
                    logger.debug(f"跳过重复URL: {result.url}")
                else:
                    url_new_results.append(result)
                    # 将当前 URL 加入已存在集合，避免同批次重复
                    existing_urls.add(result.url)

            if url_duplicate_count > 0:
                logger.info(f"⚠️ 跳过 {url_duplicate_count} 条重复URL记录")

            # ==================== content_hash 二次去重 ====================
            # 4. 确保所有结果都有 content_hash
            for result in url_new_results:
                result.ensure_content_hash()

            # 5. 获取所有 content_hash
            content_hashes = [result.content_hash for result in url_new_results]

            # 6. 查询数据库中已存在的 content_hash
            existing_hashes = set()
            if content_hashes:
                async for doc in collection.find(
                    {"content_hash": {"$in": content_hashes}},
                    {"content_hash": 1}
                ):
                    existing_hashes.add(doc.get("content_hash"))

            # 7. 过滤出新结果
            new_results = []
            duplicate_count = 0

            for result in url_new_results:
                if result.content_hash not in existing_hashes:
                    new_results.append(result)
                    # 将当前 hash 加入已存在集合，避免同批次重复
                    existing_hashes.add(result.content_hash)
                else:
                    duplicate_count += 1
                    logger.debug(f"跳过重复内容: {result.url} (hash: {result.content_hash})")

            # 8. 保存新结果
            if new_results:
                result_dicts = [self._result_to_dict(result) for result in new_results]
                await collection.insert_many(result_dicts)
                logger.info(
                    f"保存 LangGraph 搜索结果成功: "
                    f"新增{len(new_results)}条, 跳过URL重复{url_duplicate_count}条, "
                    f"跳过内容重复{duplicate_count}条, 跳过无标题{skipped_no_title}条"
                )
            else:
                logger.info(
                    f"无新结果保存: URL重复{url_duplicate_count}条, 内容重复{duplicate_count}条"
                    f"{f', 跳过无标题{skipped_no_title}条' if skipped_no_title > 0 else ''}"
                )

            return {
                "saved": len(new_results),
                "duplicates": duplicate_count,
                "total": len(results),
                "skipped_no_title": skipped_no_title,
                "url_duplicates": url_duplicate_count
            }

        except Exception as e:
            logger.error(f"保存 LangGraph 搜索结果失败: {e}")
            raise

    async def bulk_create(self, entities: List[LangGraphSearchResult]) -> List[str]:
        """批量创建搜索结果"""
        if not entities:
            return []

        try:
            collection = await self._get_collection()
            result_dicts = [self._result_to_dict(entity) for entity in entities]

            result = await collection.insert_many(result_dicts)
            logger.info(f"✅ 批量创建 LangGraph 搜索结果: {len(result.inserted_ids)} 条")

            return [str(id) for id in result.inserted_ids]

        except Exception as e:
            logger.error(f"❌ 批量创建 LangGraph 搜索结果失败: {e}")
            raise

    async def delete_by_task_id(self, task_id: str) -> int:
        """删除任务的所有搜索结果"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_many({"task_id": task_id})

            logger.info(f"✅ 删除任务 LangGraph 搜索结果: {task_id}, 删除数量: {result.deleted_count}")
            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 删除任务 LangGraph 搜索结果失败: {e}")
            raise

    # ==================== 统计方法 ====================

    async def get_task_statistics(self, task_id: str) -> Dict[str, Any]:
        """获取任务的搜索结果统计信息

        Returns:
            统计信息: {
                "total": 50,
                "by_layer": {0: 5, 1: 15, 2: 10, 3: 12, 4: 8},
                "avg_scores": {"relevance": 0.75, "credibility": 0.80, "final": 0.78},
                "top_sources": ["xinhuanet.com", "reuters.com", ...]
            }
        """
        try:
            collection = await self._get_collection()

            # 总数
            total = await collection.count_documents({"task_id": task_id})

            # 按层级统计
            pipeline_layer = [
                {"$match": {"task_id": task_id}},
                {"$group": {"_id": "$layer", "count": {"$sum": 1}}}
            ]
            by_layer = {}
            async for doc in collection.aggregate(pipeline_layer):
                by_layer[doc["_id"]] = doc["count"]

            # 平均分数
            # 保留 avg_scores 结构以保持向后兼容，但返回空值
            avg_scores = {"relevance": None, "credibility": None, "final": None}

            # 顶级来源
            pipeline_sources = [
                {"$match": {"task_id": task_id}},
                {"$group": {"_id": "$source", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]

            top_sources = []
            async for doc in collection.aggregate(pipeline_sources):
                top_sources.append({"source": doc["_id"], "count": doc["count"]})

            return {
                "total": total,
                "by_layer": by_layer,
                "avg_scores": avg_scores,
                "top_sources": top_sources,
            }

        except Exception as e:
            logger.error(f"❌ 获取任务统计信息失败: {e}")
            raise

    async def check_existing_urls(self, urls: List[str]) -> set:
        """检查哪些 URL 已存在于数据库（全局 URL 去重）

        Args:
            urls: URL 列表

        Returns:
            已存在的 URL 集合
        """
        try:
            collection = await self._get_collection()

            existing_urls = set()
            async for doc in collection.find(
                {"url": {"$in": urls}},
                {"url": 1}
            ):
                existing_urls.add(doc.get("url"))

            if existing_urls:
                logger.debug(f"发现{len(existing_urls)}个已存在的 URL（全局去重）")

            return existing_urls

        except Exception as e:
            logger.error(f"检查已存在 URL 失败: {e}")
            raise

    # ==================== v4.5.6: 任务列表聚合方法 ====================

    async def get_distinct_tasks(
        self,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[Dict[str, Any]], int]:
        """获取有 LangGraph 结果的任务列表（聚合查询）

        v4.5.6 新增：用于前端"库外信息" Tab 展示任务选择器

        Args:
            keyword: 搜索关键词（搜索 task_id 或结果标题）
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            (任务摘要列表, 总任务数量)
            每个任务包含: task_id, result_count, created_at, updated_at, statistics
        """
        try:
            collection = await self._get_collection()

            # v4.5.7: 构建聚合管道
            pipeline = []

            # 1. 始终过滤掉空 task_id 的记录（排除 null、空字符串、"None" 字符串）
            pipeline.append({"$match": {
                "task_id": {"$exists": True, "$nin": [None, "", "None"]}
            }})

            # 2. 添加关键词搜索条件（可选）
            if keyword:
                pipeline.append({"$match": {
                    "$or": [
                        {"task_id": {"$regex": keyword, "$options": "i"}},
                        {"title": {"$regex": keyword, "$options": "i"}}
                    ]
                }})

            # 3. 按 task_id 分组，计算统计信息
            pipeline.append({
                "$group": {
                    "_id": "$task_id",
                    "result_count": {"$sum": 1},
                    "created_at": {"$min": "$created_at"},
                    "updated_at": {"$max": "$created_at"},
                    # 层级分布
                    "layer_0_count": {"$sum": {"$cond": [{"$eq": ["$layer", 0]}, 1, 0]}},
                    "layer_1_count": {"$sum": {"$cond": [{"$eq": ["$layer", 1]}, 1, 0]}},
                    "layer_2_count": {"$sum": {"$cond": [{"$eq": ["$layer", 2]}, 1, 0]}},
                    "layer_3_count": {"$sum": {"$cond": [{"$eq": ["$layer", 3]}, 1, 0]}},
                    "layer_4_count": {"$sum": {"$cond": [{"$eq": ["$layer", 4]}, 1, 0]}},
                    # 取最新的一条结果的标题作为 query 推断
                    "sample_titles": {"$push": "$title"},
                }
            })

            # 4. 按更新时间降序排序
            pipeline.append({"$sort": {"updated_at": -1}})

            # 5. 先获取总数（不带分页）
            count_pipeline = pipeline.copy()
            count_pipeline.append({"$count": "total"})

            total = 0
            async for doc in collection.aggregate(count_pipeline):
                total = doc.get("total", 0)

            # 6. 分页
            skip = (page - 1) * page_size
            pipeline.append({"$skip": skip})
            pipeline.append({"$limit": page_size})

            # 执行聚合
            tasks = []
            async for doc in collection.aggregate(pipeline):
                # 构建统计信息
                # v4.8.0: avg_scores 改为空值，评分字段不再存储
                statistics = {
                    "by_layer": {
                        0: doc.get("layer_0_count", 0),
                        1: doc.get("layer_1_count", 0),
                        2: doc.get("layer_2_count", 0),
                        3: doc.get("layer_3_count", 0),
                        4: doc.get("layer_4_count", 0),
                    },
                    "avg_scores": {
                        "final": None,
                        "relevance": None,
                        "credibility": None,
                    }
                }

                # 从 sample_titles 中取第一个非空标题作为 query 推断
                sample_titles = doc.get("sample_titles", [])
                query = None
                if sample_titles:
                    # 取最新的标题（列表末尾）
                    for title in reversed(sample_titles[:5]):
                        if title and title.strip():
                            query = title[:50] + ("..." if len(title) > 50 else "")
                            break

                tasks.append({
                    "task_id": doc["_id"],
                    "query": query,
                    "result_count": doc.get("result_count", 0),
                    "created_at": doc.get("created_at"),
                    "updated_at": doc.get("updated_at"),
                    "statistics": statistics,
                })

            logger.info(
                f"获取 LangGraph 任务列表: keyword={keyword}, "
                f"page={page}/{(total + page_size - 1) // page_size if total > 0 else 1}, "
                f"返回 {len(tasks)}/{total} 个任务"
            )

            return tasks, total

        except Exception as e:
            logger.error(f"❌ 获取 LangGraph 任务列表失败: {e}")
            raise

    # ==================== v4.5.4: 分页查询方法 ====================

    async def find_with_pagination(
        self,
        task_id: Optional[str] = None,
        conversation_id: Optional[str] = None,  # v4.6.0: 支持按 conversation_id 查询
        keyword: Optional[str] = None,
        layer: Optional[int] = None,
        min_score: Optional[float] = None,  # v4.8.0: 保留参数兼容性，但不再使用
        translator_status: Optional[str] = None,
        only_translated: bool = False,
        exclude_transferred: bool = False,
        langgraph_status: Optional[List[str]] = None,  # v4.7.0: 处理状态筛选
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",  # v4.8.0: 排序字段
        sort_order: str = "desc"
    ) -> tuple[List[LangGraphSearchResult], int]:
        """分页查询 LangGraph 搜索结果（支持模糊搜索）

        v4.5.4 新增
        v4.5.5 更新: 新增 translator_status, only_translated, exclude_transferred 筛选
        v4.6.0 更新: 支持按 conversation_id 查询（与 task_id 二选一）
        v4.7.0 更新: 新增 langgraph_status 筛选（支持多选）
        v4.8.0 更新: 移除评分字段排序，改用 created_at

        Args:
            task_id: 任务 ID（与 conversation_id 二选一）
            conversation_id: 对话会话 ID（与 task_id 二选一，用于前端查询历史会话的搜索结果）
            keyword: 模糊搜索关键词（搜索 title）
            layer: 筛选层级 (0-4)
            min_score: 最低分数筛选（v4.8.0: 保留参数兼容性，但不再使用）
            translator_status: 翻译状态筛选 (pending/processing/completed/failed)
            only_translated: 仅返回 translator_status 有值的记录
            exclude_transferred: 排除已转移到 news_results 的记录
            langgraph_status: 处理状态筛选列表 (pending/transferred/discarded)，支持多选
            page: 页码（从 1 开始）
            page_size: 每页数量（最大 100）
            sort_by: 排序字段（created_at, layer, source_tier）
            sort_order: 排序方向（asc, desc）

        Returns:
            (结果列表, 总数量)

        Raises:
            ValueError: 如果 task_id 和 conversation_id 都为空
        """
        # v4.6.0: 验证至少有一个查询条件
        if not task_id and not conversation_id:
            raise ValueError("task_id 和 conversation_id 必须至少提供一个")

        try:
            collection = await self._get_collection()

            # v4.6.0: 构建查询条件（支持 task_id 或 conversation_id）
            query: Dict[str, Any] = {}
            if task_id:
                query["task_id"] = task_id
            if conversation_id:
                query["conversation_id"] = conversation_id

            # 模糊搜索 title
            if keyword:
                query["title"] = {"$regex": keyword, "$options": "i"}

            # 层级筛选
            if layer is not None:
                query["layer"] = layer

            # if min_score is not None:

            # v4.5.5: 翻译状态筛选
            if translator_status:
                query["translator_status"] = translator_status
            elif only_translated:
                # 仅返回 translator_status 有值的记录
                query["translator_status"] = {"$ne": None, "$exists": True}

            # v4.5.5: 排除已转移的记录
            if exclude_transferred:
                query["transferred_to_news"] = {"$ne": True}

            # v4.7.0: 处理状态筛选（支持多选）
            if langgraph_status:
                # 验证状态值
                valid_statuses = {s.value for s in LangGraphResultStatus}
                invalid_statuses = set(langgraph_status) - valid_statuses
                if invalid_statuses:
                    logger.warning(
                        f"⚠️ 忽略无效的 langgraph_status 值: {invalid_statuses}"
                    )
                    langgraph_status = [s for s in langgraph_status if s in valid_statuses]

                if langgraph_status:
                    if len(langgraph_status) == 1:
                        query["langgraph_status"] = langgraph_status[0]
                    else:
                        query["langgraph_status"] = {"$in": langgraph_status}

            # 排序方向
            sort_direction = -1 if sort_order == "desc" else 1

            # v4.8.0: 验证排序字段（移除评分字段）
            valid_sort_fields = ["created_at", "layer", "source_tier"]
            if sort_by not in valid_sort_fields:
                sort_by = "created_at"

            # 计算总数
            total = await collection.count_documents(query)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(query).sort(sort_by, sort_direction).skip(skip).limit(page_size)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            # v4.6.0: 更新日志以反映查询方式
            query_desc = f"task_id={task_id}" if task_id else f"conversation_id={conversation_id}"
            logger.info(
                f"分页查询 LangGraph 结果: {query_desc}, "
                f"keyword={keyword}, page={page}/{(total + page_size - 1) // page_size}, "
                f"返回 {len(results)}/{total} 条"
            )

            return results, total

        except Exception as e:
            logger.error(f"❌ 分页查询 LangGraph 搜索结果失败: {e}")
            raise


# 单例实例
mongo_langgraph_result_repository = MongoLangGraphResultRepository()

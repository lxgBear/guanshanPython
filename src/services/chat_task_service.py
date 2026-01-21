"""
Chat Task Service - 聊天任务业务逻辑层

v3.0.0 新增：支持后台任务执行模式

核心功能：
- 创建和执行聊天任务
- 支持同步等待和异步执行两种模式
- 任务完成后自动保存到历史记录
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx

from src.infrastructure.database.chat_task_repository import (
    chat_task_repository,
    ChatTaskRepository
)
from src.infrastructure.database.connection import get_mongodb_database
from src.services.search_engine_adapter import search_engine_adapter  # v4.2.0: 使用搜索引擎适配器
from src.services.nl_search.search_history_service import search_history_service
from bson import ObjectId

logger = logging.getLogger(__name__)

# AI服务配置 (支持环境变量覆盖)
REMOTE_AI_SERVICE_URL = os.getenv("LAYER_AI_SERVICE_URL", "http://localhost:8035/chat")
REMOTE_AI_SERVICE_TIMEOUT = 120.0


class ChatTaskService:
    """聊天任务服务"""

    def __init__(self):
        self.repository = chat_task_repository

    async def create_task(
        self,
        user_id: int,
        question: str,
        search_mode: str = "single",
        conversation_id: Optional[str] = None
    ) -> str:
        """创建新任务

        Args:
            user_id: 用户ID
            question: 用户问题
            search_mode: 搜索模式
            conversation_id: 对话ID

        Returns:
            task_id: 任务ID
        """
        return await self.repository.create_task(
            user_id=user_id,
            question=question,
            search_mode=search_mode,
            conversation_id=conversation_id
        )

    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        """执行任务（核心业务逻辑）

        完整流程：
        1. 更新状态为 searching
        2. 调用 NL Search 服务搜索
        3. 更新状态为 processing
        4. 调用远程 AI 服务处理
        5. 保存结果到历史记录
        6. 更新状态为 completed

        Args:
            task_id: 任务ID

        Returns:
            执行结果
        """
        try:
            # 获取任务信息
            task = await self.repository.get_task(task_id)
            if not task:
                raise ValueError(f"任务不存在: {task_id}")

            user_id = task["user_id"]
            question = task["question"]
            search_mode = task["search_mode"]
            conversation_id = task.get("conversation_id")

            logger.info(f"开始执行任务: task_id={task_id}, question={question[:50]}...")

            # Step 1: 更新状态 - 开始搜索
            await self.repository.update_status(
                task_id=task_id,
                status=ChatTaskRepository.STATUS_SEARCHING,
                progress_message="正在搜索相关信息...",
                progress_percentage=10
            )

            # Step 2: 调用搜索引擎适配器 (v4.2.0: 支持 LangGraph 和多语言检测)
            search_result = await search_engine_adapter.search(
                query=question,
                user_id=str(user_id),
                search_mode=search_mode,
                task_id=task_id  # v4.5.2: 传递 task_id 用于数据库存储
            )

            log_id = search_result.get("log_id")
            search_results_count = len(search_result.get("results", []))
            logger.info(
                f"[SEARCH_COMPLETE] task_id={task_id}, log_id={log_id}, "
                f"results_count={search_results_count}, "
                f"engine={search_result.get('engine_used', 'unknown')}, "
                f"success={search_result.get('success', False)}"
            )

            # 如果搜索结果为空，记录警告
            if search_results_count == 0:
                logger.warning(
                    f"[SEARCH_EMPTY] task_id={task_id}, "
                    f"engine={search_result.get('engine_used')}, "
                    f"error={search_result.get('error', 'No results returned')}"
                )

            # Step 3: 更新状态 - AI处理中
            await self.repository.update_status(
                task_id=task_id,
                status=ChatTaskRepository.STATUS_PROCESSING,
                progress_message="AI正在分析和生成回答...",
                progress_percentage=40
            )

            # Step 4: 调用远程 AI 服务
            search_results_for_ai = search_result.get("results", [])
            logger.info(
                f"[AI_REQUEST] task_id={task_id}, "
                f"question='{question[:50]}...', "
                f"search_results_count={len(search_results_for_ai)}, "
                f"log_id={log_id}"
            )

            ai_result = await self._call_ai_service(
                question=question,
                search_results=search_results_for_ai,
                user_id=str(user_id),
                log_id=log_id
            )

            ai_sources_count = len(ai_result.get("sources", []))
            logger.info(
                f"[AI_RESPONSE] task_id={task_id}, "
                f"sources_count={ai_sources_count}, "
                f"answer_length={len(ai_result.get('answer', ''))}"
            )

            # 检查数据来源差异（搜索结果 vs AI返回）
            if search_results_count == 0 and ai_sources_count > 0:
                logger.warning(
                    f"[DATA_SOURCE_MISMATCH] task_id={task_id}, "
                    f"search_results=0, ai_sources={ai_sources_count}, "
                    f"AI服务可能使用了历史数据而非实时搜索结果"
                )

            # Step 5: 增强来源数据（从MongoDB获取完整信息）
            ai_sources = ai_result.get("sources", [])
            enhanced_sources = await self._enhance_sources(ai_sources)
            logger.info(
                f"[ENHANCE_SOURCES] task_id={task_id}, "
                f"input_count={len(ai_sources)}, "
                f"enhanced_count={len(enhanced_sources)}"
            )

            # Step 6: 保存到历史记录
            history_id = None
            try:
                sources_for_history = [
                    {
                        "mongo_id": s.get("mongo_id"),
                        "source": s.get("source", ""),
                        "title": s.get("title", ""),
                        "score": s.get("score", 0),
                        "category": s.get("category", {}),
                        "publish_time": s.get("publish_time", ""),
                        "preview": (s.get("preview") or "")[:200]
                    }
                    for s in enhanced_sources
                ]

                history_id = await search_history_service.save_from_sync_response(
                    user_id=user_id,
                    question=question,
                    answer=ai_result.get("answer", ""),
                    sources=sources_for_history,
                    conversation_id=conversation_id,
                    search_mode=search_mode
                )
                logger.info(f"保存历史记录: task_id={task_id}, history_id={history_id}")

            except Exception as e:
                logger.warning(f"保存历史记录失败: {e}")

            # Step 7: 构建最终结果
            final_result = {
                "question": question,
                "answer": ai_result.get("answer", ""),
                "sources": enhanced_sources,
                "sources_count": len(enhanced_sources),
                "answer_length": len(ai_result.get("answer", "")),
                "status": "success"
            }

            # Step 7.5: 💾 保存搜索结果到本地 JSON 文件（用于优化分析）
            try:
                save_dir = Path("data/search_results")
                save_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                question_slug = question[:30].replace(" ", "_").replace("/", "_")
                filename = f"{timestamp}_{question_slug}_async_task.json"
                filepath = save_dir / filename

                save_data = {
                    "timestamp": datetime.now().isoformat(),
                    "task_id": task_id,
                    "user_id": user_id,
                    "mode": "async",
                    "request": {
                        "question": question,
                        "search_mode": search_mode,
                        "conversation_id": conversation_id,
                    },
                    "search_results": search_result.get("results", []),
                    "ai_result": {
                        "answer": ai_result.get("answer", ""),
                        "sources_count": len(ai_result.get("sources", [])),
                    },
                    "enhanced_sources": enhanced_sources,
                    "response_summary": {
                        "sources_count": len(enhanced_sources),
                        "answer_length": len(ai_result.get("answer", "")),
                        "status": "success",
                    }
                }

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)

                logger.info(f"💾 异步任务结果已保存: {filepath}")

            except Exception as save_error:
                logger.warning(f"⚠️ 保存异步任务结果失败: {save_error}")

            # Step 8: 完成任务
            await self.repository.complete_task(
                task_id=task_id,
                result=final_result,
                history_id=history_id
            )

            logger.info(f"任务执行完成: task_id={task_id}")
            return final_result

        except Exception as e:
            logger.error(f"任务执行失败: task_id={task_id}, error={e}", exc_info=True)

            # 标记任务失败
            await self.repository.fail_task(
                task_id=task_id,
                error_message=str(e)
            )

            raise

    async def _call_ai_service(
        self,
        question: str,
        search_results: List[Dict],
        user_id: str,
        log_id: str
    ) -> Dict[str, Any]:
        """调用远程AI服务

        Args:
            question: 用户问题
            search_results: 搜索结果
            user_id: 用户ID
            log_id: 日志ID

        Returns:
            AI服务返回结果 {answer, sources}
        """
        try:
            async with httpx.AsyncClient(timeout=REMOTE_AI_SERVICE_TIMEOUT) as client:
                ai_request_data = {
                    "question": question,
                    "search_results": search_results,
                    "user_id": user_id,
                    "log_id": log_id
                }

                async with client.stream(
                    "POST",
                    REMOTE_AI_SERVICE_URL,
                    json=ai_request_data
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise Exception(f"AI服务返回错误: {response.status_code}, {error_text.decode()[:200]}")

                    # 解析 SSE 流
                    answer_chunks = []
                    ai_sources = []

                    async for line in response.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue

                        try:
                            event_data = json.loads(line[6:])
                            event_type = event_data.get("type")

                            if event_type == "answer_chunk":
                                answer_chunks.append(event_data.get("data", ""))
                            elif event_type == "sources":
                                ai_sources = event_data.get("data", [])
                            elif event_type == "stream_end":
                                logger.debug("AI SSE 流结束")

                        except json.JSONDecodeError:
                            continue

                    return {
                        "answer": "".join(answer_chunks),
                        "sources": ai_sources
                    }

        except httpx.TimeoutException:
            raise Exception(f"AI服务超时 ({REMOTE_AI_SERVICE_TIMEOUT}秒)")
        except httpx.RequestError as e:
            raise Exception(f"AI服务请求失败: {str(e)}")

    async def _enhance_sources(
        self,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """增强来源数据（从MongoDB获取完整信息）

        Args:
            sources: AI返回的来源列表

        Returns:
            增强后的来源列表
        """
        if not sources:
            return []

        db = await get_mongodb_database()
        enhanced = []

        # 去重
        seen_ids = set()
        unique_sources = []
        for s in sources:
            mongo_id = s.get("mongo_id")
            if mongo_id and mongo_id not in seen_ids:
                seen_ids.add(mongo_id)
                unique_sources.append(s)

        for source in unique_sources:
            mongo_id = source.get("mongo_id")
            source_type = source.get("source", "")

            if not mongo_id:
                continue

            # 处理默认 category
            category = source.get("category", {})
            if not category or not all(k in category for k in ["大类", "类别", "地域"]):
                category = {"大类": "未分类", "类别": "未分类", "地域": "未知"}

            enhanced_source = {
                "id": source.get("id", ""),
                "mongo_id": mongo_id,
                "title": source.get("title", ""),
                "source": source_type,
                "score": source.get("score", 0.0),
                "category": category,
                "publish_time": source.get("publish_time", "未知时间"),
                "preview": source.get("preview", "")
            }

            # 根据来源类型查询不同集合
            try:
                if source_type == "用户上传":
                    file_result = await db["file_uploads"].find_one(
                        {"_id": ObjectId(mongo_id)},
                        {"title": 1, "content": 1, "storage_url": 1, "_id": 0}
                    )
                    if file_result:
                        enhanced_source["url"] = file_result.get("storage_url")
                        enhanced_source["title_zh"] = file_result.get("title")
                        enhanced_source["content_zh"] = file_result.get("content")
                else:
                    news_result = await db["news_results"].find_one(
                        {"_id": mongo_id},
                        {
                            "url": 1,
                            "news_results.title_zh": 1,
                            "news_results.summary_zh": 1,
                            "news_results.content_zh": 1,
                            "_id": 0
                        }
                    )
                    if news_result:
                        enhanced_source["url"] = news_result.get("url")
                        nested = news_result.get("news_results", {})
                        enhanced_source["title_zh"] = nested.get("title_zh")
                        enhanced_source["summary_zh"] = nested.get("summary_zh")
                        enhanced_source["content_zh"] = nested.get("content_zh")

            except Exception as e:
                logger.warning(f"增强来源数据失败: mongo_id={mongo_id}, error={e}")

            enhanced.append(enhanced_source)

        return enhanced

    async def get_task_result(
        self,
        task_id: str,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取任务结果

        Args:
            task_id: 任务ID
            user_id: 用户ID

        Returns:
            任务信息和结果
        """
        task = await self.repository.get_task_by_user(task_id, user_id)
        if not task:
            return None

        return {
            "task_id": task["_id"],
            "status": task["status"],
            "progress": task["progress"],
            "question": task["question"],
            "result": task.get("result"),
            "error": task.get("error"),
            "history_id": task.get("history_id"),
            "created_at": task["created_at"].isoformat() if task.get("created_at") else None,
            "completed_at": task["completed_at"].isoformat() if task.get("completed_at") else None
        }

    async def get_user_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """获取用户任务列表

        Args:
            user_id: 用户ID
            status: 状态过滤
            limit: 返回数量
            offset: 偏移量

        Returns:
            任务列表和总数
        """
        tasks = await self.repository.get_user_tasks(
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )

        total = await self.repository.count_user_tasks(user_id, status)

        return {
            "items": [
                {
                    "task_id": t["_id"],
                    "question": t["question"],
                    "status": t["status"],
                    "progress": t["progress"],
                    "history_id": t.get("history_id"),
                    "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
                    "completed_at": t["completed_at"].isoformat() if t.get("completed_at") else None
                }
                for t in tasks
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }


# 单例实例
chat_task_service = ChatTaskService()

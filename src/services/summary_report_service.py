"""智能总结报告业务逻辑服务"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import time

from src.core.domain.entities.summary_report import (
    SummaryReport,
    SummaryReportTask,
    SummaryReportDataItem,
    SummaryReportVersion
)
from src.infrastructure.database.summary_report_repositories import (
    SummaryReportRepository,
    SummaryReportTaskRepository,
    SummaryReportDataItemRepository,
    SummaryReportVersionRepository
)
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Redis缓存是可选的
try:
    from src.infrastructure.cache import redis_client, cache_key_gen
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis_client = None
    cache_key_gen = None
    logger.warning("Redis模块未安装，缓存功能将被禁用")


class LLMService:
    """
    LLM服务（预留接口）

    待LLM模块开发完成后实现
    用于调用大语言模型生成报告总结
    """

    async def generate_summary(
        self,
        report_id: str,
        content_items: List[Dict[str, Any]],
        generation_mode: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        生成报告总结（预留接口）

        Args:
            report_id: 报告ID
            content_items: 内容项列表
            generation_mode: 生成模式 (comprehensive/summary/analysis)

        Returns:
            生成结果字典:
            {
                "success": bool,
                "content": str,  # 生成的内容
                "model": str,    # 使用的模型
                "tokens_used": int,
                "generation_time": float
            }
        """
        # TODO: 实现LLM调用逻辑
        logger.warning("⚠️  LLM服务未实现，返回占位内容")
        return {
            "success": False,
            "content": "",
            "model": "pending",
            "tokens_used": 0,
            "generation_time": 0.0,
            "error": "LLM module not yet implemented"
        }

    async def refine_content(
        self,
        original_content: str,
        refinement_instructions: str
    ) -> Dict[str, Any]:
        """
        优化内容（预留接口）

        用于根据用户指示优化和改进已生成的内容
        """
        # TODO: 实现内容优化逻辑
        logger.warning("⚠️  LLM内容优化服务未实现")
        return {
            "success": False,
            "refined_content": original_content,
            "error": "LLM refinement not yet implemented"
        }


class AIAnalysisService:
    """
    AI分析服务（预留接口）

    待AI模块开发完成后实现
    用于数据分析、趋势识别、关键信息提取等
    """

    async def analyze_data(
        self,
        report_id: str,
        data_items: List[Dict[str, Any]],
        analysis_type: str = "trend"
    ) -> Dict[str, Any]:
        """
        分析数据（预留接口）

        Args:
            report_id: 报告ID
            data_items: 数据项列表
            analysis_type: 分析类型 (trend/keyword/sentiment/classification)

        Returns:
            分析结果字典:
            {
                "success": bool,
                "analysis_results": dict,
                "insights": list,
                "recommendations": list
            }
        """
        # TODO: 实现AI分析逻辑
        logger.warning("⚠️  AI分析服务未实现，返回占位内容")
        return {
            "success": False,
            "analysis_results": {},
            "insights": [],
            "recommendations": [],
            "error": "AI analysis module not yet implemented"
        }

    async def extract_keywords(
        self,
        content: str,
        max_keywords: int = 10
    ) -> List[str]:
        """
        提取关键词（预留接口）
        """
        # TODO: 实现关键词提取
        logger.warning("⚠️  AI关键词提取服务未实现")
        return []


class SummaryReportService:
    """智能总结报告管理服务"""

    def __init__(self):
        self.db = None
        self.report_repo = None
        self.task_repo = None
        self.data_item_repo = None
        self.version_repo = None
        self.llm_service = LLMService()
        self.ai_service = AIAnalysisService()

    async def _init_repos(self):
        """初始化仓储"""
        if not self.db:
            self.db = await get_mongodb_database()
            self.report_repo = SummaryReportRepository(self.db)
            self.task_repo = SummaryReportTaskRepository(self.db)
            self.data_item_repo = SummaryReportDataItemRepository(self.db)
            self.version_repo = SummaryReportVersionRepository(self.db)

    # ==========================================
    # 报告管理
    # ==========================================

    async def create_report(
        self,
        title: str,
        description: Optional[str],
        report_type: str,
        created_by: str,
        **kwargs
    ) -> SummaryReport:
        """创建总结报告"""
        await self._init_repos()

        report = SummaryReport(
            title=title,
            description=description,
            report_type=report_type,
            created_by=created_by,
            **kwargs
        )

        return await self.report_repo.create(report)

    async def get_report(self, report_id: str) -> Optional[SummaryReport]:
        """获取报告详情"""
        await self._init_repos()
        report = await self.report_repo.find_by_id(report_id)

        if report:
            # 增加查看次数
            await self.report_repo.increment_view_count(report_id)

        return report

    async def list_reports(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[SummaryReport]:
        """列出报告"""
        await self._init_repos()
        return await self.report_repo.find_all(
            created_by=created_by,
            status=status,
            report_type=report_type,
            limit=limit,
            skip=skip
        )

    async def update_report(
        self,
        report_id: str,
        update_data: Dict[str, Any]
    ) -> bool:
        """更新报告"""
        await self._init_repos()
        return await self.report_repo.update(report_id, update_data)

    async def delete_report(self, report_id: str) -> bool:
        """删除报告（级联删除关联数据）"""
        await self._init_repos()

        # 删除关联的任务
        await self.task_repo.delete_by_report(report_id)

        # 删除关联的数据项
        await self.data_item_repo.delete_by_report(report_id)

        # 删除版本历史
        await self.version_repo.delete_by_report(report_id)

        # 删除报告
        return await self.report_repo.delete(report_id)

    # ==========================================
    # 任务关联管理
    # ==========================================

    async def add_task_to_report(
        self,
        report_id: str,
        task_id: str,
        task_type: str,
        task_name: str,
        added_by: str,
        priority: int = 0
    ) -> SummaryReportTask:
        """添加任务到报告"""
        await self._init_repos()

        # 检查是否已存在
        exists = await self.task_repo.exists(report_id, task_id, task_type)
        if exists:
            raise ValueError(f"Task {task_id} already added to report {report_id}")

        report_task = SummaryReportTask(
            report_id=report_id,
            task_id=task_id,
            task_type=task_type,
            task_name=task_name,
            added_by=added_by,
            priority=priority
        )

        result = await self.task_repo.create(report_task)

        # 更新报告的任务计数
        count = await self.task_repo.count_by_report(report_id)
        await self.report_repo.update_task_count(report_id, count)

        # ==========================================
        # 缓存失效：删除该报告的所有搜索缓存
        # ==========================================
        if REDIS_AVAILABLE:
            cache_pattern = cache_key_gen.report_pattern(report_id)
            deleted_count = await redis_client.delete_pattern(cache_pattern)
            if deleted_count > 0:
                logger.info(f"🗑️ 缓存失效: {cache_pattern}, 删除 {deleted_count} 个缓存键")

        return result

    async def get_report_tasks(
        self,
        report_id: str,
        is_active: Optional[bool] = None
    ) -> List[SummaryReportTask]:
        """获取报告的所有任务"""
        await self._init_repos()
        return await self.task_repo.find_by_report(report_id, is_active)

    async def remove_task_from_report(
        self,
        report_id: str,
        task_id: str,
        task_type: str
    ) -> bool:
        """从报告中移除任务"""
        await self._init_repos()
        result = await self.task_repo.delete(report_id, task_id, task_type)

        if result:
            # 更新报告的任务计数
            count = await self.task_repo.count_by_report(report_id)
            await self.report_repo.update_task_count(report_id, count)

            # ==========================================
            # 缓存失效：删除该报告的所有搜索缓存
            # ==========================================
            if REDIS_AVAILABLE:
                cache_pattern = cache_key_gen.report_pattern(report_id)
                deleted_count = await redis_client.delete_pattern(cache_pattern)
                if deleted_count > 0:
                    logger.info(f"🗑️ 缓存失效: {cache_pattern}, 删除 {deleted_count} 个缓存键")

        return result

    # ==========================================
    # 数据项管理
    # ==========================================

    async def add_data_item(
        self,
        report_id: str,
        source_type: str,
        title: str,
        content: str,
        added_by: str,
        **kwargs
    ) -> SummaryReportDataItem:
        """添加数据项到报告"""
        await self._init_repos()

        data_item = SummaryReportDataItem(
            report_id=report_id,
            source_type=source_type,
            title=title,
            content=content,
            added_by=added_by,
            **kwargs
        )

        result = await self.data_item_repo.create(data_item)

        # 更新报告的数据项计数
        count = await self.data_item_repo.count_by_report(report_id)
        await self.report_repo.update_data_item_count(report_id, count)

        return result

    async def get_report_data_items(
        self,
        report_id: str,
        is_visible: Optional[bool] = None,
        limit: int = 100
    ) -> List[SummaryReportDataItem]:
        """获取报告的所有数据项"""
        await self._init_repos()
        return await self.data_item_repo.find_by_report(
            report_id,
            is_visible=is_visible,
            limit=limit
        )

    async def search_data_items(
        self,
        report_id: str,
        search_query: str,
        limit: int = 50
    ) -> List[SummaryReportDataItem]:
        """
        模糊搜索数据项（联表查询）

        从用户选择的定时任务和搜索任务表中获取内容
        """
        await self._init_repos()

        # 使用全文搜索
        return await self.data_item_repo.search(report_id, search_query, limit)

    async def _search_scheduled_results(
        self,
        task_ids: List[str],
        search_query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        查询定时任务的搜索结果（内部方法）

        使用优化的聚合管道和查询提示
        """
        if not task_ids:
            return []

        try:
            # 优化的聚合管道：先过滤后联表
            pipeline = [
                # 第一阶段：精确匹配（使用索引）
                {
                    "$match": {
                        "task_id": {"$in": task_ids},
                        "$text": {"$search": search_query}
                    }
                },
                # 第二阶段：按相关性排序
                {
                    "$sort": {"score": {"$meta": "textScore"}}
                },
                # 第三阶段：限制结果数
                {"$limit": limit},
                # 第四阶段：联表查询（只查询需要的字段）
                {
                    "$lookup": {
                        "from": "search_tasks",
                        "let": {"taskId": "$task_id"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {"$eq": ["$id", "$$taskId"]}
                                }
                            },
                            # 只返回需要的字段（减少数据传输）
                            {
                                "$project": {
                                    "_id": 0,
                                    "id": 1,
                                    "name": 1,
                                    "query": 1
                                }
                            }
                        ],
                        "as": "task_info"
                    }
                },
                # 第五阶段：投影（只返回需要的字段）
                {
                    "$project": {
                        "_id": 0,
                        "result_id": 1,
                        "task_id": 1,
                        "title": 1,
                        "url": 1,
                        "markdown_content": 1,
                        "created_at": 1,
                        "task_info": {"$arrayElemAt": ["$task_info", 0]},
                        "relevance_score": {"$meta": "textScore"}
                    }
                }
            ]

            # 使用hint强制使用最优索引
            cursor = self.db.search_results.aggregate(
                pipeline,
                hint="idx_task_created"  # 强制使用 task_id + created_at 索引
            )

            results = await cursor.to_list(length=limit)
            logger.debug(f"📊 查询定时任务结果: {len(results)} 条")
            return results

        except Exception as e:
            logger.error(f"❌ 查询定时任务结果失败: {e}")
            return []

    async def _search_instant_results(
        self,
        task_ids: List[str],
        search_query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        查询即时任务的搜索结果（内部方法）

        使用优化的聚合管道和查询提示
        """
        if not task_ids:
            return []

        try:
            # 优化的聚合管道：先过滤后联表
            pipeline = [
                # 第一阶段：精确匹配（使用索引）
                {
                    "$match": {
                        "execution_id": {"$in": task_ids},
                        "$text": {"$search": search_query}
                    }
                },
                # 第二阶段：按相关性排序
                {
                    "$sort": {"score": {"$meta": "textScore"}}
                },
                # 第三阶段：限制结果数
                {"$limit": limit},
                # 第四阶段：联表查询（只查询需要的字段）
                {
                    "$lookup": {
                        "from": "instant_search_tasks",
                        "let": {"execId": "$execution_id"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {"$eq": ["$execution_id", "$$execId"]}
                                }
                            },
                            # 只返回需要的字段
                            {
                                "$project": {
                                    "_id": 0,
                                    "execution_id": 1,
                                    "query": 1,
                                    "created_at": 1
                                }
                            }
                        ],
                        "as": "task_info"
                    }
                },
                # 第五阶段：投影
                {
                    "$project": {
                        "_id": 0,
                        "result_id": 1,
                        "execution_id": 1,
                        "title": 1,
                        "url": 1,
                        "markdown_content": 1,
                        "created_at": 1,
                        "task_info": {"$arrayElemAt": ["$task_info", 0]},
                        "relevance_score": {"$meta": "textScore"}
                    }
                }
            ]

            # 使用hint强制使用最优索引
            cursor = self.db.instant_search_results.aggregate(
                pipeline,
                hint="idx_execution_created"  # 强制使用 execution_id + created_at 索引
            )

            results = await cursor.to_list(length=limit)
            logger.debug(f"📊 查询即时任务结果: {len(results)} 条")
            return results

        except Exception as e:
            logger.error(f"❌ 查询即时任务结果失败: {e}")
            return []

    async def search_across_tasks(
        self,
        report_id: str,
        search_query: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        跨任务联表查询搜索结果（优化版 + Redis缓存）

        性能优化策略：
        1. Redis缓存：5分钟TTL，减少重复查询压力
        2. 分阶段查询：先获取任务列表（小表），再分离类型
        3. 并行查询：使用asyncio.gather同时查询scheduled和instant结果
        4. 查询提示：使用hint强制使用最优索引
        5. 结果限制：每个任务类型限制结果数，避免过载
        6. 投影优化：只返回需要的字段，减少数据传输

        性能目标：
        - 缓存命中: <50ms
        - 2个任务: <1s (冷查询)
        - 3-5个任务: <2s (冷查询)
        - 6-10个任务: <3s (冷查询)
        """
        await self._init_repos()

        # ==========================================
        # Redis缓存检查（如果可用）
        # ==========================================
        cache_key = None
        if REDIS_AVAILABLE:
            cache_key = cache_key_gen.search_result(report_id, search_query, limit)
            cached_result = await redis_client.get(cache_key)

            if cached_result:
                logger.info(f"✅ 缓存命中: {cache_key}")
                return cached_result

            logger.debug(f"🔍 缓存未命中，执行查询: {cache_key}")

        # ==========================================
        # 阶段1: 获取活跃任务列表（使用覆盖索引，小表查询）
        # ==========================================
        report_tasks = await self.task_repo.find_by_report(
            report_id,
            is_active=True
        )

        if not report_tasks:
            empty_result = {
                "scheduled_results": [],
                "instant_results": [],
                "merged_results": [],
                "total_count": 0,
                "query_time": 0,
                "task_stats": {
                    "scheduled_tasks": 0,
                    "instant_tasks": 0,
                    "total_tasks": 0
                }
            }
            # 缓存空结果（较短TTL）
            if REDIS_AVAILABLE and cache_key:
                await redis_client.set(cache_key, empty_result, ttl=60)
            return empty_result

        # ==========================================
        # 阶段2: 分离任务类型（内存操作，避免复杂条件）
        # ==========================================
        scheduled_task_ids = [
            rt.task_id for rt in report_tasks
            if rt.task_type == "scheduled"
        ]
        instant_task_ids = [
            rt.task_id for rt in report_tasks
            if rt.task_type == "instant"
        ]

        logger.info(
            f"🔍 跨任务搜索 - 报告: {report_id}, "
            f"定时任务: {len(scheduled_task_ids)}, "
            f"即时任务: {len(instant_task_ids)}"
        )

        # ==========================================
        # 阶段3: 并行查询（使用asyncio.gather，最大化性能）
        # ==========================================
        start_time = time.time()

        # 并发执行两个查询
        scheduled_results, instant_results = await asyncio.gather(
            self._search_scheduled_results(
                scheduled_task_ids,
                search_query,
                limit
            ),
            self._search_instant_results(
                instant_task_ids,
                search_query,
                limit
            ),
            return_exceptions=True  # 捕获异常而不中断
        )

        # 处理异常结果
        if isinstance(scheduled_results, Exception):
            logger.error(f"❌ 定时任务查询异常: {scheduled_results}")
            scheduled_results = []

        if isinstance(instant_results, Exception):
            logger.error(f"❌ 即时任务查询异常: {instant_results}")
            instant_results = []

        # ==========================================
        # 阶段4: 合并结果并排序（按相关性分数）
        # ==========================================
        all_results = []
        for result in scheduled_results:
            result["source_type"] = "scheduled"
            all_results.append(result)
        for result in instant_results:
            result["source_type"] = "instant"
            all_results.append(result)

        # 按相关性分数排序
        all_results.sort(
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )

        # 限制总结果数
        if len(all_results) > limit:
            all_results = all_results[:limit]

        query_time = time.time() - start_time

        logger.info(
            f"✅ 跨任务搜索完成 - 总结果: {len(all_results)}, "
            f"查询时间: {query_time:.3f}s"
        )

        # 构建查询结果
        search_result = {
            "scheduled_results": scheduled_results,
            "instant_results": instant_results,
            "merged_results": all_results,
            "total_count": len(all_results),
            "query_time": query_time,
            "task_stats": {
                "scheduled_tasks": len(scheduled_task_ids),
                "instant_tasks": len(instant_task_ids),
                "total_tasks": len(report_tasks)
            }
        }

        # ==========================================
        # Redis缓存结果（5分钟TTL）
        # ==========================================
        if REDIS_AVAILABLE and cache_key:
            await redis_client.set(cache_key, search_result, ttl=300)
            logger.debug(f"💾 缓存已设置: {cache_key}, TTL: 300s")

        return search_result

    async def update_data_item(
        self,
        item_id: str,
        update_data: Dict[str, Any]
    ) -> bool:
        """更新数据项"""
        await self._init_repos()
        return await self.data_item_repo.update(item_id, update_data)

    async def delete_data_item(self, item_id: str, report_id: str) -> bool:
        """删除数据项"""
        await self._init_repos()
        result = await self.data_item_repo.delete(item_id)

        if result:
            # 更新报告的数据项计数
            count = await self.data_item_repo.count_by_report(report_id)
            await self.report_repo.update_data_item_count(report_id, count)

        return result

    # ==========================================
    # 内容编辑和版本管理
    # ==========================================

    async def update_report_content(
        self,
        report_id: str,
        content_text: str,
        content_format: str = "markdown",
        is_manual: bool = False,
        updated_by: str = "",
        change_description: Optional[str] = None
    ) -> bool:
        """更新报告内容（支持富文本编辑）"""
        await self._init_repos()

        # 获取当前报告
        report = await self.report_repo.find_by_id(report_id)
        if not report:
            return False

        # 如果启用自动版本管理，创建版本快照
        if report.auto_version and is_manual:
            version = SummaryReportVersion(
                report_id=report_id,
                version_number=report.version + 1,
                content_snapshot=report.content.copy(),
                change_description=change_description or "Manual content update",
                change_type="manual" if is_manual else "auto_generated",
                created_by=updated_by,
                content_size=len(content_text)
            )
            await self.version_repo.create(version)

        # 更新内容
        return await self.report_repo.update_content(
            report_id,
            content_text,
            content_format,
            is_manual
        )

    async def get_report_versions(
        self,
        report_id: str,
        limit: int = 20
    ) -> List[SummaryReportVersion]:
        """获取报告版本历史"""
        await self._init_repos()
        return await self.version_repo.find_by_report(report_id, limit)

    async def rollback_to_version(
        self,
        report_id: str,
        version_number: int,
        updated_by: str
    ) -> bool:
        """回滚到指定版本"""
        await self._init_repos()

        # 获取目标版本
        version = await self.version_repo.find_by_version_number(report_id, version_number)
        if not version:
            return False

        # 恢复内容
        content_snapshot = version.content_snapshot
        content_text = content_snapshot.get("text", "")
        content_format = content_snapshot.get("format", "markdown")

        return await self.update_report_content(
            report_id,
            content_text,
            content_format,
            is_manual=True,
            updated_by=updated_by,
            change_description=f"Rollback to version {version_number}"
        )

    # ==========================================
    # LLM/AI 生成功能（预留接口）
    # ==========================================

    async def generate_report_with_llm(
        self,
        report_id: str,
        generation_mode: str = "comprehensive",
        llm_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        使用LLM生成报告内容（预留接口）

        Args:
            report_id: 报告ID
            generation_mode: 生成模式
            llm_config: LLM配置参数

        Returns:
            生成结果
        """
        await self._init_repos()

        # 更新报告状态为生成中
        await self.report_repo.update_status(report_id, "generating")

        try:
            # 获取报告的所有数据项
            data_items = await self.data_item_repo.find_by_report(report_id)

            # 转换为LLM输入格式
            content_items = [
                {
                    "title": item.title,
                    "content": item.content,
                    "url": item.url,
                    "importance": item.importance
                }
                for item in data_items
            ]

            # 调用LLM服务生成内容
            result = await self.llm_service.generate_summary(
                report_id,
                content_items,
                generation_mode
            )

            if result["success"]:
                # 更新报告内容
                await self.update_report_content(
                    report_id,
                    result["content"],
                    content_format="markdown",
                    is_manual=False,
                    change_description="LLM generated content"
                )

                # 更新生成配置
                gen_config = {
                    "llm_model": result.get("model"),
                    "ai_analysis_type": generation_mode,
                    "generation_params": llm_config or {}
                }
                await self.report_repo.update(report_id, {
                    "generation_config": gen_config
                })

                # 更新状态为已完成
                await self.report_repo.update_status(report_id, "completed")
            else:
                # 更新状态为失败
                await self.report_repo.update_status(report_id, "failed")

            return result

        except Exception as e:
            logger.error(f"❌ LLM生成失败: {e}")
            await self.report_repo.update_status(report_id, "failed")
            return {
                "success": False,
                "error": str(e)
            }

    async def analyze_report_data_with_ai(
        self,
        report_id: str,
        analysis_type: str = "trend"
    ) -> Dict[str, Any]:
        """
        使用AI分析报告数据（预留接口）

        Args:
            report_id: 报告ID
            analysis_type: 分析类型

        Returns:
            分析结果
        """
        await self._init_repos()

        # 获取报告的所有数据项
        data_items = await self.data_item_repo.find_by_report(report_id)

        # 转换为AI分析输入格式
        analysis_items = [
            {
                "title": item.title,
                "content": item.content,
                "metadata": item.metadata,
                "tags": item.tags
            }
            for item in data_items
        ]

        # 调用AI分析服务
        return await self.ai_service.analyze_data(
            report_id,
            analysis_items,
            analysis_type
        )

    # ==========================================
    # 任务结果获取（新增功能）
    # ==========================================

    async def get_task_results_for_report(
        self,
        report_id: str,
        task_ids: Optional[List[str]] = None,
        cursor: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        获取报告关联任务的所有结果（支持游标分页）

        改进功能：用于前端初始化数据列表，减少API调用

        Args:
            report_id: 报告ID
            task_ids: 指定任务ID列表（可选，为None时返回所有关联任务的结果）
            cursor: 分页游标（格式: "task_type:task_id:created_at"）
            limit: 分页大小

        Returns:
            {
                "items": [...]  # 任务结果列表
                "meta": {
                    "has_next": bool,
                    "next_cursor": str,
                    "count": int,
                    "task_stats": {...}
                }
            }
        """
        await self._init_repos()

        # 获取报告关联的任务
        report_tasks = await self.task_repo.find_by_report(report_id, is_active=True)

        if not report_tasks:
            return {
                "items": [],
                "meta": {
                    "has_next": False,
                    "next_cursor": None,
                    "count": 0,
                    "task_stats": {
                        "scheduled_count": 0,
                        "instant_count": 0,
                        "total_count": 0
                    }
                }
            }

        # 如果指定了task_ids，过滤任务列表
        if task_ids:
            task_id_set = set(task_ids)
            report_tasks = [
                task for task in report_tasks
                if task.task_id in task_id_set
            ]

        # 分离定时任务和即时任务
        scheduled_task_ids = [
            t.task_id for t in report_tasks if t.task_type == "scheduled"
        ]
        instant_task_ids = [
            t.task_id for t in report_tasks if t.task_type == "instant"
        ]

        # 并行查询两种任务的结果
        scheduled_results, instant_results = await asyncio.gather(
            self._get_all_scheduled_results(scheduled_task_ids, limit),
            self._get_all_instant_results(instant_task_ids, limit),
            return_exceptions=True
        )

        # 处理异常
        if isinstance(scheduled_results, Exception):
            logger.error(f"❌ 获取定时任务结果失败: {scheduled_results}")
            scheduled_results = []
        if isinstance(instant_results, Exception):
            logger.error(f"❌ 获取即时任务结果失败: {instant_results}")
            instant_results = []

        # 合并结果并添加source_type标记
        all_results = []
        for result in scheduled_results:
            result["source_type"] = "scheduled"
            all_results.append(result)
        for result in instant_results:
            result["source_type"] = "instant"
            all_results.append(result)

        # 按创建时间排序（最新的在前）
        all_results.sort(
            key=lambda x: x.get("created_at", datetime.min),
            reverse=True
        )

        # 应用游标分页
        if cursor:
            # 解析游标: "source_type:created_at_timestamp"
            try:
                cursor_parts = cursor.split(":")
                if len(cursor_parts) == 2:
                    cursor_source_type, cursor_timestamp = cursor_parts
                    cursor_dt = datetime.fromtimestamp(float(cursor_timestamp))

                    # 过滤出游标之后的结果
                    all_results = [
                        r for r in all_results
                        if r.get("created_at", datetime.max) < cursor_dt or
                        (r.get("created_at") == cursor_dt and r.get("source_type") != cursor_source_type)
                    ]
            except Exception as e:
                logger.warning(f"⚠️ 游标解析失败: {e}, 忽略游标")

        # 限制结果数量（取limit+1用于判断是否有下一页）
        has_next = len(all_results) > limit
        if has_next:
            items = all_results[:limit]
        else:
            items = all_results

        # 生成下一页游标
        next_cursor = None
        if has_next and items:
            last_item = items[-1]
            last_created_at = last_item.get("created_at")
            if last_created_at:
                timestamp = last_created_at.timestamp()
                source_type = last_item.get("source_type", "scheduled")
                next_cursor = f"{source_type}:{timestamp}"

        return {
            "items": items,
            "meta": {
                "has_next": has_next,
                "next_cursor": next_cursor,
                "count": len(items),
                "task_stats": {
                    "scheduled_count": len(scheduled_task_ids),
                    "instant_count": len(instant_task_ids),
                    "total_count": len(report_tasks)
                }
            }
        }

    async def _get_all_scheduled_results(
        self,
        task_ids: List[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """获取所有定时任务的结果（内部方法）"""
        if not task_ids:
            return []

        try:
            # 查询所有结果（不需要全文搜索）
            query = {"task_id": {"$in": task_ids}}

            cursor = self.db.search_results.find(query).sort("created_at", -1).limit(limit * 2)
            results = await cursor.to_list(length=limit * 2)

            # 转换为统一格式
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "result_id": result.get("result_id") or str(result.get("_id")),
                    "task_id": result.get("task_id"),
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "markdown_content": result.get("markdown_content"),
                    "created_at": result.get("created_at"),
                    "metadata": result.get("metadata", {})
                })

            logger.debug(f"📊 获取定时任务结果: {len(formatted_results)} 条")
            return formatted_results

        except Exception as e:
            logger.error(f"❌ 获取定时任务结果失败: {e}")
            return []

    async def _get_all_instant_results(
        self,
        task_ids: List[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """获取所有即时任务的结果（内部方法）"""
        if not task_ids:
            return []

        try:
            # 查询所有结果（不需要全文搜索）
            query = {"task_id": {"$in": task_ids}}

            cursor = self.db.instant_search_results.find(query).sort("created_at", -1).limit(limit * 2)
            results = await cursor.to_list(length=limit * 2)

            # 转换为统一格式
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "result_id": result.get("result_id") or str(result.get("_id")),
                    "task_id": result.get("task_id") or result.get("execution_id"),
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "markdown_content": result.get("markdown_content"),
                    "created_at": result.get("created_at"),
                    "metadata": result.get("metadata", {})
                })

            logger.debug(f"📊 获取即时任务结果: {len(formatted_results)} 条")
            return formatted_results

        except Exception as e:
            logger.error(f"❌ 获取即时任务结果失败: {e}")
            return []


# 全局服务实例
summary_report_service = SummaryReportService()

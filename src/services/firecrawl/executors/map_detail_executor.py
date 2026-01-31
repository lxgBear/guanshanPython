"""
Map + Detail 任务执行器

执行流程：
1. Map API 发现所有URL
2. URL 去重（基于 search_results 表）
3. 规则过滤（黑名单模式）
4. LLM 判断（LangGraph 工作流）
5. 批量 Scrape 获取内容
6. 保存结果

优势：
- 智能过滤：规则 + LLM 双重过滤，只爬取详情页
- 成本优化：相比 Crawl API 节省 80-90% 积分
- URL去重：避免重复爬取已处理的内容
"""

from typing import List, Optional
from datetime import datetime

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResultBatch, ResultStatus
from src.services.firecrawl.base import TaskExecutor, ExecutorException
from src.services.map_detail.service import MapDetailService, MapDetailResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MapDetailExecutor(TaskExecutor):
    """Map + Detail 详情页爬取任务执行器

    使用 Map API 发现链接，通过规则过滤和 LLM 判断筛选详情页，
    然后批量爬取详情页内容。
    """

    def __init__(self):
        super().__init__()
        self.service: Optional[MapDetailService] = None

    def validate_config(self, task: SearchTask) -> bool:
        """验证任务配置

        Args:
            task: 搜索任务

        Returns:
            bool: 配置是否有效
        """
        if not task.crawl_url:
            self.logger.error("Map + Detail 任务必须提供 crawl_url 参数")
            return False

        if not task.crawl_url.startswith(('http://', 'https://')):
            self.logger.error(f"crawl_url 格式无效: {task.crawl_url}")
            return False

        return True

    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行 Map + Detail 任务

        Args:
            task: 搜索任务

        Returns:
            SearchResultBatch: 执行结果批次

        Raises:
            ExecutorException: 执行过程中的错误
        """
        start_time = datetime.utcnow()
        self._log_execution_start(task)

        # 1. 验证配置
        if not self.validate_config(task):
            raise ExecutorException(f"任务配置无效: {task.id}")

        try:
            # 2. 初始化服务
            if self.service is None:
                self.service = MapDetailService()

            # 3. 执行任务
            self.logger.info(
                f"🗺️  Step 1: Map API 发现链接 → "
                f"🔍 Step 2: URL 去重 → "
                f"⚙️  Step 3: 规则过滤 → "
                f"🤖 Step 4: LLM 判断 → "
                f"📥 Step 5: 批量 Scrape"
            )

            result: MapDetailResult = await self.service.execute(task)

            # 4. 创建结果批次
            batch = self._create_result_batch(
                task,
                query=f"Map+Detail: {task.crawl_url}"
            )

            # 5. 添加搜索结果
            for search_result in result.results:
                batch.add_result(search_result)

            batch.total_count = len(result.results)
            batch.credits_used = result.credits_used or 0

            # 6. 计算执行时间
            end_time = datetime.utcnow()
            batch.execution_time_ms = int(
                (end_time - start_time).total_seconds() * 1000
            )

            # 7. 记录统计信息
            self.logger.info(
                f"📊 任务统计: "
                f"发现 {result.stats.total_urls_found} 个URL | "
                f"去重后 {result.stats.urls_after_dedup} 个 | "
                f"规则过滤后 {result.stats.urls_after_filter} 个 | "
                f"LLM判断后 {result.stats.urls_after_llm} 个详情页 | "
                f"成功爬取 {result.stats.urls_scraped} 个"
            )

            self._log_execution_end(
                task,
                len(result.results),
                batch.execution_time_ms
            )

            return batch

        except Exception as e:
            self.logger.error(f"执行 Map + Detail 失败: {e}")
            raise ExecutorException(f"Map + Detail 执行失败: {str(e)}") from e

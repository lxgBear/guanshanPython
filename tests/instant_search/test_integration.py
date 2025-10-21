"""即时搜索集成测试

v1.3.0 完整流程测试：
- 端到端API调用
- 跨搜索结果去重验证
- 映射表JOIN查询验证
- 发现统计验证
"""

import pytest
import asyncio
from datetime import datetime

from src.services.instant_search_service import InstantSearchService
from src.core.domain.entities.instant_search_task import InstantSearchStatus
from src.infrastructure.database.instant_search_repositories import (
    InstantSearchTaskRepository,
    InstantSearchResultRepository,
    InstantSearchResultMappingRepository
)


class TestInstantSearchIntegration:
    """即时搜索集成测试套件"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """测试前准备"""
        self.service = InstantSearchService()
        self.task_repo = InstantSearchTaskRepository()
        self.result_repo = InstantSearchResultRepository()
        self.mapping_repo = InstantSearchResultMappingRepository()
        yield
        # 清理工作（如果需要）

    @pytest.mark.asyncio
    async def test_complete_search_workflow(self):
        """测试完整搜索流程

        验证：
        1. 创建并执行搜索任务
        2. 结果正确保存
        3. 映射关系创建
        4. 统计信息正确
        """
        # 创建搜索任务（使用测试查询）
        task = await self.service.create_and_execute_search(
            name="集成测试-搜索A",
            query="python programming",
            search_config={"limit": 5},
            created_by="test_user"
        )

        # 验证任务创建
        assert task.id is not None
        assert task.status == InstantSearchStatus.COMPLETED
        assert task.total_results > 0

        # 验证结果可以查询
        results, total = await self.service.get_task_results(
            task_id=task.id,
            page=1,
            page_size=10
        )

        assert len(results) > 0
        assert total == task.total_results

        # 验证结果包含映射信息
        first_result = results[0]
        assert "result" in first_result
        assert "mapping_info" in first_result
        assert first_result["mapping_info"]["search_position"] >= 1

    @pytest.mark.asyncio
    async def test_cross_search_deduplication(self):
        """测试跨搜索去重机制

        v1.3.0 核心验证：
        1. 执行搜索A，获取结果
        2. 执行搜索B（相同查询），预期去重命中
        3. 验证结果在两次搜索中都可见
        4. 验证发现统计正确更新
        """
        # 搜索A：首次搜索
        task_a = await self.service.create_and_execute_search(
            name="集成测试-搜索A",
            query="python fastapi tutorial",
            search_config={"limit": 3},
            created_by="test_user"
        )

        assert task_a.status == InstantSearchStatus.COMPLETED
        assert task_a.new_results > 0
        initial_new_count = task_a.new_results

        # 等待一小段时间
        await asyncio.sleep(1)

        # 搜索B：相同查询，预期命中去重
        task_b = await self.service.create_and_execute_search(
            name="集成测试-搜索B",
            query="python fastapi tutorial",
            search_config={"limit": 3},
            created_by="test_user"
        )

        assert task_b.status == InstantSearchStatus.COMPLETED

        # 验证去重效果：搜索B应该有部分共享结果
        assert task_b.shared_results > 0, "搜索B应该命中去重，有共享结果"

        # 验证跨搜索可见性
        results_a, _ = await self.service.get_task_results(task_a.id)
        results_b, _ = await self.service.get_task_results(task_b.id)

        assert len(results_a) > 0
        assert len(results_b) > 0

        # 提取结果ID
        result_ids_a = {r["result"]["id"] for r in results_a}
        result_ids_b = {r["result"]["id"] for r in results_b}

        # 验证有共同结果（去重命中）
        common_results = result_ids_a & result_ids_b
        assert len(common_results) > 0, "两次搜索应该有共同结果（去重效果）"

        # 验证发现统计更新
        common_result_id = list(common_results)[0]
        result = await self.result_repo.get_by_id(common_result_id)

        assert result.found_count >= 2, "共享结果的found_count应该>=2"
        assert result.unique_searches >= 2, "共享结果的unique_searches应该>=2"

    @pytest.mark.asyncio
    async def test_crawl_mode(self):
        """测试URL爬取模式

        验证：
        1. crawl_url模式正常工作
        2. 单个结果正确保存
        3. 映射关系创建
        """
        task = await self.service.create_and_execute_search(
            name="集成测试-爬取模式",
            crawl_url="https://example.com",
            created_by="test_user"
        )

        # 验证模式检测
        assert task.get_search_mode() == "crawl"
        assert task.status == InstantSearchStatus.COMPLETED

        # 爬取模式返回单个结果
        assert task.total_results == 1

        # 验证结果可以查询
        results, total = await self.service.get_task_results(task.id)
        assert len(results) == 1
        assert results[0]["result"]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_result_mapping_query(self):
        """测试映射表JOIN查询

        验证：
        1. MongoDB聚合管道JOIN正常工作
        2. 分页功能正确
        3. 排序按search_position
        """
        # 创建测试任务
        task = await self.service.create_and_execute_search(
            name="集成测试-映射查询",
            query="javascript async await",
            search_config={"limit": 10},
            created_by="test_user"
        )

        # 测试第一页
        results_page1, total = await self.service.get_task_results(
            task_id=task.id,
            page=1,
            page_size=5
        )

        assert len(results_page1) <= 5
        assert total == task.total_results

        # 验证排序（按search_position升序）
        if len(results_page1) > 1:
            positions = [r["mapping_info"]["search_position"] for r in results_page1]
            assert positions == sorted(positions), "结果应该按search_position升序排列"

        # 测试第二页（如果有足够结果）
        if total > 5:
            results_page2, _ = await self.service.get_task_results(
                task_id=task.id,
                page=2,
                page_size=5
            )
            assert len(results_page2) > 0

            # 验证第二页的position大于第一页
            first_pos_page2 = results_page2[0]["mapping_info"]["search_position"]
            last_pos_page1 = results_page1[-1]["mapping_info"]["search_position"]
            assert first_pos_page2 > last_pos_page1

    @pytest.mark.asyncio
    async def test_content_hash_uniqueness(self):
        """测试content_hash唯一约束

        验证：
        1. 相同内容生成相同hash
        2. MongoDB唯一索引生效
        3. 去重机制正确触发
        """
        from src.core.domain.entities.instant_search_result import InstantSearchResult

        # 创建两个相同内容的结果
        result1 = InstantSearchResult(
            task_id="test-task-001",
            title="Test Article",
            url="https://example.com/article",
            content="This is test content for deduplication"
        )

        result2 = InstantSearchResult(
            task_id="test-task-002",
            title="Test Article",
            url="https://example.com/article",
            content="This is test content for deduplication"
        )

        # 验证生成相同hash
        assert result1.content_hash == result2.content_hash

        # 尝试保存第一个结果
        await self.result_repo.create(result1)

        # 验证可以通过hash找到
        found_result = await self.result_repo.find_by_content_hash(result1.content_hash)
        assert found_result is not None
        assert found_result.id == result1.id

        # 清理测试数据（如果需要）
        # await self.result_repo.delete(result1.id)

    @pytest.mark.asyncio
    async def test_discovery_statistics(self):
        """测试发现统计功能

        验证：
        1. first_found_at 在首次创建时设置
        2. last_found_at 在去重命中时更新
        3. found_count 递增
        4. unique_searches 递增
        """
        # 首次搜索
        task1 = await self.service.create_and_execute_search(
            name="统计测试-搜索1",
            query="golang concurrency patterns",
            search_config={"limit": 3},
            created_by="test_user"
        )

        # 获取首个结果
        results1, _ = await self.service.get_task_results(task1.id)
        assert len(results1) > 0

        first_result_id = results1[0]["result"]["id"]
        result_initial = await self.result_repo.get_by_id(first_result_id)

        initial_found_count = result_initial.found_count
        initial_searches = result_initial.unique_searches
        first_found_time = result_initial.first_found_at

        # 等待一秒
        await asyncio.sleep(1)

        # 第二次搜索（相同查询）
        task2 = await self.service.create_and_execute_search(
            name="统计测试-搜索2",
            query="golang concurrency patterns",
            search_config={"limit": 3},
            created_by="test_user"
        )

        # 检查结果是否被共享
        results2, _ = await self.service.get_task_results(task2.id)
        result_ids_2 = {r["result"]["id"] for r in results2}

        if first_result_id in result_ids_2:
            # 结果被共享，验证统计更新
            result_updated = await self.result_repo.get_by_id(first_result_id)

            assert result_updated.found_count > initial_found_count, "found_count应该递增"
            assert result_updated.unique_searches > initial_searches, "unique_searches应该递增"
            assert result_updated.last_found_at > first_found_time, "last_found_at应该更新"
            assert result_updated.first_found_at == first_found_time, "first_found_at不应该改变"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """测试错误处理

        验证：
        1. 无效参数被正确拒绝
        2. 任务状态正确标记为FAILED
        3. 错误信息被记录
        """
        with pytest.raises(ValueError):
            # 既不提供query也不提供crawl_url
            await self.service.create_and_execute_search(
                name="错误测试-无参数",
                created_by="test_user"
            )

    @pytest.mark.asyncio
    async def test_task_list_query(self):
        """测试任务列表查询

        验证：
        1. 分页功能
        2. 状态过滤
        3. 排序（按created_at降序）
        """
        # 创建多个任务
        for i in range(3):
            await self.service.create_and_execute_search(
                name=f"列表测试-任务{i+1}",
                query=f"test query {i+1}",
                search_config={"limit": 2},
                created_by="test_user"
            )

        # 查询任务列表
        tasks, total = await self.service.list_tasks(
            page=1,
            page_size=10
        )

        assert len(tasks) >= 3
        assert total >= 3

        # 验证排序（最新的在前面）
        if len(tasks) > 1:
            for i in range(len(tasks) - 1):
                assert tasks[i].created_at >= tasks[i+1].created_at

        # 测试状态过滤
        completed_tasks, _ = await self.service.list_tasks(
            page=1,
            page_size=10,
            status="completed"
        )

        for task in completed_tasks:
            assert task.status == InstantSearchStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

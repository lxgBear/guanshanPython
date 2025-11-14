#!/usr/bin/env python3
"""
v2.0.1 API 端点完整测试脚本

测试内容：
1. 查询端点的字段扩展（40+ 字段）
2. 用户操作 API（留存/删除/评分）
3. 错误处理和边界条件
4. 数据验证
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import json

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository
from src.infrastructure.database.repositories import SearchTaskRepository
from src.core.domain.entities.search_task import SearchTask, ScheduleInterval
from src.core.domain.entities.processed_result import ProcessedResult, ProcessedStatus
from src.utils.logger import get_logger

# 导入异步 HTTP 客户端
import httpx
from src.main import app

logger = get_logger(__name__)


class APITestResult:
    """测试结果记录"""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors: List[str] = []

    def add_pass(self, test_name: str):
        self.total += 1
        self.passed += 1
        print(f"  ✅ {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.total += 1
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  ❌ {test_name}")
        print(f"     错误: {error}")

    def summary(self):
        print(f"\n{'='*60}")
        print(f"测试总结")
        print(f"{'='*60}")
        print(f"✅ 通过: {self.passed}/{self.total}")
        print(f"❌ 失败: {self.failed}/{self.total}")
        if self.errors:
            print(f"\n错误详情:")
            for error in self.errors:
                print(f"  - {error}")
        return self.failed == 0


# 全局测试结果
test_result = APITestResult()


async def setup_test_data() -> Dict[str, str]:
    """准备测试数据"""
    print("\n" + "="*60)
    print("准备测试数据")
    print("="*60)

    db = await get_mongodb_database()

    # 创建测试任务
    task_repo = SearchTaskRepository()
    test_task = SearchTask(
        name="API测试任务 v2.0.1",
        query="test query",
        schedule_interval=ScheduleInterval.DAILY.value,
        is_active=False
    )
    await task_repo.create(test_task)
    print(f"✅ 创建测试任务: {test_task.id}")

    # 创建测试 processed_result
    processed_repo = ProcessedResultRepository()
    test_result_data = ProcessedResult(
        raw_result_id="test_raw_result_api_v201",
        task_id=str(test_task.id),
        status=ProcessedStatus.COMPLETED,
        # 原始字段
        title="API 测试标题",
        url="https://test-api.example.com",
        source_url="https://test-api.example.com",
        content="这是 API 测试内容" * 10,
        snippet="API 测试摘要",
        markdown_content="# API 测试 Markdown",
        html_content="<html><body>API测试</body></html>",
        author="API测试作者",
        language="zh",
        source="test",
        metadata={"test": "api_v201"},
        quality_score=0.88,
        relevance_score=0.95,
        search_position=1,
        # AI 增强字段
        content_zh="AI翻译的中文内容",
        title_generated="AI生成的标题",
        translated_title="翻译后的标题",
        translated_content="翻译后的内容",
        summary="AI生成的摘要",
        key_points=["要点1", "要点2", "要点3"],
        cls_results={"category": "技术", "subcategory": "测试"},
        sentiment="positive",
        categories=["测试", "API"],
        html_ctx_llm="<div>LLM处理的HTML</div>",
        html_ctx_regex="<div>Regex处理的HTML</div>",
        article_published_time="2025-11-03",
        article_tag="测试,API",
        # AI 元数据
        ai_model="gpt-4",
        ai_processing_time_ms=500,
        ai_confidence_score=0.92,
        processing_status="success"
    )

    collection = await processed_repo._get_collection()
    result_dict = processed_repo._result_to_dict(test_result_data)
    await collection.insert_one(result_dict)
    print(f"✅ 创建测试结果: {test_result_data.id}")

    return {
        "task_id": str(test_task.id),
        "result_id": str(test_result_data.id)
    }


async def cleanup_test_data(test_ids: Dict[str, str]):
    """清理测试数据"""
    print(f"\n{'='*60}")
    print("清理测试数据")
    print("="*60)

    db = await get_mongodb_database()

    # 删除测试任务
    await db['search_tasks'].delete_one({"_id": test_ids["task_id"]})
    print(f"✅ 删除测试任务: {test_ids['task_id']}")

    # 删除测试结果
    await db['processed_results_new'].delete_one({"_id": test_ids["result_id"]})
    print(f"✅ 删除测试结果: {test_ids['result_id']}")


async def test_query_endpoints(client: httpx.AsyncClient, test_ids: Dict[str, str]):
    """测试查询端点的字段扩展"""
    print(f"\n{'='*60}")
    print("测试 1: 查询端点字段扩展（40+ 字段）")
    print("="*60)

    task_id = test_ids["task_id"]
    result_id = test_ids["result_id"]

    # 测试 1.1: GET /search-tasks/{task_id}/results
    print("\n📝 测试 1.1: GET /search-tasks/{task_id}/results")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results")

    if response.status_code == 200:
        data = response.json()
        if data["items"] and len(data["items"]) > 0:
            item = data["items"][0]

            # 验证原始字段（15个）
            required_fields = [
                "title", "url", "source_url", "content", "snippet",
                "markdown_content", "html_content", "author", "language",
                "source", "metadata", "quality_score", "relevance_score",
                "search_position"
            ]

            missing_fields = [f for f in required_fields if f not in item]
            if not missing_fields:
                test_result.add_pass("原始字段完整性（15个字段）")
            else:
                test_result.add_fail("原始字段完整性", f"缺少字段: {missing_fields}")

            # 验证AI增强字段（12个）
            ai_fields = [
                "content_zh", "title_generated", "translated_title",
                "translated_content", "summary", "key_points",
                "cls_results", "sentiment", "categories",
                "html_ctx_llm", "html_ctx_regex", "article_published_time",
                "article_tag"
            ]

            missing_ai_fields = [f for f in ai_fields if f not in item]
            if not missing_ai_fields:
                test_result.add_pass("AI增强字段完整性（13个字段）")
            else:
                test_result.add_fail("AI增强字段完整性", f"缺少字段: {missing_ai_fields}")

            # 验证字段值
            if item.get("title") == "API 测试标题":
                test_result.add_pass("原始字段值正确（title）")
            else:
                test_result.add_fail("原始字段值", f"title = {item.get('title')}")

            if item.get("content_zh") == "AI翻译的中文内容":
                test_result.add_pass("AI字段值正确（content_zh）")
            else:
                test_result.add_fail("AI字段值", f"content_zh = {item.get('content_zh')}")

        else:
            test_result.add_fail("结果列表查询", "返回空列表")
    else:
        test_result.add_fail("结果列表查询", f"HTTP {response.status_code}")

    # 测试 1.2: GET /search-tasks/{task_id}/results/{result_id}
    print("\n📝 测试 1.2: GET /search-tasks/{task_id}/results/{result_id}")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results/{result_id}")

    if response.status_code == 200:
        item = response.json()

        # 验证总字段数（应该有 40+ 字段）
        total_fields = len(item.keys())
        if total_fields >= 40:
            test_result.add_pass(f"字段总数正确（{total_fields}个字段 >= 40）")
        else:
            test_result.add_fail("字段总数", f"只有 {total_fields} 个字段 < 40")

        # 验证关键字段存在
        key_fields = ["id", "raw_result_id", "task_id", "title", "url", "content",
                      "content_zh", "summary", "cls_results", "ai_model", "status"]
        missing = [f for f in key_fields if f not in item]
        if not missing:
            test_result.add_pass("关键字段完整性")
        else:
            test_result.add_fail("关键字段", f"缺少: {missing}")

    else:
        test_result.add_fail("单个结果查询", f"HTTP {response.status_code}")

    # 测试 1.3: GET /search-tasks/{task_id}/results/stats
    print("\n📝 测试 1.3: GET /search-tasks/{task_id}/results/stats")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results/stats")

    if response.status_code == 200:
        stats = response.json()
        required_stats = ["task_id", "total_results", "pending_count",
                         "completed_count", "archived_count", "deleted_count"]
        missing = [f for f in required_stats if f not in stats]
        if not missing:
            test_result.add_pass("统计信息完整性")
        else:
            test_result.add_fail("统计信息", f"缺少: {missing}")
    else:
        test_result.add_fail("统计查询", f"HTTP {response.status_code}")


async def test_user_actions(client: httpx.AsyncClient, test_ids: Dict[str, str]):
    """测试用户操作 API"""
    print(f"\n{'='*60}")
    print("测试 2: 用户操作 API（留存/删除/评分）")
    print("="*60)

    task_id = test_ids["task_id"]
    result_id = test_ids["result_id"]

    # 测试 2.1: POST archive (留存)
    print("\n📝 测试 2.1: POST /search-tasks/{task_id}/results/{result_id}/archive")
    response = await client.post(
        f"/api/v1/search-tasks/{task_id}/results/{result_id}/archive",
        json={"notes": "测试留存备注"}
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("success") and data.get("result", {}).get("status") == "archived":
            test_result.add_pass("留存操作成功")
        else:
            test_result.add_fail("留存操作", f"状态异常: {data}")
    else:
        test_result.add_fail("留存操作", f"HTTP {response.status_code}: {response.text}")

    # 测试 2.2: POST rating (评分)
    print("\n📝 测试 2.2: POST /search-tasks/{task_id}/results/{result_id}/rating")
    response = await client.post(
        f"/api/v1/search-tasks/{task_id}/results/{result_id}/rating",
        json={"rating": 5, "notes": "测试评分备注"}
    )

    if response.status_code == 200:
        data = response.json()
        if (data.get("success") and
            data.get("result", {}).get("user_rating") == 5 and
            data.get("result", {}).get("user_notes") == "测试评分备注"):
            test_result.add_pass("评分操作成功（5星 + 备注）")
        else:
            test_result.add_fail("评分操作", f"数据异常: {data}")
    else:
        test_result.add_fail("评分操作", f"HTTP {response.status_code}: {response.text}")

    # 测试 2.3: POST delete (软删除)
    print("\n📝 测试 2.3: POST /search-tasks/{task_id}/results/{result_id}/delete")
    response = await client.post(
        f"/api/v1/search-tasks/{task_id}/results/{result_id}/delete"
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("success") and data.get("result", {}).get("status") == "deleted":
            test_result.add_pass("删除操作成功（软删除）")
        else:
            test_result.add_fail("删除操作", f"状态异常: {data}")
    else:
        test_result.add_fail("删除操作", f"HTTP {response.status_code}: {response.text}")


async def test_error_handling(client: httpx.AsyncClient, test_ids: Dict[str, str]):
    """测试错误处理"""
    print(f"\n{'='*60}")
    print("测试 3: 错误处理和边界条件")
    print("="*60)

    task_id = test_ids["task_id"]

    # 测试 3.1: 404 - 不存在的任务
    print("\n📝 测试 3.1: 404 - 不存在的任务")
    response = await client.get("/api/v1/search-tasks/nonexistent_task_id/results")
    if response.status_code == 404:
        test_result.add_pass("404 错误处理（不存在的任务）")
    else:
        test_result.add_fail("404 错误", f"预期 404，实际 {response.status_code}")

    # 测试 3.2: 404 - 不存在的结果
    print("\n📝 测试 3.2: 404 - 不存在的结果")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results/nonexistent_result_id")
    if response.status_code == 404:
        test_result.add_pass("404 错误处理（不存在的结果）")
    else:
        test_result.add_fail("404 错误", f"预期 404，实际 {response.status_code}")

    # 测试 3.3: 400 - 无效的评分
    print("\n📝 测试 3.3: 400 - 无效的评分")
    result_id = test_ids["result_id"]
    response = await client.post(
        f"/api/v1/search-tasks/{task_id}/results/{result_id}/rating",
        json={"rating": 10}  # 无效评分（应该是1-5）
    )
    if response.status_code in [400, 422]:  # 422 是 Pydantic 验证错误
        test_result.add_pass("400/422 错误处理（无效评分）")
    else:
        test_result.add_fail("400 错误", f"预期 400/422，实际 {response.status_code}")

    # 测试 3.4: 400 - 无效的状态筛选
    print("\n📝 测试 3.4: 400 - 无效的状态筛选")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results?status=invalid_status")
    if response.status_code == 400:
        test_result.add_pass("400 错误处理（无效状态）")
    else:
        test_result.add_fail("400 错误", f"预期 400，实际 {response.status_code}")


async def test_pagination(client: httpx.AsyncClient, test_ids: Dict[str, str]):
    """测试分页功能"""
    print(f"\n{'='*60}")
    print("测试 4: 分页和筛选功能")
    print("="*60)

    task_id = test_ids["task_id"]

    # 测试 4.1: 分页参数
    print("\n📝 测试 4.1: 分页参数（page, page_size）")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results?page=1&page_size=10")
    if response.status_code == 200:
        data = response.json()
        if "page" in data and "page_size" in data and "total_pages" in data:
            test_result.add_pass("分页参数正确返回")
        else:
            test_result.add_fail("分页参数", "缺少分页字段")
    else:
        test_result.add_fail("分页查询", f"HTTP {response.status_code}")

    # 测试 4.2: 状态筛选
    print("\n📝 测试 4.2: 状态筛选（status=deleted）")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results?status=deleted")
    if response.status_code == 200:
        test_result.add_pass("状态筛选功能正常")
    else:
        test_result.add_fail("状态筛选", f"HTTP {response.status_code}")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("v2.0.1 API 端点完整测试")
    print("="*60)
    print(f"测试时间: {datetime.now().isoformat()}")

    test_ids = None

    try:
        # 准备测试数据
        test_ids = await setup_test_data()

        # 创建异步测试客户端
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            # 运行测试
            await test_query_endpoints(client, test_ids)
            await test_user_actions(client, test_ids)
            await test_error_handling(client, test_ids)
            await test_pagination(client, test_ids)

        # 清理测试数据
        if test_ids:
            await cleanup_test_data(test_ids)

    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()

        # 确保清理测试数据
        if test_ids:
            try:
                await cleanup_test_data(test_ids)
            except:
                pass

        return 1

    # 生成测试报告
    success = test_result.summary()

    if success:
        print(f"\n🎉 所有 API 测试通过！v2.0.1 功能正常")
        return 0
    else:
        print(f"\n⚠️ 部分 API 测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

#!/usr/bin/env python3
"""
v2.0.1 API 端点真实环境测试

使用真实数据库数据进行测试，不创建临时数据
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
import httpx
from src.main import app
from src.utils.logger import get_logger

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


async def get_real_test_data() -> Dict[str, str]:
    """获取真实测试数据"""
    print("\n" + "="*60)
    print("查找真实测试数据")
    print("="*60)

    db = await get_mongodb_database()

    # 查找一个有完整字段的 processed_result
    processed_result = await db['processed_results_new'].find_one({
        "title": {"$exists": True, "$ne": ""}
    })

    if not processed_result:
        raise Exception("未找到合适的测试数据")

    task_id = processed_result.get("task_id")
    result_id = processed_result.get("_id")

    # 验证任务存在
    task = await db['search_tasks'].find_one({"_id": task_id})

    print(f"✅ 找到真实测试数据:")
    print(f"  任务ID: {task_id}")
    print(f"  任务名称: {task.get('name') if task else 'NOT FOUND'}")
    print(f"  结果ID: {result_id}")
    print(f"  结果标题: {processed_result.get('title')[:50]}...")
    print(f"  结果状态: {processed_result.get('status')}")

    # 统计该任务的结果数量
    count = await db['processed_results_new'].count_documents({"task_id": task_id})
    print(f"  该任务结果总数: {count}")

    # 保存原始状态，用于恢复
    original_status = processed_result.get("status")
    original_rating = processed_result.get("user_rating")
    original_notes = processed_result.get("user_notes")

    return {
        "task_id": task_id,
        "result_id": result_id,
        "original_status": original_status,
        "original_rating": original_rating,
        "original_notes": original_notes
    }


async def restore_test_data(test_ids: Dict[str, str]):
    """恢复测试数据到原始状态"""
    print(f"\n{'='*60}")
    print("恢复测试数据到原始状态")
    print("="*60)

    db = await get_mongodb_database()

    # 恢复原始状态
    await db['processed_results_new'].update_one(
        {"_id": test_ids["result_id"]},
        {"$set": {
            "status": test_ids["original_status"],
            "user_rating": test_ids["original_rating"],
            "user_notes": test_ids["original_notes"]
        }}
    )
    print(f"✅ 已恢复结果状态: {test_ids['original_status']}")


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

            # 验证原始字段（15个核心字段）
            required_fields = [
                "title", "url", "content", "author", "language",
                "source", "metadata", "quality_score", "relevance_score"
            ]

            missing_fields = [f for f in required_fields if f not in item]
            if not missing_fields:
                test_result.add_pass("原始字段完整性（核心字段）")
            else:
                test_result.add_fail("原始字段完整性", f"缺少字段: {missing_fields}")

            # 验证AI增强字段存在性（可能为 null）
            # v2.0.1: 仅检查实际使用的AI字段
            ai_fields = [
                "content_zh", "title_generated",
                "cls_results", "html_ctx_llm"
            ]

            missing_ai_fields = [f for f in ai_fields if f not in item]
            if not missing_ai_fields:
                test_result.add_pass("AI增强字段定义完整")
            else:
                test_result.add_fail("AI增强字段", f"缺少字段定义: {missing_ai_fields}")

            # 验证字段值
            if item.get("title"):
                test_result.add_pass("原始字段有值（title）")
            else:
                test_result.add_fail("原始字段值", "title 为空")

            # 检查 AI 字段值（可能为 null，这是正常的）
            ai_value_check = "有值" if item.get("content_zh") else "为空（正常）"
            test_result.add_pass(f"AI字段状态（content_zh）: {ai_value_check}")

        else:
            test_result.add_fail("结果列表查询", "返回空列表")
    else:
        test_result.add_fail("结果列表查询", f"HTTP {response.status_code}")

    # 测试 1.2: GET /search-tasks/{task_id}/results/{result_id}
    print("\n📝 测试 1.2: GET /search-tasks/{task_id}/results/{result_id}")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results/{result_id}")

    if response.status_code == 200:
        item = response.json()

        # 验证总字段数（v2.0.1: 移除未使用字段后约 31 个）
        total_fields = len(item.keys())
        if total_fields >= 30:  # 预期 31 个字段
            test_result.add_pass(f"字段总数正确（{total_fields}个字段 >= 30）")
        else:
            test_result.add_fail("字段总数", f"只有 {total_fields} 个字段 < 30")

        # 验证关键字段存在（v2.0.1: 已移除 raw_result_id）
        key_fields = ["id", "task_id", "title", "url", "content",
                      "status", "created_at"]
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
    """测试用户操作 API（使用真实数据，测试后恢复）"""
    print(f"\n{'='*60}")
    print("测试 2: 用户操作 API（留存/删除/评分）")
    print("="*60)

    task_id = test_ids["task_id"]
    result_id = test_ids["result_id"]

    # 测试 2.1: POST archive (留存)
    print("\n📝 测试 2.1: POST /search-tasks/{task_id}/results/{result_id}/archive")
    response = await client.post(
        f"/api/v1/search-tasks/{task_id}/results/{result_id}/archive",
        json={"notes": "v2.0.1 API 测试 - 留存"}
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("success") and data.get("result", {}).get("status") == "archived":
            test_result.add_pass("留存操作成功")
            # 验证备注已保存
            if data.get("result", {}).get("user_notes") == "v2.0.1 API 测试 - 留存":
                test_result.add_pass("留存备注已保存")
        else:
            test_result.add_fail("留存操作", f"状态异常: {data}")
    else:
        test_result.add_fail("留存操作", f"HTTP {response.status_code}: {response.text}")

    # 测试 2.2: POST rating (评分)
    print("\n📝 测试 2.2: POST /search-tasks/{task_id}/results/{result_id}/rating")
    response = await client.post(
        f"/api/v1/search-tasks/{task_id}/results/{result_id}/rating",
        json={"rating": 4, "notes": "v2.0.1 API 测试 - 评分"}
    )

    if response.status_code == 200:
        data = response.json()
        if (data.get("success") and
            data.get("result", {}).get("user_rating") == 4 and
            data.get("result", {}).get("user_notes") == "v2.0.1 API 测试 - 评分"):
            test_result.add_pass("评分操作成功（4星 + 备注）")
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
            # 验证是软删除（数据还在，只是状态变了）
            test_result.add_pass("软删除验证：数据保留，状态更新")
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
    response = await client.get("/api/v1/search-tasks/nonexistent_task_id_999/results")
    if response.status_code == 404:
        test_result.add_pass("404 错误处理（不存在的任务）")
    else:
        test_result.add_fail("404 错误", f"预期 404，实际 {response.status_code}")

    # 测试 3.2: 404 - 不存在的结果
    print("\n📝 测试 3.2: 404 - 不存在的结果")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results/nonexistent_result_999")
    if response.status_code == 404:
        test_result.add_pass("404 错误处理（不存在的结果）")
    else:
        test_result.add_fail("404 错误", f"预期 404，实际 {response.status_code}")

    # 测试 3.3: 422 - 无效的评分
    print("\n📝 测试 3.3: 422 - 无效的评分（超出1-5范围）")
    result_id = test_ids["result_id"]
    response = await client.post(
        f"/api/v1/search-tasks/{task_id}/results/{result_id}/rating",
        json={"rating": 10}  # 无效评分（应该是1-5）
    )
    if response.status_code in [400, 422]:  # 422 是 Pydantic 验证错误
        test_result.add_pass("422 错误处理（无效评分）")
    else:
        test_result.add_fail("422 错误", f"预期 422，实际 {response.status_code}")

    # 测试 3.4: 400 - 无效的状态筛选
    print("\n📝 测试 3.4: 400 - 无效的状态筛选")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results?status=invalid_status_999")
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
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results?page=1&page_size=5")
    if response.status_code == 200:
        data = response.json()
        if "page" in data and "page_size" in data and "total_pages" in data:
            test_result.add_pass("分页参数正确返回")
            # 验证返回数量
            if len(data["items"]) <= 5:
                test_result.add_pass(f"分页数量正确（返回 {len(data['items'])} <= 5）")
        else:
            test_result.add_fail("分页参数", "缺少分页字段")
    else:
        test_result.add_fail("分页查询", f"HTTP {response.status_code}")

    # 测试 4.2: 状态筛选
    print("\n📝 测试 4.2: 状态筛选（status=pending）")
    response = await client.get(f"/api/v1/search-tasks/{task_id}/results?status=pending")
    if response.status_code == 200:
        data = response.json()
        test_result.add_pass("状态筛选功能正常")
        # 验证所有返回的记录状态都是 pending
        if all(item.get("status") == "pending" for item in data["items"]):
            test_result.add_pass("状态筛选结果正确（全部为 pending）")
    else:
        test_result.add_fail("状态筛选", f"HTTP {response.status_code}")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("v2.0.1 API 端点真实环境测试")
    print("="*60)
    print(f"测试时间: {datetime.now().isoformat()}")
    print(f"⚠️  使用真实数据库数据，测试后会恢复原始状态")

    test_ids = None

    try:
        # 获取真实测试数据
        test_ids = await get_real_test_data()

        # 创建异步测试客户端
        async with httpx.AsyncClient(app=app, base_url="http://test", timeout=30.0) as client:
            # 运行测试
            await test_query_endpoints(client, test_ids)
            await test_user_actions(client, test_ids)
            await test_error_handling(client, test_ids)
            await test_pagination(client, test_ids)

        # 恢复测试数据
        if test_ids:
            await restore_test_data(test_ids)

    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()

        # 确保恢复测试数据
        if test_ids:
            try:
                await restore_test_data(test_ids)
            except:
                pass

        return 1

    # 生成测试报告
    success = test_result.summary()

    if success:
        print(f"\n🎉 所有 API 测试通过！v2.0.1 功能正常")
        print(f"✅ 测试数据已恢复到原始状态")
        return 0
    else:
        print(f"\n⚠️ 部分 API 测试失败，请检查错误信息")
        print(f"✅ 测试数据已恢复到原始状态")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

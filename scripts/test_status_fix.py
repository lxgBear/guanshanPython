"""测试 status 字段错误处理修复

验证即使数据库中有无效的 status 值，API 也能正常工作
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository
from src.core.domain.entities.processed_result import ProcessedStatus


async def test_status_handling():
    """测试无效 status 值的处理"""
    print("🔍 测试 status 字段错误处理...")

    repo = ProcessedResultRepository()

    try:
        # 测试 1: 获取所有任务结果
        print("\n测试 1: 获取任务 244383648711102464 的结果...")
        results, total = await repo.get_by_task(
            task_id="244383648711102464",
            page=1,
            page_size=5
        )

        print(f"✅ 成功获取 {len(results)} 条结果 (总数: {total})")

        for result in results:
            print(f"  - ID: {result.id}")
            print(f"    Status: {result.status.value}")
            print(f"    Title: {result.title[:50]}...")
            print()

        # 测试 2: 测试手动构造的无效数据
        print("\n测试 2: 测试无效 status 值处理...")
        invalid_data = {
            "_id": "test_id",
            "task_id": "test_task",
            "status": "这是一个无效的状态值",  # 无效的 status
            "title": "测试标题",
            "url": "http://test.com"
        }

        result = repo._dict_to_result(invalid_data)
        print(f"✅ 成功处理无效 status 值")
        print(f"   原始值: '这是一个无效的状态值'")
        print(f"   处理后: {result.status.value}")
        print(f"   默认值: {ProcessedStatus.PENDING.value}")

        assert result.status == ProcessedStatus.PENDING, "应该使用默认值 PENDING"

        print("\n✅ 所有测试通过！")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_status_handling())
    sys.exit(0 if success else 1)

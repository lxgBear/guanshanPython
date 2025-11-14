"""
测试修复后的智能搜索功能

使用原失败任务的查询创建新任务进行测试
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.smart_search_service import SmartSearchService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_smart_search():
    """测试智能搜索修复效果"""

    print(f"\n{'='*80}")
    print(f"测试智能搜索修复效果")
    print(f"{'='*80}\n")

    try:
        service = SmartSearchService()

        # 使用原失败任务的查询
        original_query = "东盟国家领导人会议释放了什么信号？"

        print(f"📝 原始查询: {original_query}\n")

        # 阶段1: 创建任务并分解查询
        print(f"{'='*80}")
        print(f"阶段1: 创建任务并分解查询")
        print(f"{'='*80}\n")

        task = await service.create_and_decompose(
            name=f"修复测试_{original_query[:20]}",
            query=original_query,
            created_by="test_user"
        )

        print(f"✅ 任务创建成功")
        print(f"   任务ID: {task.id}")
        print(f"   状态: {task.status.value}")
        print(f"   LLM分解的查询数: {len(task.decomposed_queries)}\n")

        print(f"📋 LLM分解的查询:")
        for idx, q in enumerate(task.decomposed_queries, 1):
            print(f"   {idx}. {q.query}")
            print(f"      原因: {q.reasoning}\n")

        # 阶段2: 确认并执行（只测试第一个查询以节省积分）
        print(f"{'='*80}")
        print(f"阶段2: 确认并执行（测试第一个子查询）")
        print(f"{'='*80}\n")

        # 只使用第一个查询进行测试
        confirmed_queries = [task.decomposed_queries[0].query]
        print(f"✅ 确认的查询: {confirmed_queries}\n")

        print(f"🔍 开始执行子搜索...\n")

        # 执行搜索
        task = await service.confirm_and_execute(
            task_id=task.id,
            confirmed_queries=confirmed_queries
        )

        # 结果分析
        print(f"{'='*80}")
        print(f"执行结果")
        print(f"{'='*80}\n")

        print(f"状态: {task.status.value}")
        print(f"错误信息: {task.error_message or '无'}")
        print(f"执行时间: {task.execution_time_ms}ms\n")

        if task.aggregated_stats:
            stats = task.aggregated_stats
            print(f"📊 聚合统计:")
            print(f"   总搜索数: {stats.get('total_searches', 0)}")
            print(f"   成功搜索: {stats.get('successful_searches', 0)}")
            print(f"   失败搜索: {stats.get('failed_searches', 0)}")
            print(f"   总结果数: {stats.get('total_results_raw', 0)}")
            print(f"   去重后结果: {stats.get('total_results_deduplicated', 0)}")
            print(f"   总积分消耗: {stats.get('total_credits_used', 0)}\n")

        # 子搜索详情
        print(f"🔍 子搜索详情:")
        for sub_task_id, sub_result in task.sub_search_results.items():
            print(f"\n   任务 {sub_task_id}:")
            print(f"     查询: {sub_result.query}")
            print(f"     状态: {sub_result.status}")
            print(f"     结果数: {sub_result.result_count}")
            print(f"     积分: {sub_result.credits_used}")
            print(f"     执行时间: {sub_result.execution_time_ms}ms")
            if sub_result.error:
                print(f"     错误: {sub_result.error}")

        # 测试结论
        print(f"\n{'='*80}")
        print(f"测试结论")
        print(f"{'='*80}\n")

        if task.status.value == "completed":
            print(f"✅ 测试通过: 智能搜索功能正常工作")
            print(f"   - 子搜索成功执行")
            print(f"   - 结果成功聚合")
            print(f"   - 未出现 AttributeError")
        elif task.status.value == "partial_success":
            print(f"⚠️  部分成功: 至少一个子搜索成功")
            print(f"   - 功能基本恢复")
            print(f"   - 建议检查失败的子搜索")
        else:
            print(f"❌ 测试失败: {task.error_message}")
            print(f"   - 状态: {task.status.value}")
            print(f"   - 需要进一步调查")

        return task

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """主函数"""
    await test_smart_search()


if __name__ == "__main__":
    asyncio.run(main())

"""
测试脚本：诊断即时搜索任务 238917114149052416 为何无内容返回

诊断步骤：
1. 检查任务是否存在及其状态
2. 验证 search_execution_id
3. 检查映射表中的记录
4. 检查结果表中的记录
5. 测试完整的查询流程
6. 返回前5条结果
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.instant_search_repositories import (
    InstantSearchTaskRepository,
    InstantSearchResultRepository,
    InstantSearchResultMappingRepository
)
from src.services.instant_search_service import InstantSearchService
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 测试的任务ID
TASK_ID = "238917114149052416"


async def diagnose_task():
    """诊断任务为何无内容"""

    print("=" * 80)
    print(f"诊断即时搜索任务: {TASK_ID}")
    print("=" * 80)

    task_repo = InstantSearchTaskRepository()
    result_repo = InstantSearchResultRepository()
    mapping_repo = InstantSearchResultMappingRepository()

    # ========== 步骤1: 检查任务是否存在 ==========
    print("\n[步骤1] 检查任务是否存在...")
    task = await task_repo.get_by_id(TASK_ID)

    if not task:
        print(f"❌ 错误: 任务 {TASK_ID} 不存在！")
        return

    print(f"✅ 任务存在")
    print(f"   - 任务名称: {task.name}")
    print(f"   - 状态: {task.status.value}")
    print(f"   - 搜索执行ID: {task.search_execution_id}")
    print(f"   - 总结果数: {task.total_results}")
    print(f"   - 新结果数: {task.new_results}")
    print(f"   - 共享结果数: {task.shared_results}")
    print(f"   - 搜索模式: {task.get_search_mode()}")
    print(f"   - 查询关键词: {task.query}")
    print(f"   - 爬取URL: {task.crawl_url}")
    print(f"   - 创建时间: {task.created_at}")
    print(f"   - 完成时间: {task.completed_at}")

    if task.error_message:
        print(f"   - ⚠️ 错误信息: {task.error_message}")

    # ========== 步骤2: 检查任务状态 ==========
    print("\n[步骤2] 分析任务状态...")

    if task.status.value == "failed":
        print(f"❌ 任务执行失败: {task.error_message}")
        return

    if task.status.value == "pending":
        print(f"⚠️ 任务尚未执行（状态: pending）")
        return

    if task.status.value == "running":
        print(f"⏳ 任务正在执行中（状态: running）")
        return

    if task.total_results == 0:
        print(f"⚠️ 任务已完成但总结果数为0")
        print(f"   可能原因:")
        print(f"   1. Firecrawl API 返回空结果")
        print(f"   2. 搜索参数配置问题")
        print(f"   3. 目标网站无可用内容")

    # ========== 步骤3: 检查映射表 ==========
    print("\n[步骤3] 检查映射表中的记录...")

    db = await get_mongodb_database()
    mappings_collection = db["instant_search_result_mappings"]

    # 统计该任务的映射数量
    mapping_count = await mappings_collection.count_documents({
        "search_execution_id": task.search_execution_id
    })

    print(f"   映射记录数: {mapping_count}")

    if mapping_count == 0:
        print(f"❌ 警告: 没有找到映射记录！")
        print(f"   这意味着搜索执行后没有创建任何结果映射。")
        print(f"   可能原因:")
        print(f"   1. Firecrawl 返回空结果列表")
        print(f"   2. 结果处理过程中出错（但任务标记为完成）")
        print(f"   3. 数据一致性问题")
    else:
        # 显示前5条映射记录
        print(f"   前5条映射记录:")
        cursor = mappings_collection.find({
            "search_execution_id": task.search_execution_id
        }).sort("search_position", 1).limit(5)

        async for idx, doc in enumerate(cursor, 1):
            print(f"   [{idx}] result_id: {doc['result_id']}, "
                  f"position: {doc.get('search_position', 'N/A')}, "
                  f"is_first: {doc.get('is_first_discovery', False)}")

    # ========== 步骤4: 检查结果表 ==========
    print("\n[步骤4] 检查结果表中的记录...")

    results_collection = db["instant_search_results"]

    # 通过 task_id 查询结果（旧方式，v1.3.0 已废弃）
    task_results_count = await results_collection.count_documents({
        "task_id": task.id
    })

    print(f"   通过task_id查询的结果数: {task_results_count}")

    if task_results_count > 0:
        print(f"   ⚠️ 注意: v1.3.0架构中，结果不再直接关联task_id")
        print(f"   应该通过映射表查询，而不是直接查询task_id")

    # ========== 步骤5: 测试完整查询流程 ==========
    print("\n[步骤5] 测试完整查询流程（通过映射表JOIN）...")

    try:
        service = InstantSearchService()
        results, total = await service.get_task_results(
            task_id=task.id,
            page=1,
            page_size=5
        )

        print(f"   ✅ 查询成功")
        print(f"   总结果数: {total}")
        print(f"   本页结果数: {len(results)}")

        if total == 0:
            print(f"\n❌ 根本原因: 映射表中没有该任务的记录")
            print(f"   search_execution_id: {task.search_execution_id}")
            print(f"   建议:")
            print(f"   1. 检查任务执行日志")
            print(f"   2. 验证 Firecrawl API 响应")
            print(f"   3. 检查 _process_and_save_results 方法是否被调用")

        # ========== 步骤6: 显示前5条结果 ==========
        if len(results) > 0:
            print(f"\n[步骤6] 前5条搜索结果:")
            for idx, item in enumerate(results, 1):
                result_data = item["result"]
                mapping_info = item["mapping_info"]

                print(f"\n   --- 结果 {idx} ---")
                print(f"   标题: {result_data.get('title', 'N/A')[:80]}")
                print(f"   URL: {result_data.get('url', 'N/A')[:100]}")
                print(f"   内容片段: {result_data.get('snippet', result_data.get('content', ''))[:150]}")
                print(f"   搜索位置: {mapping_info['search_position']}")
                print(f"   首次发现: {mapping_info['is_first_discovery']}")
                print(f"   发现时间: {mapping_info['found_at']}")
                print(f"   发现次数: {result_data.get('found_count', 1)}")

    except Exception as e:
        print(f"   ❌ 查询失败: {str(e)}")
        import traceback
        traceback.print_exc()

    # ========== 总结 ==========
    print("\n" + "=" * 80)
    print("诊断总结")
    print("=" * 80)

    if task.status.value == "completed" and task.total_results == 0:
        print("【问题】任务已完成但没有结果")
        print("【可能原因】")
        print("  1. Firecrawl API 对该查询返回空结果")
        print("  2. 搜索配置不当（例如：域名限制过严）")
        print("  3. 目标网站在搜索时无可用内容")
        print("【建议】")
        print("  1. 检查任务的 query 和 search_config 参数")
        print("  2. 使用 Firecrawl 测试同样的搜索参数")
        print("  3. 查看应用日志中的 Firecrawl 响应")

    elif mapping_count > 0 and task.total_results > 0:
        print("【状态】任务正常，结果可通过映射表查询")
        print(f"【结果统计】总计 {task.total_results} 条结果（新: {task.new_results}, 共享: {task.shared_results}）")

    else:
        print("【状态】数据一致性异常")
        print(f"  - 任务统计的总结果数: {task.total_results}")
        print(f"  - 映射表中的记录数: {mapping_count}")
        print(f"【建议】检查数据完整性和事务处理逻辑")


async def main():
    """主函数"""
    try:
        await diagnose_task()
    except Exception as e:
        logger.error(f"诊断过程出错: {str(e)}", exc_info=True)
        print(f"\n❌ 诊断过程出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n开始诊断即时搜索任务...\n")
    asyncio.run(main())
    print("\n诊断完成！\n")

"""
测试即时搜索功能 - 创建新任务并获取5条结果

验证修复后的 FirecrawlAdapter 是否能正常工作
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.instant_search_service import InstantSearchService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_instant_search_5_results():
    """测试即时搜索并获取5条结果"""

    print("=" * 80)
    print("测试即时搜索功能 - 获取5条结果")
    print("=" * 80)

    try:
        # 创建服务实例
        service = InstantSearchService()

        # 测试参数
        test_query = "特朗普最近的行程"
        test_name = f"测试搜索_{test_query}_5条结果"

        print(f"\n📝 测试参数:")
        print(f"   查询关键词: {test_query}")
        print(f"   任务名称: {test_name}")
        print(f"   结果限制: 5条")

        # 创建并执行搜索
        print(f"\n🚀 开始执行即时搜索...")

        task = await service.create_and_execute_search(
            name=test_name,
            query=test_query,
            search_config={'limit': 5},
            created_by="test_script"
        )

        print(f"\n✅ 搜索任务执行完成！")
        print(f"\n📊 任务统计:")
        print(f"   任务ID: {task.id}")
        print(f"   搜索执行ID: {task.search_execution_id}")
        print(f"   状态: {task.status.value}")
        print(f"   总结果数: {task.total_results}")
        print(f"   新结果: {task.new_results}")
        print(f"   共享结果: {task.shared_results}")
        print(f"   消耗积分: {task.credits_used}")
        print(f"   执行时间: {task.execution_time_ms}ms")

        if task.error_message:
            print(f"   ⚠️ 错误信息: {task.error_message}")

        # 如果成功，获取结果详情
        if task.status.value == "completed" and task.total_results > 0:
            print(f"\n📄 获取搜索结果详情...")

            results, total = await service.get_task_results(
                task_id=task.id,
                page=1,
                page_size=5
            )

            print(f"\n🎯 搜索结果 (共{total}条，显示前{len(results)}条):")
            print("=" * 80)

            for idx, item in enumerate(results, 1):
                result_data = item["result"]
                mapping_info = item["mapping_info"]

                print(f"\n【结果 {idx}】")
                print(f"标题: {result_data.get('title', 'N/A')}")
                print(f"URL: {result_data.get('url', 'N/A')[:100]}")

                # 显示内容片段
                content = result_data.get('content', '')
                snippet = result_data.get('snippet', '')
                display_text = snippet if snippet else content[:200]
                print(f"摘要: {display_text}...")

                # 映射信息
                print(f"搜索位置: 第{mapping_info['search_position']}位")
                print(f"首次发现: {'是' if mapping_info['is_first_discovery'] else '否'}")
                print(f"发现时间: {mapping_info['found_at']}")
                print(f"发现次数: {result_data.get('found_count', 1)}次")

                # 内容长度统计
                markdown_len = len(result_data.get('markdown_content', ''))
                html_len = len(result_data.get('html_content', ''))
                print(f"内容长度: markdown={markdown_len}字符, html={html_len}字符")
                print("-" * 80)

        elif task.status.value == "failed":
            print(f"\n❌ 任务执行失败")
            print(f"   错误原因: {task.error_message or '未知错误'}")

        else:
            print(f"\n⚠️ 任务未返回结果")
            print(f"   可能原因:")
            print(f"   1. Firecrawl API 对该查询没有找到结果")
            print(f"   2. 搜索参数配置需要调整")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    try:
        await test_instant_search_5_results()
    except Exception as e:
        logger.error(f"测试过程出错: {str(e)}", exc_info=True)
        print(f"\n❌ 测试过程出错: {str(e)}")


if __name__ == "__main__":
    print("\n开始测试即时搜索功能...\n")
    asyncio.run(main())
    print("\n测试完成！\n")

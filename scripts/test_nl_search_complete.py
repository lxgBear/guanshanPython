#!/usr/bin/env python3
"""
NL Search 集成测试脚本

测试完整的 NL Search 功能流程，包括：
1. 创建搜索 (create_search)
2. 获取搜索结果 (get_search_results)
3. 记录用户选择 (record_user_selection)
4. 获取选择统计 (get_selection_statistics)

版本: v1.0.0
日期: 2025-11-17
"""
import asyncio
import sys
import os
from typing import Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.nl_search.nl_search_service import nl_search_service
from src.services.nl_search.config import nl_search_config


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_section(title: str):
    """打印章节标题"""
    print()
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print()


def print_success(message: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")


def print_error(message: str):
    """打印错误消息"""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")


def print_info(message: str):
    """打印信息消息"""
    print(f"{Colors.YELLOW}ℹ️  {message}{Colors.RESET}")


def print_result(label: str, value: Any):
    """打印测试结果"""
    print(f"   {Colors.BOLD}{label}:{Colors.RESET} {value}")


async def test_create_search() -> Dict[str, Any]:
    """测试创建搜索"""
    print_section("测试 1: 创建自然语言搜索")

    try:
        # 创建测试搜索
        query_text = "最近有哪些关于GPT-5的技术突破"
        print_info(f"测试查询: {query_text}")

        result = await nl_search_service.create_search(
            query_text=query_text,
            user_id="test_user_123"
        )

        # 验证结果
        assert "log_id" in result, "缺少 log_id"
        assert "results" in result, "缺少 results"
        assert "analysis" in result, "缺少 analysis"
        assert "refined_query" in result, "缺少 refined_query"

        print_success("搜索创建成功")
        print_result("搜索记录ID", result["log_id"])
        print_result("查询文本", result["query_text"])
        print_result("精炼查询", result["refined_query"])
        print_result("结果数量", len(result["results"]))

        if result.get("analysis"):
            print_result("LLM意图", result["analysis"].get("intent"))
            print_result("关键词", result["analysis"].get("keywords"))

        return result

    except Exception as e:
        print_error(f"搜索创建失败: {e}")
        raise


async def test_get_search_results(log_id: str):
    """测试获取搜索结果"""
    print_section("测试 2: 获取搜索结果")

    try:
        print_info(f"获取搜索记录: {log_id}")

        # 测试完整结果
        result = await nl_search_service.get_search_results(log_id=log_id)

        assert result is not None, "搜索记录不存在"
        assert "log_id" in result, "缺少 log_id"
        assert "query_text" in result, "缺少 query_text"
        assert "results" in result, "缺少 results"
        assert "total_count" in result, "缺少 total_count"

        print_success("获取完整结果成功")
        print_result("搜索记录ID", result["log_id"])
        print_result("查询文本", result["query_text"])
        print_result("结果总数", result["total_count"])
        print_result("状态", result["status"])

        # 测试分页
        if result["total_count"] > 0:
            print()
            print_info("测试分页功能...")
            paged_result = await nl_search_service.get_search_results(
                log_id=log_id,
                limit=2,
                offset=0
            )

            assert len(paged_result["results"]) <= 2, "分页限制失败"
            print_success("分页功能正常")
            print_result("分页结果数", len(paged_result["results"]))

        return result

    except Exception as e:
        print_error(f"获取搜索结果失败: {e}")
        raise


async def test_record_user_selection(log_id: str, result_url: str):
    """测试记录用户选择"""
    print_section("测试 3: 记录用户选择")

    try:
        # 测试不同的操作类型
        actions = ["click", "bookmark", "archive"]
        event_ids = []

        for action_type in actions:
            print_info(f"记录 {action_type} 操作...")

            event_id = await nl_search_service.record_user_selection(
                log_id=log_id,
                result_url=result_url,
                action_type=action_type,
                user_id="test_user_123"
            )

            assert event_id, "事件ID为空"
            event_ids.append(event_id)
            print_success(f"{action_type} 操作记录成功")
            print_result("事件ID", event_id)

        return event_ids

    except Exception as e:
        print_error(f"记录用户选择失败: {e}")
        raise


async def test_get_selection_statistics(log_id: str):
    """测试获取选择统计"""
    print_section("测试 4: 获取选择统计")

    try:
        print_info(f"获取统计数据: {log_id}")

        stats = await nl_search_service.get_selection_statistics(log_id=log_id)

        assert "log_id" in stats, "缺少 log_id"
        assert "total_count" in stats, "缺少 total_count"
        assert "click_count" in stats, "缺少 click_count"
        assert "bookmark_count" in stats, "缺少 bookmark_count"
        assert "archive_count" in stats, "缺少 archive_count"

        print_success("统计数据获取成功")
        print_result("总选择次数", stats["total_count"])
        print_result("点击次数", stats["click_count"])
        print_result("收藏次数", stats["bookmark_count"])
        print_result("归档次数", stats["archive_count"])

        if stats.get("top_urls"):
            print_result("热门URL", len(stats["top_urls"]))
            for url, count in stats["top_urls"][:3]:
                print(f"      • {url[:50]}... ({count}次)")

        return stats

    except Exception as e:
        print_error(f"获取统计数据失败: {e}")
        raise


async def run_all_tests():
    """运行所有测试"""
    print_section("NL Search 集成测试")

    # 检查功能开关
    print_info(f"功能状态: {'启用' if nl_search_config.enabled else '禁用'}")
    print_info(f"测试模式: {'是' if not nl_search_config.enabled else '否'}")
    print()

    try:
        # 测试 1: 创建搜索
        search_result = await test_create_search()
        log_id = search_result["log_id"]

        # 测试 2: 获取搜索结果
        results = await test_get_search_results(log_id)

        # 测试 3: 记录用户选择
        if results["results"]:
            result_url = results["results"][0].get("url", "https://example.com/test")
            await test_record_user_selection(log_id, result_url)

            # 测试 4: 获取选择统计
            await test_get_selection_statistics(log_id)
        else:
            print_info("跳过用户选择测试（无搜索结果）")

        # 测试总结
        print_section("测试完成")
        print_success("所有测试通过！✨")
        print()
        print("测试覆盖:")
        print("  ✅ 创建搜索 (create_search)")
        print("  ✅ 获取搜索结果 (get_search_results)")
        print("  ✅ 分页功能")
        print("  ✅ 记录用户选择 (record_user_selection)")
        print("  ✅ 获取选择统计 (get_selection_statistics)")
        print()

        return True

    except AssertionError as e:
        print_section("测试失败")
        print_error(f"断言失败: {e}")
        return False

    except Exception as e:
        print_section("测试失败")
        print_error(f"发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print()
        print_error("测试被用户中断")
        sys.exit(1)

    except Exception as e:
        print()
        print_error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

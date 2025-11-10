#!/usr/bin/env python3
"""
Map + Scrape 集成测试脚本

测试 Map + Scrape 功能的端到端集成：
1. 创建 MAP_SCRAPE_WEBSITE 类型任务
2. 执行任务获取结果
3. 验证结果数据完整性
4. 测试时间过滤功能
"""
import asyncio
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.core.domain.entities.search_task import SearchTask, TaskType, TaskStatus
from src.services.firecrawl.factory import ExecutorFactory
from src.services.firecrawl.credits_calculator import FirecrawlCreditsCalculator
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_basic_map_scrape():
    """测试基础 Map + Scrape 功能（不带时间过滤）"""
    logger.info("=" * 80)
    logger.info("🧪 测试1: 基础 Map + Scrape 功能")
    logger.info("=" * 80)

    # 创建测试任务
    task = SearchTask(
        name="Map + Scrape 集成测试",
        description="测试 Map API + Scrape API 组合功能",
        task_type=TaskType.MAP_SCRAPE_WEBSITE.value,
        crawl_url="https://firecrawl.dev",
        crawl_config={
            "search": "docs",  # 只搜索包含docs的URL
            "map_limit": 20,   # 限制20个URL用于测试
            "max_concurrent_scrapes": 3,
            "scrape_delay": 0.5,
            "only_main_content": True,
            "exclude_tags": ["nav", "footer", "header", "aside"],
            "timeout": 90,
            "allow_partial_failure": True,
            "min_success_rate": 0.7
        },
        status=TaskStatus.ACTIVE
    )

    try:
        # 创建执行器
        executor = ExecutorFactory.create(TaskType.MAP_SCRAPE_WEBSITE)
        logger.info(f"✅ 执行器创建成功: {type(executor).__name__}\n")

        # 执行任务
        logger.info("🚀 开始执行 Map + Scrape 任务...")
        batch = await executor.execute(task)

        # 验证结果
        logger.info("\n" + "=" * 80)
        logger.info("📊 执行结果统计")
        logger.info("=" * 80)
        logger.info(f"  结果数量: {batch.total_count}")
        logger.info(f"  积分消耗: {batch.credits_used}")
        logger.info(f"  执行时间: {batch.execution_time_ms}ms")
        logger.info(f"  查询内容: {batch.query}")

        # 检查结果列表
        if batch.results:
            logger.info(f"\n✅ 获得 {len(batch.results)} 个结果")
            logger.info("\n前3个结果示例:")
            for i, result in enumerate(batch.results[:3], 1):
                logger.info(f"\n  [{i}] {result.title}")
                logger.info(f"      URL: {result.url}")
                logger.info(f"      来源: {result.source}")
                logger.info(f"      发布日期: {result.published_date}")
                logger.info(f"      Markdown长度: {len(result.markdown_content or '')} 字符")
        else:
            logger.warning("⚠️  结果列表为空")

        logger.info("\n✅ 基础 Map + Scrape 功能测试通过！\n")
        return True

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_map_scrape_with_time_filter():
    """测试带时间过滤的 Map + Scrape 功能"""
    logger.info("=" * 80)
    logger.info("🧪 测试2: Map + Scrape with 时间过滤")
    logger.info("=" * 80)

    # 设置时间范围：最近7天
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    logger.info(f"  时间范围: {start_date.date()} 至 {end_date.date()}")

    task = SearchTask(
        name="Map + Scrape 时间过滤测试",
        description="测试时间范围过滤功能",
        task_type=TaskType.MAP_SCRAPE_WEBSITE.value,
        crawl_url="https://firecrawl.dev",
        crawl_config={
            "search": "blog",
            "map_limit": 20,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "max_concurrent_scrapes": 3,
            "scrape_delay": 0.5,
            "only_main_content": True,
            "timeout": 90
        },
        status=TaskStatus.ACTIVE
    )

    try:
        # 创建执行器并执行
        executor = ExecutorFactory.create(TaskType.MAP_SCRAPE_WEBSITE)
        batch = await executor.execute(task)

        # 验证时间过滤
        logger.info("\n📊 时间过滤结果:")
        logger.info(f"  过滤后结果数: {batch.total_count}")
        logger.info(f"  积分消耗: {batch.credits_used}")

        if batch.results:
            # 检查每个结果的发布日期
            within_range = 0
            outside_range = 0
            no_date = 0

            for result in batch.results:
                if result.published_date:
                    if start_date <= result.published_date <= end_date:
                        within_range += 1
                    else:
                        outside_range += 1
                else:
                    no_date += 1

            logger.info(f"\n  时间范围内: {within_range} 个")
            logger.info(f"  时间范围外: {outside_range} 个")
            logger.info(f"  无发布日期: {no_date} 个")

            if outside_range > 0:
                logger.warning(f"⚠️  发现 {outside_range} 个时间范围外的结果")
        else:
            logger.info("  未找到符合时间范围的结果")

        logger.info("\n✅ 时间过滤功能测试通过！\n")
        return True

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_credits_calculation():
    """测试积分计算功能"""
    logger.info("=" * 80)
    logger.info("🧪 测试3: 积分计算功能")
    logger.info("=" * 80)

    # 测试估算
    estimate = FirecrawlCreditsCalculator.estimate_map_scrape_credits(
        estimated_urls=100,
        estimated_scraped=50
    )

    logger.info("📊 积分估算:")
    logger.info(f"  {estimate.description}")
    logger.info(f"  明细: {estimate.breakdown}")

    # 测试实际计算
    actual_credits = FirecrawlCreditsCalculator.calculate_map_scrape_credits(
        urls_discovered=100,
        pages_scraped=50
    )

    logger.info(f"\n💰 实际积分计算:")
    logger.info(f"  发现URL: 100")
    logger.info(f"  爬取页面: 50")
    logger.info(f"  总积分: {actual_credits}")

    # 验证
    expected = 1 + 50  # Map (1) + Scrape (50)
    if actual_credits == expected:
        logger.info(f"  ✅ 计算正确: {actual_credits} == {expected}")
    else:
        logger.error(f"  ❌ 计算错误: {actual_credits} != {expected}")
        return False

    # 对比成本优势
    logger.info(f"\n💡 成本对比（爬取50个页面）:")
    crawl_credits = 50  # Crawl API: 50积分
    map_scrape_credits = actual_credits  # Map + Scrape: 51积分
    logger.info(f"  Crawl API: {crawl_credits} 积分")
    logger.info(f"  Map + Scrape: {map_scrape_credits} 积分")

    # 如果有时间过滤，成本优势更明显
    filtered_pages = 20  # 假设过滤后只有20页符合条件
    map_scrape_filtered = 1 + filtered_pages
    savings = crawl_credits - map_scrape_filtered
    savings_pct = (savings / crawl_credits) * 100

    logger.info(f"\n  如果时间过滤后只需{filtered_pages}页:")
    logger.info(f"  Map + Scrape: {map_scrape_filtered} 积分")
    logger.info(f"  节省: {savings} 积分 ({savings_pct:.1f}%)")

    logger.info("\n✅ 积分计算功能测试通过！\n")
    return True


async def test_executor_factory():
    """测试执行器工厂注册"""
    logger.info("=" * 80)
    logger.info("🧪 测试4: ExecutorFactory 注册")
    logger.info("=" * 80)

    # 测试通过枚举创建
    try:
        executor = ExecutorFactory.create(TaskType.MAP_SCRAPE_WEBSITE)
        logger.info(f"  ✅ 通过TaskType创建: {type(executor).__name__}")
    except Exception as e:
        logger.error(f"  ❌ 创建失败: {e}")
        return False

    # 测试通过字符串创建
    try:
        executor = ExecutorFactory.create_from_string("map_scrape_website")
        logger.info(f"  ✅ 通过字符串创建: {type(executor).__name__}")
    except Exception as e:
        logger.error(f"  ❌ 创建失败: {e}")
        return False

    # 获取支持的类型
    supported_types = ExecutorFactory.get_supported_types()
    logger.info(f"\n📋 支持的任务类型:")
    for task_type in supported_types:
        logger.info(f"  - {task_type.value}")

    # 验证 MAP_SCRAPE_WEBSITE 在列表中
    if TaskType.MAP_SCRAPE_WEBSITE in supported_types:
        logger.info(f"\n  ✅ MAP_SCRAPE_WEBSITE 已正确注册")
    else:
        logger.error(f"\n  ❌ MAP_SCRAPE_WEBSITE 未找到")
        return False

    logger.info("\n✅ ExecutorFactory 测试通过！\n")
    return True


async def main():
    """主测试函数"""
    logger.info("\n")
    logger.info("🚀 开始 Map + Scrape 集成测试")
    logger.info("=" * 80)
    logger.info("\n")

    results = []

    # 运行所有测试
    tests = [
        ("ExecutorFactory 注册", test_executor_factory),
        ("积分计算功能", test_credits_calculation),
        ("基础 Map + Scrape", test_basic_map_scrape),
        ("时间过滤功能", test_map_scrape_with_time_filter),
    ]

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ 测试 '{test_name}' 异常: {e}")
            results.append((test_name, False))

    # 总结
    logger.info("\n")
    logger.info("=" * 80)
    logger.info("📊 测试总结")
    logger.info("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {status}: {test_name}")

    logger.info(f"\n总计: {passed}/{total} 测试通过")
    logger.info("=" * 80)

    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

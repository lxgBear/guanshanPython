#!/usr/bin/env python3
"""
验证 Map + Scrape 功能是否在 API 中可用

测试内容:
1. 验证 TaskType 枚举包含 MAP_SCRAPE_WEBSITE
2. 测试创建 Map + Scrape 任务
3. 验证任务配置正确
"""
import sys
import requests
from datetime import datetime, timedelta

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.core.domain.entities.search_task import TaskType
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "http://localhost:8000/api/v1"


def test_task_type_enum():
    """测试 TaskType 枚举"""
    logger.info("=" * 80)
    logger.info("🧪 测试 1: TaskType 枚举验证")
    logger.info("=" * 80)

    # 验证枚举存在
    assert hasattr(TaskType, 'MAP_SCRAPE_WEBSITE'), "❌ MAP_SCRAPE_WEBSITE 枚举不存在"

    # 验证枚举值
    assert TaskType.MAP_SCRAPE_WEBSITE.value == "map_scrape_website", "❌ 枚举值不正确"

    logger.info("✅ TaskType.MAP_SCRAPE_WEBSITE 枚举存在")
    logger.info(f"✅ 枚举值: {TaskType.MAP_SCRAPE_WEBSITE.value}")

    # 列出所有任务类型
    logger.info("\n📋 所有任务类型:")
    for task_type in TaskType:
        logger.info(f"  - {task_type.value}")

    logger.info("\n✅ 测试 1 通过！\n")
    return True


def test_create_map_scrape_task():
    """测试创建 Map + Scrape 任务"""
    logger.info("=" * 80)
    logger.info("🧪 测试 2: 创建 Map + Scrape 任务")
    logger.info("=" * 80)

    # 准备测试数据
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    task_data = {
        "name": "Map + Scrape API 测试任务",
        "description": "验证 Map + Scrape 功能已正确集成到 API",
        "crawl_url": "https://firecrawl.dev",
        "task_type": "map_scrape_website",
        "crawl_config": {
            "search": "docs",
            "map_limit": 50,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "max_concurrent_scrapes": 3,
            "scrape_delay": 0.5,
            "only_main_content": True,
            "wait_for": 3000,
            "timeout": 90,
            "allow_partial_failure": True,
            "min_success_rate": 0.8
        },
        "schedule_interval": "DAILY",
        "is_active": False,  # 不启用，只测试创建
        "execute_immediately": False
    }

    logger.info(f"📤 发送请求到: {BASE_URL}/search-tasks")
    logger.info(f"📋 任务类型: {task_data['task_type']}")
    logger.info(f"🌐 爬取URL: {task_data['crawl_url']}")

    # 发送请求
    try:
        response = requests.post(
            f"{BASE_URL}/search-tasks",
            json=task_data,
            timeout=30
        )

        logger.info(f"\n📥 响应状态码: {response.status_code}")

        if response.status_code == 201:
            result = response.json()
            logger.info("✅ 任务创建成功！")
            logger.info(f"\n📊 任务信息:")
            logger.info(f"  ID: {result.get('id')}")
            logger.info(f"  名称: {result.get('name')}")
            logger.info(f"  类型: {result.get('task_type')}")
            logger.info(f"  模式: {result.get('task_mode')}")
            logger.info(f"  状态: {result.get('status')}")
            logger.info(f"  调度间隔: {result.get('schedule_display')}")

            # 验证配置
            crawl_config = result.get('crawl_config', {})
            logger.info(f"\n📋 Map + Scrape 配置:")
            logger.info(f"  search: {crawl_config.get('search')}")
            logger.info(f"  map_limit: {crawl_config.get('map_limit')}")
            logger.info(f"  max_concurrent_scrapes: {crawl_config.get('max_concurrent_scrapes')}")
            logger.info(f"  allow_partial_failure: {crawl_config.get('allow_partial_failure')}")

            logger.info("\n✅ 测试 2 通过！")

            # 清理测试任务
            task_id = result.get('id')
            if task_id:
                delete_response = requests.delete(f"{BASE_URL}/search-tasks/{task_id}")
                if delete_response.status_code == 200:
                    logger.info(f"🗑️  测试任务已清理 (ID: {task_id})")

            return True
        else:
            logger.error(f"❌ 任务创建失败: {response.status_code}")
            logger.error(f"响应内容: {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_executor_factory():
    """测试 ExecutorFactory 是否注册了 MapScrapeExecutor"""
    logger.info("=" * 80)
    logger.info("🧪 测试 3: ExecutorFactory 注册验证")
    logger.info("=" * 80)

    try:
        from src.services.firecrawl.factory import ExecutorFactory

        # 测试通过枚举创建
        executor = ExecutorFactory.create(TaskType.MAP_SCRAPE_WEBSITE)
        logger.info(f"✅ 通过 TaskType 创建执行器: {type(executor).__name__}")

        # 测试通过字符串创建
        executor = ExecutorFactory.create_from_string("map_scrape_website")
        logger.info(f"✅ 通过字符串创建执行器: {type(executor).__name__}")

        # 获取支持的类型
        supported_types = ExecutorFactory.get_supported_types()
        logger.info(f"\n📋 支持的任务类型 ({len(supported_types)} 个):")
        for task_type in supported_types:
            logger.info(f"  - {task_type.value}")

        # 验证 MAP_SCRAPE_WEBSITE 在列表中
        assert TaskType.MAP_SCRAPE_WEBSITE in supported_types, "❌ MAP_SCRAPE_WEBSITE 未注册"
        logger.info("\n✅ MAP_SCRAPE_WEBSITE 已正确注册")

        logger.info("\n✅ 测试 3 通过！\n")
        return True

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 80)
    logger.info("🚀 Map + Scrape API 验证测试")
    logger.info("=" * 80)
    logger.info("\n")

    results = []

    # 运行测试
    tests = [
        ("TaskType 枚举验证", test_task_type_enum),
        ("ExecutorFactory 注册验证", test_executor_factory),
        ("创建 Map + Scrape 任务", test_create_map_scrape_task),
    ]

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ 测试 '{test_name}' 异常: {e}")
            results.append((test_name, False))

    # 总结
    logger.info("\n" + "=" * 80)
    logger.info("📊 测试总结")
    logger.info("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {status}: {test_name}")

    logger.info(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        logger.info("\n🎉 所有测试通过！Map + Scrape 功能已成功集成到 API！")
    else:
        logger.error(f"\n⚠️  {total - passed} 个测试失败")

    logger.info("=" * 80)

    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

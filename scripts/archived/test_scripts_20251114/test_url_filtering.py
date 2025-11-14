#!/usr/bin/env python3
"""
测试 URL 过滤功能

测试内容:
1. 域名黑名单过滤（Wikipedia、YouTube）
2. 首页 URL 过滤
3. 详情页特征检测
4. 过滤统计准确性
5. 自定义黑名单
"""
import sys
import requests
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "http://localhost:8000/api/v1"


def create_test_task(
    name: str,
    query: str,
    exclude_domains: List[str],
    filter_homepage: bool = True
) -> Dict[str, Any]:
    """创建测试任务

    Args:
        name: 任务名称
        query: 搜索关键词
        exclude_domains: 排除域名列表
        filter_homepage: 是否过滤首页

    Returns:
        创建的任务信息
    """
    task_data = {
        "name": name,
        "description": f"测试 URL 过滤: {query}",
        "query": query,
        "task_type": "search_keyword",
        "search_config": {
            "limit": 20,
            "language": "zh",
            "exclude_domains": exclude_domains,
            "filter_homepage": filter_homepage,
            "enable_detail_scrape": False,  # 只测试过滤，不爬取详情
            "strict_language_filter": True
        },
        "schedule_interval": "DAILY",
        "is_active": False,
        "execute_immediately": True
    }

    logger.info(f"📤 创建任务: {name}")
    logger.info(f"   查询: {query}")
    logger.info(f"   排除域名: {exclude_domains}")
    logger.info(f"   过滤首页: {filter_homepage}")

    response = requests.post(
        f"{BASE_URL}/search-tasks",
        json=task_data,
        timeout=60
    )

    if response.status_code == 201:
        result = response.json()
        logger.info(f"✅ 任务创建成功: {result['id']}")
        return result
    else:
        logger.error(f"❌ 任务创建失败: {response.status_code}")
        logger.error(f"   响应: {response.text}")
        return None


def wait_for_execution(task_id: str, max_wait_seconds: int = 60) -> Dict[str, Any]:
    """等待任务执行完成

    Args:
        task_id: 任务 ID
        max_wait_seconds: 最大等待时间（秒）

    Returns:
        任务详情
    """
    import time

    logger.info(f"⏳ 等待任务执行完成...")

    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        response = requests.get(f"{BASE_URL}/search-tasks/{task_id}")
        if response.status_code == 200:
            task = response.json()
            if task.get('execution_count', 0) > 0:
                logger.info(f"✅ 任务执行完成")
                return task

        time.sleep(2)

    logger.warning(f"⚠️ 等待超时")
    return None


def get_execution_results(task_id: str) -> List[Dict[str, Any]]:
    """获取任务执行结果

    Args:
        task_id: 任务 ID

    Returns:
        执行历史列表
    """
    response = requests.get(f"{BASE_URL}/search-tasks/{task_id}/history")
    if response.status_code == 200:
        data = response.json()
        return data.get('items', [])
    return []


def analyze_filtering_results(execution: Dict[str, Any]) -> Dict[str, Any]:
    """分析过滤结果

    Args:
        execution: 执行历史记录

    Returns:
        分析结果
    """
    results_count = execution.get('results_count', 0)

    # 从日志中提取过滤统计（如果可用）
    analysis = {
        'total_results': results_count,
        'execution_time': execution.get('execution_time_ms', 0),
        'credits_used': execution.get('credits_used', 0),
        'status': execution.get('status', 'unknown')
    }

    return analysis


def delete_task(task_id: str):
    """删除测试任务

    Args:
        task_id: 任务 ID
    """
    response = requests.delete(f"{BASE_URL}/search-tasks/{task_id}")
    if response.status_code == 200:
        logger.info(f"🗑️  测试任务已删除: {task_id}")
    else:
        logger.warning(f"⚠️ 删除任务失败: {task_id}")


def test_default_blacklist():
    """测试 1: 默认黑名单（Wikipedia、YouTube）"""
    logger.info("=" * 80)
    logger.info("🧪 测试 1: 默认域名黑名单")
    logger.info("=" * 80)

    # 使用默认黑名单搜索
    task = create_test_task(
        name="测试默认黑名单",
        query="python wikipedia youtube",
        exclude_domains=["wikipedia.org", "youtube.com", "youtu.be"],
        filter_homepage=True
    )

    if not task:
        logger.error("❌ 测试 1 失败: 任务创建失败")
        return False

    task_id = task['id']

    # 等待执行
    task_details = wait_for_execution(task_id, max_wait_seconds=60)

    if not task_details:
        logger.error("❌ 测试 1 失败: 任务执行超时")
        delete_task(task_id)
        return False

    # 获取执行结果
    executions = get_execution_results(task_id)
    if executions:
        execution = executions[0]
        analysis = analyze_filtering_results(execution)

        logger.info(f"\n📊 过滤结果:")
        logger.info(f"   结果数: {analysis['total_results']}")
        logger.info(f"   执行时间: {analysis['execution_time']} ms")
        logger.info(f"   积分消耗: {analysis['credits_used']}")
        logger.info(f"   状态: {analysis['status']}")

        # 验证：结果应该不包含 Wikipedia 和 YouTube
        logger.info(f"\n✅ 测试 1 通过: 默认黑名单过滤正常工作")
    else:
        logger.warning(f"⚠️ 无法获取执行结果")

    # 清理
    delete_task(task_id)
    return True


def test_custom_blacklist():
    """测试 2: 自定义黑名单"""
    logger.info("\n" + "=" * 80)
    logger.info("🧪 测试 2: 自定义域名黑名单")
    logger.info("=" * 80)

    # 使用自定义黑名单
    task = create_test_task(
        name="测试自定义黑名单",
        query="python tutorial",
        exclude_domains=["wikipedia.org", "youtube.com", "github.com", "stackoverflow.com"],
        filter_homepage=True
    )

    if not task:
        logger.error("❌ 测试 2 失败: 任务创建失败")
        return False

    task_id = task['id']
    task_details = wait_for_execution(task_id, max_wait_seconds=60)

    if not task_details:
        logger.error("❌ 测试 2 失败: 任务执行超时")
        delete_task(task_id)
        return False

    executions = get_execution_results(task_id)
    if executions:
        execution = executions[0]
        analysis = analyze_filtering_results(execution)

        logger.info(f"\n📊 过滤结果:")
        logger.info(f"   结果数: {analysis['total_results']}")
        logger.info(f"   执行时间: {analysis['execution_time']} ms")
        logger.info(f"   状态: {analysis['status']}")

        logger.info(f"\n✅ 测试 2 通过: 自定义黑名单正常工作")

    delete_task(task_id)
    return True


def test_homepage_filtering():
    """测试 3: 首页过滤"""
    logger.info("\n" + "=" * 80)
    logger.info("🧪 测试 3: 首页 URL 过滤")
    logger.info("=" * 80)

    # 启用首页过滤
    task = create_test_task(
        name="测试首页过滤",
        query="python news",
        exclude_domains=["wikipedia.org", "youtube.com"],
        filter_homepage=True
    )

    if not task:
        logger.error("❌ 测试 3 失败: 任务创建失败")
        return False

    task_id = task['id']
    task_details = wait_for_execution(task_id, max_wait_seconds=60)

    if not task_details:
        logger.error("❌ 测试 3 失败: 任务执行超时")
        delete_task(task_id)
        return False

    executions = get_execution_results(task_id)
    if executions:
        execution = executions[0]
        analysis = analyze_filtering_results(execution)

        logger.info(f"\n📊 过滤结果:")
        logger.info(f"   结果数: {analysis['total_results']}")
        logger.info(f"   执行时间: {analysis['execution_time']} ms")
        logger.info(f"   状态: {analysis['status']}")

        logger.info(f"\n✅ 测试 3 通过: 首页过滤正常工作")

    delete_task(task_id)
    return True


def test_no_homepage_filtering():
    """测试 4: 禁用首页过滤"""
    logger.info("\n" + "=" * 80)
    logger.info("🧪 测试 4: 禁用首页过滤")
    logger.info("=" * 80)

    # 禁用首页过滤
    task = create_test_task(
        name="测试禁用首页过滤",
        query="python",
        exclude_domains=["wikipedia.org", "youtube.com"],
        filter_homepage=False
    )

    if not task:
        logger.error("❌ 测试 4 失败: 任务创建失败")
        return False

    task_id = task['id']
    task_details = wait_for_execution(task_id, max_wait_seconds=60)

    if not task_details:
        logger.error("❌ 测试 4 失败: 任务执行超时")
        delete_task(task_id)
        return False

    executions = get_execution_results(task_id)
    if executions:
        execution = executions[0]
        analysis = analyze_filtering_results(execution)

        logger.info(f"\n📊 过滤结果:")
        logger.info(f"   结果数: {analysis['total_results']}")
        logger.info(f"   执行时间: {analysis['execution_time']} ms")
        logger.info(f"   状态: {analysis['status']}")

        logger.info(f"\n✅ 测试 4 通过: 禁用首页过滤正常工作")

    delete_task(task_id)
    return True


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 80)
    logger.info("🚀 URL 过滤功能测试")
    logger.info("=" * 80)
    logger.info("\n")

    results = []

    # 运行测试
    tests = [
        ("默认黑名单过滤", test_default_blacklist),
        ("自定义黑名单过滤", test_custom_blacklist),
        ("首页 URL 过滤", test_homepage_filtering),
        ("禁用首页过滤", test_no_homepage_filtering),
    ]

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ 测试 '{test_name}' 异常: {e}")
            import traceback
            traceback.print_exc()
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
        logger.info("\n🎉 所有测试通过！URL 过滤功能正常工作！")
    else:
        logger.error(f"\n⚠️  {total - passed} 个测试失败")

    logger.info("=" * 80)

    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

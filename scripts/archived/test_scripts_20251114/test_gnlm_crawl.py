#!/usr/bin/env python3
"""测试 gnlm.com.mm 网站爬取功能"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

async def create_test_task():
    """创建测试任务"""
    task_data = {
        "name": "缅甸GNLM新闻监控测试",
        "description": "测试爬取 www.gnlm.com.mm 缅甸官方新闻网站",
        "query": "www.gnlm.com.mm latest news Myanmar",
        "search_config": {
            "limit": 5,
            "language": "en",
            "include_domains": ["www.gnlm.com.mm"],
            "scrape_formats": ["markdown", "html", "links"],
            "only_main_content": True
        },
        "schedule_interval": "DAILY",
        "is_active": True
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        print("📝 创建测试任务...")
        response = await client.post(
            f"{BASE_URL}/search-tasks",
            json=task_data
        )

        if response.status_code == 201:
            task = response.json()
            print(f"✅ 任务创建成功!")
            print(f"   任务ID: {task['id']}")
            print(f"   任务名称: {task['name']}")
            print(f"   查询: {task['query']}")
            return task['id']
        else:
            print(f"❌ 创建任务失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return None


async def execute_task(task_id: str):
    """执行任务"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        print(f"\n🚀 执行任务 {task_id}...")
        response = await client.post(
            f"http://localhost:8000/api/v1/internal/search-tasks/{task_id}/execute"
        )

        if response.status_code == 200:
            result = response.json()
            print(f"\n{'='*60}")
            print(f"✅ 执行结果:")
            print(f"{'='*60}")
            print(f"   成功状态: {result['success']}")
            print(f"   任务名称: {result['task_name']}")
            print(f"   获取结果数: {result['total_results']}")
            print(f"   执行时间: {result['execution_time_ms']}ms")
            print(f"   消耗积分: {result['credits_used']}")
            print(f"   测试模式: {result['is_test_mode']}")

            if result['error_message']:
                print(f"   错误信息: {result['error_message']}")

            if result['results_preview']:
                print(f"\n📄 结果预览 (前{len(result['results_preview'])}条):")
                print(f"{'-'*60}")
                for i, item in enumerate(result['results_preview'], 1):
                    print(f"\n   [{i}] {item.get('title', 'No title')}")
                    print(f"       URL: {item.get('url', 'No URL')}")
                    print(f"       来源: {item.get('source', 'unknown')}")
                    snippet = item.get('snippet', '')
                    if snippet:
                        print(f"       摘要: {snippet[:100]}...")

            print(f"{'='*60}\n")
            return result
        else:
            print(f"❌ 执行任务失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return None


async def get_task_results(task_id: str):
    """获取任务的搜索结果"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"\n📊 获取任务 {task_id} 的搜索结果...")
        response = await client.get(
            f"{BASE_URL}/search-tasks/{task_id}/results",
            params={"page": 1, "page_size": 10}
        )

        if response.status_code == 200:
            data = response.json()
            print(f"\n{'='*60}")
            print(f"📋 搜索结果列表:")
            print(f"{'='*60}")
            print(f"   总结果数: {data['total']}")
            print(f"   当前页: {data['page']}/{data['total_pages']}")

            if data['items']:
                print(f"\n   结果详情:")
                for i, item in enumerate(data['items'], 1):
                    print(f"\n   [{i}] {item['title']}")
                    print(f"       URL: {item['url']}")
                    print(f"       来源: {item['source']}")
                    if item.get('html_content'):
                        print(f"       HTML内容长度: {len(item['html_content'])} 字符")
                    if item.get('markdown_content'):
                        print(f"       Markdown内容长度: {len(item['markdown_content'])} 字符")

            print(f"{'='*60}\n")
            return data
        else:
            print(f"❌ 获取结果失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return None


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("🌐 GNLM.COM.MM 网站爬取测试")
    print("="*60 + "\n")

    # 1. 创建任务
    task_id = await create_test_task()
    if not task_id:
        print("\n❌ 测试失败: 无法创建任务")
        return

    # 等待一下
    await asyncio.sleep(2)

    # 2. 执行任务
    result = await execute_task(task_id)
    if not result:
        print("\n❌ 测试失败: 无法执行任务")
        return

    # 等待一下
    await asyncio.sleep(2)

    # 3. 获取结果
    if result['success'] and result['total_results'] > 0:
        results = await get_task_results(task_id)

        if results and results['total'] > 0:
            print("✅ 测试成功!")
            print(f"   成功爬取 {results['total']} 条结果")
            print(f"   任务ID: {task_id}")
        else:
            print("⚠️  任务执行成功，但未获取到存储的结果")
    else:
        print("⚠️  任务执行完成，但可能未成功获取数据")
        if result.get('is_test_mode'):
            print("   (当前为测试模式，返回模拟数据)")

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

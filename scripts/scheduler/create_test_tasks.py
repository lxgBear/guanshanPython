#!/usr/bin/env python3
"""快速创建5分钟测试任务"""

import asyncio
import httpx
import json
import os

# 禁用代理以直接访问localhost
os.environ['no_proxy'] = 'localhost,127.0.0.1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

BASE_URL = "http://localhost:8000/api/v1"


async def create_test_tasks():
    """创建两个测试任务"""
    print("\n🚀 创建5分钟定时测试任务...\n")

    # 任务1: 关键词搜索
    keyword_task = {
        "name": "【测试】关键词搜索 - 5分钟",
        "description": "测试每5分钟执行的关键词搜索任务",
        "query": "AI news technology",
        "search_config": {
            "limit": 3,
            "language": "en",
            "sources": ["web", "news"]
        },
        "schedule_interval": "MINUTES_5",
        "is_active": True
    }

    # 任务2: URL爬取
    crawl_task = {
        "name": "【测试】URL爬取 - 5分钟",
        "description": "测试每5分钟执行的URL爬取任务",
        "query": "ignored",
        "crawl_url": "https://www.anthropic.com",
        "search_config": {
            "wait_for": 2000,
            "exclude_tags": ["nav", "footer"]
        },
        "schedule_interval": "MINUTES_5",
        "is_active": True
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 创建任务1
        print("1️⃣ 创建关键词搜索任务...")
        try:
            response = await client.post(f"{BASE_URL}/search-tasks", json=keyword_task)
            if response.status_code == 201:
                result = response.json()
                print(f"   ✅ 成功! 任务ID: {result['id']}")
                print(f"   调度间隔: {result['schedule_display']}")
                print(f"   下次执行: {result.get('next_run_time', 'N/A')}")
            else:
                print(f"   ❌ 失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"   ❌ 异常: {e}")

        print()

        # 创建任务2
        print("2️⃣ 创建URL爬取任务...")
        try:
            response = await client.post(f"{BASE_URL}/search-tasks", json=crawl_task)
            if response.status_code == 201:
                result = response.json()
                print(f"   ✅ 成功! 任务ID: {result['id']}")
                print(f"   爬取URL: {result['crawl_url']}")
                print(f"   调度间隔: {result['schedule_display']}")
                print(f"   下次执行: {result.get('next_run_time', 'N/A')}")
            else:
                print(f"   ❌ 失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"   ❌ 异常: {e}")

    print("\n" + "="*70)
    print("✅ 任务创建完成!")
    print("="*70)
    print("\n提示:")
    print("  - 任务将每5分钟自动执行")
    print("  - 查看执行日志: 观察服务器控制台输出")
    print("  - 监控执行情况: 运行 python test_scheduler_5min.py")
    print("  - 查看所有任务: GET /api/v1/search-tasks")
    print("  - 查看调度器状态: GET /api/v1/scheduler/status\n")


if __name__ == "__main__":
    asyncio.run(create_test_tasks())

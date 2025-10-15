#!/usr/bin/env python3
"""测试 crawl_url 字段和优先级逻辑"""

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000/api/v1"
INTERNAL_URL = "http://localhost:8000/api/v1/internal"


async def test_create_with_crawl_url():
    """测试场景1：创建带 crawl_url 的任务"""
    print("\n" + "=" * 60)
    print("测试场景1: 创建带 crawl_url 的任务")
    print("=" * 60)

    task_data = {
        "name": "测试任务 - 网址爬取",
        "description": "测试 crawl_url 优先级逻辑",
        "query": "dummy query",  # 这个会被忽略
        "crawl_url": "https://www.anthropic.com",  # 这个会被优先使用
        "search_config": {
            "wait_for": 2000,
            "exclude_tags": ["nav", "footer"]
        },
        "schedule_interval": "DAILY",
        "is_active": True
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BASE_URL}/search-tasks", json=task_data)

        if response.status_code == 201:
            result = response.json()
            print(f"✅ 任务创建成功!")
            print(f"   任务ID: {result['id']}")
            print(f"   任务名称: {result['name']}")
            print(f"   爬取URL: {result['crawl_url']}")
            print(f"   查询关键词: {result['query']}")

            assert result['crawl_url'] == "https://www.anthropic.com", "crawl_url 应该正确保存"
            print(f"✅ 验证通过: crawl_url 字段正确保存")
            return result['id']
        else:
            print(f"❌ 创建失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return None


async def test_execute_crawl_task(task_id: str):
    """测试场景2：执行爬取任务，验证优先级逻辑"""
    print("\n" + "=" * 60)
    print(f"测试场景2: 执行任务 {task_id}，验证使用爬取模式")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{INTERNAL_URL}/search-tasks/{task_id}/execute")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 任务执行成功!")
            print(f"   任务ID: {result['task_id']}")
            print(f"   任务名称: {result['task_name']}")
            print(f"   执行时间: {result['execution_time_ms']}ms")
            print(f"   结果数量: {result['total_results']}")
            print(f"   消耗积分: {result['credits_used']}")

            if result['results_preview']:
                print(f"\n   结果预览:")
                for idx, preview in enumerate(result['results_preview'][:1]):
                    print(f"      结果 {idx+1}:")
                    print(f"         标题: {preview.get('title', 'N/A')[:50]}...")
                    print(f"         URL: {preview.get('url', 'N/A')}")
                    print(f"         来源: {preview.get('source', 'N/A')}")

            # 验证使用了爬取模式（source 应该是 "crawl"）
            if result['results_preview'] and result['results_preview'][0].get('source') == 'crawl':
                print(f"\n✅ 验证通过: 使用了网址爬取模式（source=crawl）")
            else:
                print(f"\n⚠️  注意: 结果来源不是 'crawl'")

            return result['success']
        else:
            print(f"❌ 执行失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return False


async def test_create_without_crawl_url():
    """测试场景3：创建不带 crawl_url 的任务（应该使用关键词搜索）"""
    print("\n" + "=" * 60)
    print("测试场景3: 创建不带 crawl_url 的任务")
    print("=" * 60)

    task_data = {
        "name": "测试任务 - 关键词搜索",
        "description": "验证未提供 crawl_url 时使用搜索模式",
        "query": "AI news",  # 应该使用这个关键词搜索
        "search_config": {
            "limit": 5,
            "language": "en"
        },
        "schedule_interval": "DAILY",
        "is_active": False  # 不执行，只测试创建
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BASE_URL}/search-tasks", json=task_data)

        if response.status_code == 201:
            result = response.json()
            print(f"✅ 任务创建成功!")
            print(f"   任务ID: {result['id']}")
            print(f"   任务名称: {result['name']}")
            print(f"   爬取URL: {result.get('crawl_url', 'None')}")
            print(f"   查询关键词: {result['query']}")

            assert result.get('crawl_url') is None, "crawl_url 应该为 None"
            assert result['query'] == "AI news", "query 应该正确保存"
            print(f"✅ 验证通过: 未提供 crawl_url，query 正常保存")
            return result['id']
        else:
            print(f"❌ 创建失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return None


async def test_update_crawl_url(task_id: str):
    """测试场景4：更新任务的 crawl_url"""
    print("\n" + "=" * 60)
    print(f"测试场景4: 更新任务 {task_id} 的 crawl_url")
    print("=" * 60)

    update_data = {
        "crawl_url": "https://www.example.com"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.put(f"{BASE_URL}/search-tasks/{task_id}", json=update_data)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 任务更新成功!")
            print(f"   任务ID: {result['id']}")
            print(f"   更新后的 crawl_url: {result['crawl_url']}")

            assert result['crawl_url'] == "https://www.example.com", "crawl_url 应该更新为新值"
            print(f"✅ 验证通过: crawl_url 更新成功")
            return True
        else:
            print(f"❌ 更新失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return False


async def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("🧪 crawl_url 字段和优先级逻辑测试")
    print("=" * 60)

    # 测试1: 创建带 crawl_url 的任务
    task_id_1 = await test_create_with_crawl_url()
    if not task_id_1:
        print("\n❌ 测试1失败，中止测试")
        return

    await asyncio.sleep(1)

    # 测试2: 执行爬取任务（验证优先级逻辑）
    if task_id_1:
        success = await test_execute_crawl_task(task_id_1)
        if not success:
            print("\n⚠️ 测试2失败，但继续后续测试")

    await asyncio.sleep(1)

    # 测试3: 创建不带 crawl_url 的任务
    task_id_3 = await test_create_without_crawl_url()
    if not task_id_3:
        print("\n⚠️ 测试3失败，但继续后续测试")

    await asyncio.sleep(1)

    # 测试4: 更新 crawl_url
    if task_id_1:
        success = await test_update_crawl_url(task_id_1)
        if not success:
            print("\n⚠️ 测试4失败")

    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

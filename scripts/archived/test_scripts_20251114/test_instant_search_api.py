#!/usr/bin/env python3
"""即时搜索API手动测试脚本

用于手动测试v1.3.0即时搜索API的完整流程，包括：
- 创建并执行搜索
- 查询任务详情
- 查询搜索结果
- 验证跨搜索去重

运行方式：
    python scripts/test_instant_search_api.py
"""

import asyncio
import httpx
from typing import Dict, Any
from datetime import datetime


BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"


class InstantSearchAPITester:
    """即时搜索API测试器"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        # 禁用代理，直接连接
        self.client = httpx.AsyncClient(
            timeout=30.0,
            proxies={},  # 禁用代理
            verify=True
        )

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

    async def create_search(
        self,
        name: str,
        query: str = None,
        crawl_url: str = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """创建并执行搜索"""
        url = f"{self.base_url}{API_PREFIX}/instant-search-tasks"

        payload = {
            "name": name,
            "search_config": {"limit": limit},
            "created_by": "api_test"
        }

        if query:
            payload["query"] = query
        if crawl_url:
            payload["crawl_url"] = crawl_url

        print(f"\n{'='*60}")
        print(f"📤 POST {url}")
        print(f"📝 请求体: {payload}")

        response = await self.client.post(url, json=payload)

        print(f"📥 状态码: {response.status_code}")

        if response.status_code == 201:
            data = response.json()
            print(f"✅ 任务创建成功:")
            print(f"   - ID: {data['id']}")
            print(f"   - 名称: {data['name']}")
            print(f"   - 状态: {data['status']}")
            print(f"   - 搜索模式: {data['search_mode']}")
            print(f"   - 总结果: {data['total_results']}")
            print(f"   - 新结果: {data['new_results']}")
            print(f"   - 共享结果: {data['shared_results']}")
            print(f"   - 执行时间: {data['execution_time_ms']}ms")
            return data
        else:
            print(f"❌ 请求失败: {response.text}")
            return None

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务详情"""
        url = f"{self.base_url}{API_PREFIX}/instant-search-tasks/{task_id}"

        print(f"\n{'='*60}")
        print(f"📤 GET {url}")

        response = await self.client.get(url)

        print(f"📥 状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ 任务详情:")
            print(f"   - ID: {data['id']}")
            print(f"   - 名称: {data['name']}")
            print(f"   - 状态: {data['status']}")
            print(f"   - 总结果: {data['total_results']}")
            print(f"   - 新结果: {data['new_results']}")
            print(f"   - 共享结果: {data['shared_results']}")
            return data
        else:
            print(f"❌ 请求失败: {response.text}")
            return None

    async def get_results(
        self,
        task_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """获取搜索结果"""
        url = f"{self.base_url}{API_PREFIX}/instant-search-tasks/{task_id}/results"
        params = {"page": page, "page_size": page_size}

        print(f"\n{'='*60}")
        print(f"📤 GET {url}?page={page}&page_size={page_size}")

        response = await self.client.get(url, params=params)

        print(f"📥 状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ 搜索结果:")
            print(f"   - 总数: {data['total']}")
            print(f"   - 当前页: {data['page']}/{data['total_pages']}")
            print(f"   - 结果数: {len(data['results'])}")

            for idx, item in enumerate(data['results'][:3], 1):
                result = item['result']
                mapping = item['mapping_info']
                print(f"\n   📄 结果 #{idx}:")
                print(f"      - 标题: {result['title'][:60]}...")
                print(f"      - URL: {result['url']}")
                print(f"      - 排名: {mapping['search_position']}")
                print(f"      - 相关性: {mapping['relevance_score']}")
                print(f"      - 首次发现: {mapping['is_first_discovery']}")
                print(f"      - 被发现次数: {result['found_count']}")
                print(f"      - 不同搜索数: {result['unique_searches']}")

            return data
        else:
            print(f"❌ 请求失败: {response.text}")
            return None

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 10,
        status: str = None
    ) -> Dict[str, Any]:
        """获取任务列表"""
        url = f"{self.base_url}{API_PREFIX}/instant-search-tasks"
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status

        print(f"\n{'='*60}")
        print(f"📤 GET {url} (page={page}, page_size={page_size})")

        response = await self.client.get(url, params=params)

        print(f"📥 状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ 任务列表:")
            print(f"   - 总数: {data['total']}")
            print(f"   - 当前页: {data['page']}/{data['total_pages']}")

            for task in data['tasks'][:5]:
                print(f"\n   📋 任务: {task['name']}")
                print(f"      - ID: {task['id']}")
                print(f"      - 状态: {task['status']}")
                print(f"      - 总结果: {task['total_results']}")
                print(f"      - 新/共享: {task['new_results']}/{task['shared_results']}")

            return data
        else:
            print(f"❌ 请求失败: {response.text}")
            return None

    async def test_deduplication(self):
        """测试跨搜索去重机制"""
        print("\n" + "="*60)
        print("🧪 测试v1.3.0跨搜索去重机制")
        print("="*60)

        # 搜索A：首次搜索
        print("\n【步骤1】执行搜索A...")
        task_a = await self.create_search(
            name="去重测试-搜索A",
            query="python fastapi mongodb",
            limit=2  # 限制2条
        )

        if not task_a:
            print("❌ 搜索A失败")
            return

        # 等待1秒
        await asyncio.sleep(1)

        # 搜索B：相同查询
        print("\n【步骤2】执行搜索B（相同查询）...")
        task_b = await self.create_search(
            name="去重测试-搜索B",
            query="python fastapi mongodb",
            limit=2  # 限制2条
        )

        if not task_b:
            print("❌ 搜索B失败")
            return

        # 分析去重效果
        print("\n【步骤3】分析去重效果...")
        print(f"✅ 搜索A: 新结果={task_a['new_results']}, 共享结果={task_a['shared_results']}")
        print(f"✅ 搜索B: 新结果={task_b['new_results']}, 共享结果={task_b['shared_results']}")

        if task_b['shared_results'] > 0:
            print(f"\n🎯 去重成功！搜索B命中 {task_b['shared_results']} 个共享结果")
            dedup_rate = (task_b['shared_results'] / task_b['total_results']) * 100
            print(f"   去重率: {dedup_rate:.1f}%")
        else:
            print("\n⚠️  未检测到共享结果（可能是Firecrawl返回了不同结果）")

        # 验证跨搜索可见性
        print("\n【步骤4】验证结果在两次搜索中都可见...")
        results_a = await self.get_results(task_a['id'], page=1, page_size=2)
        results_b = await self.get_results(task_b['id'], page=1, page_size=2)

        if results_a and results_b:
            ids_a = {r['result']['id'] for r in results_a['results']}
            ids_b = {r['result']['id'] for r in results_b['results']}
            common = ids_a & ids_b

            if common:
                print(f"\n✅ 跨搜索可见性验证成功！")
                print(f"   共同结果数: {len(common)}")
                print(f"   共同结果ID: {list(common)[:3]}")
            else:
                print("\n⚠️  没有检测到共同结果")


async def main():
    """主测试流程"""
    tester = InstantSearchAPITester()

    try:
        print("\n" + "="*60)
        print("🚀 即时搜索API测试开始")
        print(f"📍 API地址: {BASE_URL}{API_PREFIX}")
        print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        # 测试1：创建Search模式任务
        print("\n【测试1】Search模式 - 关键词搜索")
        task1 = await tester.create_search(
            name="API测试-Search模式",
            query="python async programming",
            limit=2  # 限制2条，节省配额
        )

        if task1:
            await asyncio.sleep(1)
            await tester.get_task(task1['id'])
            await tester.get_results(task1['id'], page=1, page_size=10)

        # 测试2：创建Crawl模式任务
        print("\n【测试2】Crawl模式 - URL爬取")
        task2 = await tester.create_search(
            name="API测试-Crawl模式",
            crawl_url="https://example.com",
            limit=1
        )

        if task2:
            await asyncio.sleep(1)
            await tester.get_results(task2['id'])

        # 测试3：任务列表
        print("\n【测试3】任务列表查询")
        await tester.list_tasks(page=1, page_size=5)

        # 测试4：跨搜索去重（注释掉以节省配额）
        print("\n【测试4】跨搜索去重机制 - 已跳过以节省API配额")
        print("💡 提示: 取消注释 test_deduplication() 以测试去重功能")
        # await tester.test_deduplication()

        print("\n" + "="*60)
        print("✅ 所有测试完成")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())

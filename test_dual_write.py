#!/usr/bin/env python3
"""
测试双写功能

测试 NL Search 是否正确将结果写入 search_results 集合
"""
import asyncio
import requests
import json
from motor.motor_asyncio import AsyncIOMotorClient

# 测试配置
API_BASE_URL = "http://localhost:8000"
MONGODB_URI = "mongodb://hancens.top:40717/guanshan"


async def test_dual_write():
    """测试双写功能"""
    print("=" * 60)
    print("测试 NL Search 双写功能")
    print("=" * 60)

    # 1. 连接MongoDB
    print("\n1️⃣ 连接 MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.guanshan

    # 2. 调用 NL Search API（使用multi模式获取更多结果）
    print("\n2️⃣ 调用 NL Search API（multi模式）...")
    response = requests.post(
        f"{API_BASE_URL}/api/v1/nl-search/",
        json={
            "query_text": "Python异步编程最佳实践",
            "search_mode": "multi"
        },
        proxies={"http": None, "https": None}
    )

    if response.status_code != 200:
        print(f"❌ API调用失败: {response.status_code}")
        print(response.text)
        return

    result = response.json()
    log_id = result["log_id"]
    print(f"✅ 搜索完成: log_id={log_id}")
    print(f"   查询文本: {result['query_text']}")
    print(f"   搜索模式: {result['search_mode']}")
    print(f"   结果数量: {len(result['results'])}")

    # 3. 等待异步写入完成
    print("\n3️⃣ 等待异步双写完成...")
    await asyncio.sleep(2)

    # 4. 检查 nl_search_logs.search_results (原有存储)
    print("\n4️⃣ 检查 nl_search_logs.search_results（原有存储）...")
    log_doc = await db.nl_search_logs.find_one({"_id": log_id})
    if log_doc and "search_results" in log_doc:
        embedded_count = len(log_doc["search_results"])
        print(f"✅ nl_search_logs: 找到 {embedded_count} 条结果（嵌入式存储）")
        # 显示第一条结果的字段
        if log_doc["search_results"]:
            first_result = log_doc["search_results"][0]
            print(f"   第一条结果字段: {list(first_result.keys())[:10]}...")
    else:
        print(f"❌ nl_search_logs: 未找到结果")

    # 5. 检查 search_results 集合（新双写存储）
    print("\n5️⃣ 检查 search_results 集合（新双写存储）...")
    search_results_docs = await db.search_results.find({"task_id": log_id}).to_list(None)

    if search_results_docs:
        print(f"✅ search_results: 找到 {len(search_results_docs)} 条结果（独立集合）")

        # 显示第一条结果的详细信息
        first_doc = search_results_docs[0]
        print(f"\n📄 第一条结果详情:")
        print(f"   ID: {first_doc['_id']}")
        print(f"   task_id: {first_doc['task_id']}")
        print(f"   title: {first_doc.get('title', 'N/A')[:50]}...")
        print(f"   url: {first_doc.get('url', 'N/A')}")
        print(f"   source: {first_doc.get('source', 'N/A')}")
        print(f"   status: {first_doc.get('status', 'N/A')}")
        print(f"   markdown_content: {len(first_doc.get('markdown_content', '')) if first_doc.get('markdown_content') else 0} 字符")
        print(f"   html_content: {len(first_doc.get('html_content', '')) if first_doc.get('html_content') else 0} 字符")
        print(f"   content_hash: {first_doc.get('content_hash', 'N/A')[:16]}...")
        print(f"   created_at: {first_doc.get('created_at', 'N/A')}")

        # 验证 Firecrawl 数据存在
        has_markdown = bool(first_doc.get('markdown_content'))
        has_html = bool(first_doc.get('html_content'))
        has_metadata = bool(first_doc.get('metadata'))

        print(f"\n✅ Firecrawl 数据验证:")
        print(f"   markdown_content: {'✅ 存在' if has_markdown else '❌ 缺失'}")
        print(f"   html_content: {'✅ 存在' if has_html else '❌ 缺失'}")
        print(f"   metadata: {'✅ 存在' if has_metadata else '❌ 缺失'}")

    else:
        print(f"❌ search_results: 未找到任何结果（task_id={log_id}）")

    # 6. 验证数据一致性
    print("\n6️⃣ 验证数据一致性...")
    if log_doc and "search_results" in log_doc and search_results_docs:
        embedded_count = len(log_doc["search_results"])
        collection_count = len(search_results_docs)

        if embedded_count == collection_count:
            print(f"✅ 数据一致: 两处存储的结果数量相同 ({embedded_count} 条)")
        else:
            print(f"⚠️ 数据不一致: 嵌入式={embedded_count}, 独立集合={collection_count}")

    # 7. 统计信息
    print("\n7️⃣ 统计信息...")
    total_nl_search_results = await db.search_results.count_documents({"source": "nl_search"})
    print(f"   search_results 集合中 source=nl_search 的总记录数: {total_nl_search_results}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

    # 关闭连接
    client.close()


if __name__ == "__main__":
    asyncio.run(test_dual_write())

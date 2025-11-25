#!/usr/bin/env python3
"""
检查数据库中的双写数据
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = "mongodb://guanshan:5iSFspPkCLG5cRiD@hancens.top:40717/?authSource=guanshan"


async def check_data():
    """检查数据库"""
    print("=" * 60)
    print("检查数据库中的双写数据")
    print("=" * 60)

    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.guanshan

    # 1. 检查最新的 nl_search_logs
    print("\n1️⃣ 检查最新的 nl_search_logs...")
    latest_logs = await db.nl_search_logs.find().sort("created_at", -1).limit(3).to_list(3)

    if latest_logs:
        print(f"✅ 找到 {len(latest_logs)} 条最新日志")
        for log in latest_logs:
            log_id = log["_id"]
            query = log.get("query_text", "N/A")[:50]
            created_at = log.get("created_at")
            results_count = len(log.get("search_results", []))
            print(f"\n   Log ID: {log_id}")
            print(f"   Query: {query}")
            print(f"   Created: {created_at}")
            print(f"   Results (embedded): {results_count}")

            # 检查对应的 search_results 集合数据
            sr_count = await db.search_results.count_documents({"task_id": log_id})
            print(f"   Results (search_results collection): {sr_count}")

            if sr_count > 0:
                print(f"   ✅ 双写成功！")
            else:
                print(f"   ❌ 未找到对应的独立集合数据")
    else:
        print("❌ 没有找到 nl_search_logs")

    # 2. 统计 search_results 集合
    print("\n2️⃣ 统计 search_results 集合...")
    total_results = await db.search_results.count_documents({})
    nl_search_results = await db.search_results.count_documents({"source": "nl_search"})

    print(f"   总记录数: {total_results}")
    print(f"   source=nl_search 的记录数: {nl_search_results}")

    # 3. 查看最新的 nl_search 结果
    if nl_search_results > 0:
        print("\n3️⃣ 最新的 nl_search 结果...")
        latest_nl_results = await db.search_results.find(
            {"source": "nl_search"}
        ).sort("created_at", -1).limit(3).to_list(3)

        for result in latest_nl_results:
            print(f"\n   ID: {result['_id']}")
            print(f"   task_id: {result.get('task_id', 'N/A')}")
            print(f"   title: {result.get('title', 'N/A')[:60]}")
            print(f"   url: {result.get('url', 'N/A')}")
            print(f"   has_markdown: {bool(result.get('markdown_content'))}")
            print(f"   has_html: {bool(result.get('html_content'))}")
            print(f"   created_at: {result.get('created_at', 'N/A')}")

    print("\n" + "=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(check_data())

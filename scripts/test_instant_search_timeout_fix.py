#!/usr/bin/env python3
"""
测试即时搜索超时修复
验证：
1. 超时时间是否延长到 60 秒
2. 重试机制是否生效
3. 错误消息是否更详细
"""
import asyncio
import httpx
import time
from datetime import datetime


async def test_instant_search():
    """测试即时搜索 API"""
    api_url = "http://localhost:8000/api/v1/instant-search-tasks"

    # 测试数据
    test_query = "测试超时修复"

    print(f"\n{'='*60}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试查询: {test_query}")
    print(f"{'='*60}\n")

    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print("发送即时搜索请求...")
            response = await client.post(
                api_url,
                json={
                    "query": test_query,
                    "limit": 5,
                    "created_by": "test_user"
                }
            )

            elapsed = time.time() - start_time

            print(f"\n响应状态: {response.status_code}")
            print(f"耗时: {elapsed:.2f} 秒")

            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ 搜索成功!")
                print(f"任务ID: {data.get('id')}")
                print(f"结果数量: {len(data.get('results', []))}")
            else:
                print(f"\n❌ 搜索失败")
                print(f"错误详情: {response.text}")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ 请求异常")
        print(f"耗时: {elapsed:.2f} 秒")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {str(e)}")

    print(f"\n{'='*60}")
    print("测试完成")
    print(f"{'='*60}\n")

    # 验证点
    print("\n验证结果:")
    print(f"1. 超时时间: {elapsed:.2f}秒 (期望: 接近60秒而不是30秒)")
    print(f"2. 检查服务器日志中的错误消息格式")
    print(f"3. 检查是否有重试日志")


if __name__ == "__main__":
    asyncio.run(test_instant_search())

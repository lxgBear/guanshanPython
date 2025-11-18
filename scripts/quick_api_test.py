#!/usr/bin/env python3
"""快速API测试 - 绕过网络问题"""
import requests
import json

print("=" * 60)
print("NL Search MongoDB 迁移 - 直接 API 测试")
print("=" * 60)

base_url = "http://127.0.0.1:8000"

# 测试 1: 健康检查
print("\n测试 1: 健康检查")
try:
    response = requests.get(f"{base_url}/health", timeout=5)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试 2: NL Search 状态
print("\n测试 2: NL Search 状态")
try:
    response = requests.get(f"{base_url}/api/v1/nl-search/status", timeout=5)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"✅ 响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    else:
        print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试 3: NL Search 列表
print("\n测试 3: NL Search 列表")
try:
    response = requests.get(f"{base_url}/api/v1/nl-search?limit=2", timeout=5)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 返回 {data.get('total', 0)} 条记录")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
    else:
        print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)

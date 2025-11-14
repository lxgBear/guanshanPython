#!/usr/bin/env python3
"""
执行任务 244887942339018752 测试脚本
验证 v2.1.1 修复后的效果
"""
import requests
import time

# 任务 ID
TASK_ID = "244887942339018752"
API_BASE = "http://localhost:8000"

def execute_task():
    """执行任务"""
    try:
        print(f"\n🚀 开始执行任务: {TASK_ID}")
        print("-" * 60)

        # 调用内部执行接口
        url = f"{API_BASE}/internal/search-tasks/{TASK_ID}/execute"
        print(f"📍 请求URL: {url}")

        response = requests.post(url, timeout=300)

        print(f"📊 响应状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ 任务执行成功!")
            print(f"📋 响应数据:")
            print(f"  - 消息: {data.get('message')}")
            print(f"  - 任务ID: {data.get('task_id')}")
            print(f"  - 结果数: {data.get('result_count', 'N/A')}")
            return True
        else:
            print(f"❌ 任务执行失败: {response.status_code}")
            print(f"错误详情: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("⏱️  请求超时（300秒）")
        return False
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        return False

def get_task_status():
    """获取任务状态"""
    try:
        url = f"{API_BASE}/api/v1/search-tasks/{TASK_ID}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            print("\n📊 任务当前状态:")
            print(f"  - 任务名称: {data.get('name')}")
            print(f"  - 任务类型: {data.get('task_type')}")
            print(f"  - 任务模式: {data.get('task_mode')}")
            print(f"  - 是否激活: {data.get('is_active')}")
            print(f"  - 执行次数: {data.get('execution_count')}")
            print(f"  - 成功次数: {data.get('success_count')}")
            print(f"  - 失败次数: {data.get('failure_count')}")
            print(f"  - 总结果数: {data.get('total_results')}")
            print(f"  - 最后执行: {data.get('last_executed_at')}")
        else:
            print(f"获取任务状态失败: {response.status_code}")

    except Exception as e:
        print(f"获取状态出错: {e}")

def main():
    print("=" * 60)
    print("任务 244887942339018752 执行测试")
    print("验证 v2.1.1 Firecrawl wait_for/timeout 修复")
    print("=" * 60)

    # 获取执行前状态
    print("\n【执行前状态】")
    get_task_status()

    # 等待用户确认
    print("\n" + "=" * 60)
    input("按 Enter 键开始执行任务...")

    # 执行任务
    success = execute_task()

    if success:
        # 等待任务完成
        print("\n⏳ 等待任务完成（预计 2-3 分钟）...")
        time.sleep(180)  # 等待3分钟

        # 获取执行后状态
        print("\n【执行后状态】")
        get_task_status()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()

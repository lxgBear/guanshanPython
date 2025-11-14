#!/usr/bin/env python3
"""测试定时任务首次立即执行功能"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

def test_immediate_execution():
    """测试首次立即执行功能"""
    print("=" * 60)
    print("测试定时任务首次立即执行功能")
    print("=" * 60)

    # 1. 创建任务（启用立即执行）
    print("\n[1] 创建任务（execute_immediately=True）")
    task_data = {
        "name": "测试首次立即执行",
        "description": "验证 execute_immediately 参数功能",
        "query": "Myanmar test immediate",
        "target_website": "www.example.com",
        "schedule_interval": "HOURLY",
        "is_active": True,
        "execute_immediately": True  # 启用立即执行
    }

    try:
        response = requests.post(
            f"{BASE_URL}/search-tasks",
            json=task_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 201:
            task = response.json()
            task_id = task["id"]
            print(f"✅ 任务创建成功")
            print(f"   任务ID: {task_id}")
            print(f"   任务名称: {task['name']}")
            print(f"   执行次数: {task['execution_count']}")

            # 2. 等待后台执行（立即执行是异步的）
            print(f"\n[2] 等待后台执行（60秒）...")
            time.sleep(60)

            # 3. 查询任务状态
            print(f"\n[3] 查询任务执行状态")
            status_response = requests.get(f"{BASE_URL}/search-tasks/{task_id}/status")
            if status_response.status_code == 200:
                task_status = status_response.json()
                print(f"   执行次数: {task_status['execution_count']}")
                print(f"   成功次数: {task_status['success_count']}")
                print(f"   失败次数: {task_status['failure_count']}")
                print(f"   最后执行时间: {task_status.get('last_executed_at', 'N/A')}")

                if task_status['execution_count'] > 0:
                    print(f"\n✅ 测试通过：任务已立即执行")

                    # 4. 查询搜索结果
                    print(f"\n[4] 查询搜索结果")
                    results_response = requests.get(
                        f"{BASE_URL}/search-tasks/{task_id}/results?page=1&page_size=10"
                    )
                    if results_response.status_code == 200:
                        results_data = results_response.json()
                        print(f"   结果总数: {results_data['total']}")
                        print(f"   返回结果: {len(results_data['items'])} 条")
                        print(f"\n✅ 首次立即执行功能验证成功！")
                    else:
                        print(f"⚠️ 查询结果失败: {results_response.status_code}")
                else:
                    print(f"\n❌ 测试失败：任务未执行")
            else:
                print(f"❌ 查询状态失败: {status_response.status_code}")

        else:
            print(f"❌ 任务创建失败: {response.status_code}")
            print(f"   错误详情: {response.text}")

    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接失败：服务可能未启动")
        print(f"   错误: {e}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

    print("\n" + "=" * 60)


def test_no_immediate_execution():
    """测试禁用立即执行"""
    print("\n" + "=" * 60)
    print("测试禁用立即执行（execute_immediately=False）")
    print("=" * 60)

    task_data = {
        "name": "测试禁用立即执行",
        "description": "验证 execute_immediately=False",
        "query": "Myanmar test no immediate",
        "schedule_interval": "HOURLY",
        "is_active": True,
        "execute_immediately": False  # 禁用立即执行
    }

    try:
        response = requests.post(
            f"{BASE_URL}/search-tasks",
            json=task_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 201:
            task = response.json()
            task_id = task["id"]
            print(f"✅ 任务创建成功")
            print(f"   任务ID: {task_id}")
            print(f"   执行次数: {task['execution_count']}")

            # 等待一小段时间
            print(f"\n等待 10 秒...")
            time.sleep(10)

            # 查询任务状态
            status_response = requests.get(f"{BASE_URL}/search-tasks/{task_id}/status")
            if status_response.status_code == 200:
                task_status = status_response.json()
                print(f"   执行次数: {task_status['execution_count']}")

                if task_status['execution_count'] == 0:
                    print(f"\n✅ 测试通过：任务未立即执行（符合预期）")
                else:
                    print(f"\n❌ 测试失败：任务不应该执行")
            else:
                print(f"❌ 查询状态失败: {status_response.status_code}")
        else:
            print(f"❌ 任务创建失败: {response.status_code}")
            print(f"   错误详情: {response.text}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # 测试启用立即执行
    test_immediate_execution()

    # 测试禁用立即执行
    time.sleep(2)
    test_no_immediate_execution()

    print("\n✅ 所有测试完成")

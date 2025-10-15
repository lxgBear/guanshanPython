#!/usr/bin/env python3
"""
5分钟定时任务测试脚本

测试场景：
1. 创建关键词搜索任务（每5分钟执行）
2. 创建URL爬取任务（每5分钟执行）
3. 监控任务执行情况
4. 验证数据正确存储到数据库
"""

import asyncio
import httpx
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# 禁用代理以直接访问localhost
os.environ['no_proxy'] = 'localhost,127.0.0.1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

BASE_URL = "http://localhost:8000/api/v1"

# 测试任务配置
KEYWORD_TASK_CONFIG = {
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

URL_CRAWL_TASK_CONFIG = {
    "name": "【测试】URL爬取 - 5分钟",
    "description": "测试每5分钟执行的URL爬取任务",
    "query": "ignored",  # 会被忽略
    "crawl_url": "https://www.anthropic.com",
    "search_config": {
        "wait_for": 2000,
        "exclude_tags": ["nav", "footer"]
    },
    "schedule_interval": "MINUTES_5",
    "is_active": True
}


class TaskMonitor:
    """任务监控器"""

    def __init__(self):
        self.created_task_ids = []
        self.execution_history = {}

    async def create_task(self, config: Dict[str, Any]) -> Optional[str]:
        """创建测试任务"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{BASE_URL}/search-tasks", json=config)

                if response.status_code == 201:
                    result = response.json()
                    task_id = result['id']
                    self.created_task_ids.append(task_id)
                    self.execution_history[task_id] = {
                        "name": result['name'],
                        "mode": "crawl" if result.get('crawl_url') else "search",
                        "executions": []
                    }
                    return task_id
                else:
                    print(f"❌ 创建任务失败: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"❌ 创建任务异常: {e}")
            return None

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{BASE_URL}/search-tasks/{task_id}")

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            print(f"⚠️ 获取任务状态失败: {e}")
            return None

    async def get_task_results(self, task_id: str, page: int = 1) -> Optional[Dict[str, Any]]:
        """获取任务执行结果"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{BASE_URL}/search-results/task/{task_id}",
                    params={"page": page, "page_size": 10}
                )

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            print(f"⚠️ 获取任务结果失败: {e}")
            return None

    async def check_scheduler_status(self) -> Optional[Dict[str, Any]]:
        """检查调度器状态"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{BASE_URL}/scheduler/status")

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            print(f"⚠️ 获取调度器状态失败: {e}")
            return None

    async def monitor_tasks(self, duration_minutes: int = 15):
        """监控任务执行（指定时长）"""
        print(f"\n{'='*70}")
        print(f"📊 开始监控任务执行 (持续 {duration_minutes} 分钟)")
        print(f"{'='*70}\n")

        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        check_interval = 30  # 每30秒检查一次

        last_execution_counts = {tid: 0 for tid in self.created_task_ids}

        while datetime.now() < end_time:
            remaining = (end_time - datetime.now()).total_seconds()
            print(f"\n⏱️ 监控中... 剩余时间: {int(remaining/60)}分{int(remaining%60)}秒")

            # 检查调度器状态
            scheduler_status = await self.check_scheduler_status()
            if scheduler_status:
                print(f"   调度器状态: {scheduler_status['status']}")
                print(f"   活跃任务数: {scheduler_status['active_jobs']}")

            # 检查每个任务的执行情况
            for task_id in self.created_task_ids:
                task_status = await self.get_task_status(task_id)

                if task_status:
                    task_name = task_status['name']
                    exec_count = task_status['execution_count']
                    success_count = task_status['success_count']
                    last_exec = task_status.get('last_executed_at')
                    next_run = task_status.get('next_run_time')

                    # 检查是否有新执行
                    if exec_count > last_execution_counts[task_id]:
                        print(f"\n   ✅ 【{task_name}】新执行完成!")
                        print(f"      执行次数: {exec_count} | 成功: {success_count}")
                        print(f"      最后执行: {last_exec}")
                        print(f"      下次执行: {next_run}")

                        # 获取最新结果
                        results = await self.get_task_results(task_id)
                        if results and results['total'] > 0:
                            print(f"      结果数量: {results['total']}条")
                            if results['items']:
                                latest = results['items'][0]
                                print(f"      最新结果: {latest['title'][:50]}...")
                                print(f"      来源: {latest['source']}")

                        last_execution_counts[task_id] = exec_count
                    else:
                        print(f"   ⏳ 【{task_name}】等待执行... (下次: {next_run})")

            # 等待下次检查
            await asyncio.sleep(check_interval)

        print(f"\n{'='*70}")
        print(f"✅ 监控完成")
        print(f"{'='*70}\n")

    async def print_final_report(self):
        """打印最终统计报告"""
        print(f"\n{'='*70}")
        print(f"📋 最终执行统计报告")
        print(f"{'='*70}\n")

        for task_id in self.created_task_ids:
            task_status = await self.get_task_status(task_id)

            if task_status:
                print(f"任务: {task_status['name']}")
                print(f"  ID: {task_id}")
                print(f"  模式: {'URL爬取' if task_status.get('crawl_url') else '关键词搜索'}")
                print(f"  总执行次数: {task_status['execution_count']}")
                print(f"  成功次数: {task_status['success_count']}")
                print(f"  失败次数: {task_status['failure_count']}")
                print(f"  成功率: {task_status['success_rate']:.1f}%")
                print(f"  总结果数: {task_status['total_results']}")
                print(f"  总消耗积分: {task_status['total_credits_used']}")
                print(f"  平均结果数: {task_status['average_results']:.1f}")
                print(f"  创建时间: {task_status['created_at']}")
                print(f"  最后执行: {task_status.get('last_executed_at', 'N/A')}")
                print(f"  下次执行: {task_status.get('next_run_time', 'N/A')}")

                # 获取结果详情
                results = await self.get_task_results(task_id)
                if results:
                    print(f"\n  数据库中存储的结果:")
                    print(f"    总数: {results['total']}条")
                    print(f"    总页数: {results['total_pages']}页")

                    if results['items']:
                        print(f"\n    最近结果预览:")
                        for idx, item in enumerate(results['items'][:3], 1):
                            print(f"      {idx}. {item['title'][:60]}...")
                            print(f"         URL: {item['url']}")
                            print(f"         来源: {item['source']}")
                            print(f"         创建: {item['created_at']}")

                print(f"\n{'-'*70}\n")

    async def cleanup_tasks(self, delete: bool = False):
        """清理测试任务"""
        if not delete:
            print(f"\n⚠️  测试任务保留在系统中，ID列表:")
            for task_id in self.created_task_ids:
                print(f"   - {task_id}")
            print(f"\n提示: 如需删除，请手动调用 DELETE /api/v1/search-tasks/{{task_id}}")
            return

        print(f"\n🗑️ 清理测试任务...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            for task_id in self.created_task_ids:
                try:
                    response = await client.delete(f"{BASE_URL}/search-tasks/{task_id}")
                    if response.status_code == 200:
                        print(f"   ✅ 删除任务: {task_id}")
                    else:
                        print(f"   ⚠️ 删除失败: {task_id}")
                except Exception as e:
                    print(f"   ❌ 删除异常: {task_id} - {e}")


async def main():
    """主测试流程"""
    print(f"\n{'='*70}")
    print(f"🧪 5分钟定时任务测试")
    print(f"{'='*70}\n")

    monitor = TaskMonitor()

    # 步骤1: 创建测试任务
    print(f"📝 创建测试任务...\n")

    # 创建关键词搜索任务
    print(f"1️⃣ 创建关键词搜索任务...")
    keyword_task_id = await monitor.create_task(KEYWORD_TASK_CONFIG)
    if keyword_task_id:
        print(f"   ✅ 关键词搜索任务创建成功: {keyword_task_id}")
    else:
        print(f"   ❌ 关键词搜索任务创建失败")
        return

    await asyncio.sleep(1)

    # 创建URL爬取任务
    print(f"\n2️⃣ 创建URL爬取任务...")
    crawl_task_id = await monitor.create_task(URL_CRAWL_TASK_CONFIG)
    if crawl_task_id:
        print(f"   ✅ URL爬取任务创建成功: {crawl_task_id}")
    else:
        print(f"   ❌ URL爬取任务创建失败")
        return

    # 步骤2: 检查调度器状态
    print(f"\n{'='*70}")
    print(f"🔍 检查调度器状态...")
    print(f"{'='*70}\n")

    scheduler_status = await monitor.check_scheduler_status()
    if scheduler_status:
        print(f"   状态: {scheduler_status['status']}")
        print(f"   活跃任务数: {scheduler_status['active_jobs']}")
        print(f"   下次执行时间: {scheduler_status.get('next_run_time', 'N/A')}")

        if scheduler_status['jobs']:
            print(f"\n   当前调度任务:")
            for job in scheduler_status['jobs']:
                print(f"      - {job['name']}")
                print(f"        下次执行: {job.get('next_run_time', 'N/A')}")
    else:
        print(f"   ⚠️ 无法获取调度器状态")

    # 步骤3: 监控任务执行
    print(f"\n{'='*70}")
    print(f"提示: 任务将每5分钟执行一次")
    print(f"建议监控时长: 至少15分钟（可观察3次执行）")
    print(f"{'='*70}")

    user_input = input("\n是否开始监控? (Y/n): ")
    if user_input.lower() not in ['', 'y', 'yes']:
        print(f"\n⏭️ 跳过监控")
    else:
        duration_input = input("监控时长（分钟，默认15）: ")
        duration = int(duration_input) if duration_input.isdigit() else 15

        await monitor.monitor_tasks(duration_minutes=duration)

    # 步骤4: 打印最终报告
    await monitor.print_final_report()

    # 步骤5: 清理（可选）
    cleanup_input = input("\n是否删除测试任务? (y/N): ")
    delete_tasks = cleanup_input.lower() in ['y', 'yes']
    await monitor.cleanup_tasks(delete=delete_tasks)

    print(f"\n✅ 测试完成!")


if __name__ == "__main__":
    asyncio.run(main())

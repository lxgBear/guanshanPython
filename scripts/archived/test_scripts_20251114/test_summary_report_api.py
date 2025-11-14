"""
智能总结报告系统 API 测试脚本

测试所有15个API端点的功能：
1. 报告管理（CRUD）
2. 任务关联管理
3. 数据检索与搜索
4. 内容编辑与版本管理
5. LLM/AI生成（预留接口）

使用方法:
    python scripts/test_summary_report_api.py
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import httpx
from typing import Dict, Any, List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class SummaryReportAPITester:
    """智能总结报告API测试类"""

    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_data: Dict[str, Any] = {}
        self.test_user = "test_user_summary_reports"

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

    def print_section(self, title: str):
        """打印测试章节标题"""
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print('=' * 60)

    def print_test(self, test_name: str):
        """打印测试名称"""
        print(f"\n🧪 测试: {test_name}")

    def print_success(self, message: str):
        """打印成功信息"""
        print(f"  ✅ {message}")

    def print_error(self, message: str):
        """打印错误信息"""
        print(f"  ❌ {message}")

    def print_info(self, message: str):
        """打印信息"""
        print(f"  ℹ️  {message}")

    # ==========================================
    # 模块1: 报告管理（CRUD）测试
    # ==========================================

    async def test_create_report(self) -> bool:
        """测试创建报告"""
        self.print_test("创建总结报告")

        try:
            response = await self.client.post(
                f"{self.base_url}/summary-reports/",
                json={
                    "title": "测试总结报告 - API自动化测试",
                    "description": "这是一个测试报告，用于验证API功能",
                    "report_type": "comprehensive",
                    "created_by": self.test_user
                }
            )

            if response.status_code == 201:
                report = response.json()
                self.test_data["report_id"] = report["report_id"]
                self.print_success(f"报告创建成功: {report['report_id']}")
                self.print_info(f"标题: {report['title']}")
                return True
            else:
                self.print_error(f"创建失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    async def test_list_reports(self) -> bool:
        """测试获取报告列表"""
        self.print_test("获取报告列表")

        try:
            response = await self.client.get(
                f"{self.base_url}/summary-reports/",
                params={
                    "created_by": self.test_user,
                    "page": 1,
                    "limit": 20
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.print_success(f"查询成功，共 {data['total']} 个报告")
                return True
            else:
                self.print_error(f"查询失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    async def test_get_report(self) -> bool:
        """测试获取报告详情"""
        self.print_test("获取报告详情")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.get(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}"
            )

            if response.status_code == 200:
                report = response.json()
                self.print_success("获取报告详情成功")
                self.print_info(f"状态: {report['status']}")
                self.print_info(f"版本: {report['version']}")
                return True
            else:
                self.print_error(f"获取失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    async def test_update_report(self) -> bool:
        """测试更新报告"""
        self.print_test("更新报告基础信息")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.put(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}",
                json={
                    "title": "测试总结报告 - 已更新",
                    "description": "描述已更新"
                }
            )

            if response.status_code == 200:
                self.print_success("报告更新成功")
                return True
            else:
                self.print_error(f"更新失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    # ==========================================
    # 模块2: 任务关联管理测试
    # ==========================================

    async def test_add_task_to_report(self) -> bool:
        """测试添加任务到报告"""
        self.print_test("关联任务到报告")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            # 添加定时搜索任务
            response1 = await self.client.post(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/tasks",
                json={
                    "task_id": "scheduled_task_001",
                    "task_type": "scheduled",
                    "task_name": "定时搜索任务1",
                    "added_by": self.test_user,
                    "priority": 10
                }
            )

            # 添加即时搜索任务
            response2 = await self.client.post(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/tasks",
                json={
                    "task_id": "instant_task_001",
                    "task_type": "instant",
                    "task_name": "即时搜索任务1",
                    "added_by": self.test_user,
                    "priority": 5
                }
            )

            success_count = 0
            if response1.status_code == 201:
                success_count += 1
                self.print_success("定时任务关联成功")
            if response2.status_code == 201:
                success_count += 1
                self.print_success("即时任务关联成功")

            return success_count == 2

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    async def test_get_report_tasks(self) -> bool:
        """测试获取报告的任务列表"""
        self.print_test("获取报告关联任务")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.get(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/tasks"
            )

            if response.status_code == 200:
                tasks = response.json()
                self.print_success(f"查询成功，共 {len(tasks)} 个关联任务")
                for task in tasks:
                    self.print_info(f"  - {task['task_name']} ({task['task_type']})")
                return True
            else:
                self.print_error(f"查询失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    # ==========================================
    # 模块3: 数据检索与搜索测试
    # ==========================================

    async def test_add_data_item(self) -> bool:
        """测试添加数据项"""
        self.print_test("添加数据项到报告")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.post(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/data",
                json={
                    "source_type": "manual",
                    "title": "测试数据项 - Python性能优化",
                    "content": "这是一个关于Python性能优化的测试数据项，包含了索引优化、查询优化等内容",
                    "added_by": self.test_user,
                    "url": "https://example.com/python-optimization",
                    "tags": ["Python", "性能优化", "数据库"],
                    "importance": 5
                }
            )

            if response.status_code == 201:
                item = response.json()
                self.test_data["item_id"] = item["item_id"]
                self.print_success(f"数据项添加成功: {item['item_id']}")
                return True
            else:
                self.print_error(f"添加失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    async def test_get_data_items(self) -> bool:
        """测试获取数据项列表"""
        self.print_test("获取报告数据项")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.get(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/data",
                params={"limit": 100}
            )

            if response.status_code == 200:
                items = response.json()
                self.print_success(f"查询成功，共 {len(items)} 个数据项")
                return True
            else:
                self.print_error(f"查询失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    async def test_search_report_data(self) -> bool:
        """测试跨任务联表查询（核心功能）"""
        self.print_test("跨任务联表查询搜索")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.get(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/search",
                params={
                    "q": "性能优化",
                    "limit": 50
                }
            )

            if response.status_code == 200:
                results = response.json()
                scheduled_count = len(results.get("scheduled_results", []))
                instant_count = len(results.get("instant_results", []))
                total = results.get("total_count", 0)

                self.print_success(f"联表查询成功")
                self.print_info(f"定时任务结果: {scheduled_count} 条")
                self.print_info(f"即时任务结果: {instant_count} 条")
                self.print_info(f"总计: {total} 条")
                return True
            else:
                self.print_error(f"搜索失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    # ==========================================
    # 模块4: 内容编辑与版本管理测试
    # ==========================================

    async def test_update_content(self) -> bool:
        """测试更新报告内容"""
        self.print_test("更新报告内容（富文本）")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            content = """# 测试报告内容

## 概述
这是一个测试报告的内容，使用Markdown格式编写。

## 主要发现
1. 性能优化效果显著
2. 索引策略合理
3. 查询速度提升明显

## 结论
系统运行良好，各项指标符合预期。
"""

            response = await self.client.put(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/content",
                json={
                    "content_text": content,
                    "content_format": "markdown",
                    "is_manual": True,
                    "updated_by": self.test_user,
                    "change_description": "初始内容创建"
                }
            )

            if response.status_code == 200:
                self.print_success("内容更新成功")
                return True
            else:
                self.print_error(f"更新失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    async def test_get_versions(self) -> bool:
        """测试获取版本历史"""
        self.print_test("获取版本历史")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.get(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/versions",
                params={"limit": 20}
            )

            if response.status_code == 200:
                versions = response.json()
                self.print_success(f"查询成功，共 {len(versions)} 个历史版本")
                return True
            else:
                self.print_error(f"查询失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    # ==========================================
    # 模块5: LLM/AI生成测试（预留接口）
    # ==========================================

    async def test_generate_with_llm(self) -> bool:
        """测试LLM生成（预留接口，应返回未实现提示）"""
        self.print_test("LLM生成报告（预留接口）")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.post(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/generate",
                json={
                    "generation_mode": "comprehensive"
                }
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success") == False:
                    self.print_success("预留接口正常返回（未实现提示）")
                    self.print_info(f"错误信息: {result.get('error')}")
                    return True
                else:
                    self.print_error("预期返回未实现，但接口返回成功")
                    return False
            else:
                self.print_error(f"接口调用失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    async def test_ai_analysis(self) -> bool:
        """测试AI分析（预留接口，应返回未实现提示）"""
        self.print_test("AI数据分析（预留接口）")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.get(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}/analysis",
                params={"analysis_type": "trend"}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success") == False:
                    self.print_success("预留接口正常返回（未实现提示）")
                    self.print_info(f"错误信息: {result.get('error')}")
                    return True
                else:
                    self.print_error("预期返回未实现，但接口返回成功")
                    return False
            else:
                self.print_error(f"接口调用失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    # ==========================================
    # 清理测试数据
    # ==========================================

    async def test_delete_report(self) -> bool:
        """测试删除报告（清理测试数据）"""
        self.print_test("删除报告（清理测试数据）")

        if "report_id" not in self.test_data:
            self.print_error("缺少report_id，跳过测试")
            return False

        try:
            response = await self.client.delete(
                f"{self.base_url}/summary-reports/{self.test_data['report_id']}"
            )

            if response.status_code == 204:
                self.print_success("报告删除成功")
                return True
            else:
                self.print_error(f"删除失败: {response.status_code}")
                return False

        except Exception as e:
            self.print_error(f"异常: {str(e)}")
            return False

    # ==========================================
    # 主测试流程
    # ==========================================

    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("  智能总结报告系统 API 测试")
        print("=" * 60)
        print(f"测试用户: {self.test_user}")
        print(f"API地址: {self.base_url}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        results = []

        # 模块1: 报告管理（CRUD）
        self.print_section("模块1: 报告管理（CRUD）")
        results.append(("创建报告", await self.test_create_report()))
        results.append(("获取报告列表", await self.test_list_reports()))
        results.append(("获取报告详情", await self.test_get_report()))
        results.append(("更新报告", await self.test_update_report()))

        # 模块2: 任务关联管理
        self.print_section("模块2: 任务关联管理")
        results.append(("添加任务到报告", await self.test_add_task_to_report()))
        results.append(("获取报告任务列表", await self.test_get_report_tasks()))

        # 模块3: 数据检索与搜索
        self.print_section("模块3: 数据检索与搜索")
        results.append(("添加数据项", await self.test_add_data_item()))
        results.append(("获取数据项列表", await self.test_get_data_items()))
        results.append(("跨任务联表查询", await self.test_search_report_data()))

        # 模块4: 内容编辑与版本管理
        self.print_section("模块4: 内容编辑与版本管理")
        results.append(("更新报告内容", await self.test_update_content()))
        results.append(("获取版本历史", await self.test_get_versions()))

        # 模块5: LLM/AI生成（预留接口）
        self.print_section("模块5: LLM/AI生成（预留接口）")
        results.append(("LLM生成报告", await self.test_generate_with_llm()))
        results.append(("AI数据分析", await self.test_ai_analysis()))

        # 清理测试数据
        self.print_section("清理测试数据")
        results.append(("删除报告", await self.test_delete_report()))

        # 统计结果
        self.print_section("测试结果统计")
        total = len(results)
        passed = sum(1 for _, success in results if success)
        failed = total - passed

        print(f"\n总测试数: {total}")
        print(f"通过: {passed} ✅")
        print(f"失败: {failed} ❌")
        print(f"成功率: {passed/total*100:.1f}%")

        if failed > 0:
            print("\n失败的测试:")
            for name, success in results:
                if not success:
                    print(f"  ❌ {name}")

        print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        return passed == total


async def main():
    """主函数"""
    tester = SummaryReportAPITester()

    try:
        all_passed = await tester.run_all_tests()
        sys.exit(0 if all_passed else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Summary Report V2.0 清理验证测试

测试项：
1. 基础 CRUD 操作
2. 版本管理功能
3. 内容编辑功能
4. 废弃接口验证（应返回404）
"""

import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
TEST_USER = "cleanup_test_user"


class TestSummaryReportV2Cleanup:
    """Summary Report V2.0 清理验证测试套件"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_report_id = None
        self.results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if message:
            print(f"       {message}")

        if passed:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1
            self.results["errors"].append(f"{test_name}: {message}")

    # ==========================================
    # Phase 1: 基础 CRUD 测试
    # ==========================================

    async def test_create_report(self):
        """测试创建报告"""
        print("\n📝 测试 1: 创建报告")
        try:
            response = await self.client.post(
                f"{BASE_URL}/summary-reports/",
                json={
                    "title": "V2.0 清理测试报告",
                    "description": "用于验证V2.0清理后的功能",
                    "report_type": "comprehensive",
                    "created_by": TEST_USER
                }
            )

            if response.status_code == 201:
                data = response.json()
                self.test_report_id = data.get("report_id")
                self.log_test(
                    "创建报告",
                    True,
                    f"Report ID: {self.test_report_id}"
                )
                return True
            else:
                self.log_test(
                    "创建报告",
                    False,
                    f"状态码: {response.status_code}, 响应: {response.text}"
                )
                return False

        except Exception as e:
            self.log_test("创建报告", False, f"异常: {str(e)}")
            return False

    async def test_get_report(self):
        """测试获取报告详情"""
        print("\n📋 测试 2: 获取报告详情")
        if not self.test_report_id:
            self.log_test("获取报告详情", False, "没有可用的报告ID")
            return False

        try:
            response = await self.client.get(
                f"{BASE_URL}/summary-reports/{self.test_report_id}"
            )

            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "获取报告详情",
                    True,
                    f"标题: {data.get('title')}, 状态: {data.get('status')}"
                )
                return True
            else:
                self.log_test(
                    "获取报告详情",
                    False,
                    f"状态码: {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test("获取报告详情", False, f"异常: {str(e)}")
            return False

    async def test_list_reports(self):
        """测试列出报告"""
        print("\n📄 测试 3: 列出报告（游标分页）")
        try:
            response = await self.client.get(
                f"{BASE_URL}/summary-reports/",
                params={"limit": 10}
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                meta = data.get("meta", {})
                self.log_test(
                    "列出报告",
                    True,
                    f"返回 {meta.get('count')} 条记录, has_next: {meta.get('has_next')}"
                )
                return True
            else:
                self.log_test(
                    "列出报告",
                    False,
                    f"状态码: {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test("列出报告", False, f"异常: {str(e)}")
            return False

    async def test_update_report(self):
        """测试更新报告基础信息"""
        print("\n✏️ 测试 4: 更新报告基础信息")
        if not self.test_report_id:
            self.log_test("更新报告", False, "没有可用的报告ID")
            return False

        try:
            response = await self.client.put(
                f"{BASE_URL}/summary-reports/{self.test_report_id}",
                json={
                    "title": "V2.0 清理测试报告（已更新）",
                    "description": "更新后的描述"
                }
            )

            if response.status_code == 200:
                self.log_test("更新报告", True, "基础信息更新成功")
                return True
            else:
                self.log_test(
                    "更新报告",
                    False,
                    f"状态码: {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test("更新报告", False, f"异常: {str(e)}")
            return False

    # ==========================================
    # Phase 2: 内容编辑测试
    # ==========================================

    async def test_update_content(self):
        """测试更新报告内容"""
        print("\n📝 测试 5: 更新报告内容（富文本）")
        if not self.test_report_id:
            self.log_test("更新内容", False, "没有可用的报告ID")
            return False

        try:
            content = """# V2.0 清理测试报告

## 测试内容

这是一段测试内容，用于验证V2.0清理后的内容编辑功能。

### 功能验证
- [x] 创建报告
- [x] 更新基础信息
- [x] 内容编辑

### 数据质量
- 数据源数量: 0
- 质量评分: 0.0

"""
            response = await self.client.put(
                f"{BASE_URL}/summary-reports/{self.test_report_id}/content",
                json={
                    "content_text": content,
                    "content_format": "markdown",
                    "is_manual": True,
                    "updated_by": TEST_USER,
                    "change_description": "V2.0 清理验证测试"
                }
            )

            if response.status_code == 200:
                self.log_test(
                    "更新内容",
                    True,
                    "内容更新成功，应自动创建版本记录"
                )
                return True
            else:
                self.log_test(
                    "更新内容",
                    False,
                    f"状态码: {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test("更新内容", False, f"异常: {str(e)}")
            return False

    # ==========================================
    # Phase 3: 版本管理测试
    # ==========================================

    async def test_get_versions(self):
        """测试获取版本历史"""
        print("\n📚 测试 6: 获取版本历史")
        if not self.test_report_id:
            self.log_test("获取版本", False, "没有可用的报告ID")
            return False

        try:
            response = await self.client.get(
                f"{BASE_URL}/summary-reports/{self.test_report_id}/versions",
                params={"limit": 10}
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                meta = data.get("meta", {})
                self.log_test(
                    "获取版本历史",
                    True,
                    f"版本数: {meta.get('count')}"
                )
                return True
            else:
                self.log_test(
                    "获取版本历史",
                    False,
                    f"状态码: {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test("获取版本历史", False, f"异常: {str(e)}")
            return False

    # ==========================================
    # Phase 4: 废弃接口验证
    # ==========================================

    async def test_deprecated_endpoints(self):
        """测试废弃接口（应返回404）"""
        print("\n🚫 测试 7: 验证废弃接口")

        if not self.test_report_id:
            self.log_test("废弃接口验证", False, "没有可用的报告ID")
            return False

        deprecated_endpoints = [
            # Module 2: 任务关联（已废弃）
            ("POST", f"{BASE_URL}/summary-reports/{self.test_report_id}/tasks", "添加任务关联"),
            ("GET", f"{BASE_URL}/summary-reports/{self.test_report_id}/tasks", "获取任务列表"),
            ("DELETE", f"{BASE_URL}/summary-reports/{self.test_report_id}/tasks/test_id/scheduled", "删除任务关联"),

            # Module 3: 数据检索（已废弃）
            ("GET", f"{BASE_URL}/summary-reports/{self.test_report_id}/search", "跨任务搜索"),
            ("GET", f"{BASE_URL}/summary-reports/{self.test_report_id}/data", "获取数据项"),
            ("POST", f"{BASE_URL}/summary-reports/{self.test_report_id}/data", "添加数据项"),
        ]

        all_passed = True
        for method, url, desc in deprecated_endpoints:
            try:
                if method == "GET":
                    response = await self.client.get(url)
                elif method == "POST":
                    response = await self.client.post(url, json={})
                elif method == "DELETE":
                    response = await self.client.delete(url)

                # 废弃接口应返回404
                if response.status_code == 404:
                    print(f"  ✅ {desc}: 正确返回404")
                else:
                    print(f"  ❌ {desc}: 返回 {response.status_code}（应为404）")
                    all_passed = False

            except Exception as e:
                print(f"  ⚠️ {desc}: 异常 {str(e)}")
                all_passed = False

        self.log_test(
            "废弃接口验证",
            all_passed,
            "所有废弃接口应正确返回404" if all_passed else "部分接口未返回预期状态码"
        )

        return all_passed

    # ==========================================
    # Phase 5: LLM/AI 预留接口测试
    # ==========================================

    async def test_llm_placeholder(self):
        """测试LLM生成预留接口"""
        print("\n🤖 测试 8: LLM生成预留接口")
        if not self.test_report_id:
            self.log_test("LLM接口", False, "没有可用的报告ID")
            return False

        try:
            response = await self.client.post(
                f"{BASE_URL}/summary-reports/{self.test_report_id}/generate",
                json={
                    "generation_mode": "comprehensive"
                }
            )

            # 预留接口应返回"未实现"消息
            if response.status_code == 200:
                data = response.json()
                if not data.get("success") and "not yet implemented" in data.get("error", "").lower():
                    self.log_test(
                        "LLM预留接口",
                        True,
                        "正确返回'未实现'占位响应"
                    )
                    return True

            self.log_test(
                "LLM预留接口",
                False,
                f"状态码: {response.status_code}"
            )
            return False

        except Exception as e:
            self.log_test("LLM预留接口", False, f"异常: {str(e)}")
            return False

    # ==========================================
    # Phase 6: 清理测试数据
    # ==========================================

    async def test_delete_report(self):
        """测试删除报告"""
        print("\n🗑️ 测试 9: 删除报告（清理测试数据）")
        if not self.test_report_id:
            self.log_test("删除报告", False, "没有可用的报告ID")
            return False

        try:
            response = await self.client.delete(
                f"{BASE_URL}/summary-reports/{self.test_report_id}"
            )

            if response.status_code == 204:
                self.log_test(
                    "删除报告",
                    True,
                    "测试数据已清理"
                )
                return True
            else:
                self.log_test(
                    "删除报告",
                    False,
                    f"状态码: {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test("删除报告", False, f"异常: {str(e)}")
            return False

    # ==========================================
    # 测试套件执行
    # ==========================================

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("Summary Report V2.0 清理验证测试")
        print("=" * 60)

        tests = [
            self.test_create_report,
            self.test_get_report,
            self.test_list_reports,
            self.test_update_report,
            self.test_update_content,
            self.test_get_versions,
            self.test_deprecated_endpoints,
            self.test_llm_placeholder,
            self.test_delete_report,
        ]

        for test in tests:
            await test()
            await asyncio.sleep(0.5)  # 短暂延迟

        # 打印测试总结
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"✅ 通过: {self.results['passed']}")
        print(f"❌ 失败: {self.results['failed']}")

        if self.results['failed'] > 0:
            print("\n失败详情:")
            for error in self.results['errors']:
                print(f"  - {error}")

        print("=" * 60)

        await self.close()

        return self.results['failed'] == 0


async def main():
    """主函数"""
    tester = TestSummaryReportV2Cleanup()

    try:
        success = await tester.run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
        await tester.close()
        exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试执行失败: {str(e)}")
        await tester.close()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
NL Search 和 Archive 接口全面测试

测试范围：
1. 自然语言搜索 API（5个接口）
2. 档案管理 API（5个接口）

测试维度：
- 功能正确性
- 参数验证
- 错误处理
- 数据一致性
- 权限控制
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List
import json
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.nl_search.nl_search_service import nl_search_service
from src.services.nl_search.mongo_archive_service import mongo_archive_service
from src.services.nl_search.config import nl_search_config
from src.infrastructure.database.connection import get_mongodb_database


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class APITester:
    """API 接口测试器"""

    def __init__(self):
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_data = {
            "test_user_id": 1001,
            "test_archive_id": None,
            "test_log_id": None,
            "test_news_id": None
        }

    def print_header(self, text: str):
        """打印测试头部"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

    def print_section(self, text: str):
        """打印测试章节"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'-'*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'-'*80}{Colors.RESET}")

    def print_test(self, name: str, status: str, message: str = ""):
        """打印测试结果"""
        self.total_tests += 1
        if status == "PASS":
            self.passed_tests += 1
            symbol = f"{Colors.GREEN}✅{Colors.RESET}"
            status_text = f"{Colors.GREEN}PASS{Colors.RESET}"
        elif status == "FAIL":
            self.failed_tests += 1
            symbol = f"{Colors.RED}❌{Colors.RESET}"
            status_text = f"{Colors.RED}FAIL{Colors.RESET}"
        else:  # SKIP
            symbol = f"{Colors.YELLOW}⚠️{Colors.RESET}"
            status_text = f"{Colors.YELLOW}SKIP{Colors.RESET}"

        print(f"{symbol} [{status_text}] {name}")
        if message:
            print(f"    {Colors.YELLOW}→{Colors.RESET} {message}")

        self.test_results.append({
            "name": name,
            "status": status,
            "message": message
        })

    def print_summary(self):
        """打印测试总结"""
        self.print_header("测试总结")

        print(f"总测试数: {Colors.BOLD}{self.total_tests}{Colors.RESET}")
        print(f"通过: {Colors.GREEN}{self.passed_tests}{Colors.RESET}")
        print(f"失败: {Colors.RED}{self.failed_tests}{Colors.RESET}")
        print(f"跳过: {Colors.YELLOW}{self.total_tests - self.passed_tests - self.failed_tests}{Colors.RESET}")

        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        print(f"\n成功率: {Colors.BOLD}{success_rate:.1f}%{Colors.RESET}")

        if self.failed_tests > 0:
            print(f"\n{Colors.RED}失败的测试：{Colors.RESET}")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"  - {result['name']}: {result['message']}")

    async def setup(self):
        """准备测试数据"""
        self.print_section("准备测试数据")

        try:
            # 获取一个真实的 news_result_id
            db = await get_mongodb_database()
            result = await db['news_results'].find_one()
            if result:
                self.test_data["test_news_id"] = str(result["_id"])
                self.print_test("获取测试新闻ID", "PASS", f"ID: {self.test_data['test_news_id']}")
            else:
                self.print_test("获取测试新闻ID", "SKIP", "数据库中没有新闻数据")
                return False

            return True

        except Exception as e:
            self.print_test("准备测试数据", "FAIL", str(e))
            return False

    # ==================== NL Search API 测试 ====================

    async def test_nl_search_status(self):
        """测试 1: GET /status - 功能状态检查"""
        try:
            status = await nl_search_service.get_service_status()

            if "enabled" in status and "version" in status:
                self.print_test(
                    "NL Search - 功能状态检查",
                    "PASS",
                    f"启用: {status['enabled']}, 版本: {status['version']}"
                )
                return True
            else:
                self.print_test("NL Search - 功能状态检查", "FAIL", "响应缺少必要字段")
                return False

        except Exception as e:
            self.print_test("NL Search - 功能状态检查", "FAIL", str(e))
            return False

    async def test_nl_search_create(self):
        """测试 2: POST / - 创建自然语言搜索"""
        if not nl_search_config.enabled:
            self.print_test("NL Search - 创建搜索", "SKIP", "功能未启用")
            return False

        try:
            result = await nl_search_service.create_search(
                query_text="测试查询：AI 技术突破",
                user_id=str(self.test_data["test_user_id"])
            )

            if result and "log_id" in result:
                self.test_data["test_log_id"] = result["log_id"]
                self.print_test(
                    "NL Search - 创建搜索",
                    "PASS",
                    f"log_id: {result['log_id']}"
                )
                return True
            else:
                self.print_test("NL Search - 创建搜索", "FAIL", "响应缺少 log_id")
                return False

        except Exception as e:
            self.print_test("NL Search - 创建搜索", "FAIL", str(e))
            return False

    async def test_nl_search_get_log(self):
        """测试 3: GET /{log_id} - 获取搜索记录"""
        if not self.test_data["test_log_id"]:
            self.print_test("NL Search - 获取搜索记录", "SKIP", "没有测试 log_id")
            return False

        try:
            log = await nl_search_service.get_search_log(self.test_data["test_log_id"])

            if log and "log_id" in log:
                self.print_test(
                    "NL Search - 获取搜索记录",
                    "PASS",
                    f"查询文本: {log.get('query_text', 'N/A')[:30]}..."
                )
                return True
            else:
                self.print_test("NL Search - 获取搜索记录", "FAIL", "记录不存在")
                return False

        except Exception as e:
            self.print_test("NL Search - 获取搜索记录", "FAIL", str(e))
            return False

    async def test_nl_search_list_logs(self):
        """测试 4: GET / - 查询搜索历史"""
        try:
            logs = await nl_search_service.list_search_logs(limit=10, offset=0)

            self.print_test(
                "NL Search - 查询搜索历史",
                "PASS",
                f"返回 {len(logs)} 条记录"
            )
            return True

        except Exception as e:
            self.print_test("NL Search - 查询搜索历史", "FAIL", str(e))
            return False

    # ==================== Archive API 测试 ====================

    async def test_archive_create(self):
        """测试 5: POST /archives - 创建档案"""
        if not self.test_data["test_news_id"]:
            self.print_test("Archive - 创建档案", "SKIP", "没有测试新闻ID")
            return False

        try:
            items_data = [{
                "news_result_id": self.test_data["test_news_id"],
                "edited_title": "测试档案条目",
                "edited_summary": "这是测试摘要",
                "user_rating": 5
            }]

            result = await mongo_archive_service.create_archive(
                user_id=self.test_data["test_user_id"],
                archive_name="接口测试档案",
                items=items_data,
                description="用于接口测试的档案",
                tags=["测试", "API"]
            )

            if result and "archive_id" in result:
                self.test_data["test_archive_id"] = result["archive_id"]
                self.print_test(
                    "Archive - 创建档案",
                    "PASS",
                    f"archive_id: {result['archive_id']}, 条目数: {result['items_count']}"
                )
                return True
            else:
                self.print_test("Archive - 创建档案", "FAIL", "响应缺少 archive_id")
                return False

        except Exception as e:
            self.print_test("Archive - 创建档案", "FAIL", str(e))
            return False

    async def test_archive_list(self):
        """测试 6: GET /archives - 查询档案列表"""
        try:
            archives = await mongo_archive_service.list_archives(
                user_id=self.test_data["test_user_id"],
                limit=20,
                offset=0
            )

            self.print_test(
                "Archive - 查询档案列表",
                "PASS",
                f"返回 {len(archives)} 个档案"
            )
            return True

        except Exception as e:
            self.print_test("Archive - 查询档案列表", "FAIL", str(e))
            return False

    async def test_archive_get(self):
        """测试 7: GET /archives/{archive_id} - 获取档案详情"""
        if not self.test_data["test_archive_id"]:
            self.print_test("Archive - 获取档案详情", "SKIP", "没有测试 archive_id")
            return False

        try:
            archive = await mongo_archive_service.get_archive(
                archive_id=self.test_data["test_archive_id"],
                user_id=self.test_data["test_user_id"]
            )

            if archive and "items" in archive:
                self.print_test(
                    "Archive - 获取档案详情",
                    "PASS",
                    f"档案: {archive['archive_name']}, 条目数: {len(archive['items'])}"
                )
                return True
            else:
                self.print_test("Archive - 获取档案详情", "FAIL", "档案不存在")
                return False

        except Exception as e:
            self.print_test("Archive - 获取档案详情", "FAIL", str(e))
            return False

    async def test_archive_update(self):
        """测试 8: PUT /archives/{archive_id} - 更新档案"""
        if not self.test_data["test_archive_id"]:
            self.print_test("Archive - 更新档案", "SKIP", "没有测试 archive_id")
            return False

        try:
            success = await mongo_archive_service.update_archive(
                archive_id=self.test_data["test_archive_id"],
                user_id=self.test_data["test_user_id"],
                archive_name="接口测试档案 - 已更新",
                description="更新后的描述",
                tags=["测试", "API", "已更新"]
            )

            if success:
                self.print_test("Archive - 更新档案", "PASS", "更新成功")
                return True
            else:
                self.print_test("Archive - 更新档案", "FAIL", "更新失败")
                return False

        except Exception as e:
            self.print_test("Archive - 更新档案", "FAIL", str(e))
            return False

    async def test_archive_delete(self):
        """测试 9: DELETE /archives/{archive_id} - 删除档案"""
        if not self.test_data["test_archive_id"]:
            self.print_test("Archive - 删除档案", "SKIP", "没有测试 archive_id")
            return False

        try:
            success = await mongo_archive_service.delete_archive(
                archive_id=self.test_data["test_archive_id"],
                user_id=self.test_data["test_user_id"]
            )

            if success:
                # 验证删除
                archive = await mongo_archive_service.get_archive(
                    archive_id=self.test_data["test_archive_id"],
                    user_id=self.test_data["test_user_id"]
                )

                if archive is None:
                    self.print_test("Archive - 删除档案", "PASS", "删除成功并验证")
                    return True
                else:
                    self.print_test("Archive - 删除档案", "FAIL", "删除后仍可查询")
                    return False
            else:
                self.print_test("Archive - 删除档案", "FAIL", "删除失败")
                return False

        except Exception as e:
            self.print_test("Archive - 删除档案", "FAIL", str(e))
            return False

    # ==================== 边界和错误测试 ====================

    async def test_archive_permission(self):
        """测试 10: 权限验证 - 其他用户无法访问"""
        if not self.test_data["test_archive_id"]:
            # 先创建一个测试档案
            await self.test_archive_create()

        if not self.test_data["test_archive_id"]:
            self.print_test("Archive - 权限验证", "SKIP", "无法创建测试档案")
            return False

        try:
            # 使用不同的用户ID尝试访问
            archive = await mongo_archive_service.get_archive(
                archive_id=self.test_data["test_archive_id"],
                user_id=9999  # 不同的用户
            )

            if archive is None:
                self.print_test("Archive - 权限验证", "PASS", "正确拒绝无权访问")
                return True
            else:
                self.print_test("Archive - 权限验证", "FAIL", "权限验证失败，允许了无权访问")
                return False

        except Exception as e:
            self.print_test("Archive - 权限验证", "FAIL", str(e))
            return False

    async def test_archive_invalid_data(self):
        """测试 11: 输入验证 - 无效数据"""
        try:
            # 尝试创建空名称的档案（应该失败）
            try:
                await mongo_archive_service.create_archive(
                    user_id=self.test_data["test_user_id"],
                    archive_name="",  # 空名称
                    items=[],  # 空条目
                    description="测试",
                    tags=[]
                )
                self.print_test("Archive - 输入验证", "FAIL", "接受了无效输入")
                return False

            except ValueError:
                self.print_test("Archive - 输入验证", "PASS", "正确拒绝无效输入")
                return True

        except Exception as e:
            self.print_test("Archive - 输入验证", "FAIL", f"意外错误: {str(e)}")
            return False

    # ==================== 主测试流程 ====================

    async def run_all_tests(self):
        """运行所有测试"""
        self.print_header("NL Search & Archive API 全面测试")

        # 准备测试数据
        if not await self.setup():
            print(f"\n{Colors.RED}测试数据准备失败，中止测试{Colors.RESET}")
            return False

        # NL Search API 测试
        self.print_section("自然语言搜索 API 测试")
        await self.test_nl_search_status()
        await self.test_nl_search_create()
        await self.test_nl_search_get_log()
        await self.test_nl_search_list_logs()

        # Archive API 测试
        self.print_section("档案管理 API 测试")
        await self.test_archive_create()
        await self.test_archive_list()
        await self.test_archive_get()
        await self.test_archive_update()
        await self.test_archive_permission()  # 权限测试在删除前
        await self.test_archive_delete()

        # 边界和错误测试
        self.print_section("边界和错误处理测试")
        await self.test_archive_invalid_data()

        # 打印总结
        self.print_summary()

        return self.failed_tests == 0


async def main():
    """主函数"""
    tester = APITester()
    success = await tester.run_all_tests()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

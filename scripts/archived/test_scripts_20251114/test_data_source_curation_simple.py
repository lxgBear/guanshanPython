#!/usr/bin/env python3
"""
数据源整编功能简化测试

直接在MongoDB中创建测试数据，测试核心功能：
1. 数据源CRUD操作
2. 原始数据添加/移除（带状态同步）
3. 数据源确定/恢复（带状态同步）
"""

import asyncio
import httpx
from datetime import datetime
from motor import motor_asyncio
from bson import ObjectId

BASE_URL = "http://localhost:8000/api/v1"
TEST_USER = "test_data_curator"
MONGODB_URL = "mongodb://localhost:27017/guanshan_test"


class SimpleDataSourceTester:
    """简化的数据源整编功能测试器"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.db_client = motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
        self.db = self.db_client.guanshan_test
        self.test_data_source_id = None
        self.test_instant_search_result_id = None
        self.results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
        self.db_client.close()

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

    async def setup_test_data(self):
        """准备测试数据：直接在MongoDB中创建即时搜索结果"""
        print("\n🔧 测试准备：创建测试数据")

        try:
            # 生成snowflake风格的ID（与系统保持一致）
            import time
            result_id = str(int(time.time() * 1000000))

            # 直接在MongoDB中创建一条即时搜索结果（匹配系统schema）
            instant_search_result = {
                "_id": ObjectId(),
                "id": result_id,  # 使用string id字段，service查询使用这个字段
                "title": "测试数据源整编功能",
                "url": "https://test.example.com/article",
                "markdown_content": "这是测试内容",
                "snippet": "测试摘要内容",
                "content": "完整的测试内容用于数据源整编功能验证",
                "metadata": {
                    "language": "zh",
                    "source": "firecrawl"
                },
                "status": "pending",  # 初始状态为pending
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

            await self.db.instant_search_results.insert_one(instant_search_result)
            self.test_instant_search_result_id = result_id  # 使用string id

            self.log_test(
                "准备测试数据",
                True,
                f"创建即时搜索结果: {self.test_instant_search_result_id}"
            )
            return True

        except Exception as e:
            self.log_test("准备测试数据", False, f"异常: {str(e)}")
            return False

    async def test_create_data_source(self):
        """测试创建数据源"""
        print("\n📝 测试 1: 创建数据源")

        try:
            response = await self.client.post(
                f"{BASE_URL}/data-sources/",
                json={
                    "title": "Python Web开发最佳实践",
                    "description": "收集Python Web开发相关的优质资源",
                    "created_by": TEST_USER,
                    "tags": ["Python", "Web开发", "最佳实践"]
                }
            )

            if response.status_code == 201:
                data = response.json()
                data_source = data.get("data", {})
                self.test_data_source_id = data_source.get("id")

                # 验证初始状态
                is_valid = (
                    data_source.get("status") == "draft" and
                    data_source.get("total_raw_data_count") == 0
                )

                self.log_test(
                    "创建数据源",
                    is_valid,
                    f"ID: {self.test_data_source_id}, 状态: {data_source.get('status')}"
                )
                return is_valid
            else:
                self.log_test(
                    "创建数据源",
                    False,
                    f"状态码: {response.status_code}, 响应: {response.text}"
                )
                return False

        except Exception as e:
            self.log_test("创建数据源", False, f"异常: {str(e)}")
            return False

    async def test_add_raw_data(self):
        """测试添加原始数据（验证状态同步）"""
        print("\n📦 测试 2: 添加原始数据（状态同步）")

        if not self.test_data_source_id or not self.test_instant_search_result_id:
            self.log_test("添加原始数据", False, "缺少必要的测试ID")
            return False

        try:
            # 1. 添加原始数据
            response = await self.client.post(
                f"{BASE_URL}/data-sources/{self.test_data_source_id}/raw-data",
                json={
                    "data_id": self.test_instant_search_result_id,
                    "data_type": "instant",
                    "added_by": TEST_USER
                }
            )

            if response.status_code != 200:
                self.log_test(
                    "添加原始数据",
                    False,
                    f"添加失败，状态码: {response.status_code}, 响应: {response.text}"
                )
                return False

            # 2. 验证数据源统计更新
            ds_response = await self.client.get(
                f"{BASE_URL}/data-sources/{self.test_data_source_id}"
            )
            ds_data = ds_response.json().get("data", {})

            # 3. 验证原始数据状态变更 → processing
            isr = await self.db.instant_search_results.find_one(
                {"id": self.test_instant_search_result_id}
            )

            # 验证结果
            is_valid = (
                ds_data.get("total_raw_data_count") == 1 and
                ds_data.get("instant_data_count") == 1 and
                isr.get("status") == "processing"
            )

            self.log_test(
                "添加原始数据（状态同步）",
                is_valid,
                f"数据源数量: {ds_data.get('total_raw_data_count')}, "
                f"原始数据状态: {isr.get('status')} (应为processing)"
            )
            return is_valid

        except Exception as e:
            self.log_test("添加原始数据", False, f"异常: {str(e)}")
            return False

    async def test_confirm_data_source(self):
        """测试确定数据源（验证事务状态同步）"""
        print("\n✅ 测试 3: 确定数据源（事务状态同步）")

        if not self.test_data_source_id:
            self.log_test("确定数据源", False, "没有可用的数据源ID")
            return False

        try:
            # 1. 确定数据源
            response = await self.client.post(
                f"{BASE_URL}/data-sources/{self.test_data_source_id}/confirm",
                json={"confirmed_by": TEST_USER}
            )

            if response.status_code != 200:
                self.log_test(
                    "确定数据源",
                    False,
                    f"确定失败，状态码: {response.status_code}, 响应: {response.text}"
                )
                return False

            # 2. 验证数据源状态 → confirmed
            ds_response = await self.client.get(
                f"{BASE_URL}/data-sources/{self.test_data_source_id}"
            )
            ds_data = ds_response.json().get("data", {})

            # 3. 验证原始数据状态 → completed
            isr = await self.db.instant_search_results.find_one(
                {"id": self.test_instant_search_result_id}
            )

            # 验证结果
            is_valid = (
                ds_data.get("status") == "confirmed" and
                ds_data.get("confirmed_by") == TEST_USER and
                isr.get("status") == "completed"
            )

            self.log_test(
                "确定数据源（事务状态同步）",
                is_valid,
                f"数据源状态: {ds_data.get('status')}, "
                f"原始数据状态: {isr.get('status')} (应为completed)"
            )
            return is_valid

        except Exception as e:
            self.log_test("确定数据源", False, f"异常: {str(e)}")
            return False

    async def test_revert_to_draft(self):
        """测试恢复为草稿（验证事务状态同步）"""
        print("\n🔄 测试 4: 恢复为草稿（事务状态同步）")

        if not self.test_data_source_id:
            self.log_test("恢复为草稿", False, "没有可用的数据源ID")
            return False

        try:
            # 1. 恢复为草稿
            response = await self.client.post(
                f"{BASE_URL}/data-sources/{self.test_data_source_id}/revert",
                json={"reverted_by": TEST_USER}
            )

            if response.status_code != 200:
                self.log_test(
                    "恢复为草稿",
                    False,
                    f"恢复失败，状态码: {response.status_code}, 响应: {response.text}"
                )
                return False

            # 2. 验证数据源状态 → draft
            ds_response = await self.client.get(
                f"{BASE_URL}/data-sources/{self.test_data_source_id}"
            )
            ds_data = ds_response.json().get("data", {})

            # 3. 验证原始数据状态 → processing
            isr = await self.db.instant_search_results.find_one(
                {"id": self.test_instant_search_result_id}
            )

            # 验证结果
            is_valid = (
                ds_data.get("status") == "draft" and
                ds_data.get("confirmed_by") is None and
                isr.get("status") == "processing"
            )

            self.log_test(
                "恢复为草稿（事务状态同步）",
                is_valid,
                f"数据源状态: {ds_data.get('status')}, "
                f"原始数据状态: {isr.get('status')} (应为processing)"
            )
            return is_valid

        except Exception as e:
            self.log_test("恢复为草稿", False, f"异常: {str(e)}")
            return False

    async def test_delete_data_source(self):
        """测试删除数据源（验证状态同步）"""
        print("\n🗑️  测试 5: 删除数据源（状态同步）")

        if not self.test_data_source_id:
            self.log_test("删除数据源", False, "没有可用的数据源ID")
            return False

        try:
            # 1. 删除数据源（草稿状态）
            response = await self.client.delete(
                f"{BASE_URL}/data-sources/{self.test_data_source_id}",
                params={"deleted_by": TEST_USER}
            )

            if response.status_code != 200:
                self.log_test(
                    "删除数据源",
                    False,
                    f"删除失败，状态码: {response.status_code}, 响应: {response.text}"
                )
                return False

            # 2. 验证原始数据状态 → archived（草稿删除后）
            isr = await self.db.instant_search_results.find_one(
                {"id": self.test_instant_search_result_id}
            )

            is_valid = isr.get("status") == "archived"

            self.log_test(
                "删除数据源（状态同步）",
                is_valid,
                f"原始数据状态: {isr.get('status')} (应为archived)"
            )
            return is_valid

        except Exception as e:
            self.log_test("删除数据源", False, f"异常: {str(e)}")
            return False

    async def cleanup_test_data(self):
        """清理测试数据"""
        print("\n🧹 清理测试数据")

        try:
            # 删除测试用的即时搜索结果
            if self.test_instant_search_result_id:
                await self.db.instant_search_results.delete_one(
                    {"id": self.test_instant_search_result_id}
                )
                print(f"   删除测试结果: {self.test_instant_search_result_id}")

            print("   ✅ 清理完成")

        except Exception as e:
            print(f"   ⚠️ 清理失败: {str(e)}")

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("数据源整编功能综合测试（简化版）")
        print("=" * 60)

        # Phase 1: 准备测试数据
        setup_ok = await self.setup_test_data()
        if not setup_ok:
            print("\n❌ 测试数据准备失败，终止测试")
            return False

        await asyncio.sleep(1)

        # Phase 2-5: 执行测试
        tests = [
            self.test_create_data_source,
            self.test_add_raw_data,
            self.test_confirm_data_source,
            self.test_revert_to_draft,
            self.test_delete_data_source,
        ]

        for test in tests:
            await test()
            await asyncio.sleep(0.5)

        # 清理测试数据
        await self.cleanup_test_data()

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
    tester = SimpleDataSourceTester()

    try:
        success = await tester.run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
        await tester.close()
        exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        await tester.close()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())

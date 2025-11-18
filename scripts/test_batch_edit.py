#!/usr/bin/env python3
"""
用户批量编辑功能集成测试脚本

测试批量编辑的完整功能流程

版本: v1.0.0
日期: 2025-11-17
"""
import asyncio
import sys
import os
from typing import Dict, Any
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.user_edit_service import user_edit_service
from src.core.domain.entities.processed_result import ProcessedResult
from src.utils.snowflake import generate_id


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_section(title: str):
    """打印章节标题"""
    print()
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print()


def print_success(message: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")


def print_error(message: str):
    """打印错误消息"""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")


def print_info(message: str):
    """打印信息消息"""
    print(f"{Colors.YELLOW}ℹ️  {message}{Colors.RESET}")


def print_result(label: str, value: Any):
    """打印测试结果"""
    print(f"   {Colors.BOLD}{label}:{Colors.RESET} {value}")


async def create_test_records() -> list[str]:
    """创建测试记录"""
    print_section("准备测试数据")

    try:
        print_info("创建3条测试记录...")

        record_ids = []

        for i in range(1, 4):
            # 创建测试实体
            entity = ProcessedResult(
                id=generate_id(),
                raw_result_id=f"raw_{generate_id()}",
                task_id=f"test_task_{generate_id()}",
                title=f"测试标题{i}",
                url=f"https://example.com/test{i}",
                content=f"这是测试内容{i}",
                content_zh=f"这是中文测试内容{i}",
                snippet=f"测试摘要{i}",
                source="example.com",
                language="zh",
                search_position=i,
                quality_score=0.8 + i * 0.05,
                relevance_score=0.9,
                news_results={
                    "title": f"AI标题{i}",
                    "content": f"AI内容{i}",
                    "source": "example.com",
                    "category": {
                        "大类": "测试",
                        "类别": "分类",
                        "地域": "中国"
                    },
                    "media_urls": []
                },
                article_tag=["测试", "标签"],
                created_at=datetime.utcnow(),
                processing_status="completed"
            )

            # 保存到数据库
            record_id = await user_edit_service.repository.create(entity, "test_user")
            record_ids.append(record_id)

            print_success(f"创建测试记录{i}: {record_id}")

        print_info(f"测试数据准备完成，共{len(record_ids)}条记录")
        return record_ids

    except Exception as e:
        print_error(f"创建测试数据失败: {e}")
        raise


async def test_batch_update_flexible(record_ids: list[str]):
    """测试批量更新（灵活模式）"""
    print_section("测试 1: 批量更新（灵活模式）")

    try:
        print_info("每条记录编辑不同字段...")

        updates = [
            {
                "id": record_ids[0],
                "title": "修正后的标题1",
                "content_zh": "修正后的中文内容1",
                "user_rating": 5
            },
            {
                "id": record_ids[1],
                "title": "修正后的标题2",
                "article_tag": ["GPT-5", "AI", "技术"]
            },
            {
                "id": record_ids[2],
                "news_results": {
                    "category": {
                        "大类": "科技",
                        "类别": "人工智能",
                        "地域": "美国"
                    }
                },
                "user_rating": 4
            }
        ]

        result = await user_edit_service.batch_update(
            updates=updates,
            editor_id="test_editor_flexible"
        )

        assert result["success"], "批量更新失败"
        assert result["updated"] == 3, f"期望更新3条，实际{result['updated']}条"

        print_success("批量灵活更新成功")
        print_result("总数", result["total"])
        print_result("成功", result["updated"])
        print_result("失败", result["failed"])

        # 打印详细结果
        for item in result["results"]:
            if item["success"]:
                print(f"   ✓ {item['id']}: {', '.join(item['updated_fields'])}")

    except Exception as e:
        print_error(f"批量灵活更新失败: {e}")
        raise


async def test_batch_update_fields(record_ids: list[str]):
    """测试批量更新（统一字段模式）"""
    print_section("测试 2: 批量更新（统一字段）")

    try:
        print_info("为所有记录设置相同的分类和标签...")

        updates = {
            "news_results": {
                "category": {
                    "大类": "新闻",
                    "类别": "国际",
                    "地域": "欧洲"
                }
            },
            "article_tag": ["新闻", "国际", "测试"],
            "user_rating": 5
        }

        result = await user_edit_service.batch_update_fields(
            record_ids=record_ids,
            updates=updates,
            editor_id="test_editor_fields"
        )

        assert result["success"], "批量统一更新失败"
        assert result["updated"] == 3, f"期望更新3条，实际{result['updated']}条"

        print_success("批量统一更新成功")
        print_result("总数", result["total"])
        print_result("成功", result["updated"])
        print_result("失败", result["failed"])
        print_result("更新字段", ", ".join(result["updated_fields"]))

    except Exception as e:
        print_error(f"批量统一更新失败: {e}")
        raise


async def test_single_update(record_id: str):
    """测试单条更新"""
    print_section("测试 3: 单条更新")

    try:
        print_info(f"更新单条记录: {record_id}")

        updates = {
            "title": "单条更新的标题",
            "content_zh": "单条更新的内容",
            "news_results": {
                "title": "单条更新的AI标题",
                "content": "单条更新的AI内容",
                "category": {
                    "大类": "科技",
                    "类别": "前沿技术",
                    "地域": "全球"
                }
            },
            "user_rating": 5,
            "user_notes": "这是一条优质内容"
        }

        result = await user_edit_service.update_one(
            record_id=record_id,
            updates=updates,
            editor_id="test_editor_single"
        )

        assert result["success"], "单条更新失败"

        print_success("单条更新成功")
        print_result("记录ID", result["id"])
        print_result("更新字段", ", ".join(result["updated_fields"]))

        # 验证更新
        updated_record = await user_edit_service.get_by_id(record_id)
        assert updated_record.title == "单条更新的标题", "标题更新失败"
        assert updated_record.user_rating == 5, "评分更新失败"

        print_success("更新验证通过")

    except Exception as e:
        print_error(f"单条更新失败: {e}")
        raise


async def test_field_validation():
    """测试字段验证"""
    print_section("测试 4: 字段验证")

    try:
        print_info("测试不可编辑字段验证...")

        # 尝试编辑不允许的字段
        try:
            updates = {
                "url": "https://hacker.com",  # 不允许编辑
                "ai_model": "hacked"  # 不允许编辑
            }

            await user_edit_service.update_one(
                record_id="test_id",
                updates=updates,
                editor_id="test_editor"
            )

            print_error("字段验证失败 - 应该拒绝不可编辑字段")

        except ValueError as e:
            print_success(f"字段验证通过 - 正确拒绝: {str(e)}")

        # 测试评分范围验证
        print_info("测试评分范围验证...")
        try:
            updates = {"user_rating": 10}  # 超出范围

            await user_edit_service.validate_editable_fields(updates)

            print_error("评分验证失败 - 应该拒绝超出范围的评分")

        except ValueError as e:
            print_success(f"评分验证通过 - 正确拒绝: {str(e)}")

    except Exception as e:
        print_error(f"字段验证测试失败: {e}")
        raise


async def test_query_operations(record_ids: list[str]):
    """测试查询操作"""
    print_section("测试 5: 查询操作")

    try:
        # 获取单条记录
        print_info(f"获取单条记录: {record_ids[0]}")
        record = await user_edit_service.get_by_id(record_ids[0])
        assert record is not None, "记录不存在"
        print_success("获取单条记录成功")

        # 查询失败的记录ID
        print_info("测试查询不存在的记录...")
        not_exist = await user_edit_service.get_by_id("not_exist_id")
        assert not_exist is None, "应该返回None"
        print_success("查询不存在记录验证通过")

    except Exception as e:
        print_error(f"查询操作测试失败: {e}")
        raise


async def cleanup_test_data(record_ids: list[str]):
    """清理测试数据"""
    print_section("清理测试数据")

    try:
        print_info(f"删除{len(record_ids)}条测试记录...")

        for record_id in record_ids:
            success = await user_edit_service.repository.delete(record_id)
            if success:
                print(f"   ✓ 删除记录: {record_id}")
            else:
                print(f"   ✗ 删除失败: {record_id}")

        print_success("测试数据清理完成")

    except Exception as e:
        print_error(f"清理测试数据失败: {e}")


async def run_all_tests():
    """运行所有测试"""
    print_section("用户批量编辑功能集成测试")

    record_ids = []

    try:
        # 准备测试数据
        record_ids = await create_test_records()

        # 测试 1: 批量灵活更新
        await test_batch_update_flexible(record_ids)

        # 测试 2: 批量统一更新
        await test_batch_update_fields(record_ids)

        # 测试 3: 单条更新
        await test_single_update(record_ids[0])

        # 测试 4: 字段验证
        await test_field_validation()

        # 测试 5: 查询操作
        await test_query_operations(record_ids)

        # 测试总结
        print_section("测试完成")
        print_success("所有测试通过！✨")
        print()
        print("测试覆盖:")
        print("  ✅ 批量更新（灵活模式）")
        print("  ✅ 批量更新（统一字段）")
        print("  ✅ 单条更新")
        print("  ✅ 字段验证")
        print("  ✅ 查询操作")
        print()

        return True

    except AssertionError as e:
        print_section("测试失败")
        print_error(f"断言失败: {e}")
        return False

    except Exception as e:
        print_section("测试失败")
        print_error(f"发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理测试数据
        if record_ids:
            await cleanup_test_data(record_ids)


def main():
    """主函数"""
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print()
        print_error("测试被用户中断")
        sys.exit(1)

    except Exception as e:
        print()
        print_error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

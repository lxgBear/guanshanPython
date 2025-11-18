#!/usr/bin/env python3
"""
档案管理 API 快速测试脚本

用途: 测试档案管理的基本功能
日期: 2025-11-17
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.nl_search.mongo_archive_service import mongo_archive_service


async def test_create_archive():
    """测试创建档案"""
    print("\n" + "="*60)
    print("测试 1: 创建档案")
    print("="*60)

    try:
        # 测试数据（使用真实的 news_result_id）
        test_items = [
            {
                "news_result_id": "244879702695698433",  # 真实雪花ID
                "edited_title": "测试档案条目 1",
                "edited_summary": "这是测试摘要",
                "user_rating": 5
            }
        ]

        result = await mongo_archive_service.create_archive(
            user_id=1001,
            archive_name="测试档案 - API功能验证",
            items=test_items,
            description="用于测试档案管理API功能",
            tags=["测试", "API"]
        )

        print(f"✅ 档案创建成功！")
        print(f"   档案ID: {result['archive_id']}")
        print(f"   档案名称: {result['archive_name']}")
        print(f"   条目数量: {result['items_count']}")
        print(f"   创建时间: {result['created_at']}")

        return result['archive_id']

    except Exception as e:
        print(f"❌ 创建档案失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_list_archives(user_id=1001):
    """测试查询档案列表"""
    print("\n" + "="*60)
    print("测试 2: 查询档案列表")
    print("="*60)

    try:
        archives = await mongo_archive_service.list_archives(
            user_id=user_id,
            limit=10,
            offset=0
        )

        print(f"✅ 查询成功！找到 {len(archives)} 个档案")
        for idx, archive in enumerate(archives, 1):
            print(f"\n   档案 {idx}:")
            print(f"     ID: {archive['archive_id']}")
            print(f"     名称: {archive['archive_name']}")
            print(f"     条目数: {archive['items_count']}")
            print(f"     标签: {archive['tags']}")

        return archives

    except Exception as e:
        print(f"❌ 查询档案列表失败: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_get_archive(archive_id, user_id=1001):
    """测试获取档案详情"""
    print("\n" + "="*60)
    print("测试 3: 获取档案详情")
    print("="*60)

    try:
        archive = await mongo_archive_service.get_archive(
            archive_id=archive_id,
            user_id=user_id
        )

        if archive:
            print(f"✅ 获取成功！")
            print(f"   档案名称: {archive['archive_name']}")
            print(f"   描述: {archive['description']}")
            print(f"   标签: {archive['tags']}")
            print(f"   条目数: {archive['items_count']}")
            print(f"\n   条目列表:")
            for idx, item in enumerate(archive['items'], 1):
                print(f"     {idx}. {item['title']}")
                print(f"        评分: {item.get('user_rating', 'N/A')}")
        else:
            print(f"⚠️ 档案不存在")

        return archive

    except Exception as e:
        print(f"❌ 获取档案详情失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_update_archive(archive_id, user_id=1001):
    """测试更新档案"""
    print("\n" + "="*60)
    print("测试 4: 更新档案")
    print("="*60)

    try:
        success = await mongo_archive_service.update_archive(
            archive_id=archive_id,
            user_id=user_id,
            archive_name="测试档案 - 已更新",
            description="更新后的描述",
            tags=["测试", "API", "已更新"]
        )

        if success:
            print(f"✅ 更新成功！")
        else:
            print(f"❌ 更新失败")

        return success

    except Exception as e:
        print(f"❌ 更新档案失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_delete_archive(archive_id, user_id=1001):
    """测试删除档案"""
    print("\n" + "="*60)
    print("测试 5: 删除档案")
    print("="*60)

    try:
        success = await mongo_archive_service.delete_archive(
            archive_id=archive_id,
            user_id=user_id
        )

        if success:
            print(f"✅ 删除成功！")
        else:
            print(f"❌ 删除失败")

        return success

    except Exception as e:
        print(f"❌ 删除档案失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("="*60)
    print("档案管理系统 - API 功能测试")
    print("="*60)

    test_user_id = 1001

    # 测试 1: 创建档案
    archive_id = await test_create_archive()
    if not archive_id:
        print("\n❌ 测试中断：创建档案失败")
        return 1

    # 测试 2: 查询档案列表
    await test_list_archives(test_user_id)

    # 测试 3: 获取档案详情
    await test_get_archive(archive_id, test_user_id)

    # 测试 4: 更新档案
    await test_update_archive(archive_id, test_user_id)

    # 测试 5: 删除档案
    await test_delete_archive(archive_id, test_user_id)

    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

#!/usr/bin/env python3
"""
档案管理 API 简化测试（不需要真实新闻数据）

测试档案的基本 CRUD 操作
"""
import asyncio
import sys
from pathlib import Path
import uuid
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.mongo_nl_user_archive_repository import MongoNLUserArchiveRepository


async def main():
    """主函数 - 直接测试 Repository 层"""
    print("="*60)
    print("档案管理系统 - 简化功能测试")
    print("="*60)

    repo = MongoNLUserArchiveRepository()

    # 准备测试数据（模拟快照）
    mock_snapshot = {
        "original_title": "测试新闻标题",
        "original_content": "这是测试新闻内容",
        "category": {"大类": "科技", "类别": "AI", "地域": "全球"},
        "published_at": datetime.utcnow().isoformat(),
        "source": "test.com",
        "media_urls": []
    }

    test_items = [
        {
            "id": str(uuid.uuid4()),
            "news_result_id": "999999999999999",  # 模拟ID
            "edited_title": "编辑后的标题",
            "edited_summary": "编辑后的摘要",
            "user_notes": "我的备注",
            "user_rating": 5,
            "snapshot_data": mock_snapshot,
            "display_order": 0,
            "created_at": datetime.utcnow()
        }
    ]

    # 测试 1: 创建档案
    print("\n📝 测试 1: 创建档案")
    print("-" * 60)
    archive_id = await repo.create(
        user_id=1001,
        archive_name="测试档案 - 简化版本",
        items=test_items,
        description="用于测试的简化档案",
        tags=["测试", "简化"]
    )

    if archive_id:
        print(f"✅ 创建成功！档案ID: {archive_id}")
    else:
        print("❌ 创建失败")
        return 1

    # 测试 2: 查询档案列表
    print("\n📋 测试 2: 查询档案列表")
    print("-" * 60)
    archives = await repo.get_by_user(user_id=1001, limit=5)
    print(f"✅ 找到 {len(archives)} 个档案")
    for idx, archive in enumerate(archives, 1):
        print(f"  {idx}. {archive['archive_name']} (条目数: {archive['items_count']})")

    # 测试 3: 获取档案详情
    print("\n🔍 测试 3: 获取档案详情")
    print("-" * 60)
    archive = await repo.get_by_id(archive_id)
    if archive:
        print(f"✅ 档案名称: {archive['archive_name']}")
        print(f"   描述: {archive['description']}")
        print(f"   标签: {archive['tags']}")
        print(f"   条目数: {archive['items_count']}")
        print(f"   条目列表:")
        for item in archive['items']:
            print(f"     - {item['edited_title']} (评分: {item['user_rating']})")
    else:
        print("❌ 获取失败")

    # 测试 4: 更新档案
    print("\n✏️  测试 4: 更新档案")
    print("-" * 60)
    success = await repo.update(
        archive_id=archive_id,
        archive_name="测试档案 - 已更新",
        description="更新后的描述",
        tags=["测试", "已更新"]
    )
    print(f"{'✅ 更新成功' if success else '❌ 更新失败'}")

    # 测试 5: 删除档案
    print("\n🗑️  测试 5: 删除档案")
    print("-" * 60)
    success = await repo.delete(archive_id)
    print(f"{'✅ 删除成功' if success else '❌ 删除失败'}")

    # 验证删除
    archive = await repo.get_by_id(archive_id)
    if archive is None:
        print("✅ 验证：档案已不存在")
    else:
        print("⚠️  警告：档案仍然存在")

    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

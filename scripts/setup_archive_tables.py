#!/usr/bin/env python3
"""
档案管理表创建和验证脚本

用途: 创建 nl_user_archives 和 nl_user_selections 表及触发器
作者: Archive System Setup
日期: 2025-11-17
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.infrastructure.database.connection import get_mariadb_session


async def create_tables():
    """创建档案管理表和触发器"""
    print("🚀 开始创建档案管理数据库表...")

    session = await get_mariadb_session()

    try:
        # 1. 创建 nl_user_archives 表
        print("\n📋 创建 nl_user_archives 表...")
        create_archives_table = text("""
            CREATE TABLE IF NOT EXISTS nl_user_archives (
                id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '档案唯一ID',
                user_id BIGINT NOT NULL COMMENT '用户ID（关联用户系统）',
                archive_name VARCHAR(255) NOT NULL COMMENT '档案名称（用户命名）',
                description TEXT NULL COMMENT '档案描述（可选）',
                tags JSON NULL COMMENT '档案标签（可选，JSON数组）',
                search_log_id BIGINT NULL COMMENT '关联的搜索记录ID（可选，nl_search_logs表）',
                items_count INT DEFAULT 0 COMMENT '档案中的条目数量',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',

                INDEX idx_user_id (user_id) COMMENT '用户查询索引',
                INDEX idx_search_log_id (search_log_id) COMMENT '搜索记录关联索引',
                INDEX idx_created_at (created_at DESC) COMMENT '创建时间索引（降序）',

                FOREIGN KEY (search_log_id) REFERENCES nl_search_logs(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='NL Search 用户档案主表'
        """)

        await session.execute(create_archives_table)
        await session.commit()
        print("✅ nl_user_archives 表创建成功")

        # 2. 创建 nl_user_selections 表
        print("\n📋 创建 nl_user_selections 表...")
        create_selections_table = text("""
            CREATE TABLE IF NOT EXISTS nl_user_selections (
                id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '条目唯一ID',
                archive_id BIGINT NOT NULL COMMENT '所属档案ID',
                user_id BIGINT NOT NULL COMMENT '用户ID（冗余存储，便于查询）',
                news_result_id VARCHAR(255) NOT NULL COMMENT '新闻结果ID（MongoDB中的ObjectId）',

                edited_title VARCHAR(500) NULL COMMENT '用户编辑后的标题（可选）',
                edited_summary TEXT NULL COMMENT '用户编辑后的摘要（可选）',
                user_notes TEXT NULL COMMENT '用户备注（可选）',
                user_rating INT NULL COMMENT '用户评分（1-5，可选）',

                snapshot_data JSON NOT NULL COMMENT '原始新闻数据快照（完整JSON）',
                display_order INT DEFAULT 0 COMMENT '档案内显示顺序（用户可调整）',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '添加到档案的时间',

                INDEX idx_archive_id (archive_id) COMMENT '档案查询索引',
                INDEX idx_user_id (user_id) COMMENT '用户查询索引',
                INDEX idx_news_result_id (news_result_id) COMMENT '新闻结果关联索引',
                INDEX idx_display_order (archive_id, display_order) COMMENT '显示顺序索引',

                FOREIGN KEY (archive_id) REFERENCES nl_user_archives(id) ON DELETE CASCADE,
                UNIQUE KEY uk_archive_news (archive_id, news_result_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='NL Search 用户档案条目表'
        """)

        await session.execute(create_selections_table)
        await session.commit()
        print("✅ nl_user_selections 表创建成功")

        # 3. 创建触发器 - INSERT
        print("\n📋 创建触发器: trg_archive_items_insert...")
        try:
            # 先删除已存在的触发器
            drop_trigger_insert = text("DROP TRIGGER IF EXISTS trg_archive_items_insert")
            await session.execute(drop_trigger_insert)
            await session.commit()

            create_trigger_insert = text("""
                CREATE TRIGGER trg_archive_items_insert
                AFTER INSERT ON nl_user_selections
                FOR EACH ROW
                BEGIN
                    UPDATE nl_user_archives
                    SET items_count = items_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.archive_id;
                END
            """)

            await session.execute(create_trigger_insert)
            await session.commit()
            print("✅ INSERT 触发器创建成功")
        except Exception as e:
            print(f"⚠️ INSERT 触发器创建失败（可能已存在）: {e}")

        # 4. 创建触发器 - DELETE
        print("\n📋 创建触发器: trg_archive_items_delete...")
        try:
            # 先删除已存在的触发器
            drop_trigger_delete = text("DROP TRIGGER IF EXISTS trg_archive_items_delete")
            await session.execute(drop_trigger_delete)
            await session.commit()

            create_trigger_delete = text("""
                CREATE TRIGGER trg_archive_items_delete
                AFTER DELETE ON nl_user_selections
                FOR EACH ROW
                BEGIN
                    UPDATE nl_user_archives
                    SET items_count = items_count - 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = OLD.archive_id;
                END
            """)

            await session.execute(create_trigger_delete)
            await session.commit()
            print("✅ DELETE 触发器创建成功")
        except Exception as e:
            print(f"⚠️ DELETE 触发器创建失败（可能已存在）: {e}")

        print("\n" + "="*60)
        print("✅ 数据库表创建完成！")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 创建失败: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()


async def verify_tables():
    """验证表结构和触发器"""
    print("\n🔍 验证表结构...")

    session = await get_mariadb_session()

    try:
        # 验证 nl_user_archives 表
        print("\n📊 nl_user_archives 表结构:")
        result = await session.execute(text("DESCRIBE nl_user_archives"))
        rows = result.fetchall()
        for row in rows:
            print(f"  - {row[0]}: {row[1]} {row[2]} {row[3]}")

        # 验证 nl_user_selections 表
        print("\n📊 nl_user_selections 表结构:")
        result = await session.execute(text("DESCRIBE nl_user_selections"))
        rows = result.fetchall()
        for row in rows:
            print(f"  - {row[0]}: {row[1]} {row[2]} {row[3]}")

        # 验证索引
        print("\n🔑 nl_user_archives 索引:")
        result = await session.execute(text("SHOW INDEX FROM nl_user_archives"))
        rows = result.fetchall()
        for row in rows:
            print(f"  - {row[2]}: {row[4]} ({row[10]})")

        print("\n🔑 nl_user_selections 索引:")
        result = await session.execute(text("SHOW INDEX FROM nl_user_selections"))
        rows = result.fetchall()
        for row in rows:
            print(f"  - {row[2]}: {row[4]} ({row[10]})")

        # 验证触发器
        print("\n⚡ 触发器:")
        result = await session.execute(text("SHOW TRIGGERS LIKE 'nl_user_%'"))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"  - {row[0]}: {row[1]} on {row[2]}")
        else:
            print("  ⚠️ 未找到触发器")

        print("\n" + "="*60)
        print("✅ 表结构验证完成！")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        raise
    finally:
        await session.close()


async def main():
    """主函数"""
    print("="*60)
    print("档案管理系统 - 数据库表创建脚本")
    print("="*60)

    try:
        # 创建表
        await create_tables()

        # 验证表结构
        await verify_tables()

        print("\n✅ 所有操作完成！档案管理系统数据库已就绪。")
        return 0

    except Exception as e:
        print(f"\n❌ 脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

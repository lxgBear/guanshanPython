#!/usr/bin/env python3
"""
创建 NL Search 数据表

使用方式:
    python scripts/create_nl_search_tables.py

说明:
- 读取 SQL 脚本并执行
- 自动跳过注释和查询语句
- 提供执行结果反馈
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.connection import get_mariadb_session
from src.utils.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)


async def create_nl_search_tables():
    """创建 NL Search 相关表"""
    logger.info("开始创建 NL Search 数据表...")

    try:
        # 获取数据库会话
        session = await get_mariadb_session()

        # 读取 SQL 脚本
        sql_file = Path(__file__).parent / "create_nl_search_tables.sql"
        logger.info(f"读取 SQL 脚本: {sql_file}")

        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 分割并执行 SQL 语句
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]

        success_count = 0
        skip_count = 0

        for i, statement in enumerate(statements, 1):
            # 跳过注释行和查询语句（SELECT, SHOW, DESC）
            if (statement.startswith('--') or
                statement.upper().startswith('SELECT') or
                statement.upper().startswith('SHOW') or
                statement.upper().startswith('DESC')):
                skip_count += 1
                continue

            try:
                await session.execute(text(statement))
                await session.commit()
                success_count += 1

                # 提取语句类型
                stmt_type = statement.split()[0].upper()
                logger.info(f"✅ [{i}/{len(statements)}] {stmt_type} 执行成功")

            except Exception as e:
                # 如果表已存在，不算错误
                if "already exists" in str(e).lower():
                    logger.warning(f"⚠️  [{i}/{len(statements)}] 表已存在，跳过")
                    skip_count += 1
                else:
                    logger.error(f"❌ [{i}/{len(statements)}] 执行失败: {e}")
                    logger.error(f"   SQL: {statement[:100]}...")
                    raise

        # 验证表是否创建成功
        result = await session.execute(
            text("SHOW TABLES LIKE 'nl_search_logs'")
        )
        table_exists = result.fetchone() is not None

        if table_exists:
            logger.info("\n" + "="*60)
            logger.info("🎉 NL Search 数据表创建完成！")
            logger.info("="*60)
            logger.info(f"✅ 成功执行: {success_count} 条语句")
            logger.info(f"⏭️  跳过: {skip_count} 条语句")
            logger.info(f"📊 表名: nl_search_logs")
            logger.info("="*60)

            # 显示表结构
            result = await session.execute(text("DESC nl_search_logs"))
            rows = result.fetchall()

            logger.info("\n📋 表结构:")
            logger.info("-" * 80)
            logger.info(f"{'字段':<20} {'类型':<20} {'NULL':<8} {'键':<8} {'默认值':<15} {'额外'}")
            logger.info("-" * 80)
            for row in rows:
                logger.info(f"{row[0]:<20} {row[1]:<20} {row[2]:<8} {row[3]:<8} {str(row[4] or ''):<15} {row[5] or ''}")
            logger.info("-" * 80)

        else:
            logger.error("❌ 表创建失败，请检查 SQL 脚本")
            return False

        await session.close()
        return True

    except Exception as e:
        logger.error(f"❌ 创建数据表失败: {e}")
        return False


async def main():
    """主函数"""
    try:
        success = await create_nl_search_tables()

        if success:
            logger.info("\n✅ 所有操作已完成！可以开始使用 NL Search 功能。")
            sys.exit(0)
        else:
            logger.error("\n❌ 操作未完成，请检查错误信息。")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("\n⚠️  操作被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ 发生未预期的错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

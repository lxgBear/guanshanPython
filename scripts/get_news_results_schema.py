"""获取 news_results 表的字段结构"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database


async def get_news_results_schema():
    """获取 news_results 表的字段结构"""
    try:
        db = await get_mongodb_database()

        # 检查集合是否存在
        collections = await db.list_collection_names()
        if 'news_results' not in collections:
            print("❌ news_results 集合不存在")
            print(f"\n可用的集合: {', '.join(collections)}")
            return

        print("✅ news_results 集合存在")

        # 获取一个文档样例
        news_results = db.news_results
        sample_doc = await news_results.find_one()

        if not sample_doc:
            print("⚠️ news_results 集合为空，无法获取字段结构")
            return

        print(f"\n📊 news_results 表字段结构（基于样例文档）:")
        print("=" * 80)

        # 递归打印字段结构
        def print_fields(obj, indent=0):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    value_type = type(value).__name__
                    if isinstance(value, dict):
                        print("  " * indent + f"- {key}: dict")
                        print_fields(value, indent + 1)
                    elif isinstance(value, list):
                        if value:
                            print("  " * indent + f"- {key}: list[{type(value[0]).__name__}]")
                            if isinstance(value[0], dict):
                                print_fields(value[0], indent + 1)
                        else:
                            print("  " * indent + f"- {key}: list[]")
                    else:
                        # 显示值的示例（如果不是太长）
                        value_str = str(value)
                        if len(value_str) > 50:
                            value_str = value_str[:50] + "..."
                        print("  " * indent + f"- {key}: {value_type} = {value_str}")

        print_fields(sample_doc)

        # 统计总字段数
        total_count = await news_results.count_documents({})
        print("\n" + "=" * 80)
        print(f"📈 统计信息:")
        print(f"  - 总记录数: {total_count}")
        print(f"  - 字段数量: {len(sample_doc)}")

        # 输出所有字段名（用于代码生成）
        print(f"\n📝 所有字段名列表:")
        field_names = list(sample_doc.keys())
        for field in field_names:
            print(f"  - {field}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(get_news_results_schema())

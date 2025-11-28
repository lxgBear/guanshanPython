"""
NL Search 测试数据生成脚本

功能:
- 创建真实的自然语言搜索记录（从 news_results 表获取真实数据）
- 生成完整的搜索日志（包含 LLM 分析和搜索结果）
- 支持不同的查询主题和搜索模式
- 提供数据清理和查询功能

用法:
    python scripts/create_nl_search_test_data.py --create 5            # 创建5条搜索记录
    python scripts/create_nl_search_test_data.py --list 10             # 列出最近10条记录
    python scripts/create_nl_search_test_data.py --stats               # 查看统计信息
    python scripts/create_nl_search_test_data.py --cleanup             # 清理测试数据
    python scripts/create_nl_search_test_data.py --user-id user_123 --create 3  # 指定用户
"""
import asyncio
import argparse
import sys
import os
from datetime import datetime
from typing import List, Dict, Any
import random

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id
from src.utils.logger import get_logger

logger = get_logger(__name__)


# 预定义的搜索主题和查询
SEARCH_TOPICS = [
    {
        "query": "缅甸KK园区最新动态",
        "intent": "news_inquiry",
        "keywords": ["缅甸", "KK园区", "诈骗", "园区"],
        "entities": ["缅甸", "KK园区", "妙瓦底"],
        "time_range": "recent",
        "search_terms": ["缅甸", "KK", "园区", "妙瓦底", "诈骗"]
    },
    {
        "query": "中国留学生人权案件",
        "intent": "human_rights_inquiry",
        "keywords": ["留学生", "人权", "文字狱", "案件"],
        "entities": ["中国", "留学生", "张雅笛"],
        "time_range": "recent",
        "search_terms": ["留学生", "人权", "文字狱", "张雅笛"]
    },
    {
        "query": "东南亚网络诈骗调查",
        "intent": "investigation_report",
        "keywords": ["东南亚", "网络诈骗", "调查", "犯罪"],
        "entities": ["东南亚", "缅甸", "诈骗集团"],
        "time_range": "recent",
        "search_terms": ["东南亚", "诈骗", "网络犯罪", "缅甸"]
    },
    {
        "query": "BBC中文网新闻报道",
        "intent": "media_content",
        "keywords": ["BBC", "中文", "新闻", "报道"],
        "entities": ["BBC", "中文网"],
        "time_range": "any",
        "search_terms": ["BBC", "中文", "新闻"]
    },
    {
        "query": "维基百科地理条目",
        "intent": "encyclopedia_search",
        "keywords": ["维基百科", "地理", "百科全书"],
        "entities": ["维基百科"],
        "time_range": "any",
        "search_terms": ["维基百科", "地理", "百科"]
    }
]


class NLSearchTestDataGenerator:
    """NL Search 测试数据生成器"""

    def __init__(self):
        self.db = None
        self.nl_search_logs_collection = None
        self.news_results_collection = None

    async def initialize(self):
        """初始化数据库连接"""
        self.db = await get_mongodb_database()
        self.nl_search_logs_collection = self.db["nl_search_logs"]
        self.news_results_collection = self.db["news_results"]
        logger.info("数据库连接初始化成功")

    async def create_search_log_with_results(
        self,
        user_id: str,
        topic: Dict[str, Any],
        results_count: int = 5
    ) -> str:
        """
        创建一条搜索记录（包含搜索结果）

        Args:
            user_id: 用户ID
            topic: 搜索主题配置
            results_count: 结果数量

        Returns:
            str: 创建的搜索记录ID
        """
        # 1. 生成搜索日志ID
        log_id = generate_string_id()

        # 2. 从 news_results 中查找匹配的新闻
        search_results = await self._find_matching_news(topic, results_count)

        # 3. 构建 LLM 分析结果
        llm_analysis = {
            "intent": topic["intent"],
            "keywords": topic["keywords"],
            "entities": topic["entities"],
            "time_range": topic["time_range"],
            "confidence": round(random.uniform(0.85, 0.98), 2),
            "refined_query": f"{' '.join(topic['keywords'][:3])}",
            "search_strategy": "keyword_match"
        }

        # 4. 构建搜索配置
        search_config = {
            "max_results": results_count,
            "source": "gpt5_search",
            "mode": "single"
        }

        # 5. 创建搜索日志文档
        document = {
            "_id": log_id,
            "query_text": topic["query"],
            "user_id": user_id,
            "llm_analysis": llm_analysis,
            "search_config": search_config,
            "search_results": search_results,  # 嵌入式存储
            "results_count": len(search_results),
            "total_results": random.randint(len(search_results), len(search_results) + 10),
            "high_score_results": len(search_results),
            "score_threshold": 0.6,
            "status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "metadata": {
                "test": True,  # 标记为测试数据
                "data_source": "news_results",
                "generator": "create_nl_search_test_data.py"
            }
        }

        # 6. 插入数据库
        await self.nl_search_logs_collection.insert_one(document)

        logger.info(
            f"✅ 创建搜索记录: log_id={log_id}, "
            f"query='{topic['query']}', results={len(search_results)}"
        )

        return log_id

    async def _find_matching_news(
        self,
        topic: Dict[str, Any],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        根据主题从 news_results 中查找匹配的新闻

        Args:
            topic: 搜索主题
            limit: 结果数量限制

        Returns:
            List[Dict]: 搜索结果列表
        """
        search_terms = topic["search_terms"]

        # 构建查询条件（使用正则表达式匹配标题或内容）
        query_conditions = []
        for term in search_terms:
            query_conditions.append({"title": {"$regex": term, "$options": "i"}})
            query_conditions.append({"content": {"$regex": term, "$options": "i"}})

        # 查询匹配的新闻
        cursor = self.news_results_collection.find(
            {"$or": query_conditions} if query_conditions else {}
        ).limit(limit)

        news_list = await cursor.to_list(length=limit)

        # 如果匹配的新闻不足，随机补充其他新闻
        if len(news_list) < limit:
            additional_needed = limit - len(news_list)
            existing_ids = [news["_id"] for news in news_list]

            additional_cursor = self.news_results_collection.aggregate([
                {"$match": {"_id": {"$nin": existing_ids}}},
                {"$sample": {"size": additional_needed}}
            ])

            additional_news = await additional_cursor.to_list(length=additional_needed)
            news_list.extend(additional_news)

        # 转换为搜索结果格式
        search_results = []
        for i, news in enumerate(news_list):
            result = {
                "title": news.get("title", "无标题"),
                "url": news.get("url") or news.get("source_url", ""),
                "snippet": news.get("snippet") or news.get("content", "")[:200],
                "mongo_id": str(news["_id"]),  # RAG使用的ID
                "position": i + 1,
                "score": round(random.uniform(0.6, 0.95), 2),
                "source": news.get("source", "unknown"),
                "categories": news.get("categories", []),
                "quality_score": news.get("quality_score", 0.0),
                "relevance_score": round(random.uniform(0.7, 1.0), 2)
            }
            search_results.append(result)

        return search_results

    async def create_multiple(self, count: int, user_id: str):
        """
        创建多条搜索记录

        Args:
            count: 创建数量
            user_id: 用户ID
        """
        logger.info(f"🚀 开始创建 {count} 条搜索记录...")

        created_ids = []

        for i in range(count):
            # 随机选择一个主题
            topic = random.choice(SEARCH_TOPICS)

            # 创建搜索记录
            log_id = await self.create_search_log_with_results(
                user_id=user_id,
                topic=topic,
                results_count=random.randint(3, 8)
            )

            created_ids.append(log_id)

            # 添加延迟，避免时间戳完全相同
            await asyncio.sleep(0.1)

        logger.info(f"✅ 成功创建 {len(created_ids)} 条搜索记录")
        return created_ids

    async def list_recent(self, limit: int = 10):
        """
        列出最近的搜索记录

        Args:
            limit: 返回数量
        """
        cursor = self.nl_search_logs_collection.find(
            {"metadata.test": True}
        ).sort("created_at", -1).limit(limit)

        logs = await cursor.to_list(length=limit)

        if not logs:
            logger.info("📭 没有找到搜索记录")
            return

        logger.info(f"\n📋 最近 {len(logs)} 条搜索记录:\n")

        for i, log in enumerate(logs, 1):
            print(f"{i}. Log ID: {log['_id']}")
            print(f"   查询: {log['query_text']}")
            print(f"   用户: {log.get('user_id', 'N/A')}")
            print(f"   状态: {log['status']}")
            print(f"   结果数: {log['results_count']}")
            print(f"   创建时间: {log['created_at']}")

            # 显示搜索结果预览
            if log.get("search_results"):
                print(f"   搜索结果预览:")
                for j, result in enumerate(log["search_results"][:3], 1):
                    print(f"      {j}. {result['title'][:50]}... (score: {result['score']})")

            print()

    async def show_stats(self):
        """显示统计信息"""
        total = await self.nl_search_logs_collection.count_documents({})
        test_count = await self.nl_search_logs_collection.count_documents({"metadata.test": True})

        # 统计不同状态的记录
        completed = await self.nl_search_logs_collection.count_documents({"status": "completed"})
        pending = await self.nl_search_logs_collection.count_documents({"status": "pending"})
        failed = await self.nl_search_logs_collection.count_documents({"status": "failed"})

        # 统计用户分布
        user_stats = await self.nl_search_logs_collection.aggregate([
            {"$match": {"metadata.test": True}},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]).to_list(length=100)

        logger.info(f"\n📊 NL Search 搜索记录统计:\n")
        print(f"总记录数: {total}")
        print(f"测试数据: {test_count}")
        print(f"\n状态分布:")
        print(f"  ✅ Completed: {completed}")
        print(f"  ⏳ Pending: {pending}")
        print(f"  ❌ Failed: {failed}")

        if user_stats:
            print(f"\n用户分布:")
            for stat in user_stats[:5]:
                print(f"  {stat['_id']}: {stat['count']} 条记录")

    async def cleanup(self):
        """清理测试数据"""
        logger.info("🧹 开始清理测试数据...")

        result = await self.nl_search_logs_collection.delete_many({"metadata.test": True})

        logger.info(f"✅ 清理完成，删除了 {result.deleted_count} 条测试记录")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="NL Search 测试数据生成工具")

    parser.add_argument("--create", type=int, metavar="N", help="创建 N 条搜索记录")
    parser.add_argument("--list", type=int, metavar="N", help="列出最近 N 条记录")
    parser.add_argument("--stats", action="store_true", help="查看统计信息")
    parser.add_argument("--cleanup", action="store_true", help="清理测试数据")
    parser.add_argument("--user-id", type=str, default="user_1001", help="用户ID (默认: user_1001)")

    args = parser.parse_args()

    # 如果没有提供任何参数，显示帮助信息
    if not any([args.create, args.list, args.stats, args.cleanup]):
        parser.print_help()
        sys.exit(0)

    # 初始化生成器
    generator = NLSearchTestDataGenerator()
    await generator.initialize()

    try:
        # 执行操作
        if args.cleanup:
            await generator.cleanup()

        if args.create:
            await generator.create_multiple(args.create, args.user_id)

        if args.list:
            await generator.list_recent(args.list)

        if args.stats:
            await generator.show_stats()

    except Exception as e:
        logger.error(f"❌ 操作失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

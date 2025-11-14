#!/usr/bin/env python3
"""
数据库连接和Firecrawl API测试脚本

功能：
1. 启动项目并连接MongoDB数据库
2. 获取两条Firecrawl API返回的原始数据

运行方式：
    python scripts/test_db_and_firecrawl.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseAndFirecrawlTester:
    """数据库连接和Firecrawl API测试器"""

    def __init__(self):
        self.mongo_client = None
        self.db = None
        self.firecrawl_adapter = None

    async def connect_database(self) -> bool:
        """连接MongoDB数据库"""
        print("\n" + "="*70)
        print("📊 步骤1: 连接MongoDB数据库")
        print("="*70)

        try:
            print(f"🔌 正在连接MongoDB...")
            print(f"   URL: {settings.MONGODB_URL.split('@')[1] if '@' in settings.MONGODB_URL else 'localhost'}")
            print(f"   数据库: {settings.MONGODB_DB_NAME}")

            # 创建MongoDB连接
            self.mongo_client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
                minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
                serverSelectionTimeoutMS=5000
            )

            self.db = self.mongo_client[settings.MONGODB_DB_NAME]

            # 测试连接
            await asyncio.wait_for(
                self.mongo_client.admin.command('ping'),
                timeout=5.0
            )

            # 获取数据库统计信息
            stats = await self.db.command("dbStats")
            collections = await self.db.list_collection_names()

            print(f"\n✅ MongoDB连接成功！")
            print(f"\n📊 数据库信息:")
            print(f"   - 数据库名称: {stats['db']}")
            print(f"   - 集合数量: {stats['collections']}")
            print(f"   - 数据大小: {stats['dataSize'] / 1024 / 1024:.2f} MB")
            print(f"   - 索引数量: {stats['indexes']}")
            print(f"\n📁 集合列表:")
            for coll in collections[:10]:  # 只显示前10个
                count = await self.db[coll].count_documents({})
                print(f"   - {coll}: {count} 条记录")

            return True

        except asyncio.TimeoutError:
            print(f"\n❌ MongoDB连接超时")
            print(f"   请检查MongoDB服务是否正在运行")
            return False
        except Exception as e:
            print(f"\n❌ MongoDB连接失败: {e}")
            return False

    async def init_firecrawl(self) -> bool:
        """初始化Firecrawl适配器"""
        print("\n" + "="*70)
        print("🔥 步骤2: 初始化Firecrawl适配器")
        print("="*70)

        try:
            print(f"🔑 正在初始化Firecrawl...")
            print(f"   API Key: {settings.FIRECRAWL_API_KEY[:10]}...{settings.FIRECRAWL_API_KEY[-10:]}")
            print(f"   Base URL: {settings.FIRECRAWL_BASE_URL}")
            print(f"   Timeout: {settings.FIRECRAWL_TIMEOUT}s")

            self.firecrawl_adapter = FirecrawlAdapter(api_key=settings.FIRECRAWL_API_KEY)

            print(f"\n✅ Firecrawl适配器初始化成功！")
            return True

        except ValueError as e:
            print(f"\n❌ Firecrawl初始化失败: {e}")
            print(f"   请检查.env文件中的FIRECRAWL_API_KEY配置")
            return False
        except Exception as e:
            print(f"\n❌ Firecrawl初始化失败: {e}")
            return False

    async def test_firecrawl_scrape(self) -> dict:
        """测试Firecrawl scrape方法（爬取单个页面）"""
        print("\n" + "="*70)
        print("🌐 步骤3: 测试Firecrawl Scrape API（爬取单个页面）")
        print("="*70)

        test_url = "https://example.com"

        try:
            print(f"📍 目标URL: {test_url}")
            print(f"⏱️  开始时间: {datetime.now().strftime('%H:%M:%S')}")
            print(f"🔄 正在爬取...")

            start_time = asyncio.get_event_loop().time()

            # 调用scrape方法
            result = await self.firecrawl_adapter.scrape(test_url)

            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            print(f"\n✅ 爬取成功！")
            print(f"⏱️  耗时: {duration:.2f}秒")

            # 构造原始响应数据
            raw_response = {
                "success": True,
                "method": "scrape",
                "url": test_url,
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": round(duration, 2),
                "data": {
                    "url": result.url,
                    "content": result.content[:500] + "..." if len(result.content) > 500 else result.content,
                    "content_length": len(result.content),
                    "markdown": result.markdown[:500] + "..." if result.markdown and len(result.markdown) > 500 else result.markdown,
                    "markdown_length": len(result.markdown) if result.markdown else 0,
                    "html_length": len(result.html) if result.html else 0,
                    "metadata": result.metadata,
                    "has_screenshot": result.screenshot is not None
                }
            }

            print(f"\n📄 响应数据摘要:")
            print(f"   - URL: {result.url}")
            print(f"   - 内容长度: {len(result.content)} 字符")
            print(f"   - Markdown长度: {len(result.markdown) if result.markdown else 0} 字符")
            print(f"   - HTML长度: {len(result.html) if result.html else 0} 字符")
            print(f"   - 元数据: {len(result.metadata)} 项")

            return raw_response

        except Exception as e:
            print(f"\n❌ Scrape API调用失败: {e}")
            return {
                "success": False,
                "method": "scrape",
                "url": test_url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def test_firecrawl_scrape_2(self) -> dict:
        """测试Firecrawl scrape方法（爬取第二个页面）"""
        print("\n" + "="*70)
        print("🌐 步骤4: 测试Firecrawl Scrape API（爬取第二个页面）")
        print("="*70)

        test_url = "https://www.iana.org/domains/reserved"

        try:
            print(f"📍 目标URL: {test_url}")
            print(f"⏱️  开始时间: {datetime.now().strftime('%H:%M:%S')}")
            print(f"🔄 正在爬取...")

            start_time = asyncio.get_event_loop().time()

            # 调用scrape方法
            result = await self.firecrawl_adapter.scrape(test_url)

            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            print(f"\n✅ 爬取成功！")
            print(f"⏱️  耗时: {duration:.2f}秒")

            # 构造原始响应数据
            raw_response = {
                "success": True,
                "method": "scrape",
                "url": test_url,
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": round(duration, 2),
                "data": {
                    "url": result.url,
                    "content": result.content[:500] + "..." if len(result.content) > 500 else result.content,
                    "content_length": len(result.content),
                    "markdown": result.markdown[:500] + "..." if result.markdown and len(result.markdown) > 500 else result.markdown,
                    "markdown_length": len(result.markdown) if result.markdown else 0,
                    "html_length": len(result.html) if result.html else 0,
                    "metadata": result.metadata,
                    "has_screenshot": result.screenshot is not None
                }
            }

            print(f"\n📄 响应数据摘要:")
            print(f"   - URL: {result.url}")
            print(f"   - 内容长度: {len(result.content)} 字符")
            print(f"   - Markdown长度: {len(result.markdown) if result.markdown else 0} 字符")
            print(f"   - HTML长度: {len(result.html) if result.html else 0} 字符")
            print(f"   - 元数据: {len(result.metadata)} 项")

            return raw_response

        except Exception as e:
            print(f"\n❌ Scrape API调用失败: {e}")
            return {
                "success": False,
                "method": "scrape",
                "url": test_url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def display_raw_response(self, response: dict, title: str):
        """显示原始API响应"""
        print("\n" + "="*70)
        print(f"📦 {title}")
        print("="*70)
        print("\n```json")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        print("```\n")

    async def run(self):
        """运行完整测试流程"""
        print("\n" + "="*70)
        print("🚀 启动数据库连接和Firecrawl API测试")
        print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        try:
            # 步骤1: 连接数据库
            db_connected = await self.connect_database()

            if not db_connected:
                print("\n⚠️ 数据库连接失败，但继续测试Firecrawl API")

            # 步骤2: 初始化Firecrawl
            firecrawl_ready = await self.init_firecrawl()

            if not firecrawl_ready:
                print("\n❌ Firecrawl初始化失败，测试终止")
                return

            # 步骤3: 测试Scrape API (第1次)
            scrape_response_1 = await self.test_firecrawl_scrape()

            # 步骤4: 测试Scrape API (第2次)
            scrape_response_2 = await self.test_firecrawl_scrape_2()

            # 显示原始响应
            print("\n" + "="*70)
            print("📊 原始API响应数据")
            print("="*70)

            self.display_raw_response(scrape_response_1, "原始响应 #1: Scrape API (example.com)")
            self.display_raw_response(scrape_response_2, "原始响应 #2: Scrape API (iana.org/domains/reserved)")

            # 测试总结
            print("\n" + "="*70)
            print("✅ 测试完成总结")
            print("="*70)

            print(f"\n📊 测试结果:")
            print(f"   ✅ 数据库连接: {'成功' if db_connected else '失败'}")
            print(f"   ✅ Firecrawl初始化: {'成功' if firecrawl_ready else '失败'}")
            print(f"   ✅ Scrape API #1: {'成功' if scrape_response_1.get('success') else '失败'}")
            print(f"   ✅ Scrape API #2: {'成功' if scrape_response_2.get('success') else '失败'}")

            if db_connected:
                print(f"\n💡 数据库信息:")
                print(f"   - 连接URL: {settings.MONGODB_URL.split('@')[1] if '@' in settings.MONGODB_URL else 'localhost'}")
                print(f"   - 数据库名: {settings.MONGODB_DB_NAME}")

            print(f"\n💡 Firecrawl API信息:")
            print(f"   - API Key: 已配置")
            print(f"   - Scrape #1: {'✅ 正常' if scrape_response_1.get('success') else '❌ 失败'}")
            print(f"   - Scrape #2: {'✅ 正常' if scrape_response_2.get('success') else '❌ 失败'}")

            print(f"\n🎉 所有测试流程已完成！")

        except Exception as e:
            print(f"\n❌ 测试过程中发生错误: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        print("\n" + "="*70)
        print("🧹 清理资源")
        print("="*70)

        if self.mongo_client:
            self.mongo_client.close()
            print("✅ MongoDB连接已关闭")

        print("✅ 资源清理完成")


async def main():
    """主函数"""
    tester = DatabaseAndFirecrawlTester()
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())

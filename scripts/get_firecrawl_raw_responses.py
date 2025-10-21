#!/usr/bin/env python3
"""
获取Firecrawl API原始响应数据

功能：
1. 调用Firecrawl API获取两条原始响应
2. 保存原始JSON响应到文件
3. 显示响应数据

运行方式：
    python scripts/get_firecrawl_raw_responses.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FirecrawlRawResponseFetcher:
    """Firecrawl原始响应获取器"""

    def __init__(self):
        self.firecrawl_adapter = None
        self.responses = []

    async def init_firecrawl(self) -> bool:
        """初始化Firecrawl适配器"""
        try:
            print("\n" + "="*70)
            print("🔥 初始化Firecrawl适配器")
            print("="*70)

            self.firecrawl_adapter = FirecrawlAdapter(api_key=settings.FIRECRAWL_API_KEY)
            print(f"✅ Firecrawl适配器初始化成功")
            return True
        except Exception as e:
            print(f"❌ Firecrawl初始化失败: {e}")
            return False

    async def fetch_response_1(self) -> dict:
        """获取第一条原始响应 - Scrape API"""
        print("\n" + "="*70)
        print("📥 获取第1条原始响应: Scrape API")
        print("="*70)

        test_url = "https://firecrawl.dev"

        try:
            print(f"🌐 目标URL: {test_url}")
            print(f"⏱️  开始时间: {datetime.now().strftime('%H:%M:%S')}")

            start_time = asyncio.get_event_loop().time()

            # 调用scrape方法
            result = await self.firecrawl_adapter.scrape(test_url)

            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            # 构造完整的原始响应（包含所有字段）
            raw_response = {
                "success": True,
                "request": {
                    "method": "scrape",
                    "url": test_url,
                    "timestamp": datetime.now().isoformat(),
                    "api_base": settings.FIRECRAWL_BASE_URL
                },
                "response": {
                    "url": result.url,
                    "content": result.content,
                    "markdown": result.markdown,
                    "html": result.html,
                    "metadata": result.metadata,
                    "screenshot": result.screenshot
                },
                "performance": {
                    "duration_seconds": round(duration, 2),
                    "content_length": len(result.content),
                    "markdown_length": len(result.markdown) if result.markdown else 0,
                    "html_length": len(result.html) if result.html else 0
                }
            }

            print(f"✅ 获取成功 (耗时: {duration:.2f}秒)")
            print(f"   - 内容长度: {len(result.content)} 字符")
            print(f"   - 元数据项: {len(result.metadata)} 项")

            return raw_response

        except Exception as e:
            print(f"❌ 获取失败: {e}")
            return {
                "success": False,
                "request": {
                    "method": "scrape",
                    "url": test_url,
                    "timestamp": datetime.now().isoformat()
                },
                "error": str(e)
            }

    async def fetch_response_2(self) -> dict:
        """获取第二条原始响应 - Scrape API（不同URL）"""
        print("\n" + "="*70)
        print("📥 获取第2条原始响应: Scrape API")
        print("="*70)

        test_url = "https://docs.firecrawl.dev/introduction"

        try:
            print(f"🌐 目标URL: {test_url}")
            print(f"⏱️  开始时间: {datetime.now().strftime('%H:%M:%S')}")

            start_time = asyncio.get_event_loop().time()

            # 调用scrape方法
            result = await self.firecrawl_adapter.scrape(test_url)

            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            # 构造完整的原始响应
            raw_response = {
                "success": True,
                "request": {
                    "method": "scrape",
                    "url": test_url,
                    "timestamp": datetime.now().isoformat(),
                    "api_base": settings.FIRECRAWL_BASE_URL
                },
                "response": {
                    "url": result.url,
                    "content": result.content,
                    "markdown": result.markdown,
                    "html": result.html,
                    "metadata": result.metadata,
                    "screenshot": result.screenshot
                },
                "performance": {
                    "duration_seconds": round(duration, 2),
                    "content_length": len(result.content),
                    "markdown_length": len(result.markdown) if result.markdown else 0,
                    "html_length": len(result.html) if result.html else 0
                }
            }

            print(f"✅ 获取成功 (耗时: {duration:.2f}秒)")
            print(f"   - 内容长度: {len(result.content)} 字符")
            print(f"   - 元数据项: {len(result.metadata)} 项")

            return raw_response

        except Exception as e:
            print(f"❌ 获取失败: {e}")
            return {
                "success": False,
                "request": {
                    "method": "scrape",
                    "url": test_url,
                    "timestamp": datetime.now().isoformat()
                },
                "error": str(e)
            }

    def save_responses(self, responses: list):
        """保存原始响应到JSON文件"""
        print("\n" + "="*70)
        print("💾 保存原始响应到文件")
        print("="*70)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for idx, response in enumerate(responses, 1):
            filename = f"firecrawl_raw_response_{idx}_{timestamp}.json"
            filepath = Path(__file__).parent.parent / filename

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(response, f, ensure_ascii=False, indent=2)

                print(f"✅ 响应 #{idx} 已保存到: {filename}")
                print(f"   文件大小: {filepath.stat().st_size / 1024:.2f} KB")

            except Exception as e:
                print(f"❌ 保存响应 #{idx} 失败: {e}")

    def display_responses(self, responses: list):
        """显示原始响应数据"""
        print("\n" + "="*70)
        print("📊 原始响应数据")
        print("="*70)

        for idx, response in enumerate(responses, 1):
            print(f"\n{'='*70}")
            print(f"原始响应 #{idx}")
            print(f"{'='*70}")

            # 显示请求信息
            if "request" in response:
                req = response["request"]
                print(f"\n📤 请求信息:")
                print(f"   - 方法: {req.get('method', 'N/A')}")
                print(f"   - URL: {req.get('url', 'N/A')}")
                print(f"   - 时间: {req.get('timestamp', 'N/A')}")

            # 显示响应信息
            if response.get("success") and "response" in response:
                resp = response["response"]
                print(f"\n📥 响应信息:")
                print(f"   - URL: {resp.get('url', 'N/A')}")
                print(f"   - 内容长度: {len(resp.get('content', ''))} 字符")
                print(f"   - Markdown长度: {len(resp.get('markdown', '') or '')} 字符")

                print(f"\n📋 元数据:")
                metadata = resp.get('metadata', {})
                for key, value in list(metadata.items())[:10]:  # 只显示前10个
                    print(f"   - {key}: {value}")

                if len(metadata) > 10:
                    print(f"   ... 还有 {len(metadata) - 10} 项元数据")

                print(f"\n⚡ 性能:")
                perf = response.get("performance", {})
                print(f"   - 耗时: {perf.get('duration_seconds', 0)}秒")
                print(f"   - 内容大小: {perf.get('content_length', 0)} 字符")

                # 显示内容预览
                content = resp.get('content', '')
                if content:
                    print(f"\n📄 内容预览 (前500字符):")
                    print(f"   {content[:500]}...")
            else:
                print(f"\n❌ 请求失败:")
                print(f"   错误: {response.get('error', 'Unknown error')}")

    async def run(self):
        """运行完整流程"""
        print("\n" + "="*70)
        print("🚀 Firecrawl原始响应获取程序")
        print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        try:
            # 初始化Firecrawl
            if not await self.init_firecrawl():
                print("\n❌ 初始化失败，程序终止")
                return

            # 获取两条原始响应
            response_1 = await self.fetch_response_1()
            self.responses.append(response_1)

            response_2 = await self.fetch_response_2()
            self.responses.append(response_2)

            # 保存响应到文件
            self.save_responses(self.responses)

            # 显示响应数据
            self.display_responses(self.responses)

            # 总结
            print("\n" + "="*70)
            print("✅ 完成")
            print("="*70)

            success_count = sum(1 for r in self.responses if r.get("success"))
            print(f"\n📊 统计:")
            print(f"   - 总请求: 2")
            print(f"   - 成功: {success_count}")
            print(f"   - 失败: {2 - success_count}")

            if success_count == 2:
                print(f"\n🎉 所有API调用成功！")
                print(f"   原始响应数据已保存到项目根目录")
            else:
                print(f"\n⚠️ 部分API调用失败，请查看详细信息")

        except Exception as e:
            print(f"\n❌ 程序执行出错: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """主函数"""
    fetcher = FirecrawlRawResponseFetcher()
    await fetcher.run()


if __name__ == "__main__":
    asyncio.run(main())

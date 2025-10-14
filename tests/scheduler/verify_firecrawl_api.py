#!/usr/bin/env python
"""
Firecrawl API 验证脚本

快速验证 Firecrawl API Key 是否有效
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def verify_firecrawl_api():
    """验证 Firecrawl API 连接"""

    logger.info("=" * 70)
    logger.info("🔐 验证 Firecrawl API Key")
    logger.info("=" * 70)

    # 显示配置
    logger.info(f"\n📋 当前配置:")
    logger.info(f"   - API Base URL: {settings.FIRECRAWL_BASE_URL}")
    logger.info(f"   - API Key: {settings.FIRECRAWL_API_KEY[:20]}...")
    logger.info(f"   - Timeout: {settings.FIRECRAWL_TIMEOUT}s")

    # 准备请求
    headers = {
        "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }

    # 测试1: 简单的搜索请求（限制1条结果）
    logger.info(f"\n🧪 测试1: 简单搜索请求")
    logger.info(f"   查询: 'Python'")
    logger.info(f"   限制: 1条结果")

    try:
        async with httpx.AsyncClient(proxies=None, trust_env=False) as client:
            response = await client.post(
                f"{settings.FIRECRAWL_BASE_URL}/v2/search",
                headers=headers,
                json={"query": "Python", "limit": 1},
                timeout=60.0  # 增加超时时间
            )

            logger.info(f"📡 响应状态码: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ API 调用成功！")
                logger.info(f"📦 响应数据键: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

                # 显示结果摘要
                if isinstance(data, dict):
                    if 'data' in data:
                        results = data.get('data', [])
                        logger.info(f"📊 返回结果数: {len(results) if isinstance(results, list) else 'N/A (not a list)'}")
                        logger.info(f"📦 Data类型: {type(results)}")

                        # 处理不同的响应格式
                        if isinstance(results, list) and len(results) > 0:
                            first_result = results[0]
                            logger.info(f"\n📄 第一条结果:")
                            logger.info(f"   标题: {first_result.get('title', 'N/A')}")
                            logger.info(f"   URL: {first_result.get('url', 'N/A')}")
                        elif isinstance(results, dict):
                            logger.info(f"\n📄 Data内容 (dict):")
                            for key, value in list(results.items())[:5]:  # 显示前5个键
                                logger.info(f"   {key}: {str(value)[:100]}")

                    if 'creditsUsed' in data:
                        logger.info(f"💰 消耗积分: {data.get('creditsUsed', 'N/A')}")
                    elif 'credits_used' in data:
                        logger.info(f"💰 消耗积分: {data.get('credits_used', 'N/A')}")

                logger.info(f"\n✅ Firecrawl API Key 有效！")
                return True

            elif response.status_code == 401:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                logger.error(f"❌ API Key 无效或已过期")
                logger.error(f"   错误信息: {error_data}")
                return False

            elif response.status_code == 429:
                logger.error(f"❌ API 调用配额已用完")
                logger.error(f"   响应: {response.text[:200]}")
                return False

            else:
                logger.error(f"❌ API 返回错误状态码: {response.status_code}")
                logger.error(f"   响应: {response.text[:200]}")
                return False

    except httpx.TimeoutException:
        logger.error(f"❌ 请求超时（60秒）")
        logger.error(f"   可能原因:")
        logger.error(f"   - Firecrawl API 服务响应慢")
        logger.error(f"   - 网络连接问题")
        logger.error(f"   - API endpoint 可能已更改")
        return False

    except httpx.ConnectError as e:
        logger.error(f"❌ 无法连接到 Firecrawl API")
        logger.error(f"   错误: {e}")
        logger.error(f"   请检查网络连接")
        return False

    except Exception as e:
        logger.error(f"❌ 发生意外错误: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"堆栈:\n{traceback.format_exc()}")
        return False


async def main():
    """主函数"""
    logger.info("\n🚀 开始验证 Firecrawl API\n")

    success = await verify_firecrawl_api()

    logger.info("\n" + "=" * 70)
    if success:
        logger.info("✅ 验证通过: Firecrawl API 可以正常使用")
        logger.info("\n💡 下一步:")
        logger.info("   运行完整测试: python tests/scheduler/test_real_firecrawl_api.py")
    else:
        logger.info("❌ 验证失败: Firecrawl API 无法使用")
        logger.info("\n💡 建议:")
        logger.info("   1. 检查 .env 文件中的 FIRECRAWL_API_KEY 是否正确")
        logger.info("   2. 访问 https://firecrawl.dev 查看API文档和账户状态")
        logger.info("   3. 确认API Key 没有过期且有足够的配额")
        logger.info("   4. 如需使用测试模式，在 .env 中设置 TEST_MODE=true")

    logger.info("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
项目验证脚本
验证基本功能是否正常工作
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.core.domain.entities.document import Document, DocumentStatus, DocumentMetadata
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def validate_config():
    """验证配置"""
    print("\n1. 验证配置...")
    
    try:
        # 检查基本配置
        assert settings.FIRECRAWL_API_KEY
        assert settings.FIRECRAWL_API_KEY != "your-firecrawl-api-key-here"
        print("   ✓ 配置验证通过")
        print(f"   - 应用名称: {settings.APP_NAME}")
        print(f"   - 版本: {settings.VERSION}")
        print(f"   - API密钥已配置")
        return True
    except AssertionError as e:
        print(f"   ✗ 配置验证失败: 缺少必要的配置项")
        return False
    except Exception as e:
        print(f"   ✗ 配置验证失败: {e}")
        return False


async def validate_domain_model():
    """验证领域模型"""
    print("\n2. 验证领域模型...")
    
    try:
        # 创建文档实体
        metadata = DocumentMetadata(title="测试文档")
        doc = Document(
            url="https://example.com",
            content="测试内容",
            metadata=metadata
        )
        
        # 验证基本属性
        assert doc.url == "https://example.com"
        assert doc.status == DocumentStatus.PENDING
        assert doc.is_processable()  # 检查是否可处理
        
        # 测试状态转换
        doc.mark_as_processing()
        assert doc.status == DocumentStatus.PROCESSING
        
        doc.mark_as_completed()
        assert doc.status == DocumentStatus.COMPLETED
        
        print("   ✓ 领域模型验证通过")
        print(f"   - 文档ID: {doc.id}")
        print(f"   - 状态转换正常")
        return True
    except Exception as e:
        print(f"   ✗ 领域模型验证失败: {e}")
        return False


async def validate_firecrawl_adapter():
    """验证Firecrawl适配器"""
    print("\n3. 验证Firecrawl适配器...")
    
    try:
        # 创建适配器实例
        adapter = FirecrawlAdapter()
        print("   ✓ Firecrawl适配器创建成功")
        print(f"   - API密钥已配置")
        print(f"   - 超时设置: {adapter.timeout}秒")
        print(f"   - 最大重试次数: {adapter.max_retries}")
        
        # 注意：实际爬取需要有效的API密钥和网络连接
        print("   ! 跳过实际爬取测试（需要有效API密钥）")
        
        return True
    except ValueError as e:
        if "Firecrawl API密钥未配置" in str(e):
            print(f"   ✗ Firecrawl适配器验证失败: API密钥未配置")
        else:
            print(f"   ✗ Firecrawl适配器验证失败: {e}")
        return False
    except Exception as e:
        print(f"   ✗ Firecrawl适配器验证失败: {e}")
        return False


async def validate_api_health():
    """验证API健康状态"""
    print("\n4. 验证API健康状态...")
    
    try:
        import urllib.request
        import json
        
        # 使用标准库避免httpx proxy问题
        try:
            with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    print("   ✓ API健康检查通过")
                    print(f"   - 状态: {data['status']}")
                    print(f"   - 应用: {data['app']}")
                    print(f"   - 版本: {data['version']}")
                    return True
                else:
                    print(f"   ✗ API健康检查失败: 状态码 {response.status}")
                    return False
        except (urllib.error.URLError, ConnectionRefusedError):
            print("   ! API服务未运行（请先运行 scripts/start_dev.sh）")
            return None
    except Exception as e:
        print(f"   ✗ API健康检查失败: {e}")
        return False


async def main():
    """主验证函数"""
    print("="*50)
    print("关山智能系统 - 功能验证")
    print("="*50)
    
    results = []
    
    # 执行各项验证
    results.append(await validate_config())
    results.append(await validate_domain_model())
    results.append(await validate_firecrawl_adapter())
    results.append(await validate_api_health())
    
    # 汇总结果
    print("\n" + "="*50)
    print("验证结果汇总:")
    print("="*50)
    
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    skipped = sum(1 for r in results if r is None)
    
    print(f"✓ 通过: {passed}")
    print(f"✗ 失败: {failed}")
    print(f"! 跳过: {skipped}")
    
    if failed == 0:
        print("\n🎉 所有验证通过！项目初始化成功！")
        return 0
    else:
        print("\n⚠️ 部分验证失败，请检查配置和依赖。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
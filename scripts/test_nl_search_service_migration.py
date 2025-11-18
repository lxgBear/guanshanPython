#!/usr/bin/env python3
"""
NL Search Service MongoDB 迁移集成测试

测试完整的服务层集成：Repository → Service → API 数据流

测试范围：
1. Service 层创建搜索记录
2. Service 层获取记录详情
3. Service 层列出搜索历史
4. Service 层关键词搜索
5. 验证 MongoDB 数据一致性
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.nl_search.nl_search_service import NLSearchService


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


async def test_service_initialization():
    """测试服务初始化"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 1: Service 初始化{Colors.RESET}")
    print("-" * 60)

    try:
        service = NLSearchService()

        # 验证 repository 是 MongoDB 版本
        repo_class = service.repository.__class__.__name__
        if repo_class == "MongoNLSearchLogRepository":
            print(f"{Colors.GREEN}✅ 初始化成功{Colors.RESET}")
            print(f"   Repository: {repo_class}")
            return service, True
        else:
            print(f"{Colors.RED}❌ Repository 类型错误: {repo_class}{Colors.RESET}")
            return service, False

    except Exception as e:
        print(f"{Colors.RED}❌ 初始化失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return None, False


async def test_create_search_log(service):
    """测试创建搜索记录"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 2: 创建搜索记录{Colors.RESET}")
    print("-" * 60)

    try:
        # 直接测试 repository 创建（绕过 LLM 和搜索）
        log_id = await service.repository.create(
            query_text="测试迁移：MongoDB 集成测试查询",
            user_id="test_user_migration",
            llm_analysis={
                "intent": "test_migration",
                "keywords": ["MongoDB", "迁移", "测试"],
                "confidence": 0.99
            }
        )

        if log_id and isinstance(log_id, str):
            print(f"{Colors.GREEN}✅ 创建成功{Colors.RESET}")
            print(f"   Log ID: {log_id} (类型: {type(log_id).__name__})")
            return log_id, True
        else:
            print(f"{Colors.RED}❌ 创建失败或返回类型错误{Colors.RESET}")
            return None, False

    except Exception as e:
        print(f"{Colors.RED}❌ 创建失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return None, False


async def test_get_search_log(service, log_id):
    """测试获取搜索记录"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 3: 获取搜索记录{Colors.RESET}")
    print("-" * 60)

    try:
        log = await service.get_search_log(log_id)

        if log:
            print(f"{Colors.GREEN}✅ 获取成功{Colors.RESET}")
            print(f"   Log ID: {log['log_id']}")
            print(f"   Query: {log['query_text']}")
            print(f"   Analysis: {log.get('analysis', {}).get('intent', 'N/A')}")
            print(f"   Created At: {log.get('created_at', 'N/A')}")
            return True
        else:
            print(f"{Colors.RED}❌ 获取失败：记录不存在{Colors.RESET}")
            return False

    except Exception as e:
        print(f"{Colors.RED}❌ 获取失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


async def test_update_llm_analysis(service, log_id):
    """测试更新 LLM 分析"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 4: 更新 LLM 分析{Colors.RESET}")
    print("-" * 60)

    try:
        success = await service.repository.update_llm_analysis(
            log_id=log_id,
            llm_analysis={
                "intent": "updated_test",
                "keywords": ["MongoDB", "迁移", "测试", "更新"],
                "confidence": 0.98
            }
        )

        if success:
            print(f"{Colors.GREEN}✅ 更新成功{Colors.RESET}")

            # 验证更新
            log = await service.get_search_log(log_id)
            if log and log.get('analysis', {}).get('intent') == 'updated_test':
                print(f"   验证通过：intent = {log['analysis']['intent']}")
                return True
            else:
                print(f"{Colors.YELLOW}⚠️  更新成功但验证失败{Colors.RESET}")
                return False
        else:
            print(f"{Colors.RED}❌ 更新失败{Colors.RESET}")
            return False

    except Exception as e:
        print(f"{Colors.RED}❌ 更新失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


async def test_list_search_logs(service):
    """测试列出搜索历史"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 5: 列出搜索历史{Colors.RESET}")
    print("-" * 60)

    try:
        logs = await service.list_search_logs(limit=5, offset=0)

        print(f"{Colors.GREEN}✅ 查询成功{Colors.RESET}")
        print(f"   返回记录数: {len(logs)}")

        for i, log in enumerate(logs[:3], 1):  # 只显示前3条
            print(f"   {i}. {log['query_text'][:50]}... (ID: {log['log_id']})")

        return True

    except Exception as e:
        print(f"{Colors.RED}❌ 查询失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


async def test_search_by_keyword(service):
    """测试关键词搜索"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 6: 关键词搜索{Colors.RESET}")
    print("-" * 60)

    try:
        logs = await service.search_by_keyword(keyword="MongoDB", limit=5)

        print(f"{Colors.GREEN}✅ 搜索成功{Colors.RESET}")
        print(f"   找到记录数: {len(logs)}")

        for i, log in enumerate(logs[:3], 1):  # 只显示前3条
            keywords = log.get('analysis', {}).get('keywords', [])
            print(f"   {i}. {log['query_text'][:50]}... (关键词: {keywords})")

        return True

    except Exception as e:
        print(f"{Colors.RED}❌ 搜索失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


async def test_service_status(service):
    """测试服务状态"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 7: 服务状态检查{Colors.RESET}")
    print("-" * 60)

    try:
        status = await service.get_service_status()

        print(f"{Colors.GREEN}✅ 状态查询成功{Colors.RESET}")
        print(f"   Enabled: {status['enabled']}")
        print(f"   Version: {status['version']}")
        print(f"   LLM Configured: {status['llm_configured']}")
        print(f"   Search Configured: {status['search_configured']}")
        print(f"   Test Mode: {status['test_mode']}")

        return True

    except Exception as e:
        print(f"{Colors.RED}❌ 状态查询失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


async def test_cleanup(service, log_id):
    """清理测试数据"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 8: 清理测试数据{Colors.RESET}")
    print("-" * 60)

    try:
        success = await service.repository.delete_by_id(log_id)

        if success:
            print(f"{Colors.GREEN}✅ 清理成功{Colors.RESET}")
            print(f"   已删除测试记录: {log_id}")
            return True
        else:
            print(f"{Colors.RED}❌ 清理失败{Colors.RESET}")
            return False

    except Exception as e:
        print(f"{Colors.RED}❌ 清理失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试流程"""
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}NL Search Service MongoDB 迁移集成测试{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")

    passed = 0
    failed = 0

    # 测试 1: 初始化
    service, success = await test_service_initialization()
    if success:
        passed += 1
    else:
        failed += 1
        print(f"\n{Colors.RED}测试中止：初始化失败{Colors.RESET}")
        return 1

    # 测试 2: 创建记录
    log_id, success = await test_create_search_log(service)
    if success:
        passed += 1
    else:
        failed += 1
        print(f"\n{Colors.RED}测试中止：创建记录失败{Colors.RESET}")
        return 1

    # 测试 3: 获取记录
    if await test_get_search_log(service, log_id):
        passed += 1
    else:
        failed += 1

    # 测试 4: 更新分析
    if await test_update_llm_analysis(service, log_id):
        passed += 1
    else:
        failed += 1

    # 测试 5: 列出历史
    if await test_list_search_logs(service):
        passed += 1
    else:
        failed += 1

    # 测试 6: 关键词搜索
    if await test_search_by_keyword(service):
        passed += 1
    else:
        failed += 1

    # 测试 7: 服务状态
    if await test_service_status(service):
        passed += 1
    else:
        failed += 1

    # 测试 8: 清理
    if await test_cleanup(service, log_id):
        passed += 1
    else:
        failed += 1

    # 打印总结
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}测试总结{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"总测试数: {passed + failed}")
    print(f"{Colors.GREEN}通过: {passed}{Colors.RESET}")
    print(f"{Colors.RED}失败: {failed}{Colors.RESET}")

    success_rate = (passed / (passed + failed) * 100) if (passed + failed) > 0 else 0
    print(f"\n成功率: {Colors.BOLD}{success_rate:.1f}%{Colors.RESET}")

    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 所有测试通过！MongoDB 迁移成功！{Colors.RESET}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

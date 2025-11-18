#!/usr/bin/env python3
"""
NL Search MongoDB Repository 测试脚本

测试 NL Search 从 MariaDB 迁移到 MongoDB 后的功能。

测试范围：
1. 创建搜索日志
2. 查询日志
3. 更新 LLM 分析
4. 更新状态
5. 关键词搜索
6. 删除功能
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.mongo_nl_search_repository import MongoNLSearchLogRepository


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


async def test_create():
    """测试创建搜索日志"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 1: 创建搜索日志{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        log_id = await repo.create(
            query_text="测试查询：最近有哪些AI技术突破",
            user_id="test_user_001",
            llm_analysis={
                "intent": "technology_news",
                "keywords": ["AI", "技术突破"],
                "entities": ["AI"],
                "time_range": "recent",
                "confidence": 0.95
            },
            search_config={
                "max_results": 10,
                "source": "gpt5_search"
            }
        )

        print(f"{Colors.GREEN}✅ 创建成功{Colors.RESET}")
        print(f"   日志ID: {log_id}")
        return log_id

    except Exception as e:
        print(f"{Colors.RED}❌ 创建失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_by_id(log_id):
    """测试获取日志详情"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 2: 获取日志详情{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        log = await repo.get_by_id(log_id)

        if log:
            print(f"{Colors.GREEN}✅ 获取成功{Colors.RESET}")
            print(f"   查询文本: {log['query_text']}")
            print(f"   用户ID: {log.get('user_id', 'N/A')}")
            print(f"   状态: {log.get('status', 'N/A')}")
            print(f"   LLM分析: {log.get('llm_analysis', {}).get('intent', 'N/A')}")
            print(f"   关键词: {log.get('llm_analysis', {}).get('keywords', [])}")
            print(f"   创建时间: {log.get('created_at', 'N/A')}")
            return True
        else:
            print(f"{Colors.RED}❌ 日志不存在{Colors.RESET}")
            return False

    except Exception as e:
        print(f"{Colors.RED}❌ 获取失败: {e}{Colors.RESET}")
        return False


async def test_update_llm_analysis(log_id):
    """测试更新 LLM 分析"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 3: 更新 LLM 分析{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        success = await repo.update_llm_analysis(
            log_id=log_id,
            llm_analysis={
                "intent": "updated_intent",
                "keywords": ["AI", "技术突破", "更新"],
                "confidence": 0.98
            }
        )

        if success:
            print(f"{Colors.GREEN}✅ 更新成功{Colors.RESET}")
            return True
        else:
            print(f"{Colors.RED}❌ 更新失败{Colors.RESET}")
            return False

    except Exception as e:
        print(f"{Colors.RED}❌ 更新失败: {e}{Colors.RESET}")
        return False


async def test_update_status(log_id):
    """测试更新状态"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 4: 更新状态{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        success = await repo.update_status(
            log_id=log_id,
            status="completed",
            results_count=5
        )

        if success:
            print(f"{Colors.GREEN}✅ 更新成功{Colors.RESET}")
            return True
        else:
            print(f"{Colors.RED}❌ 更新失败{Colors.RESET}")
            return False

    except Exception as e:
        print(f"{Colors.RED}❌ 更新失败: {e}{Colors.RESET}")
        return False


async def test_get_recent():
    """测试获取最近记录"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 5: 获取最近记录{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        logs = await repo.get_recent(limit=5, offset=0)

        print(f"{Colors.GREEN}✅ 查询成功{Colors.RESET}")
        print(f"   返回记录数: {len(logs)}")

        for i, log in enumerate(logs, 1):
            print(f"   {i}. {log['query_text'][:50]}... (ID: {log['_id']})")

        return True

    except Exception as e:
        print(f"{Colors.RED}❌ 查询失败: {e}{Colors.RESET}")
        return False


async def test_search_by_keyword():
    """测试关键词搜索"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 6: 关键词搜索{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        logs = await repo.search_by_keyword(keyword="AI", limit=10)

        print(f"{Colors.GREEN}✅ 搜索成功{Colors.RESET}")
        print(f"   找到记录数: {len(logs)}")

        for i, log in enumerate(logs, 1):
            keywords = log.get('llm_analysis', {}).get('keywords', [])
            print(f"   {i}. {log['query_text'][:50]}... (关键词: {keywords})")

        return True

    except Exception as e:
        print(f"{Colors.RED}❌ 搜索失败: {e}{Colors.RESET}")
        return False


async def test_count_total():
    """测试统计总数"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 7: 统计总记录数{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        total = await repo.count_total()

        print(f"{Colors.GREEN}✅ 统计成功{Colors.RESET}")
        print(f"   总记录数: {total}")
        return True

    except Exception as e:
        print(f"{Colors.RED}❌ 统计失败: {e}{Colors.RESET}")
        return False


async def test_delete_by_id(log_id):
    """测试删除记录"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 8: 删除记录{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        success = await repo.delete_by_id(log_id)

        if success:
            print(f"{Colors.GREEN}✅ 删除成功{Colors.RESET}")
            return True
        else:
            print(f"{Colors.RED}❌ 删除失败{Colors.RESET}")
            return False

    except Exception as e:
        print(f"{Colors.RED}❌ 删除失败: {e}{Colors.RESET}")
        return False


async def test_create_indexes():
    """测试创建索引"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}测试 9: 创建索引{Colors.RESET}")
    print("-" * 60)

    repo = MongoNLSearchLogRepository()

    try:
        await repo.create_indexes()

        print(f"{Colors.GREEN}✅ 索引创建成功{Colors.RESET}")
        print(f"   已创建的索引:")
        print(f"   1. created_at (倒序)")
        print(f"   2. user_id + created_at (复合)")
        print(f"   3. status")
        print(f"   4. query_text (文本搜索)")
        return True

    except Exception as e:
        print(f"{Colors.RED}❌ 索引创建失败: {e}{Colors.RESET}")
        return False


async def main():
    """主测试流程"""
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}NL Search MongoDB Repository 功能测试{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")

    passed = 0
    failed = 0

    # 测试 1: 创建索引
    if await test_create_indexes():
        passed += 1
    else:
        failed += 1

    # 测试 2: 创建日志
    log_id = await test_create()
    if log_id:
        passed += 1
    else:
        failed += 1
        print(f"\n{Colors.RED}测试中止：创建日志失败{Colors.RESET}")
        return 1

    # 测试 3: 获取详情
    if await test_get_by_id(log_id):
        passed += 1
    else:
        failed += 1

    # 测试 4: 更新 LLM 分析
    if await test_update_llm_analysis(log_id):
        passed += 1
    else:
        failed += 1

    # 测试 5: 更新状态
    if await test_update_status(log_id):
        passed += 1
    else:
        failed += 1

    # 测试 6: 获取最近记录
    if await test_get_recent():
        passed += 1
    else:
        failed += 1

    # 测试 7: 关键词搜索
    if await test_search_by_keyword():
        passed += 1
    else:
        failed += 1

    # 测试 8: 统计总数
    if await test_count_total():
        passed += 1
    else:
        failed += 1

    # 测试 9: 删除记录
    if await test_delete_by_id(log_id):
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

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

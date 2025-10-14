#!/usr/bin/env python
"""
测试运行脚本

统一的测试执行入口，支持运行不同类型的测试。

使用方法:
    python tests/run_tests.py                    # 运行所有测试
    python tests/run_tests.py --type unit        # 只运行单元测试
    python tests/run_tests.py --type scheduler   # 只运行调度器测试
    python tests/run_tests.py --verbose          # 详细输出
"""

import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TestRunner:
    """测试运行器"""

    def __init__(self, test_type: str = "all", verbose: bool = False):
        self.test_type = test_type
        self.verbose = verbose
        self.tests_dir = Path(__file__).parent
        self.results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0
        }

    def print_header(self):
        """打印测试头部"""
        logger.info("=" * 70)
        logger.info(f"🧪 开始运行测试 - 类型: {self.test_type}")
        logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)

    async def run_scheduler_tests(self):
        """运行调度器测试"""
        logger.info("\n📋 运行调度器测试...")

        test_files = [
            self.tests_dir / "scheduler" / "test_scheduler.py",
            self.tests_dir / "scheduler" / "test_search_results_fix.py"
        ]

        for test_file in test_files:
            if test_file.exists():
                logger.info(f"\n▶️  执行: {test_file.name}")
                try:
                    # 动态导入并运行测试
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("test_module", test_file)
                    test_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(test_module)

                    # 如果有main函数，运行它
                    if hasattr(test_module, 'main'):
                        if asyncio.iscoroutinefunction(test_module.main):
                            await test_module.main()
                        else:
                            test_module.main()

                    self.results["passed"] += 1
                    logger.info(f"✅ {test_file.name} 通过")

                except Exception as e:
                    self.results["failed"] += 1
                    logger.error(f"❌ {test_file.name} 失败: {e}")
                    if self.verbose:
                        import traceback
                        traceback.print_exc()

                self.results["total"] += 1
            else:
                logger.warning(f"⚠️  测试文件不存在: {test_file}")

    def run_unit_tests(self):
        """运行单元测试"""
        logger.info("\n🔬 运行单元测试...")
        logger.info("ℹ️  单元测试目录为空，跳过")
        # TODO: 实现单元测试运行逻辑

    def run_integration_tests(self):
        """运行集成测试"""
        logger.info("\n🔗 运行集成测试...")
        logger.info("ℹ️  集成测试目录为空，跳过")
        # TODO: 实现集成测试运行逻辑

    async def run_all_tests(self):
        """运行所有测试"""
        if self.test_type in ["all", "unit"]:
            self.run_unit_tests()

        if self.test_type in ["all", "integration"]:
            self.run_integration_tests()

        if self.test_type in ["all", "scheduler"]:
            await self.run_scheduler_tests()

    def print_summary(self):
        """打印测试总结"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 测试结果汇总")
        logger.info("=" * 70)

        logger.info(f"总计: {self.results['total']} 个测试")
        logger.info(f"✅ 通过: {self.results['passed']}")
        logger.info(f"❌ 失败: {self.results['failed']}")
        logger.info(f"⏭️  跳过: {self.results['skipped']}")

        success_rate = (
            (self.results['passed'] / self.results['total'] * 100)
            if self.results['total'] > 0 else 0
        )
        logger.info(f"📈 成功率: {success_rate:.1f}%")

        logger.info("=" * 70)

        if self.results['failed'] == 0:
            logger.info("🎉 所有测试通过!")
            return True
        else:
            logger.error(f"❌ {self.results['failed']} 个测试失败")
            return False

    async def run(self):
        """运行测试套件"""
        self.print_header()
        await self.run_all_tests()
        success = self.print_summary()
        return 0 if success else 1


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="运行测试套件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tests/run_tests.py                    # 运行所有测试
  python tests/run_tests.py --type unit        # 只运行单元测试
  python tests/run_tests.py --type scheduler   # 只运行调度器测试
  python tests/run_tests.py --verbose          # 详细输出
        """
    )

    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration", "scheduler"],
        default="all",
        help="测试类型 (默认: all)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出"
    )

    args = parser.parse_args()

    runner = TestRunner(test_type=args.type, verbose=args.verbose)

    try:
        exit_code = asyncio.run(runner.run())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ 测试运行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

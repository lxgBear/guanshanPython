"""测试雪花算法ID系统 v1.5.0

验证所有实体正确使用雪花算法ID
"""
import sys
sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.core.domain.entities.search_result import SearchResult, SearchResultBatch
from src.core.domain.entities.search_task import SearchTask
from src.infrastructure.id_generator import generate_string_id


def test_snowflake_id_format(id_value: str, entity_name: str) -> bool:
    """验证ID是否为雪花算法格式"""
    is_valid = id_value.isdigit() and 15 <= len(id_value) <= 19
    status = "✅" if is_valid else "❌"
    print(f"{status} {entity_name} ID: {id_value} (长度: {len(id_value)}, 纯数字: {id_value.isdigit()})")
    return is_valid


def main():
    print("=" * 70)
    print("雪花算法ID系统测试 - v1.5.0")
    print("=" * 70)

    all_passed = True

    # 测试1: ID生成器
    print("\n【测试1】ID生成器")
    print("-" * 70)
    generated_id = generate_string_id()
    all_passed &= test_snowflake_id_format(generated_id, "生成器ID")

    # 测试2: SearchResult实体
    print("\n【测试2】SearchResult 实体")
    print("-" * 70)
    result = SearchResult(
        task_id="242547193395171328",  # 雪花ID
        title="Test Result",
        url="https://example.com",
        content="Test content"
    )
    all_passed &= test_snowflake_id_format(result.id, "SearchResult.id (自动生成)")
    all_passed &= test_snowflake_id_format(result.task_id, "SearchResult.task_id (手动设置)")

    # SearchResult没有get_id_string()和is_secure_id()方法（仅SearchTask有）
    print(f"ℹ️  SearchResult直接使用ID字段，无需辅助方法")

    # 测试3: SearchTask实体
    print("\n【测试3】SearchTask 实体")
    print("-" * 70)
    task = SearchTask(
        name="Test Task",
        query="test query",
        created_by="test_user"
    )
    all_passed &= test_snowflake_id_format(task.id, "SearchTask.id (自动生成)")

    # 验证ID字符串接口
    task_id_string = task.get_id_string()
    all_passed &= test_snowflake_id_format(task_id_string, "SearchTask.get_id_string()")

    # 验证安全ID检查
    task_is_secure = task.is_secure_id()
    status = "✅" if task_is_secure else "❌"
    print(f"{status} SearchTask.is_secure_id(): {task_is_secure}")
    all_passed &= task_is_secure

    # 测试4: SearchResultBatch实体
    print("\n【测试4】SearchResultBatch 实体")
    print("-" * 70)
    batch = SearchResultBatch(
        task_id="242540877529686016",  # 雪花ID
        execution_id="exec_001",
        query="test query"
    )
    all_passed &= test_snowflake_id_format(batch.id, "SearchResultBatch.id (自动生成)")
    all_passed &= test_snowflake_id_format(batch.task_id, "SearchResultBatch.task_id (手动设置)")

    # 测试5: 创建安全ID的类方法
    print("\n【测试5】类方法创建")
    print("-" * 70)
    secure_task = SearchTask.create_with_secure_id(
        name="Secure Task",
        query="secure query",
        created_by="test_user"
    )
    all_passed &= test_snowflake_id_format(secure_task.id, "SearchTask.create_with_secure_id()")

    # 最终结果
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有测试通过！ID系统已完全统一为雪花算法。")
    else:
        print("❌ 部分测试失败，请检查代码。")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

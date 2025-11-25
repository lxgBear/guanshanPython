#!/usr/bin/env python3
"""
Sonar-Pro 思维链测试工具
功能：调用 sonar-pro 模型并保存结果到 data/ 文件夹
"""
import os
import json
import time
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv()

# 配置
API_KEY = os.getenv("NL_SEARCH_LLM_API_KEY")
BASE_URL = os.getenv("NL_SEARCH_LLM_BASE_URL")
MODEL = "sonar-pro"

# 确保 data 目录存在
Path("data").mkdir(exist_ok=True)

def test_sonar_with_reasoning(query: str, reasoning_effort: str = "high", save_result: bool = True):
    """
    测试 sonar-pro 模型的思维链功能

    Args:
        query: 查询问题
        reasoning_effort: 思维链强度 (low/medium/high)
        save_result: 是否保存结果到 data/ 文件夹

    Returns:
        dict: 包含响应数据和元信息
    """
    print("=" * 80)
    print(f"Sonar-Pro 思维链测试")
    print("=" * 80)
    print(f"模型: {MODEL}")
    print(f"Reasoning 强度: {reasoning_effort}")
    print(f"查询: {query}")
    print("-" * 80)

    # 初始化客户端
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL
    )

    # 记录开始时间
    start_time = time.time()

    try:
        # 调用 API
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": query}],
            max_tokens=2000,
            temperature=0.7,
            reasoning_effort=reasoning_effort  # 启用思维链
        )

        # 计算耗时
        elapsed = time.time() - start_time

        # 转换为字典
        result = response.model_dump()

        # 提取关键信息
        usage = result.get('usage', {})
        content = result['choices'][0]['message']['content']

        # 打印摘要
        print(f"\n✅ 请求成功！")
        print(f"⏱️  响应时间: {elapsed:.2f}s")
        print(f"\n📊 Token 使用:")
        print(f"   - Prompt: {usage.get('prompt_tokens', 0)}")
        print(f"   - Completion: {usage.get('completion_tokens', 0)}")
        print(f"   - Total: {usage.get('total_tokens', 0)}")

        if 'cost' in usage:
            cost = usage['cost']
            print(f"\n💰 成本:")
            print(f"   - Output: ${cost.get('output_tokens_cost', 0):.4f}")
            print(f"   - Total: ${cost.get('total_cost', 0):.4f}")

        # 检查 reasoning 相关字段
        reasoning_fields = [k for k in result.keys() if 'reason' in k.lower()]
        if reasoning_fields:
            print(f"\n🔍 发现 Reasoning 字段: {reasoning_fields}")

        # 打印回答预览
        print(f"\n📝 回答预览 (前 500 字符):")
        print(content[:500])
        if len(content) > 500:
            print("...")

        # 保存结果
        if save_result:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/sonar_{reasoning_effort}_{timestamp}.json"

            # 添加元信息
            result['_meta'] = {
                'query': query,
                'reasoning_effort': reasoning_effort,
                'elapsed_time': elapsed,
                'timestamp': timestamp,
                'content_length': len(content)
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"\n💾 结果已保存: {filename}")

        print("\n" + "=" * 80)

        return {
            'success': True,
            'result': result,
            'elapsed': elapsed,
            'filename': filename if save_result else None
        }

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """主函数 - 交互式测试"""
    print("Sonar-Pro 思维链测试工具")
    print("=" * 80)

    # 默认测试查询
    default_queries = [
        "请介绍关于西藏的新闻",
        "分析中美在人工智能领域的竞争态势",
        "解释什么是量子计算及其应用前景"
    ]

    print("\n预设查询:")
    for i, q in enumerate(default_queries, 1):
        print(f"{i}. {q}")
    print("0. 自定义查询")

    choice = input("\n请选择查询 (0-3，默认 1): ").strip() or "1"

    if choice == "0":
        query = input("请输入您的查询: ").strip()
        if not query:
            print("查询不能为空，使用默认查询")
            query = default_queries[0]
    else:
        try:
            idx = int(choice) - 1
            query = default_queries[idx] if 0 <= idx < len(default_queries) else default_queries[0]
        except (ValueError, IndexError):
            query = default_queries[0]

    # 选择 reasoning 强度
    print("\nReasoning 强度:")
    print("1. low    - 快速响应")
    print("2. medium - 平衡 (推荐)")
    print("3. high   - 深度分析")

    effort_choice = input("\n请选择强度 (1-3，默认 3): ").strip() or "3"
    effort_map = {"1": "low", "2": "medium", "3": "high"}
    reasoning_effort = effort_map.get(effort_choice, "high")

    # 执行测试
    print("\n" + "=" * 80)
    result = test_sonar_with_reasoning(query, reasoning_effort, save_result=True)

    if result['success']:
        print("\n✅ 测试完成！")
        if result['filename']:
            print(f"📁 结果文件: {result['filename']}")
        print(f"⏱️  总耗时: {result['elapsed']:.2f}s")
    else:
        print("\n❌ 测试失败")


if __name__ == "__main__":
    import sys

    # 检查命令行参数
    if len(sys.argv) > 1:
        # 命令行模式
        query = " ".join(sys.argv[1:])
        reasoning_effort = os.getenv("REASONING_EFFORT", "high")
        test_sonar_with_reasoning(query, reasoning_effort, save_result=True)
    else:
        # 交互模式
        main()

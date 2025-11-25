#!/usr/bin/env python3
"""测试 sonar-pro 模型的 reasoning (思维链) 支持"""
import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置
API_KEY = os.getenv("NL_SEARCH_LLM_API_KEY")
BASE_URL = os.getenv("NL_SEARCH_LLM_BASE_URL")
MODEL = "sonar-pro"

print("=" * 80)
print("Sonar-Pro Reasoning 功能测试")
print("=" * 80)
print(f"模型: {MODEL}")
print(f"API Base URL: {BASE_URL}")
print(f"API Key: {API_KEY[:20]}..." if API_KEY else "No API Key")
print("-" * 80)

# 初始化客户端
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# 测试查询 - 选择一个需要推理的复杂问题
query = "分析比较中国和美国在人工智能发展方面的优势和劣势"

print(f"\n测试查询: {query}\n")
print("=" * 80)

# 测试 1: 不使用 reasoning
print("\n【测试 1】不使用 reasoning 参数")
print("-" * 80)
start_time = time.time()

try:
    response_no_reasoning = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": query}],
        max_tokens=2000,
        temperature=0.7
    )

    elapsed_1 = time.time() - start_time
    result_1 = response_no_reasoning.model_dump()

    print(f"✅ 请求成功")
    print(f"⏱️  响应时间: {elapsed_1:.2f}s")
    print(f"📊 Token 使用:")
    if 'usage' in result_1:
        usage_1 = result_1['usage']
        print(f"   - Prompt: {usage_1.get('prompt_tokens', 0)}")
        print(f"   - Completion: {usage_1.get('completion_tokens', 0)}")
        print(f"   - Total: {usage_1.get('total_tokens', 0)}")

    # 保存响应
    output_file_1 = f"data/sonar_no_reasoning_{int(time.time())}.json"
    with open(output_file_1, 'w', encoding='utf-8') as f:
        json.dump(result_1, f, ensure_ascii=False, indent=2)
    print(f"💾 响应已保存: {output_file_1}")

    # 显示回答预览
    content_1 = result_1['choices'][0]['message']['content']
    print(f"\n📝 回答预览 (前300字):")
    print(content_1[:300])
    print("...\n")

except Exception as e:
    print(f"❌ 测试 1 失败: {e}")
    result_1 = None
    elapsed_1 = 0

# 等待一下避免频率限制
time.sleep(2)

# 测试 2: 使用 reasoning (high effort)
print("\n【测试 2】使用 reasoning_effort='high'")
print("-" * 80)
start_time = time.time()

try:
    response_with_reasoning = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": query}],
        max_tokens=2000,
        temperature=0.7,
        reasoning_effort="high"  # 添加 reasoning 参数
    )

    elapsed_2 = time.time() - start_time
    result_2 = response_with_reasoning.model_dump()

    print(f"✅ 请求成功")
    print(f"⏱️  响应时间: {elapsed_2:.2f}s")
    print(f"📊 Token 使用:")
    if 'usage' in result_2:
        usage_2 = result_2['usage']
        print(f"   - Prompt: {usage_2.get('prompt_tokens', 0)}")
        print(f"   - Completion: {usage_2.get('completion_tokens', 0)}")
        print(f"   - Total: {usage_2.get('total_tokens', 0)}")

        # 检查是否有 reasoning 相关的 token
        if 'reasoning_tokens' in usage_2:
            print(f"   - Reasoning: {usage_2.get('reasoning_tokens', 0)} ⭐")

    # 检查响应中是否有 reasoning 相关字段
    print(f"\n🔍 Reasoning 相关字段:")
    reasoning_fields = [k for k in result_2.keys() if 'reason' in k.lower()]
    if reasoning_fields:
        print(f"   发现字段: {reasoning_fields} ⭐")
    else:
        print("   未发现 reasoning 相关字段")

    # 检查 choices 中的字段
    if result_2.get('choices') and result_2['choices'][0].get('message'):
        message_fields = result_2['choices'][0]['message'].keys()
        reasoning_message_fields = [k for k in message_fields if 'reason' in k.lower()]
        if reasoning_message_fields:
            print(f"   Message 中发现: {reasoning_message_fields} ⭐")

    # 保存响应
    output_file_2 = f"data/sonar_with_reasoning_{int(time.time())}.json"
    with open(output_file_2, 'w', encoding='utf-8') as f:
        json.dump(result_2, f, ensure_ascii=False, indent=2)
    print(f"💾 响应已保存: {output_file_2}")

    # 显示回答预览
    content_2 = result_2['choices'][0]['message']['content']
    print(f"\n📝 回答预览 (前300字):")
    print(content_2[:300])
    print("...\n")

except Exception as e:
    print(f"❌ 测试 2 失败: {e}")
    import traceback
    traceback.print_exc()
    result_2 = None
    elapsed_2 = 0

# 对比分析
print("\n" + "=" * 80)
print("📊 对比分析")
print("=" * 80)

if result_1 and result_2:
    print(f"\n⏱️  响应时间对比:")
    print(f"   无 reasoning: {elapsed_1:.2f}s")
    print(f"   有 reasoning: {elapsed_2:.2f}s")
    print(f"   差异: {abs(elapsed_2 - elapsed_1):.2f}s ({'+' if elapsed_2 > elapsed_1 else '-'}{abs(elapsed_2 - elapsed_1)/elapsed_1*100:.1f}%)")

    if 'usage' in result_1 and 'usage' in result_2:
        usage_1 = result_1['usage']
        usage_2 = result_2['usage']

        print(f"\n📊 Token 使用量对比:")
        print(f"   无 reasoning: {usage_1.get('total_tokens', 0)}")
        print(f"   有 reasoning: {usage_2.get('total_tokens', 0)}")

        token_diff = usage_2.get('total_tokens', 0) - usage_1.get('total_tokens', 0)
        if token_diff > 0:
            print(f"   增加: +{token_diff} tokens (+{token_diff/usage_1.get('total_tokens', 1)*100:.1f}%) ⭐")
        elif token_diff < 0:
            print(f"   减少: {token_diff} tokens ({token_diff/usage_1.get('total_tokens', 1)*100:.1f}%)")
        else:
            print(f"   无变化")

        # 检查是否有 reasoning_tokens
        if 'reasoning_tokens' in usage_2:
            print(f"   ⭐ 发现 reasoning_tokens: {usage_2['reasoning_tokens']}")

    print(f"\n📝 回答长度对比:")
    content_1 = result_1['choices'][0]['message']['content']
    content_2 = result_2['choices'][0]['message']['content']
    print(f"   无 reasoning: {len(content_1)} 字符")
    print(f"   有 reasoning: {len(content_2)} 字符")
    print(f"   差异: {len(content_2) - len(content_1)} 字符")

print("\n" + "=" * 80)
print("✅ 测试完成")
print("=" * 80)

# 结论
print("\n📌 结论:")
if result_2:
    has_reasoning_support = False

    # 检查是否有明显差异
    if result_1 and result_2:
        usage_1 = result_1.get('usage', {})
        usage_2 = result_2.get('usage', {})

        # 检查 reasoning_tokens
        if 'reasoning_tokens' in usage_2 and usage_2['reasoning_tokens'] > 0:
            has_reasoning_support = True
            print("   ✅ sonar-pro 支持 reasoning (发现 reasoning_tokens)")

        # 检查 token 增加
        elif usage_2.get('total_tokens', 0) > usage_1.get('total_tokens', 0) * 1.2:
            has_reasoning_support = True
            print("   ✅ sonar-pro 可能支持 reasoning (token 使用量明显增加)")

        # 检查响应时间增加
        elif elapsed_2 > elapsed_1 * 1.5:
            has_reasoning_support = True
            print("   ✅ sonar-pro 可能支持 reasoning (响应时间明显增加)")

    if not has_reasoning_support:
        print("   ⚠️  无法确认 sonar-pro 是否支持 reasoning")
        print("   建议: 检查响应内容质量差异或查阅官方文档")
else:
    print("   ❌ 测试失败，无法得出结论")

print("\n💡 下一步:")
print("   1. 对比两个响应文件的详细内容")
print("   2. 检查回答质量是否有显著差异")
print("   3. 查阅 Perplexity API 官方文档")
print("   4. 如需关闭 reasoning: 设置 NL_SEARCH_REASONING_ENABLED=false")

#!/usr/bin/env python3
"""Direct test of sonar-pro model"""
import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("NL_SEARCH_LLM_API_KEY")
BASE_URL = os.getenv("NL_SEARCH_LLM_BASE_URL")
MODEL = "sonar-pro"

print(f"Testing {MODEL} model...")
print(f"API Base URL: {BASE_URL}")
print(f"API Key: {API_KEY[:20]}..." if API_KEY else "No API Key")
print("-" * 80)

# Initialize client
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# Test query
query = "华语青年挺藏会负责人段荆棘的简历和背景信息"
print(f"\nQuery: {query}\n")

# Make API call
start_time = time.time()
try:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": query}
        ],
        max_tokens=2000,
        temperature=0.7
    )

    elapsed = time.time() - start_time

    # Extract response
    result = response.model_dump()

    # Print summary
    print(f"\n✅ API call successful!")
    print(f"⏱️  Response time: {elapsed:.2f}s")
    print(f"🔢 Model: {result['model']}")

    if 'usage' in result:
        usage = result['usage']
        print(f"\n📊 Token Usage:")
        print(f"   - Prompt tokens: {usage.get('prompt_tokens', 0)}")
        print(f"   - Completion tokens: {usage.get('completion_tokens', 0)}")
        print(f"   - Total tokens: {usage.get('total_tokens', 0)}")

        # Calculate cost (assuming $5/$15 per 1M tokens for input/output)
        prompt_cost = usage.get('prompt_tokens', 0) * 5 / 1_000_000
        completion_cost = usage.get('completion_tokens', 0) * 15 / 1_000_000
        total_cost = prompt_cost + completion_cost
        print(f"   - Estimated cost: ${total_cost:.4f}")

    # Check for search results
    if hasattr(response, 'search_results'):
        print(f"\n🔍 Search Results: {len(response.search_results)} results")

    # Save full response
    output_file = f"data/sonar_pro_test_{int(time.time())}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Full response saved to: {output_file}")

    # Print answer preview
    if result.get('choices'):
        content = result['choices'][0]['message']['content']
        print(f"\n📝 Answer preview (first 500 chars):")
        print(content[:500])
        print("...")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

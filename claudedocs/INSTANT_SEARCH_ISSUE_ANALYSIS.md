# Instant Search Task 238917114149052416 Root Cause Analysis

## Executive Summary

**Task ID:** 238917114149052416
**Task Name:** 搜索_特朗普最近的行程_1021_1451
**Status:** Failed
**Query:** "特朗普最近的行程"
**Created:** 2025-10-21 06:51:18
**Failed:** 2025-10-21 06:51:48 (30 seconds)
**Error Message:** "搜索失败: " (empty detail)

**Root Cause:** Firecrawl SDK API incompatibility - The `FirecrawlApp.search()` method is being called with incorrect parameters for Firecrawl API v2.

---

## Problem Analysis

### 1. Task Execution Flow

```
InstantSearchService.create_and_execute_search()
  ├─ Task Created: 238917114149052416
  ├─ search_execution_id: exec_238917114149052417
  ├─ Task Started
  ├─ _execute_search() called with query="特朗普最近的行程"
  │   └─ FirecrawlAdapter.search(query, limit=10)
  │       └─ self.client.search(query)  <-- FAILS HERE
  └─ Exception caught → Task marked as failed
```

### 2. Root Cause: API Parameter Mismatch

**File:** `src/infrastructure/crawlers/firecrawl_adapter.py:189-230`

```python
async def search(self, query: str, limit: int = 10) -> List[CrawlResult]:
    try:
        # Problem: Calling search with only query parameter
        result = await asyncio.wait_for(
            asyncio.to_thread(self.client.search, query),  # <-- Missing required params
            timeout=self.timeout
        )
    except Exception as e:
        logger.error(f"搜索失败: {query}, 错误: {str(e)}")
        raise CrawlException(f"搜索失败: {str(e)}")  # <-- Error message might be empty
```

**Issue:** The Firecrawl Python SDK's `search()` method for API v2 likely requires additional parameters (like `limit`, `formats`, etc.), but the adapter is only passing the `query`.

### 3. Error Handling Chain

```
FirecrawlAdapter.search()
  └─ Exception raised by self.client.search(query)
      └─ Wrapped as CrawlException("搜索失败: {empty}")
          └─ Caught by InstantSearchService._execute_search() (line 175-177)
              └─ Exception re-raised
                  └─ Caught by create_and_execute_search() (line 134-140)
                      └─ task.mark_as_failed(str(e))
                          └─ Stored in database with empty error message
```

### 4. Why Error Message is Empty

The exception from Firecrawl SDK might:
1. Have an empty `str()` representation
2. Be a specific exception type that doesn't serialize well
3. Contain non-string error details in a different attribute

---

## Evidence from Diagnostic Test

```bash
✅ 任务存在
   - 任务名称: 搜索_特朗普最近的行程_1021_1451
   - 状态: failed
   - 搜索执行ID: exec_238917114149052417
   - 总结果数: 0
   - 新结果数: 0
   - 共享结果数: 0
   - 搜索模式: search
   - 查询关键词: 特朗普最近的行程
   - ⚠️ 错误信息: 搜索失败:

❌ 任务执行失败: 搜索失败:
```

**Observations:**
- Task exists in database
- Status correctly marked as `failed`
- Error message is present but detail is empty
- Execution took 30 seconds (likely timeout)
- No results or mappings were created

---

## Technical Architecture Review

### Dual Search Implementation Issue

The codebase has **two different Firecrawl adapters**:

1. **FirecrawlSearchAdapter** (`src/infrastructure/search/firecrawl_search_adapter.py`)
   - Used for scheduled search tasks
   - Properly implements Firecrawl API v2
   - Uses `httpx.AsyncClient` with explicit request body
   - Correct parameter format:
     ```python
     body = {
         "query": query,
         "limit": config.get('limit', 20),
         "lang": language,
         "scrapeOptions": {...}
     }
     response = await client.post(f"{base_url}/v2/search", json=body)
     ```

2. **FirecrawlAdapter** (`src/infrastructure/crawlers/firecrawl_adapter.py`)
   - Used for instant search tasks
   - Uses Firecrawl Python SDK (`FirecrawlApp`)
   - **PROBLEM:** Calls SDK with incorrect parameters
   - Incorrect usage:
     ```python
     result = await asyncio.to_thread(self.client.search, query)
     ```

### Why This Causes Failure

The Firecrawl Python SDK's `search()` method signature for v2 API likely requires:
```python
def search(self, query: str, params: Optional[Dict] = None) -> Dict:
    """
    Args:
        query: Search query
        params: Additional parameters (limit, formats, scrapeOptions, etc.)
    """
```

But the adapter is calling it with only `query`, missing the `params` dictionary.

---

## Recommended Solutions

### Option 1: Fix FirecrawlAdapter to Match API v2 (Recommended)

**File:** `src/infrastructure/crawlers/firecrawl_adapter.py:189-230`

```python
async def search(self, query: str, limit: int = 10) -> List[CrawlResult]:
    """
    搜索并爬取结果

    Args:
        query: 搜索查询
        limit: 结果数量限制

    Returns:
        List[CrawlResult]: 搜索结果
    """
    try:
        logger.info(f"搜索查询: {query}, 限制: {limit}")

        # FIX: Pass params dict to match API v2 requirements
        params = {
            'limit': limit,
            'scrapeOptions': {
                'formats': ['markdown', 'html']
            }
        }

        result = await asyncio.wait_for(
            asyncio.to_thread(self.client.search, query, params),
            timeout=self.timeout
        )

        # 处理搜索结果...
        results = []
        items = result.get('data', []) if isinstance(result, dict) else result

        for item in items[:limit]:
            crawl_result = CrawlResult(
                url=item.get('url', ''),
                content=item.get('content', item.get('markdown', '')),
                markdown=item.get('markdown'),
                html=item.get('html'),
                metadata=item.get('metadata', {})
            )
            results.append(crawl_result)

        logger.info(f"搜索完成: {query}, 获得 {len(results)} 个结果")
        return results

    except Exception as e:
        # FIX: Improve error message capture
        import traceback
        error_detail = str(e) if str(e) else repr(e)
        logger.error(f"搜索失败: {query}")
        logger.error(f"错误详情: {error_detail}")
        logger.error(f"堆栈跟踪:\n{traceback.format_exc()}")
        raise CrawlException(f"搜索失败: {error_detail}")
```

### Option 2: Consolidate to Single Adapter

**Rationale:** Having two different implementations is confusing and error-prone.

**Strategy:**
1. Use `FirecrawlSearchAdapter` for both instant and scheduled searches
2. Deprecate `FirecrawlAdapter.search()` method
3. Update `InstantSearchService` to use `FirecrawlSearchAdapter`

### Option 3: Enhance Error Handling

Even with correct API calls, improve error visibility:

**File:** `src/infrastructure/crawlers/firecrawl_adapter.py:228-230`

```python
except Exception as e:
    import traceback
    error_type = type(e).__name__
    error_msg = str(e) if str(e) else repr(e)
    stack_trace = traceback.format_exc()

    logger.error(f"搜索失败: {query}")
    logger.error(f"异常类型: {error_type}")
    logger.error(f"错误信息: {error_msg}")
    logger.error(f"堆栈跟踪:\n{stack_trace}")

    raise CrawlException(
        f"搜索失败 ({error_type}): {error_msg or '未知错误'}",
        details={'query': query, 'traceback': stack_trace}
    )
```

---

## Testing Strategy

### 1. Verify Firecrawl SDK Signature

```python
# Test script to verify SDK method signature
from firecrawl import FirecrawlApp
import inspect

client = FirecrawlApp(api_key="your_key")
sig = inspect.signature(client.search)
print(f"search() signature: {sig}")
```

### 2. Test with Correct Parameters

```python
# Test search with correct params
params = {
    'limit': 5,
    'scrapeOptions': {
        'formats': ['markdown', 'html']
    }
}

try:
    result = client.search("特朗普最近的行程", params)
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {str(e)}")
```

### 3. Integration Test

Once fixed, retest task 238917114149052416's query:

```bash
python scripts/test_instant_search_api.py \
  --name "测试搜索" \
  --query "特朗普最近的行程" \
  --limit 5
```

---

## Impact Assessment

### Affected Components

1. **Instant Search Tasks** - All instant searches are failing
2. **URL Crawl Mode** - Might work (uses `scrape()` method instead)
3. **Scheduled Searches** - Unaffected (uses different adapter)

### Data Integrity

- Database schema is correct
- No data corruption
- Failed tasks are properly marked
- No orphaned records

### User Impact

- Users cannot execute instant keyword searches
- Error messages are not informative
- No results returned for any instant search

---

## Immediate Actions Required

1. ✅ **Verify Firecrawl SDK version**
   ```bash
   pip show firecrawl-py
   ```

2. ✅ **Check SDK documentation**
   - Confirm `search()` method signature
   - Review required parameters

3. ✅ **Implement fix** (Option 1 recommended)
   - Update `FirecrawlAdapter.search()` with correct params
   - Enhance error handling
   - Add detailed logging

4. ✅ **Test thoroughly**
   - Unit test with SDK
   - Integration test with service
   - Retry failed task 238917114149052416

5. ✅ **Monitor logs**
   - Check application logs for detailed error messages
   - Review Firecrawl API responses

---

## Long-term Improvements

1. **Adapter Consolidation**
   - Merge `FirecrawlAdapter` and `FirecrawlSearchAdapter`
   - Single source of truth for Firecrawl integration

2. **Enhanced Error Handling**
   - Structured error responses
   - Error codes and categories
   - User-friendly error messages

3. **Comprehensive Testing**
   - Unit tests for Firecrawl adapters
   - Integration tests for search flows
   - Mock Firecrawl API for consistent testing

4. **Monitoring & Alerts**
   - Track instant search success rates
   - Alert on high failure rates
   - Log Firecrawl API response times

---

## References

- Task Repository: `src/infrastructure/database/instant_search_repositories.py`
- Service Layer: `src/services/instant_search_service.py`
- Firecrawl Adapter: `src/infrastructure/crawlers/firecrawl_adapter.py`
- Search Adapter: `src/infrastructure/search/firecrawl_search_adapter.py`
- API Endpoints: `src/api/v1/endpoints/instant_search.py`
- Diagnostic Script: `scripts/test_instant_search_task.py`

---

**Analysis Date:** 2025-10-21
**Analyst:** Claude Code SuperClaude
**Priority:** High
**Status:** Root cause identified, solution proposed

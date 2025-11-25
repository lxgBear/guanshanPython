# Archive Creation ID Mismatch - Root Cause Analysis

## Executive Summary

**Problem**: Archive creation fails with "没有有效的档案条目可创建" (No valid archive entries).

**Root Cause**: Frontend constructs composite IDs (`"<log_id>-<index>"`) but backend expects actual MongoDB document `_id` values from `news_results` collection. These ID formats are incompatible.

## Investigation Timeline

### 1. Error Manifestation
- **User Action**: Click "创建档案" (Create Archive) button
- **Frontend Request**:
  ```json
  POST /api/proxy/nl-search/archives
  {
    "items": [
      {
        "news_result_id": "250994284283588608-0",  // ← Composite format
        "edited_title": "...",
        "edited_summary": "..."
      }
    ]
  }
  ```
- **Backend Response**: `400 {"detail": {"error": "输入验证失败", "message": "没有有效的档案条目可创建"}}`

### 2. Backend Processing Flow

**File**: `src/services/nl_search/mongo_archive_service.py`

```python
# Line 119-124: Iterate through items
for idx, item in enumerate(items):
    news_result_id = item.get("news_result_id")  # Gets "250994284283588608-0"

# Line 127-130: Try user_edited_results
edited_record = await self.db["user_edited_results"].find_one({
    "news_result_id": news_result_id,  # Searches for "250994284283588608-0"
    "user_id": user_id
})

# Line 163-169: Fall back to news_results
else:
    # 降级: 从 news_results 创建快照
    snapshot = await self._create_snapshot(news_result_id)  # ← Calls line 467

# Line 467: _create_snapshot method
result = await self.db["news_results"].find_one({"_id": news_result_id})
# ❌ FAILS: news_result_id="250994284283588608-0" doesn't exist

# Line 189-190: All snapshots failed → raise error
if not archive_items:
    raise ValueError("没有有效的档案条目可创建")  # ← THIS ERROR
```

### 3. Database Investigation

**Search Log**: `nl_search_logs._id = "250994284283588608"` ✅
```python
{
  "_id": "250994284283588608",
  "query_text": "请检索并整理近期全球各国家和地区因互联网消息传播引发...",
  "created_at": "2025-11-23 14:41:40.621000",
  "search_results": [],  // ❌ EMPTY ARRAY
  "results_count": 0
}
```

**News Results Collection**: ❌ No records with composite IDs
```
Query: {"_id": "250994284283588608-0"} → Not Found
Query: {"_id": "250994284283588608-1"} → Not Found
Query: {"log_id": "250994284283588608"} → Not Found (no log_id field)
```

**Search Results Collection** (Dual-Write): ❌ No results for this task_id
```
Query: {"task_id": "250994284283588608"} → Not Found
```

**Actual MongoDB Structure**:
```python
# news_results collection
{
  "_id": "249832360790564866",  // ← Simple snowflake ID
  "title": "...",
  "url": "...",
  "markdown_content": "...",
  "html_content": "..."
  // NO log_id field
}

# search_results collection (dual-write)
{
  "_id": "250996375601311749",  // ← Unique snowflake ID
  "task_id": "250994261097476096",  // ← Links to nl_search_logs
  "url": "...",
  "title": "...",
  "markdown_content": "...",
  "html_content": "..."
}
```

### 4. ID Format Analysis

| Source | ID Format | Example | Purpose |
|--------|-----------|---------|---------|
| **Frontend** | `"<log_id>-<index>"` | `"250994284283588608-0"` | Composite ID (self-constructed) |
| **nl_search_logs** | Snowflake string | `"250994284283588608"` | Search log identifier |
| **news_results** | Snowflake string | `"249832360790564866"` | News document identifier |
| **search_results** | Snowflake string | `"250996375601311749"` | Search result identifier |

**Critical Mismatch**: Frontend composite IDs don't exist anywhere in the database.

## Root Cause

The API endpoint `/api/v1/nl-search/{log_id}/results` does NOT return any unique identifier for each search result.

**Current Response Structure** (`src/api/v1/endpoints/nl_search.py:945-956`):
```python
result_items = [
    SearchResultItem(
        title=item.get("title", ""),
        url=item.get("url", ""),
        snippet=item.get("snippet", ""),
        position=item.get("position", 0),
        score=item.get("score", 0.0),
        source=item.get("source", "unknown")
    )
    # ❌ NO _id OR news_result_id FIELD!
    for item in result["results"]
]
```

**Frontend's Workaround**:
- Since API doesn't provide IDs, frontend constructs its own: `f"{log_id}-{index}"`
- This format has no meaning to the backend

## Solution Options

### Option 1: Backend Returns Document IDs ⭐ RECOMMENDED

**Modify** `/api/v1/nl-search/{log_id}/results` to return document `_id` from `search_results` collection.

**Change Required**:
```python
# src/api/v1/endpoints/nl_search.py:945-956
result_items = [
    SearchResultItem(
        id=item.get("_id"),  # ← ADD THIS FIELD
        title=item.get("title", ""),
        url=item.get("url", ""),
        snippet=item.get("snippet", ""),
        position=item.get("position", 0),
        score=item.get("score", 0.0),
        source=item.get("source", "unknown")
    )
    for item in result["results"]
]
```

**Pros**:
- Minimal backend change
- Uses existing `search_results` collection IDs
- Frontend can directly use returned IDs

**Cons**:
- Requires updating `SearchResultItem` model to include `id` field
- Requires frontend update to use returned IDs instead of constructing them

### Option 2: Backend Accepts Composite ID Format

**Modify** `mongo_archive_service.py:_create_snapshot` to parse composite IDs.

```python
async def _create_snapshot(self, news_result_id: str) -> Optional[Dict[str, Any]]:
    # Parse composite ID format: "<log_id>-<index>"
    if "-" in news_result_id:
        parts = news_result_id.split("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            log_id = parts[0]
            index = int(parts[1])

            # Get result from nl_search_logs.search_results array
            log = await self.db["nl_search_logs"].find_one({"_id": log_id})
            if log and "search_results" in log:
                results = log.get("search_results", [])
                if 0 <= index < len(results):
                    return results[index]

            # Or get from search_results collection
            result = await self.db["search_results"].find_one({
                "task_id": log_id,
                "position": index  # If position field exists
            })
            if result:
                return self._convert_to_snapshot(result)

    # Fallback to original logic
    result = await self.db["news_results"].find_one({"_id": news_result_id})
    ...
```

**Pros**:
- No frontend change required
- Backward compatible

**Cons**:
- Hacky workaround
- Adds complexity to backend
- Requires search_results array to be populated

### Option 3: Use search_results Collection with task_id + position

**Store position** in `search_results` collection during dual-write, then query by:
```python
result = await self.db["search_results"].find_one({
    "task_id": log_id,
    "position": index  # position field from search results
})
```

**Pros**:
- Clean separation of concerns
- Uses dual-write infrastructure

**Cons**:
- Requires ensuring `position` field exists in `search_results`
- Still requires parsing composite ID

## Recommended Fix

**Implement Option 1**: Return document IDs in API response.

**Implementation Steps**:

1. **Update Data Model** (`src/api/v1/endpoints/nl_search.py:151-170`):
   ```python
   class SearchResultItem(BaseModel):
       id: Optional[str] = Field(None, description="结果ID（MongoDB _id）")  # ← ADD
       title: str = Field(..., description="结果标题")
       url: str = Field(..., description="结果URL")
       snippet: str = Field(..., description="结果摘要")
       position: int = Field(..., description="结果位置")
       score: float = Field(..., description="相关性评分")
       source: str = Field(..., description="来源（serpapi/web/cache）")
   ```

2. **Update API Response** (`src/api/v1/endpoints/nl_search.py:945-956`):
   ```python
   result_items = [
       SearchResultItem(
           id=item.get("_id"),  # ← ADD THIS
           title=item.get("title", ""),
           url=item.get("url", ""),
           snippet=item.get("snippet", ""),
           position=item.get("position", 0),
           score=item.get("score", 0.0),
           source=item.get("source", "unknown")
       )
       for item in result["results"]
   ]
   ```

3. **Ensure Repository Returns _id** (`src/infrastructure/database/mongo_nl_search_repository.py:481-515`):
   - Verify `search_results` array contains `_id` field
   - Or query `search_results` collection instead of embedded array

4. **Update Frontend** (if needed):
   - Use returned `id` field instead of constructing composite IDs
   - Change `news_result_id: result.id` instead of `news_result_id: f"{log_id}-{index}"`

## Testing Plan

1. **Verify search results contain _id**:
   ```python
   result = await nl_search_service.get_search_results("250994261097476096")
   assert all("_id" in item for item in result["results"])
   ```

2. **Test archive creation**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/nl-search/archives" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": 1001,
       "archive_name": "Test Archive",
       "items": [{
         "news_result_id": "250996375601311749"  // ← Real MongoDB _id
       }]
     }'
   ```

3. **Verify snapshot creation**:
   - Check `_create_snapshot` can find document by _id
   - Verify archive entries are created successfully

## Impact Assessment

| Component | Change Required | Risk Level |
|-----------|----------------|------------|
| **Backend API Model** | Add `id` field to `SearchResultItem` | Low |
| **Backend API Response** | Include `_id` in response | Low |
| **Backend Repository** | Ensure `_id` in results | Low |
| **Frontend** | Use returned IDs | Medium (requires coordination) |
| **Database** | None | None |

**Deployment Strategy**: Backend-first deployment (backward compatible), then frontend update.

## Additional Findings

### Why search_results is Empty for log_id="250994284283588608"

The search log shows `results_count: 0`, meaning either:
1. Search failed to complete (check error logs)
2. No results were found
3. Dual-write failed

**Recommendation**: Investigate why this search didn't produce results.

### Missing log_id Field in news_results

The `news_results` collection has NO `log_id` field linking back to search logs. This makes it impossible to correlate news documents with their originating searches.

**Future Enhancement**: Add `log_id` or `task_id` field to `news_results` during scraping.

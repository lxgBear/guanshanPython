# 关山智能系统 - 代码风格与约定

## 命名规范

### Python 命名
- **变量/函数**: `snake_case` (小写下划线)
  ```python
  search_result = await get_search_results()
  def calculate_total_count(): ...
  ```

- **类名**: `PascalCase` (大驼峰)
  ```python
  class SearchTaskService:
  class LangGraphSearchResult:
  ```

- **常量**: `UPPER_SNAKE_CASE`
  ```python
  MAX_RETRY_COUNT = 3
  DEFAULT_TIMEOUT = 30
  ```

- **私有成员**: 单下划线前缀
  ```python
  self._internal_state = {}
  def _validate_input(): ...
  ```

### 文件命名
- 模块文件: `snake_case.py` (如 `search_task.py`)
- 测试文件: `test_*.py` (如 `test_search_task.py`)

## 类型提示

### 必须使用类型注解
```python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

def get_tasks(limit: int = 10) -> List[SearchTask]:
    ...

async def process_result(
    task_id: str,
    options: Optional[Dict[str, Any]] = None
) -> ProcessedResult:
    ...
```

### Pydantic 模型
```python
class SearchConfig(BaseModel):
    """搜索配置"""
    limit: int = Field(default=20, ge=1, le=100)
    sources: List[str] = Field(default_factory=lambda: ["web"])
    language: str = "zh"
```

## 文档字符串

### 函数/方法文档
```python
async def execute_search(
    query: str,
    config: SearchConfig
) -> SearchResult:
    """
    执行搜索任务
    
    Args:
        query: 搜索关键词
        config: 搜索配置
        
    Returns:
        SearchResult: 搜索结果对象
        
    Raises:
        SearchError: 搜索失败时抛出
    """
    ...
```

### 类文档
```python
class SearchTaskService:
    """
    搜索任务服务
    
    负责管理搜索任务的创建、执行和查询。
    
    Attributes:
        repository: 任务仓储
        scheduler: 任务调度器
    """
```

## 导入顺序

按以下顺序组织导入，组间空一行:

```python
# 1. 标准库
import os
import json
from typing import List, Optional
from datetime import datetime

# 2. 第三方库
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import httpx

# 3. 本地模块
from src.config import settings
from src.core.domain.entities import SearchTask
from src.services.search_service import SearchService
```

## 异步编程模式

### 优先使用 async/await
```python
# 正确
async def get_result():
    result = await repository.find_by_id(task_id)
    return result

# 避免在异步函数中使用同步阻塞调用
```

### 并发执行
```python
import asyncio

async def fetch_all():
    tasks = [
        fetch_data(url1),
        fetch_data(url2),
        fetch_data(url3)
    ]
    results = await asyncio.gather(*tasks)
    return results
```

## FastAPI 约定

### 路由定义
```python
router = APIRouter(prefix="/search-tasks", tags=["搜索任务"])

@router.post("/", response_model=SearchTaskResponse)
async def create_task(
    request: CreateTaskRequest,
    service: SearchTaskService = Depends(get_search_service)
) -> SearchTaskResponse:
    """创建搜索任务"""
    ...
```

### 依赖注入
```python
from fastapi import Depends

def get_search_service() -> SearchTaskService:
    return SearchTaskService()

async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> User:
    ...
```

## 错误处理

### 使用 HTTPException
```python
from fastapi import HTTPException, status

if not task:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"任务 {task_id} 不存在"
    )
```

### 日志记录
```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

logger.info(f"开始执行任务: {task_id}")
logger.warning(f"重试第 {attempt} 次")
logger.error(f"任务执行失败: {error}", exc_info=True)
```

## 代码格式化配置

### Black (line-length=88)
```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
```

### isort
```toml
[tool.isort]
profile = "black"
line_length = 88
```

## 测试约定

### 测试命名
```python
# 测试函数: test_<被测功能>_<场景>_<预期结果>
def test_create_task_with_valid_input_returns_task():
    ...

def test_search_with_empty_query_raises_error():
    ...
```

### pytest 标记
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    ...

@pytest.mark.integration
def test_database_connection():
    ...

@pytest.mark.slow
def test_long_running_operation():
    ...
```

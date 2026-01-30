# Map + Detail 详情页爬取功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现用户输入网址，通过 Firecrawl Map API 发现所有链接，使用规则过滤 + LLM 判断筛选详情页，批量爬取并存储到 `search_results` 表。

**Architecture:** 采用混合过滤模式（规则黑名单 + LLM 二次判断），复用现有 `SearchTask` 和 `SearchResult` 实体，通过 LangGraph 工作流实现 URL 智能分类。

**Tech Stack:** FastAPI, MongoDB (motor), LangGraph, Firecrawl API, APScheduler

**设计文档:** `docs/plans/2026-01-30-map-detail-crawl-design.md`

---

## Task 1: 添加 MAP_DETAIL 任务类型

**Files:**
- Modify: `src/core/domain/entities/search_task.py:17-23` (TaskType 枚举)
- Modify: `src/core/domain/entities/search_task.py:152-154` (添加判断方法)
- Test: `tests/unit/domain/test_search_task.py`

**Step 1: 写失败测试 - 验证新任务类型**

```python
# tests/unit/domain/test_search_task.py (新增测试)

def test_task_type_map_detail_exists():
    """测试 MAP_DETAIL 任务类型存在"""
    from src.core.domain.entities.search_task import TaskType
    assert hasattr(TaskType, 'MAP_DETAIL')
    assert TaskType.MAP_DETAIL.value == "map_detail"


def test_search_task_is_map_detail_mode():
    """测试 is_map_detail_mode 方法"""
    from src.core.domain.entities.search_task import SearchTask
    task = SearchTask(
        name="Test Map Detail",
        task_type="map_detail",
        crawl_url="https://example.com"
    )
    assert task.is_map_detail_mode() is True
    assert task.is_search_keyword_mode() is False
```

**Step 2: 运行测试验证失败**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/domain/test_search_task.py -v -k "map_detail"`
Expected: FAIL - "AttributeError: MAP_DETAIL"

**Step 3: 实现 TaskType 枚举扩展**

```python
# src/core/domain/entities/search_task.py:17-23

class TaskType(Enum):
    """任务类型枚举"""
    SEARCH_KEYWORD = "search_keyword"        # 关键词搜索模式
    SEARCH_MULTILANG = "search_multilang"    # 多语言搜索模式
    CRAWL_WEBSITE = "crawl_website"          # 网站爬取模式
    SCRAPE_URL = "scrape_url"                # 单页面爬取模式
    MAP_SCRAPE_WEBSITE = "map_scrape_website"  # Map + Scrape 组合模式
    MAP_DETAIL = "map_detail"                # Map + Detail 详情页爬取模式（新增）
```

**Step 4: 添加 is_map_detail_mode 方法**

```python
# src/core/domain/entities/search_task.py (在 is_map_scrape_mode 方法后添加)

def is_map_detail_mode(self) -> bool:
    """判断是否为 Map + Detail 详情页爬取模式"""
    return self.get_task_type() == TaskType.MAP_DETAIL
```

**Step 5: 运行测试验证通过**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/domain/test_search_task.py -v -k "map_detail"`
Expected: PASS

**Step 6: 提交**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl
git add src/core/domain/entities/search_task.py tests/unit/domain/test_search_task.py
git commit -m "feat(search-task): add MAP_DETAIL task type for detail page crawling"
```

---

## Task 2: 实现 URL 规则过滤器

**Files:**
- Create: `src/services/map_detail/__init__.py`
- Create: `src/services/map_detail/url_filter.py`
- Test: `tests/unit/services/map_detail/test_url_filter.py`

**Step 1: 创建目录结构**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl
mkdir -p src/services/map_detail
mkdir -p tests/unit/services/map_detail
touch src/services/map_detail/__init__.py
touch tests/unit/services/map_detail/__init__.py
```

**Step 2: 写失败测试 - URL 过滤器**

```python
# tests/unit/services/map_detail/test_url_filter.py

import pytest
from src.services.map_detail.url_filter import UrlFilter, NAVIGATION_BLACKLIST


class TestUrlFilter:
    """URL 过滤器测试"""

    def test_blacklist_not_empty(self):
        """测试黑名单非空"""
        assert len(NAVIGATION_BLACKLIST) > 0

    def test_filter_navigation_pages(self):
        """测试过滤导航页"""
        urls = [
            "https://example.com/news/article-123",
            "https://example.com/category/politics",
            "https://example.com/tag/breaking",
            "https://example.com/post/456",
            "https://example.com/page/2",
            "https://example.com/login",
        ]
        filter = UrlFilter()
        passed, filtered = filter.filter_by_rules(urls)

        # 应该过滤掉 category, tag, page, login
        assert "https://example.com/news/article-123" in passed
        assert "https://example.com/post/456" in passed
        assert "https://example.com/category/politics" in filtered
        assert "https://example.com/tag/breaking" in filtered
        assert "https://example.com/page/2" in filtered
        assert "https://example.com/login" in filtered

    def test_filter_empty_list(self):
        """测试空列表"""
        filter = UrlFilter()
        passed, filtered = filter.filter_by_rules([])
        assert passed == []
        assert filtered == []

    def test_custom_blacklist(self):
        """测试自定义黑名单"""
        urls = ["https://example.com/custom-nav/page"]
        filter = UrlFilter(custom_blacklist=["/custom-nav/"])
        passed, filtered = filter.filter_by_rules(urls)
        assert len(passed) == 0
        assert len(filtered) == 1
```

**Step 3: 运行测试验证失败**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/map_detail/test_url_filter.py -v`
Expected: FAIL - "ModuleNotFoundError: No module named 'src.services.map_detail.url_filter'"

**Step 4: 实现 URL 过滤器**

```python
# src/services/map_detail/url_filter.py
"""
URL 规则过滤器

基于黑名单模式过滤导航页/列表页 URL
"""
from typing import List, Tuple, Optional
from urllib.parse import urlparse

from src.utils.logger import get_logger

logger = get_logger(__name__)


# 默认导航页黑名单
NAVIGATION_BLACKLIST = [
    # 导航类
    "/category/", "/categories/",
    "/tag/", "/tags/",
    "/page/", "/pages/",
    "/archive/", "/archives/",
    "/author/", "/authors/",

    # 列表类
    "/list/", "/index/",
    "/search/", "/browse/",

    # 功能类
    "/login/", "/register/", "/signup/",
    "/contact/", "/about/", "/faq/",
    "/privacy/", "/terms/", "/policy/",
]


class UrlFilter:
    """URL 规则过滤器"""

    def __init__(self, custom_blacklist: Optional[List[str]] = None):
        """
        初始化过滤器

        Args:
            custom_blacklist: 自定义黑名单模式列表
        """
        self.blacklist = NAVIGATION_BLACKLIST.copy()
        if custom_blacklist:
            self.blacklist.extend(custom_blacklist)

    def filter_by_rules(self, urls: List[str]) -> Tuple[List[str], List[str]]:
        """
        根据规则过滤 URL

        Args:
            urls: URL 列表

        Returns:
            Tuple[List[str], List[str]]: (通过的URL列表, 被过滤的URL列表)
        """
        if not urls:
            return [], []

        passed = []
        filtered = []

        for url in urls:
            if self._is_navigation_url(url):
                filtered.append(url)
            else:
                passed.append(url)

        logger.info(
            f"规则过滤完成: 通过 {len(passed)}, 过滤 {len(filtered)}, "
            f"总计 {len(urls)}"
        )
        return passed, filtered

    def _is_navigation_url(self, url: str) -> bool:
        """
        判断 URL 是否为导航页

        Args:
            url: URL 字符串

        Returns:
            bool: 是否为导航页
        """
        url_lower = url.lower()
        parsed = urlparse(url_lower)
        path = parsed.path

        # 检查是否匹配黑名单
        for pattern in self.blacklist:
            if pattern in path:
                return True

        return False
```

**Step 5: 更新 __init__.py**

```python
# src/services/map_detail/__init__.py
"""
Map + Detail 详情页爬取服务模块
"""
from .url_filter import UrlFilter, NAVIGATION_BLACKLIST

__all__ = [
    "UrlFilter",
    "NAVIGATION_BLACKLIST",
]
```

**Step 6: 运行测试验证通过**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/map_detail/test_url_filter.py -v`
Expected: PASS

**Step 7: 提交**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl
git add src/services/map_detail/ tests/unit/services/map_detail/
git commit -m "feat(map-detail): implement URL rule-based filter with blacklist"
```

---

## Task 3: 实现 LangGraph URL 判断工作流

**Files:**
- Create: `src/services/map_detail/langgraph_filter.py`
- Test: `tests/unit/services/map_detail/test_langgraph_filter.py`

**Step 1: 写失败测试 - LangGraph State 和 Prompt**

```python
# tests/unit/services/map_detail/test_langgraph_filter.py

import pytest
from typing import List


class TestUrlFilterState:
    """URL 过滤状态测试"""

    def test_state_structure(self):
        """测试状态结构"""
        from src.services.map_detail.langgraph_filter import UrlFilterState

        state: UrlFilterState = {
            "urls": ["https://example.com/article/1"],
            "detail_pages": [],
            "navigation_pages": [],
            "error": None,
        }
        assert "urls" in state
        assert "detail_pages" in state
        assert "navigation_pages" in state


class TestDetailPagePrompt:
    """详情页判断 Prompt 测试"""

    def test_prompt_template_exists(self):
        """测试 Prompt 模板存在"""
        from src.services.map_detail.langgraph_filter import DETAIL_PAGE_FILTER_PROMPT

        assert "详情页" in DETAIL_PAGE_FILTER_PROMPT
        assert "导航页" in DETAIL_PAGE_FILTER_PROMPT
        assert "{urls}" in DETAIL_PAGE_FILTER_PROMPT


class TestLangGraphUrlFilter:
    """LangGraph URL 过滤器测试"""

    @pytest.mark.asyncio
    async def test_filter_urls_empty_list(self):
        """测试空列表"""
        from src.services.map_detail.langgraph_filter import LangGraphUrlFilter

        filter = LangGraphUrlFilter()
        result = await filter.filter_urls([])

        assert result["detail_pages"] == []
        assert result["navigation_pages"] == []
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """测试批量处理逻辑"""
        from src.services.map_detail.langgraph_filter import LangGraphUrlFilter

        filter = LangGraphUrlFilter(batch_size=2)

        # 生成 5 个 URL（应分成 3 批）
        urls = [f"https://example.com/page/{i}" for i in range(5)]
        batches = filter._split_into_batches(urls)

        assert len(batches) == 3
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2
        assert len(batches[2]) == 1
```

**Step 2: 运行测试验证失败**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/map_detail/test_langgraph_filter.py -v`
Expected: FAIL - "ModuleNotFoundError"

**Step 3: 实现 LangGraph URL 过滤器**

```python
# src/services/map_detail/langgraph_filter.py
"""
LangGraph URL 判断工作流

使用 LLM 判断 URL 是详情页还是导航页
"""
import json
from typing import List, Optional, TypedDict

from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)


# LLM 判断 Prompt
DETAIL_PAGE_FILTER_PROMPT = """你是一个URL分类专家。请判断以下URL哪些是"详情页"，哪些是"导航页/列表页"。

详情页特征：
- 包含具体文章、新闻、产品的完整内容
- URL通常包含文章ID、日期、slug等标识
- 例如: /news/2024/01/article-title, /post/12345, /p/abc123

导航页/列表页特征：
- 展示多个内容的链接列表
- URL通常是分类、标签、首页等
- 例如: /news/, /blog/, /products/

请分析以下URL列表，返回JSON格式：
{{
    "detail_pages": ["url1", "url2", ...],
    "navigation_pages": ["url3", "url4", ...]
}}

只返回 JSON，不要返回其他内容。

URL列表：
{urls}
"""


class UrlFilterState(TypedDict):
    """URL 过滤状态"""
    urls: List[str]              # 输入的 URL 列表
    detail_pages: List[str]      # 判断为详情页的 URL
    navigation_pages: List[str]  # 判断为导航页的 URL
    error: Optional[str]         # 错误信息


class LangGraphUrlFilter:
    """
    LangGraph URL 过滤器

    使用 LLM 批量判断 URL 是否为详情页
    """

    def __init__(self, batch_size: int = 50):
        """
        初始化过滤器

        Args:
            batch_size: 每批发送给 LLM 的 URL 数量（避免 token 超限）
        """
        self.batch_size = batch_size
        self._llm = None

    def _get_llm(self):
        """获取 LLM 实例（延迟加载）"""
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            # 使用配置的 LLM
            self._llm = ChatOpenAI(
                model=settings.LLM_MODEL or "gpt-4o-mini",
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
                temperature=0,
            )
        return self._llm

    def _split_into_batches(self, urls: List[str]) -> List[List[str]]:
        """
        将 URL 列表分批

        Args:
            urls: URL 列表

        Returns:
            List[List[str]]: 分批后的 URL 列表
        """
        batches = []
        for i in range(0, len(urls), self.batch_size):
            batches.append(urls[i:i + self.batch_size])
        return batches

    async def filter_urls(self, urls: List[str]) -> UrlFilterState:
        """
        使用 LLM 过滤 URL

        Args:
            urls: URL 列表

        Returns:
            UrlFilterState: 过滤结果状态
        """
        if not urls:
            return UrlFilterState(
                urls=[],
                detail_pages=[],
                navigation_pages=[],
                error=None,
            )

        try:
            llm = self._get_llm()
            batches = self._split_into_batches(urls)

            all_detail_pages = []
            all_navigation_pages = []

            for i, batch in enumerate(batches):
                logger.info(f"LLM 处理第 {i+1}/{len(batches)} 批，共 {len(batch)} 个 URL")

                # 构建 prompt
                urls_text = "\n".join(f"- {url}" for url in batch)
                prompt = DETAIL_PAGE_FILTER_PROMPT.format(urls=urls_text)

                # 调用 LLM
                response = await llm.ainvoke(prompt)
                content = response.content

                # 解析 JSON 响应
                result = self._parse_llm_response(content, batch)
                all_detail_pages.extend(result.get("detail_pages", []))
                all_navigation_pages.extend(result.get("navigation_pages", []))

            logger.info(
                f"LLM 判断完成: 详情页 {len(all_detail_pages)}, "
                f"导航页 {len(all_navigation_pages)}"
            )

            return UrlFilterState(
                urls=urls,
                detail_pages=all_detail_pages,
                navigation_pages=all_navigation_pages,
                error=None,
            )

        except Exception as e:
            logger.error(f"LLM URL 过滤失败: {e}")
            return UrlFilterState(
                urls=urls,
                detail_pages=[],
                navigation_pages=[],
                error=str(e),
            )

    def _parse_llm_response(
        self,
        content: str,
        original_urls: List[str]
    ) -> dict:
        """
        解析 LLM 响应

        Args:
            content: LLM 响应内容
            original_urls: 原始 URL 列表（用于校验）

        Returns:
            dict: 解析后的结果
        """
        try:
            # 尝试提取 JSON
            content = content.strip()
            if content.startswith("```"):
                # 移除 markdown 代码块
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            result = json.loads(content)

            # 校验返回的 URL 是否在原始列表中
            detail_pages = [
                url for url in result.get("detail_pages", [])
                if url in original_urls
            ]
            navigation_pages = [
                url for url in result.get("navigation_pages", [])
                if url in original_urls
            ]

            return {
                "detail_pages": detail_pages,
                "navigation_pages": navigation_pages,
            }

        except json.JSONDecodeError as e:
            logger.warning(f"LLM 响应 JSON 解析失败: {e}, 内容: {content[:200]}")
            # 解析失败时，保守处理：全部标记为详情页
            return {
                "detail_pages": original_urls,
                "navigation_pages": [],
            }
```

**Step 4: 更新 __init__.py**

```python
# src/services/map_detail/__init__.py
"""
Map + Detail 详情页爬取服务模块
"""
from .url_filter import UrlFilter, NAVIGATION_BLACKLIST
from .langgraph_filter import (
    LangGraphUrlFilter,
    UrlFilterState,
    DETAIL_PAGE_FILTER_PROMPT,
)

__all__ = [
    "UrlFilter",
    "NAVIGATION_BLACKLIST",
    "LangGraphUrlFilter",
    "UrlFilterState",
    "DETAIL_PAGE_FILTER_PROMPT",
]
```

**Step 5: 运行测试验证通过**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/map_detail/test_langgraph_filter.py -v`
Expected: PASS

**Step 6: 提交**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl
git add src/services/map_detail/langgraph_filter.py tests/unit/services/map_detail/test_langgraph_filter.py
git commit -m "feat(map-detail): implement LangGraph URL filter with LLM classification"
```

---

## Task 4: 实现核心服务 - MapDetailService

**Files:**
- Create: `src/services/map_detail/service.py`
- Test: `tests/unit/services/map_detail/test_service.py`

**Step 1: 写失败测试 - 服务初始化和任务创建**

```python
# tests/unit/services/map_detail/test_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestMapDetailService:
    """MapDetailService 测试"""

    @pytest.fixture
    def mock_repos(self):
        """模拟仓储"""
        with patch('src.services.map_detail.service.SearchTaskRepository') as task_repo, \
             patch('src.services.map_detail.service.SearchResultRepository') as result_repo:
            task_repo_instance = AsyncMock()
            result_repo_instance = AsyncMock()
            task_repo.return_value = task_repo_instance
            result_repo.return_value = result_repo_instance
            yield {
                'task_repo': task_repo_instance,
                'result_repo': result_repo_instance,
            }

    @pytest.mark.asyncio
    async def test_create_task(self, mock_repos):
        """测试创建任务"""
        from src.services.map_detail.service import MapDetailService
        from src.core.domain.entities.search_task import SearchTask

        mock_repos['task_repo'].save.return_value = None

        service = MapDetailService()
        service.task_repository = mock_repos['task_repo']

        task = await service.create_task(
            source_url="https://example.com",
            created_by="user123",
            enable_ai_processing=True,
        )

        assert task.task_type == "map_detail"
        assert task.crawl_url == "https://example.com"
        assert task.created_by == "user123"
        mock_repos['task_repo'].save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task_stats(self, mock_repos):
        """测试获取任务统计"""
        from src.services.map_detail.service import MapDetailService
        from src.core.domain.entities.search_task import SearchTask, TaskType

        mock_task = SearchTask(
            id="task123",
            name="Test Task",
            task_type=TaskType.MAP_DETAIL.value,
            crawl_url="https://example.com",
            crawl_config={
                "stats": {
                    "total_urls_found": 100,
                    "urls_after_dedup": 80,
                }
            }
        )
        mock_repos['task_repo'].get_by_id.return_value = mock_task

        service = MapDetailService()
        service.task_repository = mock_repos['task_repo']

        stats = await service.get_task_stats("task123")

        assert stats["total_urls_found"] == 100
        assert stats["urls_after_dedup"] == 80
```

**Step 2: 运行测试验证失败**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/map_detail/test_service.py -v`
Expected: FAIL - "ModuleNotFoundError"

**Step 3: 实现 MapDetailService**

```python
# src/services/map_detail/service.py
"""
Map + Detail 详情页爬取服务

核心业务逻辑：
1. 调用 Firecrawl Map API 获取所有链接
2. URL 去重（基于 search_results 表）
3. 规则过滤（黑名单模式）
4. LLM 判断（剩余 URL）
5. Firecrawl Scrape API 批量爬取
6. AI 处理（可选）
7. 存储到 search_results 表
"""
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List

from src.core.domain.entities.search_task import SearchTask, TaskType, TaskStatus
from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.infrastructure.database.repositories import SearchTaskRepository, SearchResultRepository
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.services.map_detail.url_filter import UrlFilter
from src.services.map_detail.langgraph_filter import LangGraphUrlFilter
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MapDetailService:
    """
    Map + Detail 详情页爬取服务

    负责协调 Map API → URL 过滤 → Scrape API → 存储 的完整流程
    """

    def __init__(self):
        self.task_repository: Optional[SearchTaskRepository] = None
        self.result_repository: Optional[SearchResultRepository] = None
        self.crawler: Optional[FirecrawlAdapter] = None
        self.url_filter: Optional[UrlFilter] = None
        self.llm_filter: Optional[LangGraphUrlFilter] = None

    async def _ensure_initialized(self):
        """确保服务已初始化"""
        if self.task_repository is None:
            self.task_repository = SearchTaskRepository()
        if self.result_repository is None:
            self.result_repository = SearchResultRepository()
        if self.crawler is None:
            self.crawler = FirecrawlAdapter()
        if self.url_filter is None:
            self.url_filter = UrlFilter()
        if self.llm_filter is None:
            self.llm_filter = LangGraphUrlFilter()

    async def create_task(
        self,
        source_url: str,
        created_by: str,
        name: Optional[str] = None,
        enable_ai_processing: bool = True,
        map_limit: int = 500,
        scrape_concurrency: int = 10,
        max_retries: int = 5,
    ) -> SearchTask:
        """
        创建 Map + Detail 爬取任务

        Args:
            source_url: 目标 URL
            created_by: 创建者用户 ID
            name: 任务名称（可选）
            enable_ai_processing: 是否启用 AI 处理
            map_limit: Map API 最大链接数
            scrape_concurrency: Scrape 并发数
            max_retries: 失败重试次数

        Returns:
            SearchTask: 创建的任务实体
        """
        await self._ensure_initialized()

        task = SearchTask.create_with_secure_id(
            name=name or f"Map+Detail: {source_url[:50]}",
            task_type=TaskType.MAP_DETAIL.value,
            crawl_url=source_url,
            created_by=created_by,
            status=TaskStatus.PENDING,
            crawl_config={
                "enable_ai_processing": enable_ai_processing,
                "map_limit": map_limit,
                "scrape_concurrency": scrape_concurrency,
                "max_retries": max_retries,
                "stats": {
                    "total_urls_found": 0,
                    "urls_after_dedup": 0,
                    "urls_after_filter": 0,
                    "urls_after_llm": 0,
                    "urls_scraped": 0,
                    "urls_failed": 0,
                },
            },
        )

        await self.task_repository.save(task)
        logger.info(f"创建 Map+Detail 任务: {task.id}, URL: {source_url}")

        return task

    async def execute(self, task_id: str) -> Dict[str, Any]:
        """
        执行 Map + Detail 爬取任务

        Args:
            task_id: 任务 ID

        Returns:
            Dict[str, Any]: 执行结果统计
        """
        await self._ensure_initialized()

        task = await self.task_repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if not task.is_map_detail_mode():
            raise ValueError(f"任务类型错误: {task.task_type}")

        try:
            # 更新任务状态为执行中
            task.status = TaskStatus.RUNNING
            task.last_executed_at = datetime.utcnow()
            await self.task_repository.update(task)

            config = task.crawl_config or {}
            stats = config.get("stats", {})

            # Step 1: Map API 获取所有链接
            logger.info(f"[{task_id}] Step 1: 调用 Map API")
            map_results = await self.crawler.map(
                url=task.crawl_url,
                limit=config.get("map_limit", 500),
            )
            urls = [item["url"] for item in map_results if item.get("url")]
            stats["total_urls_found"] = len(urls)
            logger.info(f"[{task_id}] Map API 发现 {len(urls)} 个 URL")

            # Step 2: URL 去重
            logger.info(f"[{task_id}] Step 2: URL 去重")
            existing_urls = await self.result_repository.check_existing_urls(task_id, urls)
            urls = [url for url in urls if url not in existing_urls]
            stats["urls_after_dedup"] = len(urls)
            logger.info(f"[{task_id}] 去重后剩余 {len(urls)} 个 URL")

            if not urls:
                logger.info(f"[{task_id}] 无新 URL 需要处理")
                task.status = TaskStatus.COMPLETED
                task.record_execution(success=True, results_count=0)
                config["stats"] = stats
                task.crawl_config = config
                await self.task_repository.update(task)
                return stats

            # Step 3: 规则过滤
            logger.info(f"[{task_id}] Step 3: 规则过滤")
            urls, filtered_urls = self.url_filter.filter_by_rules(urls)
            stats["urls_after_filter"] = len(urls)
            logger.info(f"[{task_id}] 规则过滤后剩余 {len(urls)} 个 URL")

            # Step 4: LLM 判断
            logger.info(f"[{task_id}] Step 4: LLM 判断")
            llm_result = await self.llm_filter.filter_urls(urls)
            detail_urls = llm_result["detail_pages"]
            stats["urls_after_llm"] = len(detail_urls)
            logger.info(f"[{task_id}] LLM 判断后 {len(detail_urls)} 个详情页")

            if not detail_urls:
                logger.info(f"[{task_id}] 无详情页需要爬取")
                task.status = TaskStatus.COMPLETED
                task.record_execution(success=True, results_count=0)
                config["stats"] = stats
                task.crawl_config = config
                await self.task_repository.update(task)
                return stats

            # Step 5: 批量 Scrape
            logger.info(f"[{task_id}] Step 5: 批量 Scrape")
            concurrency = config.get("scrape_concurrency", 10)
            results = await self._batch_scrape(
                task_id=task_id,
                urls=detail_urls,
                concurrency=concurrency,
                max_retries=config.get("max_retries", 5),
            )

            stats["urls_scraped"] = results["success_count"]
            stats["urls_failed"] = results["failed_count"]

            # Step 6: AI 处理（可选，未来实现）
            if config.get("enable_ai_processing", True):
                logger.info(f"[{task_id}] Step 6: AI 处理（待实现）")
                # TODO: 调用 AI 服务进行翻译/分类

            # 更新任务状态
            task.status = TaskStatus.COMPLETED
            task.record_execution(
                success=True,
                results_count=stats["urls_scraped"],
            )
            config["stats"] = stats
            task.crawl_config = config
            await self.task_repository.update(task)

            logger.info(f"[{task_id}] 任务完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"[{task_id}] 任务执行失败: {e}")
            task.status = TaskStatus.FAILED
            task.record_execution(success=False, error_message=str(e))
            await self.task_repository.update(task)
            raise

    async def _batch_scrape(
        self,
        task_id: str,
        urls: List[str],
        concurrency: int,
        max_retries: int,
    ) -> Dict[str, Any]:
        """
        批量爬取 URL

        Args:
            task_id: 任务 ID
            urls: URL 列表
            concurrency: 并发数
            max_retries: 最大重试次数

        Returns:
            Dict[str, Any]: 爬取统计
        """
        success_count = 0
        failed_count = 0

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(concurrency)

        async def scrape_one(url: str) -> bool:
            async with semaphore:
                for attempt in range(max_retries):
                    try:
                        result = await self.crawler.scrape(url)

                        # 保存结果
                        search_result = SearchResult(
                            task_id=task_id,
                            url=url,
                            title=result.metadata.get("title", ""),
                            snippet=result.content[:500] if result.content else "",
                            markdown_content=result.markdown,
                            source=result.metadata.get("source", "firecrawl"),
                            language=result.metadata.get("language", ""),
                            published_date=result.metadata.get("published_date"),
                            status=ResultStatus.PENDING,
                            metadata={
                                "source_type": "map_detail",
                                "crawl_method": "scrape",
                            },
                        )
                        await self.result_repository.save(search_result)

                        logger.debug(f"[{task_id}] 成功爬取: {url}")
                        return True

                    except Exception as e:
                        logger.warning(
                            f"[{task_id}] 爬取失败 (尝试 {attempt+1}/{max_retries}): "
                            f"{url}, 错误: {e}"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # 指数退避

                return False

        # 并发执行
        tasks = [scrape_one(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if result is True:
                success_count += 1
            else:
                failed_count += 1

        return {
            "success_count": success_count,
            "failed_count": failed_count,
        }

    async def get_task_stats(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务统计信息

        Args:
            task_id: 任务 ID

        Returns:
            Dict[str, Any]: 任务统计
        """
        await self._ensure_initialized()

        task = await self.task_repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        config = task.crawl_config or {}
        return config.get("stats", {})


# 全局服务实例
map_detail_service = MapDetailService()
```

**Step 4: 更新 __init__.py**

```python
# src/services/map_detail/__init__.py
"""
Map + Detail 详情页爬取服务模块
"""
from .url_filter import UrlFilter, NAVIGATION_BLACKLIST
from .langgraph_filter import (
    LangGraphUrlFilter,
    UrlFilterState,
    DETAIL_PAGE_FILTER_PROMPT,
)
from .service import MapDetailService, map_detail_service

__all__ = [
    "UrlFilter",
    "NAVIGATION_BLACKLIST",
    "LangGraphUrlFilter",
    "UrlFilterState",
    "DETAIL_PAGE_FILTER_PROMPT",
    "MapDetailService",
    "map_detail_service",
]
```

**Step 5: 运行测试验证通过**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/map_detail/test_service.py -v`
Expected: PASS

**Step 6: 提交**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl
git add src/services/map_detail/service.py tests/unit/services/map_detail/test_service.py
git commit -m "feat(map-detail): implement core MapDetailService with full workflow"
```

---

## Task 5: 实现 API 端点

**Files:**
- Create: `src/api/v1/endpoints/map_detail.py`
- Modify: `src/api/v1/router.py`
- Test: `tests/unit/api/test_map_detail.py`

**Step 1: 写失败测试 - API 端点**

```python
# tests/unit/api/test_map_detail.py

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


class TestMapDetailAPI:
    """Map Detail API 端点测试"""

    @pytest.fixture
    def mock_service(self):
        """模拟服务"""
        with patch('src.api.v1.endpoints.map_detail.map_detail_service') as mock:
            yield mock

    @pytest.fixture
    def client(self, mock_service):
        """测试客户端"""
        from src.api.v1.endpoints.map_detail import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/crawl")
        return TestClient(app)

    def test_create_task_endpoint_exists(self, client, mock_service):
        """测试创建任务端点存在"""
        mock_service.create_task = AsyncMock()

        # 应该返回 401/403（未认证），而不是 404
        response = client.post(
            "/api/v1/crawl/map-detail",
            json={"source_url": "https://example.com"}
        )
        # 没有认证时可能返回 401 或端点存在返回其他状态码
        assert response.status_code != 404

    def test_get_task_status_endpoint_exists(self, client, mock_service):
        """测试查询任务状态端点存在"""
        response = client.get("/api/v1/crawl/map-detail/task123")
        assert response.status_code != 404
```

**Step 2: 运行测试验证失败**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/api/test_map_detail.py -v`
Expected: FAIL - "ModuleNotFoundError"

**Step 3: 实现 API 端点**

```python
# src/api/v1/endpoints/map_detail.py
"""
Map + Detail 详情页爬取 API 端点

API:
  POST /api/v1/crawl/map-detail          - 创建爬取任务
  GET  /api/v1/crawl/map-detail/{task_id} - 查询任务状态
  GET  /api/v1/crawl/map-detail/{task_id}/results - 查询任务结果

权限:
  - info:create: 创建任务
"""
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.api.v1.auth import require_permissions
from src.services.map_detail import map_detail_service
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class CreateMapDetailTaskRequest(BaseModel):
    """创建任务请求"""
    source_url: str = Field(..., description="目标 URL")
    name: Optional[str] = Field(None, description="任务名称")
    enable_ai_processing: bool = Field(True, description="是否启用 AI 处理")
    map_limit: int = Field(500, ge=1, le=5000, description="Map API 最大链接数")
    scrape_concurrency: int = Field(10, ge=1, le=50, description="Scrape 并发数")
    max_retries: int = Field(5, ge=1, le=10, description="失败重试次数")

    class Config:
        json_schema_extra = {
            "example": {
                "source_url": "https://example.com/news",
                "enable_ai_processing": True,
                "map_limit": 500,
                "scrape_concurrency": 10,
            }
        }


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    source_url: str
    stats: Dict[str, int]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]


class CreateTaskResponse(BaseModel):
    """创建任务响应"""
    task_id: str
    status: str
    message: str


# ==================== API 端点 ====================

@router.post("/map-detail", response_model=CreateTaskResponse)
async def create_map_detail_task(
    request: CreateMapDetailTaskRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_permissions("info:create")),
):
    """
    创建 Map + Detail 详情页爬取任务

    使用 Firecrawl Map API 发现网站所有链接，通过规则过滤和 LLM 判断
    筛选出详情页，批量爬取并存储。

    权限: info:create
    """
    try:
        task = await map_detail_service.create_task(
            source_url=request.source_url,
            created_by=current_user.get("id", ""),
            name=request.name,
            enable_ai_processing=request.enable_ai_processing,
            map_limit=request.map_limit,
            scrape_concurrency=request.scrape_concurrency,
            max_retries=request.max_retries,
        )

        # 后台执行任务
        background_tasks.add_task(_execute_task_background, task.id)

        return CreateTaskResponse(
            task_id=task.id,
            status=task.status.value,
            message="任务已创建，正在后台执行",
        )

    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _execute_task_background(task_id: str):
    """后台执行任务"""
    try:
        await map_detail_service.execute(task_id)
    except Exception as e:
        logger.error(f"后台任务执行失败: {task_id}, 错误: {e}")


@router.get("/map-detail/{task_id}", response_model=TaskStatusResponse)
async def get_map_detail_task_status(
    task_id: str,
    current_user: Dict[str, Any] = Depends(require_permissions("info:create")),
):
    """
    查询 Map + Detail 任务状态

    权限: info:create
    """
    try:
        from src.infrastructure.database.repositories import SearchTaskRepository

        repo = SearchTaskRepository()
        task = await repo.get_by_id(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        config = task.crawl_config or {}
        stats = config.get("stats", {})

        return TaskStatusResponse(
            task_id=task.id,
            status=task.status.value,
            source_url=task.crawl_url or "",
            stats=stats,
            created_at=task.created_at.isoformat() if task.created_at else "",
            started_at=task.last_executed_at.isoformat() if task.last_executed_at else None,
            completed_at=task.updated_at.isoformat() if task.status.value == "completed" else None,
            error_message=task.last_error,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/map-detail/{task_id}/results")
async def get_map_detail_task_results(
    task_id: str,
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: Dict[str, Any] = Depends(require_permissions("info:create")),
):
    """
    查询 Map + Detail 任务结果

    权限: info:create
    """
    try:
        from src.infrastructure.database.repositories import SearchResultRepository

        repo = SearchResultRepository()
        results, total = await repo.find_by_task_id_paginated(
            task_id=task_id,
            page=page,
            page_size=limit,
        )

        return {
            "task_id": task_id,
            "total": total,
            "page": page,
            "limit": limit,
            "results": [
                {
                    "id": str(r.id),
                    "url": r.url,
                    "title": r.title,
                    "snippet": r.snippet,
                    "status": r.status.value if hasattr(r.status, 'value') else r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in results
            ],
        }

    except Exception as e:
        logger.error(f"查询任务结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 4: 注册路由**

```python
# src/api/v1/router.py (添加到现有导入和路由注册中)

# 在导入部分添加
from src.api.v1.endpoints import map_detail

# 在路由注册部分添加
# Map + Detail 爬取 - 需要 info:create 权限
api_router.include_router(
    map_detail.router,
    prefix="/crawl",
    tags=["🕷️ Map+Detail 详情页爬取"],
)
```

**Step 5: 运行测试验证通过**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/api/test_map_detail.py -v`
Expected: PASS

**Step 6: 提交**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl
git add src/api/v1/endpoints/map_detail.py src/api/v1/router.py tests/unit/api/test_map_detail.py
git commit -m "feat(api): add Map+Detail crawl API endpoints"
```

---

## Task 6: 集成测试和最终验证

**Files:**
- Test: `tests/integration/test_map_detail_integration.py`

**Step 1: 写集成测试**

```python
# tests/integration/test_map_detail_integration.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestMapDetailIntegration:
    """Map + Detail 集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_mock(self):
        """测试完整工作流（模拟）"""
        from src.services.map_detail.service import MapDetailService
        from src.core.domain.entities.search_task import SearchTask, TaskType

        # 模拟依赖
        with patch.object(MapDetailService, '_ensure_initialized', new_callable=AsyncMock):
            service = MapDetailService()

            # 模拟仓储
            service.task_repository = AsyncMock()
            service.result_repository = AsyncMock()
            service.crawler = AsyncMock()
            service.url_filter = MagicMock()
            service.llm_filter = AsyncMock()

            # 设置模拟返回值
            mock_task = SearchTask(
                id="test123",
                name="Test",
                task_type=TaskType.MAP_DETAIL.value,
                crawl_url="https://example.com",
                crawl_config={"stats": {}},
            )
            service.task_repository.get_by_id.return_value = mock_task
            service.task_repository.save.return_value = None
            service.task_repository.update.return_value = None

            # Map API 返回
            service.crawler.map.return_value = [
                {"url": "https://example.com/article/1", "title": "Article 1"},
                {"url": "https://example.com/article/2", "title": "Article 2"},
            ]

            # URL 去重
            service.result_repository.check_existing_urls.return_value = set()

            # 规则过滤
            service.url_filter.filter_by_rules.return_value = (
                ["https://example.com/article/1", "https://example.com/article/2"],
                [],
            )

            # LLM 判断
            service.llm_filter.filter_urls.return_value = {
                "detail_pages": ["https://example.com/article/1"],
                "navigation_pages": ["https://example.com/article/2"],
                "error": None,
            }

            # Scrape
            service.crawler.scrape.return_value = MagicMock(
                content="Test content",
                markdown="# Test",
                metadata={"title": "Test Article"},
            )
            service.result_repository.save.return_value = None

            # 执行
            stats = await service.execute("test123")

            # 验证
            assert service.crawler.map.called
            assert service.url_filter.filter_by_rules.called
            assert service.llm_filter.filter_urls.called
```

**Step 2: 运行集成测试**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/integration/test_map_detail_integration.py -v`
Expected: PASS

**Step 3: 运行所有相关测试**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/map_detail/ tests/unit/api/test_map_detail.py tests/integration/test_map_detail_integration.py -v`
Expected: All PASS

**Step 4: 提交**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl
git add tests/integration/test_map_detail_integration.py
git commit -m "test(map-detail): add integration tests for full workflow"
```

---

## Task 7: 定时任务集成（P2）

**Files:**
- Modify: `src/services/task_scheduler.py`
- Test: `tests/unit/services/test_scheduler_map_detail.py`

**Step 1: 写失败测试 - 调度器支持**

```python
# tests/unit/services/test_scheduler_map_detail.py

import pytest
from unittest.mock import AsyncMock, patch


class TestSchedulerMapDetailSupport:
    """调度器 Map+Detail 支持测试"""

    @pytest.mark.asyncio
    async def test_execute_map_detail_task(self):
        """测试调度器执行 Map+Detail 任务"""
        from src.core.domain.entities.search_task import SearchTask, TaskType

        mock_task = SearchTask(
            id="task123",
            name="Test Map Detail",
            task_type=TaskType.MAP_DETAIL.value,
            crawl_url="https://example.com",
        )

        with patch('src.services.task_scheduler.map_detail_service') as mock_service:
            mock_service.execute = AsyncMock(return_value={"urls_scraped": 10})

            from src.services.task_scheduler import TaskSchedulerService
            scheduler = TaskSchedulerService()

            # 应该调用 map_detail_service
            await scheduler._execute_map_detail_task(mock_task)
            mock_service.execute.assert_called_once_with(mock_task.id)
```

**Step 2: 运行测试验证失败**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/test_scheduler_map_detail.py -v`
Expected: FAIL

**Step 3: 修改调度器支持 Map+Detail**

在 `src/services/task_scheduler.py` 中添加 Map+Detail 任务执行方法：

```python
# 在 TaskSchedulerService 类中添加方法

async def _execute_map_detail_task(self, task: SearchTask) -> Dict[str, Any]:
    """
    执行 Map+Detail 任务

    Args:
        task: 搜索任务实体

    Returns:
        Dict[str, Any]: 执行结果统计
    """
    from src.services.map_detail import map_detail_service

    logger.info(f"[调度器] 执行 Map+Detail 任务: {task.id}")
    return await map_detail_service.execute(task.id)
```

并在任务执行分发逻辑中添加对 `MAP_DETAIL` 类型的处理。

**Step 4: 运行测试验证通过**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl && python -m pytest tests/unit/services/test_scheduler_map_detail.py -v`
Expected: PASS

**Step 5: 提交**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl
git add src/services/task_scheduler.py tests/unit/services/test_scheduler_map_detail.py
git commit -m "feat(scheduler): add Map+Detail task execution support"
```

---

## 完成检查清单

- [ ] Task 1: 添加 MAP_DETAIL 任务类型
- [ ] Task 2: 实现 URL 规则过滤器
- [ ] Task 3: 实现 LangGraph URL 判断工作流
- [ ] Task 4: 实现核心服务 MapDetailService
- [ ] Task 5: 实现 API 端点
- [ ] Task 6: 集成测试和最终验证
- [ ] Task 7: 定时任务集成（P2）

## 执行命令汇总

```bash
# 进入工作目录
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/map-detail-crawl

# 运行所有 Map+Detail 相关测试
python -m pytest tests/unit/services/map_detail/ tests/unit/api/test_map_detail.py tests/integration/test_map_detail_integration.py -v

# 运行完整测试套件（排除已知失败）
python -m pytest --ignore=tests/unit/workflow/ -v

# 代码检查
python -m ruff check src/services/map_detail/
python -m mypy src/services/map_detail/
```

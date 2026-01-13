"""搜索结果过滤器

v4.5.1: 实现多层过滤策略
- 黑名单域名过滤（低质量来源）
- 中文内容优先过滤
- 白名单域名加权（高质量来源）
- URL 去重
"""

import logging
import re
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse

from ..state import SearchState, SearchResult

logger = logging.getLogger(__name__)


class ResultFilter:
    """搜索结果过滤器

    实现三层过滤策略：
    1. 黑名单过滤：移除低质量来源
    2. 中文内容检测：优先保留中文相关内容
    3. 白名单加权：提升高质量来源的分数
    """

    # 黑名单域名（低质量或不相关来源）
    DOMAIN_BLACKLIST: Set[str] = {
        # 社交媒体（内容质量不稳定）
        "facebook.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "tiktok.com",
        "weibo.com",
        "zhihu.com",

        # 问答/论坛（非权威来源）
        "quora.com",
        "reddit.com",
        "stackexchange.com",
        "stackoverflow.com",

        # 视频平台（难以提取文本）
        "youtube.com",
        "youtu.be",
        "bilibili.com",
        "v.qq.com",

        # 百科类（二手信息）
        "wikipedia.org",
        "baike.baidu.com",

        # 内容农场/低质量
        "medium.com",
        "substack.com",
        "blogspot.com",
        "wordpress.com",

        # 购物/商业
        "amazon.com",
        "taobao.com",
        "jd.com",
        "alibaba.com",

        # 其他低相关性
        "pinterest.com",
        "linkedin.com",
        "indeed.com",
    }

    # 白名单域名（高质量来源 - 分数加权）
    DOMAIN_WHITELIST: Dict[str, float] = {
        # 中国官方媒体 (权重: 1.3)
        "xinhuanet.com": 1.3,
        "people.com.cn": 1.3,
        "chinadaily.com.cn": 1.3,
        "cctv.com": 1.3,
        "gov.cn": 1.3,

        # 国际权威通讯社 (权重: 1.25)
        "reuters.com": 1.25,
        "apnews.com": 1.25,
        "afp.com": 1.25,

        # 国际权威媒体 (权重: 1.2)
        "nytimes.com": 1.2,
        "washingtonpost.com": 1.2,
        "bbc.com": 1.2,
        "bbc.co.uk": 1.2,
        "theguardian.com": 1.2,
        "economist.com": 1.2,
        "ft.com": 1.2,
        "wsj.com": 1.2,

        # 日本权威媒体 (权重: 1.2)
        "nhk.or.jp": 1.2,
        "asahi.com": 1.2,
        "nikkei.com": 1.2,
        "yomiuri.co.jp": 1.2,
        "mainichi.jp": 1.2,

        # 韩国权威媒体 (权重: 1.2)
        "yna.co.kr": 1.2,
        "koreaherald.com": 1.2,
        "koreatimes.co.kr": 1.2,

        # 智库 (权重: 1.15)
        "brookings.edu": 1.15,
        "cfr.org": 1.15,
        "rand.org": 1.15,
        "csis.org": 1.15,
        "heritage.org": 1.15,
        "carnegieendowment.org": 1.15,

        # 学术机构 (权重: 1.1)
        ".edu": 1.1,  # 通用学术域名
        ".ac.": 1.1,  # 学术域名

        # 政府网站 (权重: 1.2)
        ".gov": 1.2,
        ".gov.cn": 1.3,
        ".go.jp": 1.2,
        ".go.kr": 1.2,
    }

    # 中文内容检测正则
    CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]')

    def __init__(
        self,
        enable_blacklist: bool = True,
        enable_chinese_priority: bool = True,
        enable_whitelist_boost: bool = True,
        chinese_content_min_ratio: float = 0.1,
        min_content_length: int = 50,
    ):
        """初始化过滤器

        Args:
            enable_blacklist: 是否启用黑名单过滤
            enable_chinese_priority: 是否启用中文内容优先
            enable_whitelist_boost: 是否启用白名单加权
            chinese_content_min_ratio: 中文字符最小占比（用于判断是否为中文内容）
            min_content_length: 最小内容长度（过滤空内容）
        """
        self.enable_blacklist = enable_blacklist
        self.enable_chinese_priority = enable_chinese_priority
        self.enable_whitelist_boost = enable_whitelist_boost
        self.chinese_content_min_ratio = chinese_content_min_ratio
        self.min_content_length = min_content_length

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行过滤

        作为 LangGraph 节点调用

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")
        aggregated_results = state.get("aggregated_results", [])
        target_languages = state.get("target_languages", ["zh", "en"])

        logger.info(
            f"[user:{user_id}] ResultFilter starting, "
            f"input_count={len(aggregated_results)}, "
            f"target_languages={target_languages}"
        )

        # 执行过滤
        filtered_results, stats = self.filter_results(
            results=aggregated_results,
            target_languages=target_languages,
            user_id=user_id,
        )

        logger.info(
            f"[user:{user_id}] ResultFilter complete: "
            f"{len(aggregated_results)} → {len(filtered_results)} results, "
            f"stats={stats}"
        )

        return {
            "aggregated_results": filtered_results,
            "filter_statistics": stats,
        }

    def filter_results(
        self,
        results: List[Dict[str, Any]],
        target_languages: Optional[List[str]] = None,
        user_id: str = "",
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """过滤搜索结果

        Args:
            results: 原始搜索结果列表
            target_languages: 目标语言列表
            user_id: 用户ID（用于日志）

        Returns:
            (过滤后的结果列表, 统计信息)
        """
        target_languages = target_languages or ["zh", "en"]

        stats = {
            "input_count": len(results),
            "blacklist_filtered": 0,
            "empty_content_filtered": 0,
            "duplicate_filtered": 0,
            "whitelist_boosted": 0,
            "chinese_content_count": 0,
            "output_count": 0,
        }

        filtered = []
        seen_urls: Set[str] = set()

        for result in results:
            url = result.get("url", "")
            domain = self._extract_domain(url)

            # 1. URL 去重
            normalized_url = self._normalize_url(url)
            if normalized_url in seen_urls:
                stats["duplicate_filtered"] += 1
                continue
            seen_urls.add(normalized_url)

            # 2. 黑名单过滤
            if self.enable_blacklist and self._is_blacklisted(domain):
                stats["blacklist_filtered"] += 1
                logger.debug(f"[user:{user_id}] Blacklist filtered: {domain}")
                continue

            # 3. 空内容过滤
            content = result.get("markdown_content", "") or result.get("snippet", "") or ""
            if len(content) < self.min_content_length:
                stats["empty_content_filtered"] += 1
                continue

            # 4. 白名单加权
            if self.enable_whitelist_boost:
                boost = self._get_whitelist_boost(domain)
                if boost > 1.0:
                    original_score = result.get("final_score", 0.5)
                    result["final_score"] = min(original_score * boost, 1.0)
                    result["whitelist_boosted"] = True
                    stats["whitelist_boosted"] += 1

            # 5. 中文内容标记
            if self._contains_chinese(content):
                result["has_chinese_content"] = True
                stats["chinese_content_count"] += 1

            filtered.append(result)

        # 6. 如果目标语言包含中文，优先排序中文内容
        if self.enable_chinese_priority and "zh" in target_languages:
            filtered = self._prioritize_chinese_content(filtered)

        stats["output_count"] = len(filtered)

        return filtered, stats

    def _extract_domain(self, url: str) -> str:
        """提取域名

        Args:
            url: URL 字符串

        Returns:
            域名（不含 www）
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def _normalize_url(self, url: str) -> str:
        """标准化 URL（用于去重）

        移除查询参数、片段等

        Args:
            url: 原始 URL

        Returns:
            标准化后的 URL
        """
        try:
            parsed = urlparse(url)
            # 只保留 scheme + netloc + path
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            # 移除尾部斜杠
            return normalized.rstrip("/").lower()
        except Exception:
            return url.lower()

    def _is_blacklisted(self, domain: str) -> bool:
        """检查域名是否在黑名单中

        Args:
            domain: 域名

        Returns:
            是否被黑名单
        """
        if not domain:
            return False

        # 精确匹配
        if domain in self.DOMAIN_BLACKLIST:
            return True

        # 子域名匹配（如 news.ycombinator.com）
        for blacklisted in self.DOMAIN_BLACKLIST:
            if domain.endswith(f".{blacklisted}"):
                return True

        return False

    def _get_whitelist_boost(self, domain: str) -> float:
        """获取白名单加权系数

        Args:
            domain: 域名

        Returns:
            加权系数（1.0 表示无加权）
        """
        if not domain:
            return 1.0

        # 精确匹配
        if domain in self.DOMAIN_WHITELIST:
            return self.DOMAIN_WHITELIST[domain]

        # 通用后缀匹配（如 .edu, .gov）
        for suffix, boost in self.DOMAIN_WHITELIST.items():
            if suffix.startswith(".") and domain.endswith(suffix):
                return boost

        # 子域名匹配
        for whitelisted, boost in self.DOMAIN_WHITELIST.items():
            if not whitelisted.startswith(".") and domain.endswith(f".{whitelisted}"):
                return boost

        return 1.0

    def _contains_chinese(self, text: str) -> bool:
        """检测文本是否包含足够的中文字符

        Args:
            text: 文本内容

        Returns:
            是否为中文内容
        """
        if not text:
            return False

        chinese_chars = len(self.CHINESE_PATTERN.findall(text))
        total_chars = len(text.replace(" ", "").replace("\n", ""))

        if total_chars == 0:
            return False

        ratio = chinese_chars / total_chars
        return ratio >= self.chinese_content_min_ratio

    def _prioritize_chinese_content(
        self,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """优先排序中文内容

        将有中文内容的结果排在前面，同时保持原有分数排序

        Args:
            results: 结果列表

        Returns:
            重新排序后的结果列表
        """
        chinese_results = []
        other_results = []

        for result in results:
            if result.get("has_chinese_content", False):
                chinese_results.append(result)
            else:
                other_results.append(result)

        # 各自按分数排序
        chinese_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        other_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)

        # 中文内容优先，但不完全覆盖（取前 70% 中文 + 30% 其他）
        total = len(results)
        chinese_quota = int(total * 0.7)

        prioritized = chinese_results[:chinese_quota]
        prioritized.extend(other_results)
        prioritized.extend(chinese_results[chinese_quota:])

        return prioritized


def create_result_filter(
    enable_blacklist: bool = True,
    enable_chinese_priority: bool = True,
    enable_whitelist_boost: bool = True,
) -> ResultFilter:
    """创建结果过滤器

    Args:
        enable_blacklist: 是否启用黑名单过滤
        enable_chinese_priority: 是否启用中文内容优先
        enable_whitelist_boost: 是否启用白名单加权

    Returns:
        ResultFilter 实例
    """
    return ResultFilter(
        enable_blacklist=enable_blacklist,
        enable_chinese_priority=enable_chinese_priority,
        enable_whitelist_boost=enable_whitelist_boost,
    )

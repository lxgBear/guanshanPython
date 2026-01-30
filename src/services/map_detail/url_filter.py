"""
URL 规则过滤器

使用黑名单模式过滤导航页和列表页链接
"""

from dataclasses import dataclass
from typing import List, Set, Optional
from urllib.parse import urlparse, urljoin
import re

from src.utils.logger import get_logger

logger = get_logger(__name__)


class NavigationBlacklist:
    """导航页 URL 黑名单规则"""

    # 导航类路径模式
    NAVIGATION_PATTERNS = [
        # 导航类
        r'/category\b',
        r'/categories\b',
        r'/tag\b',
        r'/tags\b',
        r'/page\b',
        r'/pages\b',
        r'/archive\b',
        r'/archives\b',
        r'/author\b',
        r'/authors\b',

        # 列表类
        r'/list\b',
        r'/index\b',
        r'/search\b',
        r'/browse\b',

        # 专题/话题聚合类
        r'/topics\b',
        r'/topic\b',
        r'/collections\b',
        r'/collection\b',
        r'/series\b',
        r'/programmes\b',

        # 直播/实时类
        r'/live\b',
        r'/stream\b',
        r'/watch\b',

        # 功能类
        r'/login\b',
        r'/register\b',
        r'/signup\b',
        r'/contact\b',
        r'/about\b',
        r'/faq\b',
        r'/privacy\b',
        r'/terms\b',
        r'/policy\b',

        # 新增：媒体中心类
        r'/media\b',
        r'/videos\b',
        r'/video\b',
        r'/audio\b',
        r'/photos\b',
        r'/gallery\b',
        r'/reel\b',
        r'/av\b',

        # 新增：新闻聚合类
        r'/news/?$',  # /news 或 /news/ 结尾
        r'/blog/?$',
        r'/articles/?$',
        r'/posts/?$',
        r'/press/?$',
        r'/releases/?$',
    ]

    # 文件扩展名黑名单
    FILE_EXTENSION_BLACKLIST = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.zip', '.rar', '.tar', '.gz',
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
        '.mp3', '.mp4', '.avi', '.mov',
        '.xml', '.json', '.rss', '.atom',
    }

    # 查询参数黑名单
    QUERY_PARAM_BLACKLIST = {
        'page', 'paged', 'pagenum', 'offset',
        'sort', 'order', 'orderby',
        'filter', 'search', 'query', 'q',
    }

    @classmethod
    def is_navigation_url(cls, url: str) -> bool:
        """判断 URL 是否为导航页/列表页

        Args:
            url: 待判断的 URL

        Returns:
            bool: True 表示是导航页，False 表示可能是详情页
        """
        # 处理空字符串
        if not url or url.strip() == "":
            logger.debug(f"[NavigationBlacklist] 空URL -> 导航页 (首页)")
            return True  # 空URL视为首页

        try:
            parsed = urlparse(url)

            # 检查是否是有效的 URL 结构
            # 如果没有 netloc 且不是相对路径，可能是无效输入
            if not parsed.netloc and not parsed.path.startswith('/'):
                logger.debug(f"[NavigationBlacklist] {url} -> 可能是详情页 (无效URL，保守处理)")
                return False  # 无效URL保守处理，不视为导航页
            path = parsed.path.lower()
            query = parsed.query.lower()

            # 详细日志：记录 URL 分析开始
            logger.info(f"[NavigationBlacklist] ====== 分析 URL ======")
            logger.info(f"[NavigationBlacklist] URL: {url}")
            logger.info(f"[NavigationBlacklist] 路径: {path}")
            logger.info(f"[NavigationBlacklist] 查询参数: {query if query else '(无)'}")
            path_parts = [p for p in path.split('/') if p]
            logger.info(f"[NavigationBlacklist] 路径部分: {path_parts}")

            # 1. 检查文件扩展名
            logger.info(f"[NavigationBlacklist] 检查 1: 文件扩展名...")
            for ext in cls.FILE_EXTENSION_BLACKLIST:
                if path.endswith(ext):
                    logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (文件扩展名: {ext})")
                    return True
            logger.info(f"[NavigationBlacklist] 检查 1: 通过 (非文件扩展名)")

            # 2. 检查路径模式
            logger.info(f"[NavigationBlacklist] 检查 2: 导航类路径模式...")
            for pattern in cls.NAVIGATION_PATTERNS:
                if re.search(pattern, path):
                    # 特殊处理：如果路径是 /blog, /news 等，但有详情页标识参数，可能是详情页
                    # 检查查询参数中是否有 p, id, post, article 等详情页标识
                    detail_id_patterns = ['p=', 'id=', 'post=', 'article=', 'story=']
                    if any(dp in query for dp in detail_id_patterns):
                        logger.info(f"[NavigationBlacklist] 检测到详情页参数，忽略路径模式匹配")
                        break
                    logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (匹配模式: {pattern})")
                    return True
            logger.info(f"[NavigationBlacklist] 检查 2: 通过 (未匹配导航模式)")

            # 3. 检查分页参数
            logger.info(f"[NavigationBlacklist] 检查 3: 分页参数...")
            if 'page=' in query or 'paged=' in query:
                logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (分页参数)")
                return True
            logger.info(f"[NavigationBlacklist] 检查 3: 通过 (无分页参数)")

            # 4. 检查是否为纯路径（根路径或只有一级路径）
            logger.info(f"[NavigationBlacklist] 检查 4: 路径深度...")
            if len(path_parts) == 0:
                logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (首页/根路径)")
                return True  # 首页
            logger.info(f"[NavigationBlacklist] 检查 4: 路径深度={len(path_parts)}")

            # 5. 检查路径最后一部分的特征
            last_part = path_parts[-1]
            logger.info(f"[NavigationBlacklist] 检查 5: 路径最后部分特征...")
            logger.info(f"[NavigationBlacklist] 最后部分: '{last_part}'")

            # 5a. 检查是否有数字ID（详情页特征）
            # 如果路径最后一部分是纯数字，可能是详情页
            if last_part.isdigit():
                logger.info(f"[NavigationBlacklist] ✓ 结果: 详情页 (纯数字ID: {last_part})")
                return False

            # 5b. 检查路径最后一部分是否是常见的分类名称（导航页特征）
            # 这些通常是分类页而非详情页
            CATEGORY_KEYWORDS = {
                'world', 'uk', 'us', 'politics', 'business', 'tech', 'technology',
                'science', 'health', 'education', 'entertainment', 'arts', 'sport',
                'sports', 'weather', 'climate', 'environment', 'travel', 'food',
                'autos', 'fashion', 'beauty', 'opinion', 'editorial', 'videos',
                'video', 'audio', 'photos', 'pictures', 'gallery', 'reel', 'av',
                'live', 'blog', 'blogs', 'magazine', 'features', 'special',
                'topics', 'subjects', 'regions', 'countries', 'cities',
            }
            if last_part.lower() in CATEGORY_KEYWORDS:
                logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (分类关键词: {last_part})")
                return True
            logger.info(f"[NavigationBlacklist] 检查 5b: '{last_part}' 不是分类关键词")

            # 6. 检查常见的列表页模式
            logger.info(f"[NavigationBlacklist] 检查 6: 单级路径检查...")
            # 如: /news/, /blog/, /products/ 等（后面没有具体内容）
            if path.endswith('/') and len(path_parts) == 1:
                # 这可能是列表页，但也可能是分类页
                # 保守策略：标记为潜在导航页，由 LLM 进一步判断
                logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (单级路径且以/结尾)")
                return True

            # 6b. 检查单级路径（不以 / 结尾，但只有一级）
            # 如: /news, /blog 等 - 这些通常是分类首页
            if len(path_parts) == 1:
                logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (单级路径: /{last_part})")
                return True
            logger.info(f"[NavigationBlacklist] 检查 6: 通过 (路径深度 > 1)")

            # 6c. 新增：检查二级纯分类路径 (如 /news/world, /blog/tech)
            # 如果路径只有2部分且第二部分是常见分��词，可能是分类页
            if len(path_parts) == 2:
                # 二级分类关键词检测
                SECOND_LEVEL_CATEGORY_KEYWORDS = {
                    'world', 'uk', 'us', 'politics', 'business', 'tech', 'technology',
                    'science', 'health', 'education', 'entertainment', 'arts', 'sport',
                    'sports', 'weather', 'climate', 'environment', 'travel', 'food',
                    'autos', 'fashion', 'beauty', 'opinion', 'editorial', 'videos',
                    'video', 'audio', 'photos', 'pictures', 'gallery', 'reel', 'av',
                    'live', 'blog', 'blogs', 'magazine', 'features', 'special',
                    'topics', 'subjects', 'regions', 'countries', 'cities', 'latest',
                    'trending', 'popular', 'newest', 'recent', 'more', 'all',
                }
                if last_part.lower() in SECOND_LEVEL_CATEGORY_KEYWORDS:
                    logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (二级分类关键词: {last_part})")
                    return True
                # 第一部分是常见分类词，第二部分可能也是分类
                first_part = path_parts[0]
                if first_part.lower() in {'news', 'blog', 'articles', 'posts', 'press', 'videos'}:
                    # 检查第二部分是否看起来像详情页（有数字、日期、长slug）
                    if not (last_part.isdigit() or '-' in last_part or len(last_part) > 20):
                        logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (二级分类: /{first_part}/{last_part})")
                        return True
                logger.info(f"[NavigationBlacklist] 检查 6c: 通过 (二级路径有详情页特征)")
            logger.info(f"[NavigationBlacklist] 检查 6c: 通过 (路径深度 > 2)")

            # 7. 检查二级分类页面
            logger.info(f"[NavigationBlacklist] 检查 7: 详情页特征分析...")
            # 如: /news/world, /blog/tech 等（没有具体的文章标识）
            # 如果路径只有2-3部分且最后一部分不包含数字、日期、slug特征，可能是分类页
            if len(path_parts) <= 3:
                # 详情页通常包含更多特征：数字、日期(YYYY-MM-DD)、长slug、hash等
                # slug 特征：多个短横线分隔的短词
                slug_count = last_part.count('-')
                has_digit = any(c.isdigit() for c in last_part)
                has_slug = slug_count >= 1
                is_long_slug = '-' in last_part and len(last_part) > 20
                is_bbc_style = last_part.startswith('c') and len(last_part) > 10
                starts_with_id = last_part.startswith('id')
                # 检查倒数第二部分是否是年份格式 (YYYY)
                has_year_pattern = (
                    len(path_parts) >= 3 and
                    path_parts[-2].isdigit() and len(path_parts[-2]) == 4
                )

                logger.info(f"[NavigationBlacklist] 详情页特征检测:")
                logger.info(f"[NavigationBlacklist]   - 包含数字: {has_digit}")
                logger.info(f"[NavigationBlacklist]   - 短横线数量: {slug_count} (≥1为详情页)")
                logger.info(f"[NavigationBlacklist]   - 长 slug (>20字符): {is_long_slug}")
                logger.info(f"[NavigationBlacklist]   - BBC 风格 (c开头>10字符): {is_bbc_style}")
                logger.info(f"[NavigationBlacklist]   - 以 id 开头: {starts_with_id}")
                logger.info(f"[NavigationBlacklist]   - 年份格式 (YYYY): {has_year_pattern}")

                has_detail_indicator = (
                    has_digit or
                    has_slug or
                    is_long_slug or
                    is_bbc_style or
                    starts_with_id or
                    has_year_pattern
                )
                if not has_detail_indicator:
                    logger.info(f"[NavigationBlacklist] ✗ 结果: 导航页 (短路径且无详情页特征)")
                    return True
                logger.info(f"[NavigationBlacklist] 检查 7: 发现详情页特征")

            logger.info(f"[NavigationBlacklist] ✓ 结果: 详情页 (通过所有导航页检查)")
            return False

        except Exception as e:
            # 解析失败时保守处理，不过滤
            logger.warning(f"[NavigationBlacklist] {url} 解析失败: {e}, 默认保留")
            return False

    @classmethod
    def should_filter_url(cls, url: str, base_url: Optional[str] = None) -> bool:
        """判断 URL 是否应该被过滤掉

        Args:
            url: 待判断的 URL
            base_url: 基础 URL，用于判断是否为外部链接

        Returns:
            bool: True 表示应该过滤，False 表示保留
        """
        try:
            parsed = urlparse(url)

            # 1. 必须是 http/https 协议
            if parsed.scheme not in ('http', 'https'):
                logger.debug(f"[NavigationBlacklist] {url} -> 过滤 (无效协议: {parsed.scheme})")
                return True

            # 2. 过滤外部链接（如果提供了 base_url）
            if base_url:
                base_parsed = urlparse(base_url)
                if parsed.netloc != base_parsed.netloc:
                    logger.debug(f"[NavigationBlacklist] {url} -> 过滤 (外部链接: {parsed.netloc} != {base_parsed.netloc})")
                    return True

            # 3. 检查是否为导航页
            if cls.is_navigation_url(url):
                return True

            logger.debug(f"[NavigationBlacklist] {url} -> 保留 (通过规则过滤)")
            return False

        except Exception as e:
            logger.warning(f"[NavigationBlacklist] {url} 检查失败: {e}, 默认过滤")
            return True


@dataclass
class FilterStats:
    """过滤统计信息"""
    total_count: int = 0
    navigation_filtered: int = 0
    external_filtered: int = 0
    invalid_filtered: int = 0
    remaining_count: int = 0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_count": self.total_count,
            "navigation_filtered": self.navigation_filtered,
            "external_filtered": self.external_filtered,
            "invalid_filtered": self.invalid_filtered,
            "remaining_count": self.remaining_count,
            "filter_rate": (
                (self.total_count - self.remaining_count) / self.total_count * 100
                if self.total_count > 0 else 0
            )
        }


class UrlFilter:
    """URL 规则过滤器

    使用黑名单模式和规则引擎过滤无效 URL
    """

    def __init__(self, base_url: str):
        """初始化过滤器

        Args:
            base_url: 基础 URL，用于判断外部链接
        """
        self.base_url = base_url
        self.blacklist = NavigationBlacklist()
        self.seen_urls: Set[str] = set()

    def filter(
        self,
        urls: List[str],
        enable_dedup: bool = True
    ) -> tuple[List[str], FilterStats]:
        """过滤 URL 列表

        Args:
            urls: 待过滤的 URL 列表
            enable_dedup: 是否启用去重

        Returns:
            (过滤后的 URL 列表, 过滤统计信息)
        """
        logger.info(f"[UrlFilter] 开始过滤 {len(urls)} 个 URL, base_url={self.base_url}")
        stats = FilterStats(total_count=len(urls))
        filtered_urls: List[str] = []

        for idx, url in enumerate(urls, 1):
            logger.debug(f"[UrlFilter] [{idx}/{len(urls)}] 处理: {url}")

            # 规范化 URL
            normalized_url = self._normalize_url(url)
            if not normalized_url:
                stats.invalid_filtered += 1
                logger.debug(f"[UrlFilter] [{idx}/{len(urls)}] {url} -> 无效URL，过滤")
                continue

            # 去重检查
            if enable_dedup:
                if normalized_url in self.seen_urls:
                    logger.debug(f"[UrlFilter] [{idx}/{len(urls)}] {url} -> 重复URL，跳过")
                    continue
                self.seen_urls.add(normalized_url)

            # 黑名单过滤
            if self.blacklist.should_filter_url(normalized_url, self.base_url):
                if self.blacklist.is_navigation_url(normalized_url):
                    stats.navigation_filtered += 1
                else:
                    stats.external_filtered += 1
                continue

            filtered_urls.append(normalized_url)
            logger.debug(f"[UrlFilter] [{idx}/{len(urls)}] {url} -> 保留")

        stats.remaining_count = len(filtered_urls)
        logger.info(
            f"[UrlFilter] 过滤完成: 总计={stats.total_count}, "
            f"导航页过滤={stats.navigation_filtered}, "
            f"外部链接过滤={stats.external_filtered}, "
            f"无效URL={stats.invalid_filtered}, "
            f"保留={stats.remaining_count}"
        )
        return filtered_urls, stats

    def _normalize_url(self, url: str) -> Optional[str]:
        """规范化 URL

        Args:
            url: 原始 URL

        Returns:
            规范化后的 URL，如果无效则返回 None
        """
        try:
            # 移除片段和多余的查询参数
            parsed = urlparse(url)

            # 移除分页相关的查询参数
            query_params = []
            if parsed.query:
                for param in parsed.query.split('&'):
                    if '=' in param:
                        key, _ = param.split('=', 1)
                        if key.lower() not in self.blacklist.QUERY_PARAM_BLACKLIST:
                            query_params.append(param)

            # 重建 URL
            normalized = parsed._replace(
                fragment='',  # 移除片段
                query='&'.join(query_params) if query_params else ''
            ).geturl()

            return normalized

        except Exception:
            return None

    def reset(self):
        """重置过滤器状态（清空已见 URL 缓存）"""
        self.seen_urls.clear()

"""
V3 严格验证规则框架

实现基于硬规则的搜索结果验证，包含：
- ValidationConfig: 可配置的验证规则
- 预定义事件配置: 如红旗大桥垮塌事件
- calculate_relevance_score: 置信度计算函数
- 动态配置生成: 根据意图自动生成验证配置
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from gsac.models.schemas import ParsedIntent


@dataclass
class ValidationConfig:
    """事件特定验证配置

    用于配置特定事件的验证规则，包含：
    - 高置信度标记 (+0.3~0.4)
    - 中置信度标记 (+0.1~0.2)
    - 时间排除规则
    - 地点排除规则
    - 内容排除规则
    - 最小置信度阈值

    Attributes:
        high_confidence_markers: 高置信度标记列表，匹配时 +0.4
        medium_confidence_markers: 中置信度标记列表，匹配时 +0.15
        temporal_exclude: 需要排除的历史年份
        location_exclude: 需要排除的其他国家/省份
        content_exclude: 需要排除的无关事件类型/URL模式
        min_confidence: 最小置信度阈值，低于此值判定为 discard
        downgrade_threshold: 降级阈值，介于此值和 min_confidence 之间判定为 downgrade
    """

    high_confidence_markers: list[str] = field(default_factory=list)
    medium_confidence_markers: list[str] = field(default_factory=list)
    temporal_exclude: list[str] = field(default_factory=list)
    location_exclude: list[str] = field(default_factory=list)
    content_exclude: list[str] = field(default_factory=list)
    min_confidence: float = 0.7
    downgrade_threshold: float = 0.3


# ============================================================================
# 预定义事件配置
# ============================================================================

# 红旗大桥垮塌事件验证配置 (2025年11月11日)
HONGQI_BRIDGE_CONFIG = ValidationConfig(
    high_confidence_markers=[
        # 桥名变体 (+0.4)
        "Hongqi",
        "hongqi",
        "红旗",
        "Red Flag",
        "red flag",
        "Hongqi Bridge",
        "红旗大桥",
        # 地点标识 (+0.3)
        "Shuangjiangkou",
        "双江口",
        "Barkam",
        "马尔康",
    ],
    medium_confidence_markers=[
        # 省/州 (+0.15)
        "Sichuan",
        "四川",
        "Aba",
        "阿坝",
        "Ngawa",
        # 事件类型 (+0.10)
        "collapse",
        "collapsed",
        "垮塌",
        "坍塌",
        "bridge collapse",
        "桥梁垮塌",
        # 时间标识 (+0.10)
        "2025",
        "November",
        "十一月",
        "Nov 2025",
        "November 2025",
    ],
    temporal_exclude=[
        # 历史年份 - 排除非目标时间的报道
        "2007",
        "2008",
        "2010",
        "2011",
        "2012",
        "2013",
        "2014",
        "2015",
        "2016",
        "2017",
        "2018",
        "2019",
        "2020",
        "2021",
        "2022",
        "2023",
        "2024",
        "1999",
        "1998",
        "1997",
    ],
    location_exclude=[
        # 其他国家 - 排除非中国的桥梁事件
        "Belgium",
        "India",
        "South Korea",
        "Korea",
        "Thailand",
        "Myanmar",
        "Vietnam",
        "Japan",
        "Bangladesh",
        "Nepal",
        "Pakistan",
        "Indonesia",
        "Philippines",
        "Malaysia",
        "Taiwan",
        "Hong Kong",
        # 其他中国省份 - 排除非四川阿坝的事件
        "Qinghai",
        "青海",
        "Gansu",
        "甘肃",
        "Yunnan",
        "云南",
        "Guizhou",
        "贵州",
        "Shaanxi",
        "陕西",
        "Tibet",
        "西藏",
        "Xinjiang",
        "新疆",
        "Chongqing",
        "重庆",
        "Hubei",
        "湖北",
        "Hunan",
        "湖南",
        "Guangdong",
        "广东",
        "Henan",
        "河南",
    ],
    content_exclude=[
        # 其他事件类型
        "railway bridge",
        "铁路桥",
        "under construction",
        "在建",
        "planned",
        "规划",
        "pedestrian bridge",
        "人行桥",
        "overpass",
        "立交桥",
        # 韩语标记 (排除韩国桥梁事件)
        "철교",
        "韩国",
        "한국",
        # URL索引页模式 (通常不含具体事件内容)
        "/topic/",
        "/topics/",
        "/tag/",
        "/tags/",
        "/category/",
        "/categories/",
        "/archive/",
    ],
    min_confidence=0.7,
    downgrade_threshold=0.3,
)


# 默认通用验证配置 (宽松模式)
DEFAULT_BROAD_CONFIG = ValidationConfig(
    high_confidence_markers=[],
    medium_confidence_markers=[],
    temporal_exclude=[],
    location_exclude=[],
    content_exclude=[
        # 仅排除索引页
        "/topic/",
        "/topics/",
        "/tag/",
        "/tags/",
        "/category/",
        "/categories/",
    ],
    min_confidence=0.3,
    downgrade_threshold=0.1,
)


# ============================================================================
# 媒体来源白名单/黑名单
# ============================================================================

# 西方主流媒体域名白名单
WESTERN_MAINSTREAM_MEDIA: set[str] = {
    # 通讯社
    "reuters.com",
    "apnews.com",
    "afp.com",
    # 英国
    "bbc.com",
    "bbc.co.uk",
    "theguardian.com",
    "ft.com",
    "economist.com",
    "telegraph.co.uk",
    "independent.co.uk",
    "thetimes.co.uk",
    # 美国
    "cnn.com",
    "nytimes.com",
    "washingtonpost.com",
    "wsj.com",
    "bloomberg.com",
    "nbcnews.com",
    "cbsnews.com",
    "abcnews.go.com",
    "foxnews.com",
    "politico.com",
    "upi.com",
    "nypost.com",
    "newsweek.com",
    "time.com",
    "usatoday.com",
    "latimes.com",
    "chicagotribune.com",
    # 欧洲
    "france24.com",
    "dw.com",
    "spiegel.de",
    "lemonde.fr",
    "elpais.com",
    "corriere.it",
    # 其他西方国家
    "aljazeera.com",
    "abc.net.au",
    "cbc.ca",
    "globalnews.ca",
    "smh.com.au",
    "nzherald.co.nz",
    # 财经专业媒体
    "forbes.com",
    "fortune.com",
    "cnbc.com",
    "marketwatch.com",
    "businessinsider.com",
    # 科技媒体
    "techcrunch.com",
    "wired.com",
    "theverge.com",
    "arstechnica.com",
}

# 社交媒体域名（应排除）
SOCIAL_MEDIA_DOMAINS: set[str] = {
    "instagram.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "fb.com",
    "tiktok.com",
    "youtube.com",
    "weibo.com",
    "reddit.com",
    "linkedin.com",
    "pinterest.com",
    "snapchat.com",
    "threads.net",
    "mastodon.social",
    "tumblr.com",
}

# 非西方媒体域名（在"西方主流媒体"约束下排除）
NON_WESTERN_MEDIA: set[str] = {
    # 中国官方媒体
    "xinhuanet.com",
    "people.com.cn",
    "chinadaily.com.cn",
    "globaltimes.cn",
    "gmw.cn",
    "cctv.com",
    "cgtn.com",
    "china.org.cn",
    "ecns.cn",
    # 华人媒体（非西方主流）
    "ntdtv.com",
    "epochtimes.com",
    "51.ca",
    "singtao.com",
    "mingpao.com",
    "wenxuecity.com",
    "6park.com",
    "backchina.com",
    # 俄罗斯媒体
    "rt.com",
    "tass.com",
    "sputniknews.com",
    "ria.ru",
    # 中东媒体（非阿拉伯半岛电视台）
    "presstv.ir",
    "tehrantimes.com",
    # 其他
    "scmp.com",  # 南华早报（立场较中立但非西方主流）
}


# ============================================================================
# 来源约束验证函数
# ============================================================================


def _extract_domain_from_url(url: str) -> str:
    """从 URL 提取域名

    Args:
        url: 完整 URL

    Returns:
        域名（小写，去除 www. 前缀）
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # 去除 www. 前缀
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _check_domain_match(domain: str, domain_set: set[str]) -> bool:
    """检查域名是否匹配域名集合

    支持子域名匹配，例如 news.bbc.co.uk 会匹配 bbc.co.uk

    Args:
        domain: 要检查的域名
        domain_set: 域名集合

    Returns:
        是否匹配
    """
    if not domain:
        return False

    # 精确匹配
    if domain in domain_set:
        return True

    # 子域名匹配
    for d in domain_set:
        if domain.endswith("." + d):
            return True

    return False


def validate_source_constraint(
    url: str,
    source_constraint: str | None,
) -> tuple[bool, str]:
    """验证 URL 是否符合来源约束

    Args:
        url: 要验证的 URL
        source_constraint: 来源约束（如 "西方主流媒体"）

    Returns:
        tuple[is_valid, reason]:
            - is_valid: 是否通过验证
            - reason: 验证结果说明
    """
    # 无约束或通用约束，直接通过
    if not source_constraint or source_constraint.lower() in ["all", "全部", ""]:
        return True, "无来源约束"

    domain = _extract_domain_from_url(url)
    if not domain:
        return True, "无法提取域名，默认通过"

    constraint_lower = source_constraint.lower()

    # ========================================
    # 西方主流媒体约束
    # ========================================
    if "西方" in constraint_lower or "western" in constraint_lower or "主流" in constraint_lower:
        # 检查社交媒体（直接排除）
        if _check_domain_match(domain, SOCIAL_MEDIA_DOMAINS):
            return False, f"社交媒体被排除: {domain}"

        # 检查非西方媒体（排除）
        if _check_domain_match(domain, NON_WESTERN_MEDIA):
            return False, f"非西方媒体被排除: {domain}"

        # 检查是否在白名单中
        if _check_domain_match(domain, WESTERN_MAINSTREAM_MEDIA):
            return True, f"西方主流媒体: {domain}"

        # 未知来源，使用宽松策略（允许通过但标记）
        return True, f"未知来源（宽松模式通过）: {domain}"

    # ========================================
    # 官方来源约束
    # ========================================
    if "官方" in constraint_lower or "official" in constraint_lower:
        # 检查是否为 .gov, .edu, .org 等官方域名
        official_suffixes = [".gov", ".edu", ".org", ".ac.", ".mil"]
        for suffix in official_suffixes:
            if suffix in domain:
                return True, f"官方来源: {domain}"
        return True, f"非官方来源（宽松模式通过）: {domain}"

    # ========================================
    # 其他约束类型
    # ========================================
    return True, f"未实现的约束类型: {source_constraint}"


# ============================================================================
# 验证计算函数
# ============================================================================


def calculate_relevance_score(
    title: str,
    content: str,
    url: str,
    config: ValidationConfig,
    source_constraint: str | None = None,
) -> tuple[float, Literal["keep", "downgrade", "discard"], str]:
    """
    计算相关性分数

    基于 V3 验证逻辑进行硬规则过滤和置信度计算

    Args:
        title: 内容标题
        content: 内容正文（建议截断到前2000字符）
        url: 内容URL
        config: 验证配置
        source_constraint: 来源约束（如 "西方主流媒体"），用于过滤非目标来源

    Returns:
        tuple[score, decision, reason]:
            - score: 置信度分数 (0.0 ~ 1.0+)
            - decision: 判定结果 ("keep", "downgrade", "discard")
            - reason: 判定理由
    """
    # ========================================
    # Step 0: 来源约束验证 (新增)
    # ========================================
    if source_constraint:
        is_valid, source_reason = validate_source_constraint(url, source_constraint)
        if not is_valid:
            return 0.0, "discard", f"来源约束不符: {source_reason}"

    # 合并文本用于匹配
    text = f"{title} {content}".lower()
    url_lower = url.lower()

    # ========================================
    # Step 1: 硬排除检查 - 内容排除规则
    # ========================================
    for exclude in config.content_exclude:
        exclude_lower = exclude.lower()
        if exclude_lower in text or exclude_lower in url_lower:
            return 0.0, "discard", f"内容排除规则: {exclude}"

    # ========================================
    # Step 2: 硬排除检查 - 地点排除规则
    # ========================================
    for exclude in config.location_exclude:
        exclude_lower = exclude.lower()
        if exclude_lower in text:
            return 0.0, "discard", f"地点排除规则: {exclude}"

    # ========================================
    # Step 3: 硬排除检查 - 时间排除规则
    # ========================================
    for exclude in config.temporal_exclude:
        # 时间排除需要更严格的匹配，避免误伤
        # 例如 "2023" 应该匹配年份，而不是其他数字序列
        # 使用正则确保是独立的年份
        pattern = rf"\b{re.escape(exclude)}\b"
        if re.search(pattern, text):
            # 检查是否同时包含目标年份（如2025），如果有则不排除
            target_year_pattern = r"\b2025\b"
            if not re.search(target_year_pattern, text):
                return 0.0, "discard", f"时间排除规则: {exclude} (非目标年份)"

    # ========================================
    # Step 4: 置信度计算
    # ========================================
    score = 0.0
    matched: list[str] = []

    # 高置信度标记 (+0.4 each)
    for marker in config.high_confidence_markers:
        marker_lower = marker.lower()
        if marker_lower in text:
            score += 0.4
            matched.append(f"[高]{marker}")

    # 中置信度标记 (+0.15 each)
    for marker in config.medium_confidence_markers:
        marker_lower = marker.lower()
        if marker_lower in text:
            score += 0.15
            matched.append(f"[中]{marker}")

    # ========================================
    # Step 5: 分数封顶 (确保不超过1.0)
    # ========================================
    score = min(score, 1.0)

    # ========================================
    # Step 6: 决策判定
    # ========================================
    if score >= config.min_confidence:
        # 高置信度，保留
        matched_str = ", ".join(matched[:5])
        if len(matched) > 5:
            matched_str += f" ... (+{len(matched) - 5})"
        return score, "keep", f"匹配: {matched_str}"

    elif score >= config.downgrade_threshold:
        # 中等置信度，降级
        matched_str = ", ".join(matched[:3])
        return score, "downgrade", f"部分匹配: {matched_str}"

    else:
        # 低置信度，丢弃
        return score, "discard", f"置信度不足: {score:.2f} < {config.min_confidence}"


# ============================================================================
# 动态配置生成
# ============================================================================


def extract_entities_from_target(target: str) -> list[str]:
    """从调查目标提取实体名称

    Args:
        target: 调查目标文本

    Returns:
        提取的实体名称列表
    """
    entities: list[str] = []

    # 提取中文词汇（2字以上）
    chinese_words = re.findall(r"[\u4e00-\u9fff]{2,}", target)
    entities.extend(chinese_words)

    # 提取英文词汇（首字母大写的词，2字以上）
    english_words = re.findall(r"[A-Z][a-z]{2,}", target)
    entities.extend(english_words)

    # 提取全大写缩写（2字以上）
    acronyms = re.findall(r"\b[A-Z]{2,}\b", target)
    entities.extend(acronyms)

    return entities


def extract_time_markers(time_range: str | None) -> list[str]:
    """从时间范围提取时间标记

    Args:
        time_range: 时间范围字符串，如 "2025-11", "2025-11-11"

    Returns:
        时间标记列表
    """
    if not time_range:
        return []

    markers: list[str] = []

    # 提取年份
    years = re.findall(r"20\d{2}", time_range)
    markers.extend(years)

    # 提取英文月份
    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    for month in month_names:
        if month.lower() in time_range.lower():
            markers.append(month)

    # 根据数字月份添加英文月份
    month_match = re.search(r"-(\d{2})(?:-|$)", time_range)
    if month_match:
        month_num = int(month_match.group(1))
        if 1 <= month_num <= 12:
            markers.append(month_names[month_num - 1])

    # 提取中文月份
    zh_months = re.findall(r"([一二三四五六七八九十]+月)", time_range)
    markers.extend(zh_months)

    return markers


def get_temporal_excludes(time_range: str | None) -> list[str]:
    """获取需要排除的历史年份

    Args:
        time_range: 时间范围字符串

    Returns:
        需要排除的年份列表
    """
    if not time_range:
        return []

    # 提取目标年份
    years = re.findall(r"(20\d{2})", time_range)
    if not years:
        return []

    target_year = int(years[0])

    # 排除目标年份之外的所有年份（±1年容错）
    excludes: list[str] = []
    for year in range(2000, target_year - 1):
        excludes.append(str(year))
    for year in range(target_year + 2, 2030):
        excludes.append(str(year))

    return excludes


def get_validation_config(intent: "ParsedIntent | None") -> ValidationConfig:
    """根据意图获取验证配置

    Args:
        intent: 解析后的意图对象

    Returns:
        对应的验证配置
    """
    if not intent:
        return DEFAULT_BROAD_CONFIG

    target = intent.investigation_target.lower() if intent.investigation_target else ""
    time_range = intent.time_range
    source_constraint = intent.source_type_constraint or ""

    # ========================================
    # 特定事件配置匹配
    # ========================================

    # 红旗大桥事件
    if "红旗" in target or "hongqi" in target:
        return HONGQI_BRIDGE_CONFIG

    # ========================================
    # 判断是否为泛搜索模式
    # ========================================
    is_broad_search = not time_range and source_constraint in ["all", "全部", "", None]

    if is_broad_search:
        return get_broad_search_config(intent)

    # ========================================
    # 动态构建配置
    # ========================================
    return ValidationConfig(
        high_confidence_markers=extract_entities_from_target(target),
        medium_confidence_markers=extract_time_markers(time_range),
        temporal_exclude=get_temporal_excludes(time_range),
        location_exclude=[],  # 动态配置不做地点排除
        content_exclude=[
            "/topic/",
            "/topics/",
            "/tag/",
            "/tags/",
            "/category/",
            "/categories/",
        ],
        min_confidence=0.5,
        downgrade_threshold=0.2,
    )


def get_broad_search_config(intent: "ParsedIntent | None") -> ValidationConfig:
    """获取泛搜索模式的验证配置

    当用户跳过要素补充时，使用宽松的验证规则

    Args:
        intent: 解析后的意图对象

    Returns:
        泛搜索模式的验证配置
    """
    if not intent:
        return DEFAULT_BROAD_CONFIG

    target = intent.investigation_target or ""

    return ValidationConfig(
        # 从目标中提取可能的关键词作为高置信度标记
        high_confidence_markers=extract_entities_from_target(target),
        medium_confidence_markers=[],
        # 泛搜索不排除时间
        temporal_exclude=[],
        # 泛搜索不排除地点
        location_exclude=[],
        # 仍然排除索引页
        content_exclude=[
            "/topic/",
            "/topics/",
            "/tag/",
            "/tags/",
            "/category/",
            "/categories/",
        ],
        # 降低最小置信度阈值
        min_confidence=0.3,
        downgrade_threshold=0.1,
    )


# ============================================================================
# 批量验证函数
# ============================================================================


def validate_results_batch(
    results: list[dict],
    config: ValidationConfig,
) -> tuple[list[dict], list[dict], int]:
    """批量验证搜索结果

    Args:
        results: 搜索结果列表，每个结果需包含 url, title, content 字段
        config: 验证配置

    Returns:
        tuple[validated, downgraded, discard_count]:
            - validated: 通过验证的结果（keep）
            - downgraded: 降级的结果（downgrade）
            - discard_count: 被丢弃的结果数量
    """
    validated: list[dict] = []
    downgraded: list[dict] = []
    discard_count = 0

    for result in results:
        url = result.get("url", "")
        title = result.get("title", "")
        content = result.get("content", result.get("markdown", ""))[:2000]  # 截断长内容

        score, decision, reason = calculate_relevance_score(
            title=title,
            content=content,
            url=url,
            config=config,
        )

        # 添加验证信息到结果
        result_with_validation = {
            **result,
            "validation_score": score,
            "validation_decision": decision,
            "validation_reason": reason,
        }

        if decision == "keep":
            validated.append(result_with_validation)
        elif decision == "downgrade":
            downgraded.append(result_with_validation)
        else:
            discard_count += 1

    return validated, downgraded, discard_count

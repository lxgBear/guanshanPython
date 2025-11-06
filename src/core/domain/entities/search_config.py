"""搜索配置实体模型 - 三层配置系统"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class SearchSource(Enum):
    """搜索来源"""
    WEB = "web"
    NEWS = "news"
    ACADEMIC = "academic"
    SOCIAL = "social"
    VIDEO = "video"
    IMAGE = "image"


class SearchCategory(Enum):
    """搜索类别"""
    TECH = "tech"
    BUSINESS = "business"
    HEALTH = "health"
    SCIENCE = "science"
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    GENERAL = "general"


class SearchLanguage(Enum):
    """搜索语言"""
    ZH = "zh"  # 中文
    EN = "en"  # 英文
    JA = "ja"  # 日文
    KO = "ko"  # 韩文
    ES = "es"  # 西班牙文
    FR = "fr"  # 法文
    DE = "de"  # 德文
    AUTO = "auto"  # 自动检测


@dataclass
class SystemSearchConfig:
    """系统级搜索配置（第一层）"""
    # 测试模式配置
    IS_TEST_MODE: bool = field(default_factory=lambda: os.getenv("TEST_MODE", "false").lower() == "true")
    
    # API 限制
    MAX_LIMIT: int = field(default_factory=lambda: 10 if os.getenv("TEST_MODE", "false").lower() == "true" else 100)
    DEFAULT_LIMIT: int = field(default_factory=lambda: 10 if os.getenv("TEST_MODE", "false").lower() == "true" else 20)
    MIN_LIMIT: int = 1
    
    # 页面大小
    MAX_PAGE_SIZE: int = field(default_factory=lambda: 10 if os.getenv("TEST_MODE", "false").lower() == "true" else 50)
    DEFAULT_PAGE_SIZE: int = field(default_factory=lambda: 10 if os.getenv("TEST_MODE", "false").lower() == "true" else 20)
    
    # 搜索超时
    SEARCH_TIMEOUT_SECONDS: int = field(default_factory=lambda: 10 if os.getenv("TEST_MODE", "false").lower() == "true" else 30)
    
    # 重试配置
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 1
    
    # 缓存配置
    ENABLE_CACHE: bool = field(default_factory=lambda: False if os.getenv("TEST_MODE", "false").lower() == "true" else True)
    CACHE_TTL_SECONDS: int = 3600  # 1小时
    
    # 消费限制
    MAX_CREDITS_PER_SEARCH: int = field(default_factory=lambda: 10 if os.getenv("TEST_MODE", "false").lower() == "true" else 100)
    MAX_CREDITS_PER_DAY: int = field(default_factory=lambda: 100 if os.getenv("TEST_MODE", "false").lower() == "true" else 10000)
    
    # 日志级别
    LOG_LEVEL: str = field(default_factory=lambda: "DEBUG" if os.getenv("TEST_MODE", "false").lower() == "true" else "INFO")
    
    # 默认值
    DEFAULT_SOURCES: List[str] = field(default_factory=lambda: [SearchSource.WEB.value, SearchSource.NEWS.value])
    DEFAULT_LANGUAGE: str = SearchLanguage.ZH.value
    DEFAULT_CATEGORIES: List[str] = field(default_factory=lambda: [SearchCategory.GENERAL.value])
    
    def get_effective_limit(self, requested_limit: Optional[int] = None) -> int:
        """获取有效的限制数"""
        if requested_limit is None:
            return self.DEFAULT_LIMIT
        return min(max(requested_limit, self.MIN_LIMIT), self.MAX_LIMIT)


@dataclass
class SearchConfigTemplate:
    """搜索配置模板（第二层）"""
    name: str = ""  # 模板名称
    description: str = ""  # 模板描述

    # 搜索参数
    limit: int = 20  # 结果数量
    sources: List[str] = field(default_factory=list)  # 搜索来源
    categories: List[str] = field(default_factory=list)  # 搜索类别
    language: str = SearchLanguage.ZH.value  # 语言

    # 过滤器
    include_domains: List[str] = field(default_factory=list)  # 包含域名
    exclude_domains: List[str] = field(default_factory=list)  # 排除域名

    # 时间范围
    time_range: Optional[str] = None  # 时间范围: "day", "week", "month", "year"

    # 高级选项
    enable_ai_summary: bool = False  # 启用AI摘要
    extract_metadata: bool = True    # 提取元数据
    follow_links: bool = False        # 跟随链接
    max_depth: int = 1               # 最大深度

    # HTML清理选项 (Firecrawl scrapeOptions)
    only_main_content: bool = True           # 只保留主要内容
    remove_base64_images: bool = False       # 保留base64图片（保留正文图片，配合onlyMainContent移除非主内容区域图片）
    block_ads: bool = True                   # 屏蔽广告
    scrape_formats: List[str] = field(default_factory=lambda: ['markdown', 'html', 'links'])  # 抓取格式
    include_tags: Optional[List[str]] = None  # 包含的HTML标签
    exclude_tags: Optional[List[str]] = field(default_factory=lambda: ["nav", "header", "footer", "aside", "form"])  # 排除的HTML标签（默认排除导航、页眉、页脚）
    wait_for: Optional[int] = None           # 等待时间(毫秒), 用于动态内容加载

    # 语言过滤
    strict_language_filter: bool = True      # 严格语言过滤
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "limit": self.limit,
            "sources": self.sources,
            "categories": self.categories,
            "language": self.language,
            "include_domains": self.include_domains,
            "exclude_domains": self.exclude_domains,
            "time_range": self.time_range,
            "enable_ai_summary": self.enable_ai_summary,
            "extract_metadata": self.extract_metadata,
            "follow_links": self.follow_links,
            "max_depth": self.max_depth,
            # HTML清理选项
            "only_main_content": self.only_main_content,
            "remove_base64_images": self.remove_base64_images,
            "block_ads": self.block_ads,
            "scrape_formats": self.scrape_formats,
            "include_tags": self.include_tags,
            "exclude_tags": self.exclude_tags,
            "wait_for": self.wait_for,
            "strict_language_filter": self.strict_language_filter
        }


@dataclass
class UserSearchConfig:
    """用户级搜索配置（第三层）"""
    # 基础配置
    template_name: Optional[str] = None  # 使用的模板
    
    # 覆盖参数（只包含用户修改的部分）
    overrides: Dict[str, Any] = field(default_factory=dict)
    
    def merge_with_template(self, template: SearchConfigTemplate) -> Dict[str, Any]:
        """与模板合并配置"""
        config = template.to_dict()
        config.update(self.overrides)
        return config
    
    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> 'UserSearchConfig':
        """从JSON创建配置"""
        return cls(
            template_name=json_data.get('template'),
            overrides={k: v for k, v in json_data.items() if k != 'template'}
        )


class SearchConfigManager:
    """搜索配置管理器 - 处理三层配置合并"""
    
    def __init__(self):
        self.system_config = SystemSearchConfig()
        self.templates: Dict[str, SearchConfigTemplate] = self._load_default_templates()
    
    def _load_default_templates(self) -> Dict[str, SearchConfigTemplate]:
        """加载默认模板"""
        return {
            "default": SearchConfigTemplate(
                name="default",
                description="默认搜索配置",
                limit=self.system_config.DEFAULT_LIMIT,
                sources=self.system_config.DEFAULT_SOURCES,
                categories=self.system_config.DEFAULT_CATEGORIES,
                language=self.system_config.DEFAULT_LANGUAGE
            ),
            "news": SearchConfigTemplate(
                name="news",
                description="新闻搜索配置",
                limit=self.system_config.DEFAULT_LIMIT,
                sources=[SearchSource.NEWS.value],
                categories=[SearchCategory.GENERAL.value],
                language=SearchLanguage.ZH.value,
                time_range="day"
            ),
            "tech": SearchConfigTemplate(
                name="tech",
                description="技术搜索配置",
                limit=self.system_config.DEFAULT_LIMIT,
                sources=[SearchSource.WEB.value, SearchSource.NEWS.value],
                categories=[SearchCategory.TECH.value, SearchCategory.SCIENCE.value],
                language=SearchLanguage.ZH.value,
                enable_ai_summary=True
            )
        }
    
    def get_effective_config(self, user_config: UserSearchConfig) -> Dict[str, Any]:
        """获取最终有效配置（三层合并）"""
        # 1. 使用系统默认值
        template_name = user_config.template_name or "default"
        template = self.templates.get(template_name, self.templates["default"])
        
        # 2. 应用模板
        config = template.to_dict()
        
        # 3. 应用用户覆盖
        config.update(user_config.overrides)
        
        # 4. 应用系统限制
        if self.system_config.IS_TEST_MODE:
            config['limit'] = min(config.get('limit', self.system_config.DEFAULT_LIMIT), 
                                 self.system_config.MAX_LIMIT)
        
        return config
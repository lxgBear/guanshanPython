"""
爬虫接口定义
遵循依赖倒置原则 - 核心层定义接口，基础设施层实现
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class CrawlResult:
    """爬取结果数据类"""
    url: str
    content: str
    markdown: Optional[str] = None
    html: Optional[str] = None
    metadata: Dict[str, Any] = None
    extracted_data: Optional[Dict] = None
    screenshot: Optional[bytes] = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.metadata is None:
            self.metadata = {}


class CrawlerInterface(ABC):
    """
    爬虫接口定义
    所有爬虫实现必须遵循此接口
    """
    
    @abstractmethod
    async def scrape(self, url: str, **options) -> CrawlResult:
        """
        爬取单个页面
        
        Args:
            url: 目标URL
            **options: 爬取选项
                - wait_for: 等待元素选择器
                - actions: 页面交互动作
                - include_tags: 包含的HTML标签
                - exclude_tags: 排除的HTML标签
                - timeout: 超时时间（秒）
        
        Returns:
            CrawlResult: 爬取结果
            
        Raises:
            CrawlException: 爬取失败时抛出
        """
        pass
    
    @abstractmethod
    async def crawl(self, url: str, limit: int = 10, **options) -> List[CrawlResult]:
        """
        爬取整个网站
        
        Args:
            url: 起始URL
            limit: 最大页面数
            **options: 爬取选项
                - max_depth: 最大深度
                - include_paths: 包含的路径模式
                - exclude_paths: 排除的路径模式
                - allow_backward_links: 是否允许回链
        
        Returns:
            List[CrawlResult]: 爬取结果列表
            
        Raises:
            CrawlException: 爬取失败时抛出
        """
        pass
    
    @abstractmethod
    async def map(self, url: str, limit: int = 100) -> List[str]:
        """
        生成站点地图（URL列表）
        
        Args:
            url: 目标网站URL
            limit: 最大URL数量
        
        Returns:
            List[str]: URL列表
            
        Raises:
            CrawlException: 映射失败时抛出
        """
        pass
    
    @abstractmethod
    async def extract(self, url: str, schema: Dict) -> Dict:
        """
        从页面提取结构化数据
        
        Args:
            url: 目标URL
            schema: 提取模式定义
                {
                    "type": "object",
                    "description": "提取描述",
                    "properties": {
                        "field_name": {"type": "string", "description": "字段描述"}
                    }
                }
        
        Returns:
            Dict: 提取的结构化数据
            
        Raises:
            CrawlException: 提取失败时抛出
        """
        pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[CrawlResult]:
        """
        搜索并爬取结果
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
        
        Returns:
            List[CrawlResult]: 搜索结果
            
        Raises:
            CrawlException: 搜索失败时抛出
        """
        pass


class CrawlException(Exception):
    """爬取异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.url = url
        self.status_code = status_code
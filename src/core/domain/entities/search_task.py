"""定时搜索任务实体模型

v1.5.0 ID系统统一：
- ✅ 完全统一使用雪花算法ID（移除UUID fallback）
- ✅ 与其他实体保持一致
- ✅ 简化ID处理逻辑
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

# 导入安全ID生成器
from src.infrastructure.id_generator import generate_string_id


class TaskStatus(Enum):
    """任务状态枚举"""
    ACTIVE = "active"       # 活跃
    PAUSED = "paused"       # 暂停
    FAILED = "failed"       # 失败
    COMPLETED = "completed" # 完成
    DISABLED = "disabled"   # 禁用


class ScheduleInterval(Enum):
    """预定义的调度间隔"""
    HOURLY_1 = ("HOURLY_1", "0 * * * *", "每小时", 60, "每小时执行一次")
    HOURLY_6 = ("HOURLY_6", "0 */6 * * *", "每6小时", 360, "每6小时执行一次（0点、6点、12点、18点）")
    HOURLY_12 = ("HOURLY_12", "0 */12 * * *", "每12小时", 720, "每12小时执行一次（0点、12点）")
    DAILY = ("DAILY", "0 9 * * *", "每天", 1440, "每天上午9点执行")
    DAYS_3 = ("DAYS_3", "0 9 */3 * *", "每3天", 4320, "每3天上午9点执行")
    WEEKLY = ("WEEKLY", "0 9 * * 1", "每周", 10080, "每周一上午9点执行")
    
    def __init__(self, enum_value, cron, display_name, minutes, description):
        self.enum_value = enum_value
        self.cron_expression = cron
        self.display_name = display_name
        self.interval_minutes = minutes
        self.description = description
    
    @classmethod
    def from_value(cls, value: str):
        """根据值获取枚举"""
        for interval in cls:
            if interval.enum_value == value:
                return interval
        raise ValueError(f"无效的调度间隔: {value}")
    
    def to_dict(self):
        """转换为字典（用于API响应）"""
        return {
            "value": self.enum_value,
            "label": self.display_name,
            "description": self.description,
            "interval_minutes": self.interval_minutes
        }


def _generate_secure_id() -> str:
    """生成安全的雪花算法ID"""
    return generate_string_id()


@dataclass
class SearchTask:
    """
    搜索任务实体

    v1.5.0 改进：
    - ✅ 统一使用雪花算法ID（移除UUID）
    - ✅ 支持高并发和分布式环境
    - ✅ 全局唯一且不可预测
    """
    # 主键（雪花算法ID，全局唯一）
    id: str = field(default_factory=_generate_secure_id)
    name: str = ""
    description: Optional[str] = None
    query: str = ""  # 搜索关键词
    target_website: Optional[str] = None  # 主要目标网站（用于前端展示，例如：www.gnlm.com.mm）
    crawl_url: Optional[str] = None  # 定时爬取的URL（优先于query关键词搜索，使用Firecrawl Scrape API）
    search_config: Dict[str, Any] = field(default_factory=dict)  # 搜索配置（JSON）
    schedule_interval: str = "DAILY"  # 调度间隔枚举值
    is_active: bool = True  # 是否启用
    status: TaskStatus = TaskStatus.ACTIVE
    
    # 元数据
    created_by: str = ""  # 创建者
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_executed_at: Optional[datetime] = None
    next_run_time: Optional[datetime] = None
    
    # 统计信息
    execution_count: int = 0  # 执行次数
    success_count: int = 0    # 成功次数
    failure_count: int = 0    # 失败次数
    total_results: int = 0    # 总结果数
    total_credits_used: int = 0  # 总消耗积分
    
    def get_schedule_interval(self) -> ScheduleInterval:
        """获取调度间隔枚举"""
        return ScheduleInterval.from_value(self.schedule_interval)
    
    def update_status(self, new_status: TaskStatus) -> None:
        """更新任务状态"""
        self.status = new_status
        self.updated_at = datetime.utcnow()
    
    def record_execution(self, success: bool, results_count: int = 0, credits_used: int = 0) -> None:
        """记录执行结果"""
        self.execution_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.total_results += results_count
        self.total_credits_used += credits_used
        self.last_executed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.execution_count == 0:
            return 0.0
        return (self.success_count / self.execution_count) * 100
    
    @property
    def average_results(self) -> float:
        """计算平均结果数"""
        if self.execution_count == 0:
            return 0.0
        return self.total_results / self.execution_count

    def extract_target_website(self) -> Optional[str]:
        """
        从 search_config 中提取主要目标网站

        Returns:
            主要目标网站域名，如果没有配置则返回 None
        """
        include_domains = self.search_config.get('include_domains', [])
        if include_domains and len(include_domains) > 0:
            # 返回第一个域名作为主要目标
            return include_domains[0]
        return None

    def sync_target_website(self) -> None:
        """
        同步 target_website 字段：
        - 如果 target_website 为空，从 search_config 提取
        - 如果 target_website 不为空，保持不变（允许用户自定义）
        """
        if not self.target_website:
            self.target_website = self.extract_target_website()
    
    def get_id_string(self) -> str:
        """获取字符串格式的ID（统一接口，v1.5.0后始终返回雪花ID）"""
        return str(self.id)

    def is_secure_id(self) -> bool:
        """检查是否使用安全的雪花算法ID（v1.5.0后始终返回True）"""
        # 雪花算法ID特征：纯数字且长度在15-19位之间
        return self.id.isdigit() and 15 <= len(self.id) <= 19
    
    @classmethod
    def create_with_secure_id(cls, **kwargs) -> 'SearchTask':
        """
        使用安全ID创建任务实例
        
        Args:
            **kwargs: 其他字段参数
            
        Returns:
            带有安全ID的SearchTask实例
        """
        # 确保使用雪花算法ID
        kwargs.pop('id', None)  # 移除可能存在的id参数
        return cls(id=_generate_secure_id(), **kwargs)
    
    @classmethod
    def migrate_from_unsafe_id(cls, task: 'SearchTask') -> 'SearchTask':
        """
        从不安全ID迁移到安全ID

        Args:
            task: 原始任务实例

        Returns:
            使用安全ID的新任务实例
        """
        # 保持其他字段不变，只替换ID
        new_task = cls(
            id=_generate_secure_id(),
            name=task.name,
            description=task.description,
            query=task.query,
            target_website=task.target_website,
            crawl_url=task.crawl_url,
            search_config=task.search_config.copy(),
            schedule_interval=task.schedule_interval,
            is_active=task.is_active,
            status=task.status,
            created_by=task.created_by,
            created_at=task.created_at,
            updated_at=task.updated_at,
            last_executed_at=task.last_executed_at,
            next_run_time=task.next_run_time,
            execution_count=task.execution_count,
            success_count=task.success_count,
            failure_count=task.failure_count,
            total_results=task.total_results,
            total_credits_used=task.total_credits_used
        )
        return new_task
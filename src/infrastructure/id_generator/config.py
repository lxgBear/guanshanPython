"""
雪花算法配置模块

提供灵活的配置管理，支持环境变量和默认值。
"""

import os
import socket
from dataclasses import dataclass, field
from typing import Optional, Union

from .types import SnowflakeConstants


@dataclass
class SnowflakeConfig:
    """雪花算法配置类"""
    
    # 数据中心ID (0-31)
    datacenter_id: int = field(default_factory=lambda: _get_default_datacenter_id())
    
    # 机器ID (0-31) 
    machine_id: int = field(default_factory=lambda: _get_default_machine_id())
    
    # 自定义时间起点 (毫秒时间戳)
    epoch_timestamp: int = SnowflakeConstants.EPOCH_TIMESTAMP
    
    def __post_init__(self):
        """配置验证"""
        self._validate()
    
    def _validate(self):
        """验证配置参数"""
        if not (0 <= self.datacenter_id <= SnowflakeConstants.MAX_DATACENTER_ID):
            raise ValueError(f"数据中心ID必须在0-{SnowflakeConstants.MAX_DATACENTER_ID}之间，当前值: {self.datacenter_id}")
            
        if not (0 <= self.machine_id <= SnowflakeConstants.MAX_MACHINE_ID):
            raise ValueError(f"机器ID必须在0-{SnowflakeConstants.MAX_MACHINE_ID}之间，当前值: {self.machine_id}")
            
        if self.epoch_timestamp <= 0:
            raise ValueError(f"时间起点必须大于0，当前值: {self.epoch_timestamp}")
    
    @classmethod
    def from_env(cls) -> 'SnowflakeConfig':
        """从环境变量创建配置"""
        return cls(
            datacenter_id=int(os.getenv('SNOWFLAKE_DATACENTER_ID', _get_default_datacenter_id())),
            machine_id=int(os.getenv('SNOWFLAKE_MACHINE_ID', _get_default_machine_id())),
            epoch_timestamp=int(os.getenv('SNOWFLAKE_EPOCH', SnowflakeConstants.EPOCH_TIMESTAMP))
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'datacenter_id': self.datacenter_id,
            'machine_id': self.machine_id,
            'epoch_timestamp': self.epoch_timestamp
        }


def _get_default_datacenter_id() -> int:
    """
    获取默认数据中心ID
    基于环境变量或主机名哈希生成
    """
    env_dc_id = os.getenv('SNOWFLAKE_DATACENTER_ID')
    if env_dc_id:
        return int(env_dc_id) & SnowflakeConstants.MAX_DATACENTER_ID
    
    # 使用主机名哈希生成数据中心ID
    hostname = socket.gethostname()
    return hash(hostname) & SnowflakeConstants.MAX_DATACENTER_ID


def _get_default_machine_id() -> int:
    """
    获取默认机器ID
    基于环境变量、线程ID、进程ID生成，确保线程安全
    """
    env_machine_id = os.getenv('SNOWFLAKE_MACHINE_ID')
    if env_machine_id:
        return int(env_machine_id) & SnowflakeConstants.MAX_MACHINE_ID
    
    # 组合线程ID和进程ID，提高唯一性
    import threading
    pid = os.getpid()
    thread_id = threading.get_ident()
    
    # 混合进程ID和线程ID的哈希值
    combined_id = hash(f"{pid}-{thread_id}") 
    return abs(combined_id) & SnowflakeConstants.MAX_MACHINE_ID


class ConfigManager:
    """配置管理器 - 单例模式"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_config(self) -> SnowflakeConfig:
        """获取配置实例"""
        if self._config is None:
            self._config = SnowflakeConfig.from_env()
        return self._config
    
    def reset_config(self, config: Optional[SnowflakeConfig] = None):
        """重置配置（主要用于测试）"""
        self._config = config
"""
雪花算法ID生成器核心实现

高性能、线程安全的分布式ID生成器。
支持每毫秒最多4096个ID，理论QPS可达400万+。
"""

import time
import threading
from typing import Optional

from .config import SnowflakeConfig
from .types import SnowflakeConstants, IDGenerator


class SnowflakeGenerator(IDGenerator):
    """
    雪花算法ID生成器
    
    ID结构 (64位):
    - 1位符号位 (固定为0)
    - 41位时间戳 (毫秒级，可用69年)
    - 5位数据中心ID (支持32个数据中心)
    - 5位机器ID (每个数据中心支持32台机器)
    - 12位序列号 (每毫秒最多4096个ID)
    """
    
    def __init__(self, config: Optional[SnowflakeConfig] = None):
        """
        初始化雪花算法生成器
        
        Args:
            config: 雪花算法配置，如为None则使用默认配置
        """
        self.config = config or SnowflakeConfig()
        
        # 上次生成ID的时间戳
        self._last_timestamp = -1
        
        # 当前毫秒内的序列号
        self._sequence = 0
        
        # 线程锁，保证线程安全
        self._lock = threading.Lock()
        
        # 预计算的位移值（性能优化）
        self._datacenter_shift = SnowflakeConstants.DATACENTER_SHIFT
        self._machine_shift = SnowflakeConstants.MACHINE_SHIFT
        self._timestamp_shift = SnowflakeConstants.TIMESTAMP_SHIFT
        
        # 预计算的ID组件
        self._datacenter_part = self.config.datacenter_id << self._datacenter_shift
        self._machine_part = self.config.machine_id << self._machine_shift
    
    def generate(self) -> int:
        """
        生成一个64位雪花算法ID
        
        Returns:
            64位整数ID
            
        Raises:
            RuntimeError: 当系统时钟回拨时抛出异常
        """
        with self._lock:
            return self._generate_unsafe()
    
    def _generate_unsafe(self) -> int:
        """内部生成方法（非线程安全）"""
        current_timestamp = self._get_timestamp()
        
        # 处理时钟回拨
        if current_timestamp < self._last_timestamp:
            raise RuntimeError(
                f"系统时钟回拨检测！"
                f"上次时间戳: {self._last_timestamp}, 当前时间戳: {current_timestamp}"
            )
        
        # 同一毫秒内生成多个ID
        if current_timestamp == self._last_timestamp:
            # 序列号递增
            self._sequence = (self._sequence + 1) & SnowflakeConstants.MAX_SEQUENCE
            
            # 序列号溢出，等待下一毫秒
            if self._sequence == 0:
                current_timestamp = self._wait_next_millis()
        else:
            # 新的毫秒，重置序列号
            self._sequence = 0
        
        # 更新上次时间戳
        self._last_timestamp = current_timestamp
        
        # 组装ID
        return self._assemble_id(current_timestamp)
    
    def _assemble_id(self, timestamp: int) -> int:
        """
        组装最终的ID
        
        Args:
            timestamp: 当前时间戳
            
        Returns:
            组装后的64位ID
        """
        return (
            ((timestamp - self.config.epoch_timestamp) << self._timestamp_shift) |
            self._datacenter_part |
            self._machine_part |
            self._sequence
        )
    
    def _get_timestamp(self) -> int:
        """获取当前毫秒级时间戳"""
        return int(time.time() * 1000)
    
    def _wait_next_millis(self) -> int:
        """等待下一毫秒"""
        timestamp = self._get_timestamp()
        while timestamp <= self._last_timestamp:
            timestamp = self._get_timestamp()
        return timestamp
    
    def generate_string(self) -> str:
        """
        生成字符串格式的ID
        
        Returns:
            字符串格式的ID
        """
        return str(self.generate())
    
    def parse_id(self, snowflake_id: int) -> dict:
        """
        解析雪花算法ID的各个组成部分
        
        Args:
            snowflake_id: 要解析的雪花算法ID
            
        Returns:
            包含各部分信息的字典
        """
        # 提取时间戳
        timestamp_part = snowflake_id >> self._timestamp_shift
        original_timestamp = timestamp_part + self.config.epoch_timestamp
        
        # 提取数据中心ID
        datacenter_mask = SnowflakeConstants.MAX_DATACENTER_ID << self._machine_shift
        datacenter_id = (snowflake_id & datacenter_mask) >> self._machine_shift
        
        # 提取机器ID
        machine_mask = SnowflakeConstants.MAX_MACHINE_ID << SnowflakeConstants.MACHINE_SHIFT
        machine_id = (snowflake_id & machine_mask) >> SnowflakeConstants.MACHINE_SHIFT
        
        # 提取序列号
        sequence = snowflake_id & SnowflakeConstants.MAX_SEQUENCE
        
        return {
            'id': snowflake_id,
            'timestamp': original_timestamp,
            'datetime': time.strftime('%Y-%m-%d %H:%M:%S', 
                                     time.localtime(original_timestamp / 1000)),
            'datacenter_id': datacenter_id,
            'machine_id': machine_id,
            'sequence': sequence
        }
    
    def batch_generate(self, count: int) -> list[int]:
        """
        批量生成ID（性能优化版本）
        
        Args:
            count: 要生成的ID数量
            
        Returns:
            ID列表
            
        Raises:
            ValueError: 当count <= 0时
        """
        if count <= 0:
            raise ValueError("生成数量必须大于0")
        
        ids = []
        with self._lock:
            for _ in range(count):
                ids.append(self._generate_unsafe())
        
        return ids
    
    def get_stats(self) -> dict:
        """获取生成器统计信息"""
        return {
            'datacenter_id': self.config.datacenter_id,
            'machine_id': self.config.machine_id,
            'epoch_timestamp': self.config.epoch_timestamp,
            'last_timestamp': self._last_timestamp,
            'current_sequence': self._sequence,
            'max_ids_per_ms': SnowflakeConstants.MAX_SEQUENCE + 1,
            'theoretical_max_qps': (SnowflakeConstants.MAX_SEQUENCE + 1) * 1000
        }
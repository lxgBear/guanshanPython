"""
ID生成器类型定义和常量
"""

from enum import Enum
from typing import Protocol


class IDGeneratorType(Enum):
    """ID生成器类型枚举"""
    SNOWFLAKE = "snowflake"
    UUID4 = "uuid4"
    CUSTOM = "custom"


class IDGenerator(Protocol):
    """ID生成器协议接口"""
    
    def generate(self) -> int:
        """生成一个64位整数ID"""
        ...
    
    def generate_string(self) -> str:
        """生成一个字符串ID"""
        ...


# 雪花算法常量
class SnowflakeConstants:
    """雪花算法相关常量"""
    
    # 时间戳起始时间 (2024-01-01 00:00:00 UTC)
    EPOCH_TIMESTAMP = 1704067200000
    
    # 各部分位数分配
    TIMESTAMP_BITS = 41  # 时间戳位数 (69年)
    DATACENTER_BITS = 5  # 数据中心位数 (32个数据中心)
    MACHINE_BITS = 5     # 机器位数 (32台机器)
    SEQUENCE_BITS = 12   # 序列号位数 (4096个序列号)
    
    # 各部分最大值
    MAX_DATACENTER_ID = (1 << DATACENTER_BITS) - 1  # 31
    MAX_MACHINE_ID = (1 << MACHINE_BITS) - 1        # 31
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1          # 4095
    
    # 位移偏移量
    MACHINE_SHIFT = SEQUENCE_BITS                              # 12
    DATACENTER_SHIFT = SEQUENCE_BITS + MACHINE_BITS           # 17
    TIMESTAMP_SHIFT = SEQUENCE_BITS + MACHINE_BITS + DATACENTER_BITS  # 22
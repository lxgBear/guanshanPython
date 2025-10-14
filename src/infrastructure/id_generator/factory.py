"""
ID生成器工厂

采用工厂模式，支持多种ID生成策略。
提供统一的创建接口，便于扩展和测试。
"""

import uuid
from typing import Dict, Type, Optional, Any

from .snowflake import SnowflakeGenerator
from .config import SnowflakeConfig, ConfigManager
from .types import IDGenerator, IDGeneratorType


class UUID4Generator(IDGenerator):
    """UUID4生成器（用于对比和备用方案）"""
    
    def generate(self) -> int:
        """生成UUID4并转换为整数（仅用于兼容性）"""
        # 注意：UUID4转整数会丢失随机性，不推荐生产使用
        return uuid.uuid4().int
    
    def generate_string(self) -> str:
        """生成UUID4字符串"""
        return str(uuid.uuid4())


class IDGeneratorFactory:
    """
    ID生成器工厂类
    
    支持多种ID生成策略，便于切换和扩展。
    """
    
    # 注册的生成器类型
    _generators: Dict[IDGeneratorType, Type[IDGenerator]] = {
        IDGeneratorType.SNOWFLAKE: SnowflakeGenerator,
        IDGeneratorType.UUID4: UUID4Generator,
    }
    
    # 单例生成器缓存
    _instances: Dict[str, IDGenerator] = {}
    
    @classmethod
    def register_generator(cls, id_type: IDGeneratorType, generator_class: Type[IDGenerator]):
        """
        注册新的生成器类型
        
        Args:
            id_type: ID生成器类型
            generator_class: 生成器类
        """
        cls._generators[id_type] = generator_class
    
    @classmethod
    def create_snowflake(cls, 
                        config: Optional[SnowflakeConfig] = None,
                        singleton: bool = True) -> SnowflakeGenerator:
        """
        创建雪花算法生成器
        
        Args:
            config: 雪花算法配置
            singleton: 是否使用单例模式
            
        Returns:
            雪花算法生成器实例
        """
        if singleton:
            cache_key = f"snowflake_{id(config) if config else 'default'}"
            if cache_key not in cls._instances:
                cls._instances[cache_key] = SnowflakeGenerator(config)
            return cls._instances[cache_key]
        
        return SnowflakeGenerator(config)
    
    @classmethod
    def create_uuid4(cls, singleton: bool = True) -> UUID4Generator:
        """
        创建UUID4生成器
        
        Args:
            singleton: 是否使用单例模式
            
        Returns:
            UUID4生成器实例
        """
        if singleton:
            cache_key = "uuid4_default"
            if cache_key not in cls._instances:
                cls._instances[cache_key] = UUID4Generator()
            return cls._instances[cache_key]
        
        return UUID4Generator()
    
    @classmethod
    def create_generator(cls, 
                        generator_type: IDGeneratorType,
                        config: Optional[Dict[str, Any]] = None,
                        singleton: bool = True) -> IDGenerator:
        """
        根据类型创建ID生成器
        
        Args:
            generator_type: 生成器类型
            config: 配置参数
            singleton: 是否使用单例模式
            
        Returns:
            ID生成器实例
            
        Raises:
            ValueError: 不支持的生成器类型
        """
        if generator_type not in cls._generators:
            raise ValueError(f"不支持的生成器类型: {generator_type}")
        
        # 根据类型创建生成器
        if generator_type == IDGeneratorType.SNOWFLAKE:
            snowflake_config = None
            if config:
                snowflake_config = SnowflakeConfig(**config)
            return cls.create_snowflake(snowflake_config, singleton)
        
        elif generator_type == IDGeneratorType.UUID4:
            return cls.create_uuid4(singleton)
        
        else:
            # 通用创建方式（用于扩展）
            generator_class = cls._generators[generator_type]
            if singleton:
                cache_key = f"{generator_type.value}_default"
                if cache_key not in cls._instances:
                    cls._instances[cache_key] = generator_class(**(config or {}))
                return cls._instances[cache_key]
            
            return generator_class(**(config or {}))
    
    @classmethod
    def create_from_env(cls) -> IDGenerator:
        """
        根据环境变量创建默认生成器
        
        Returns:
            ID生成器实例
        """
        import os
        
        # 从环境变量获取生成器类型
        generator_type_str = os.getenv('ID_GENERATOR_TYPE', 'snowflake').lower()
        
        try:
            generator_type = IDGeneratorType(generator_type_str)
        except ValueError:
            # 默认使用雪花算法
            generator_type = IDGeneratorType.SNOWFLAKE
        
        if generator_type == IDGeneratorType.SNOWFLAKE:
            config_manager = ConfigManager()
            config = config_manager.get_config()
            return cls.create_snowflake(config, singleton=True)
        else:
            return cls.create_generator(generator_type, singleton=True)
    
    @classmethod
    def get_available_types(cls) -> list[IDGeneratorType]:
        """获取支持的生成器类型列表"""
        return list(cls._generators.keys())
    
    @classmethod
    def clear_cache(cls):
        """清理单例缓存（主要用于测试）"""
        cls._instances.clear()


# 提供便捷的全局工厂方法
def create_snowflake_generator(config: Optional[SnowflakeConfig] = None) -> SnowflakeGenerator:
    """便捷方法：创建雪花算法生成器"""
    return IDGeneratorFactory.create_snowflake(config)


def create_default_generator() -> IDGenerator:
    """便捷方法：创建默认生成器（根据环境变量）"""
    return IDGeneratorFactory.create_from_env()
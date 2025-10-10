"""
日志配置模块
提供结构化日志记录功能
"""
import logging
import sys
from typing import Optional
from pathlib import Path

# 创建logs目录
logs_dir = Path(__file__).parent.parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)


def setup_logger(
    name: Optional[str] = None,
    level: str = "INFO",
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    设置日志器
    
    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件路径
    
    Returns:
        logging.Logger: 配置好的日志器
    """
    logger = logging.getLogger(name or __name__)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有的处理器
    logger.handlers = []
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        file_path = logs_dir / log_file
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称
    
    Returns:
        logging.Logger: 日志器实例
    """
    from src.config import settings
    return setup_logger(
        name,
        level=settings.LOG_LEVEL,
        log_file=f"{settings.APP_NAME.lower().replace(' ', '_')}.log"
    )
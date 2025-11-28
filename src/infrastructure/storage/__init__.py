"""
文件存储基础设施

支持多种存储提供商:
- 本地存储（开发测试）
- 阿里云 OSS
- 腾讯云 COS
- AWS S3

注意: 具体存储实现尚未完成，暂时只导出抽象基类
"""

from src.infrastructure.storage.base_storage import StorageProvider

# TODO: 实现具体存储提供商
# from src.infrastructure.storage.local_storage import LocalStorageService
# from src.infrastructure.storage.aliyun_oss import AliyunOSSService

__all__ = [
    "StorageProvider",
    # "LocalStorageService",  # 待实现
    # "AliyunOSSService"      # 待实现
]

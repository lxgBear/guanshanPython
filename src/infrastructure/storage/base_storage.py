"""
存储服务基类

定义所有存储提供商必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Optional, BinaryIO, Tuple
from pathlib import Path


class StorageProvider(ABC):
    """存储提供商抽象基类"""

    @abstractmethod
    async def upload_file(
        self,
        file_content: BinaryIO,
        destination_path: str,
        content_type: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        上传文件

        Args:
            file_content: 文件内容（二进制流）
            destination_path: 目标路径
            content_type: 内容类型（MIME type）

        Returns:
            (storage_path, access_url) 元组
        """
        pass

    @abstractmethod
    async def download_file(self, file_path: str) -> bytes:
        """
        下载文件

        Args:
            file_path: 文件路径

        Returns:
            文件内容（字节）
        """
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """
        删除文件

        Args:
            file_path: 文件路径

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    async def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在

        Args:
            file_path: 文件路径

        Returns:
            文件是否存在
        """
        pass

    @abstractmethod
    async def get_file_url(
        self,
        file_path: str,
        expires_in: Optional[int] = None
    ) -> str:
        """
        获取文件访问 URL

        Args:
            file_path: 文件路径
            expires_in: 过期时间（秒），None 表示永久

        Returns:
            访问 URL
        """
        pass

    @abstractmethod
    async def get_file_size(self, file_path: str) -> int:
        """
        获取文件大小

        Args:
            file_path: 文件路径

        Returns:
            文件大小（字节）
        """
        pass

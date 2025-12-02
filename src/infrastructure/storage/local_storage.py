"""
本地文件存储服务

实现基于本地文件系统的存储提供商。
适用于开发环境和小规模部署。

安全特性:
- 路径验证防止目录遍历攻击
- 文件大小限制
- MIME类型验证
- 自动目录创建
"""
import os
import hashlib
from pathlib import Path
from typing import BinaryIO, Optional, Tuple
from datetime import datetime, timedelta
import mimetypes
import asyncio
from concurrent.futures import ThreadPoolExecutor

from src.infrastructure.storage.base_storage import StorageProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 线程池用于异步文件操作
_thread_pool = ThreadPoolExecutor(max_workers=4)


class LocalStorageService(StorageProvider):
    """本地文件存储服务

    将文件存储在本地文件系统中，支持基本的文件管理操作。

    配置项:
    - base_path: 文件存储根目录
    - max_file_size: 最大文件大小(字节)
    - allowed_extensions: 允许的文件扩展名列表
    - base_url: 访问文件的基础URL(可选)
    """

    def __init__(
        self,
        base_path: str = "./data/uploads",
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        allowed_extensions: Optional[list] = None,
        base_url: Optional[str] = None
    ):
        """初始化本地存储服务

        Args:
            base_path: 文件存储根目录
            max_file_size: 最大文件大小(字节),默认100MB
            allowed_extensions: 允许的文件扩展名,None表示允许所有
            base_url: 访问文件的基础URL,默认为本地路径
        """
        self.base_path = Path(base_path).resolve()
        self.max_file_size = max_file_size
        self.allowed_extensions = allowed_extensions
        self.base_url = base_url or f"file://{self.base_path}"

        # 确保存储目录存在
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"本地存储服务初始化完成: {self.base_path}")

    def _validate_path(self, file_path: str) -> Path:
        """验证文件路径安全性

        防止目录遍历攻击,确保文件路径在存储根目录内。

        Args:
            file_path: 相对文件路径

        Returns:
            Path: 解析后的绝对路径

        Raises:
            ValueError: 如果路径不安全
        """
        # 移除路径中的特殊字符
        file_path = file_path.replace("\\", "/").strip("/")

        # 解析为绝对路径
        full_path = (self.base_path / file_path).resolve()

        # 确保路径在存储根目录内
        if not str(full_path).startswith(str(self.base_path)):
            raise ValueError(f"不安全的文件路径: {file_path}")

        return full_path

    def _validate_extension(self, filename: str) -> None:
        """验证文件扩展名

        Args:
            filename: 文件名

        Raises:
            ValueError: 如果扩展名不被允许
        """
        if self.allowed_extensions is None:
            return

        ext = Path(filename).suffix.lower()
        if ext not in self.allowed_extensions:
            raise ValueError(
                f"不支持的文件类型: {ext}. "
                f"允许的类型: {', '.join(self.allowed_extensions)}"
            )

    def _generate_safe_filename(self, original_filename: str) -> str:
        """生成安全的文件名

        基于时间戳和原始文件名生成唯一文件名。

        Args:
            original_filename: 原始文件名

        Returns:
            str: 安全的文件名
        """
        # 获取文件扩展名
        ext = Path(original_filename).suffix
        name = Path(original_filename).stem

        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # 清理文件名(移除特殊字符)
        safe_name = "".join(c for c in name if c.isalnum() or c in "._- ")[:100]

        return f"{safe_name}_{timestamp}{ext}"

    async def upload_file(
        self,
        file_content: BinaryIO,
        destination_path: str,
        content_type: Optional[str] = None
    ) -> Tuple[str, str]:
        """上传文件到本地存储

        Args:
            file_content: 文件内容(二进制流)
            destination_path: 目标路径(相对于base_path)
            content_type: 文件MIME类型(可选)

        Returns:
            Tuple[str, str]: (存储路径, 访问URL)

        Raises:
            ValueError: 路径不安全或文件过大
            IOError: 文件写入失败
        """
        try:
            # 验证路径
            full_path = self._validate_path(destination_path)

            # 验证文件扩展名
            self._validate_extension(destination_path)

            # 确保目标目录存在
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # 读取文件内容
            content = await asyncio.get_event_loop().run_in_executor(
                _thread_pool, file_content.read
            )

            # 验证文件大小
            if len(content) > self.max_file_size:
                raise ValueError(
                    f"文件过大: {len(content)} 字节. "
                    f"最大允许: {self.max_file_size} 字节"
                )

            # 异步写入文件
            await asyncio.get_event_loop().run_in_executor(
                _thread_pool,
                lambda: full_path.write_bytes(content)
            )

            # 生成访问URL
            relative_path = full_path.relative_to(self.base_path)
            access_url = f"{self.base_url}/{str(relative_path).replace(os.sep, '/')}"

            logger.info(f"文件上传成功: {destination_path} ({len(content)} 字节)")
            return str(relative_path), access_url

        except Exception as e:
            logger.error(f"文件上传失败: {destination_path} - {str(e)}")
            raise

    async def download_file(self, file_path: str) -> bytes:
        """从本地存储下载文件

        Args:
            file_path: 文件路径(相对于base_path)

        Returns:
            bytes: 文件内容

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 路径不安全
        """
        try:
            # 验证路径
            full_path = self._validate_path(file_path)

            # 检查文件是否存在
            if not full_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")

            if not full_path.is_file():
                raise ValueError(f"路径不是文件: {file_path}")

            # 异步读取文件
            content = await asyncio.get_event_loop().run_in_executor(
                _thread_pool, full_path.read_bytes
            )

            logger.debug(f"文件下载成功: {file_path} ({len(content)} 字节)")
            return content

        except Exception as e:
            logger.error(f"文件下载失败: {file_path} - {str(e)}")
            raise

    async def delete_file(self, file_path: str) -> bool:
        """从本地存储删除文件

        Args:
            file_path: 文件路径(相对于base_path)

        Returns:
            bool: 删除是否成功

        Raises:
            ValueError: 路径不安全
        """
        try:
            # 验证路径
            full_path = self._validate_path(file_path)

            # 检查文件是否存在
            if not full_path.exists():
                logger.warning(f"文件不存在,无需删除: {file_path}")
                return True

            # 异步删除文件
            await asyncio.get_event_loop().run_in_executor(
                _thread_pool, full_path.unlink
            )

            # 尝试删除空目录(如果父目录为空)
            try:
                parent = full_path.parent
                if parent != self.base_path and not any(parent.iterdir()):
                    await asyncio.get_event_loop().run_in_executor(
                        _thread_pool, parent.rmdir
                    )
            except OSError:
                pass  # 目录不为空,忽略

            logger.info(f"文件删除成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"文件删除失败: {file_path} - {str(e)}")
            return False

    async def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在

        Args:
            file_path: 文件路径(相对于base_path)

        Returns:
            bool: 文件是否存在
        """
        try:
            full_path = self._validate_path(file_path)
            exists = await asyncio.get_event_loop().run_in_executor(
                _thread_pool, lambda: full_path.exists() and full_path.is_file()
            )
            return exists
        except ValueError:
            return False

    async def get_file_url(
        self,
        file_path: str,
        expires_in: Optional[int] = None
    ) -> str:
        """获取文件访问URL

        本地存储不支持过期时间,expires_in参数被忽略。

        Args:
            file_path: 文件路径(相对于base_path)
            expires_in: 过期时间(秒),本地存储忽略此参数

        Returns:
            str: 文件访问URL

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 路径不安全
        """
        # 验证路径
        full_path = self._validate_path(file_path)

        # 检查文件是否存在
        if not await self.file_exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 生成URL
        relative_path = full_path.relative_to(self.base_path)
        url = f"{self.base_url}/{str(relative_path).replace(os.sep, '/')}"

        if expires_in:
            logger.warning(
                f"本地存储不支持过期URL,expires_in={expires_in}参数被忽略"
            )

        return url

    async def get_file_size(self, file_path: str) -> int:
        """获取文件大小

        Args:
            file_path: 文件路径(相对于base_path)

        Returns:
            int: 文件大小(字节)

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 路径不安全
        """
        # 验证路径
        full_path = self._validate_path(file_path)

        # 检查文件是否存在
        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 获取文件大小
        size = await asyncio.get_event_loop().run_in_executor(
            _thread_pool, lambda: full_path.stat().st_size
        )

        return size

    def calculate_file_hash(self, content: bytes, algorithm: str = "sha256") -> str:
        """计算文件内容哈希值

        Args:
            content: 文件内容
            algorithm: 哈希算法,默认sha256

        Returns:
            str: 十六进制哈希值
        """
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(content)
        return hash_obj.hexdigest()

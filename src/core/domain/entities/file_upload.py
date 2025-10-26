"""
文件上传领域实体

支持功能:
- 单文件/多文件上传
- 文件类型和大小限制
- 云存储集成（阿里云 OSS、腾讯云 COS、AWS S3）
- 完整的生命周期管理
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4


class UploadStatus(Enum):
    """上传状态枚举"""
    PENDING = "pending"           # 待上传
    UPLOADING = "uploading"       # 上传中
    PROCESSING = "processing"     # 处理中（病毒扫描、格式转换等）
    COMPLETED = "completed"       # 完成
    FAILED = "failed"             # 失败
    DELETED = "deleted"           # 已删除


class StorageProvider(Enum):
    """存储提供商枚举"""
    LOCAL = "local"               # 本地存储
    ALIYUN_OSS = "aliyun_oss"    # 阿里云 OSS
    TENCENT_COS = "tencent_cos"  # 腾讯云 COS
    AWS_S3 = "aws_s3"            # AWS S3
    QINIU = "qiniu"              # 七牛云


class FileCategory(Enum):
    """文件分类枚举"""
    DOCUMENT = "document"         # 文档（PDF, Word, Excel 等）
    IMAGE = "image"              # 图片
    VIDEO = "video"              # 视频
    AUDIO = "audio"              # 音频
    ARCHIVE = "archive"          # 压缩包
    DATA = "data"                # 数据文件（CSV, JSON 等）
    OTHER = "other"              # 其他


@dataclass
class FileUploadConfig:
    """文件上传配置"""
    # 允许的文件类型（MIME types）
    allowed_mime_types: List[str] = field(default_factory=lambda: [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "application/json",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp"
    ])

    # 允许的文件扩展名
    allowed_extensions: List[str] = field(default_factory=lambda: [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".csv", ".json", ".txt",
        ".jpg", ".jpeg", ".png", ".gif", ".webp"
    ])

    # 最大文件大小（字节）默认 10MB
    max_file_size: int = 10 * 1024 * 1024

    # 单次最多上传文件数
    max_files_per_upload: int = 10

    # 是否启用病毒扫描
    enable_virus_scan: bool = True

    # 是否自动压缩图片
    auto_compress_images: bool = True

    # 存储提供商
    storage_provider: StorageProvider = StorageProvider.LOCAL

    # 存储桶名称（云存储）
    storage_bucket: Optional[str] = None

    # 存储路径前缀
    storage_prefix: str = "uploads"


@dataclass
class FileUpload:
    """文件上传实体"""

    # 基础信息
    file_id: str = field(default_factory=lambda: str(uuid4()))
    original_filename: str = ""           # 原始文件名
    stored_filename: str = ""             # 存储文件名（带哈希）
    display_name: Optional[str] = None    # 显示名称（可自定义）

    # 文件属性
    file_size: int = 0                    # 文件大小（字节）
    mime_type: str = ""                   # MIME 类型
    file_extension: str = ""              # 文件扩展名
    category: FileCategory = FileCategory.OTHER

    # 存储信息
    storage_provider: StorageProvider = StorageProvider.LOCAL
    storage_bucket: Optional[str] = None  # 存储桶名称
    storage_path: str = ""                # 存储路径
    storage_url: Optional[str] = None     # 访问 URL
    cdn_url: Optional[str] = None         # CDN 加速 URL

    # 状态管理
    status: UploadStatus = UploadStatus.PENDING
    upload_progress: int = 0              # 上传进度（0-100）

    # 安全检查
    virus_scan_status: Optional[str] = None    # 病毒扫描状态
    content_hash: Optional[str] = None         # 内容哈希（SHA256）

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 关联信息
    uploaded_by: str = ""                 # 上传者
    related_entity_type: Optional[str] = None  # 关联实体类型（search_task, data_source 等）
    related_entity_id: Optional[str] = None    # 关联实体 ID

    # 访问控制
    is_public: bool = False               # 是否公开访问
    access_token: Optional[str] = None    # 访问令牌（私有文件）
    expires_at: Optional[datetime] = None # 过期时间

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None

    # 测试标记
    is_test_data: bool = False

    def mark_as_uploading(self, progress: int = 0) -> None:
        """标记为上传中"""
        self.status = UploadStatus.UPLOADING
        self.upload_progress = progress
        self.updated_at = datetime.utcnow()

    def mark_as_processing(self) -> None:
        """标记为处理中"""
        self.status = UploadStatus.PROCESSING
        self.upload_progress = 100
        self.updated_at = datetime.utcnow()

    def mark_as_completed(self, storage_url: str, cdn_url: Optional[str] = None) -> None:
        """标记为完成"""
        self.status = UploadStatus.COMPLETED
        self.storage_url = storage_url
        self.cdn_url = cdn_url
        self.upload_progress = 100
        self.updated_at = datetime.utcnow()

    def mark_as_failed(self, error_message: str) -> None:
        """标记为失败"""
        self.status = UploadStatus.FAILED
        self.metadata["error"] = error_message
        self.updated_at = datetime.utcnow()

    def mark_as_deleted(self) -> None:
        """软删除"""
        self.status = UploadStatus.DELETED
        self.deleted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def update_progress(self, progress: int) -> None:
        """更新上传进度"""
        self.upload_progress = min(100, max(0, progress))
        self.updated_at = datetime.utcnow()

    def set_virus_scan_result(self, is_clean: bool, details: Optional[str] = None) -> None:
        """设置病毒扫描结果"""
        self.virus_scan_status = "clean" if is_clean else "infected"
        if details:
            self.metadata["virus_scan_details"] = details
        self.updated_at = datetime.utcnow()

    def get_file_size_formatted(self) -> str:
        """获取格式化的文件大小"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def is_image(self) -> bool:
        """判断是否为图片"""
        return self.category == FileCategory.IMAGE

    def is_document(self) -> bool:
        """判断是否为文档"""
        return self.category == FileCategory.DOCUMENT

    def is_expired(self) -> bool:
        """判断是否过期"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "display_name": self.display_name,
            "file_size": self.file_size,
            "file_size_formatted": self.get_file_size_formatted(),
            "mime_type": self.mime_type,
            "file_extension": self.file_extension,
            "category": self.category.value,
            "storage_provider": self.storage_provider.value,
            "storage_bucket": self.storage_bucket,
            "storage_path": self.storage_path,
            "storage_url": self.storage_url,
            "cdn_url": self.cdn_url,
            "status": self.status.value,
            "upload_progress": self.upload_progress,
            "virus_scan_status": self.virus_scan_status,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "uploaded_by": self.uploaded_by,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
            "is_public": self.is_public,
            "access_token": self.access_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "is_test_data": self.is_test_data
        }

    def to_summary(self) -> Dict[str, Any]:
        """转换为摘要（用于列表展示）"""
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "display_name": self.display_name or self.original_filename,
            "file_size": self.file_size,
            "file_size_formatted": self.get_file_size_formatted(),
            "mime_type": self.mime_type,
            "category": self.category.value,
            "status": self.status.value,
            "upload_progress": self.upload_progress,
            "storage_url": self.storage_url if self.is_public else None,
            "cdn_url": self.cdn_url if self.is_public else None,
            "uploaded_by": self.uploaded_by,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class FileUploadBatch:
    """批量上传实体"""

    batch_id: str = field(default_factory=lambda: str(uuid4()))
    files: List[FileUpload] = field(default_factory=list)
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    total_size: int = 0

    uploaded_by: str = ""
    status: UploadStatus = UploadStatus.PENDING

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_file(self, file_upload: FileUpload) -> None:
        """添加文件到批次"""
        self.files.append(file_upload)
        self.total_files += 1
        self.total_size += file_upload.file_size
        self.updated_at = datetime.utcnow()

    def update_stats(self) -> None:
        """更新统计信息"""
        self.completed_files = sum(1 for f in self.files if f.status == UploadStatus.COMPLETED)
        self.failed_files = sum(1 for f in self.files if f.status == UploadStatus.FAILED)
        self.updated_at = datetime.utcnow()

        if self.completed_files + self.failed_files == self.total_files:
            self.status = UploadStatus.COMPLETED if self.failed_files == 0 else UploadStatus.FAILED

    def get_progress_percentage(self) -> int:
        """获取总体进度百分比"""
        if self.total_files == 0:
            return 0
        return int((self.completed_files / self.total_files) * 100)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "batch_id": self.batch_id,
            "total_files": self.total_files,
            "completed_files": self.completed_files,
            "failed_files": self.failed_files,
            "total_size": self.total_size,
            "progress_percentage": self.get_progress_percentage(),
            "uploaded_by": self.uploaded_by,
            "status": self.status.value,
            "files": [f.to_summary() for f in self.files],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

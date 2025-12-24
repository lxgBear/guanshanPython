"""
文件上传服务API端点

提供文件上传、下载、删除和列表功能。
"""
from typing import Optional, List
from datetime import datetime
from io import BytesIO
import os

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    Depends,
    Query,
    Response
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.dependencies.auth import require_permissions
from src.infrastructure.storage.local_storage import LocalStorageService
from src.infrastructure.database.file_upload_repository import MongoFileUploadRepository
from src.core.domain.entities.file_upload import (
    FileUpload,
    UploadStatus,
    StorageProvider as StorageProviderEnum
)
from src.utils.logger import get_logger
from src.infrastructure.id_generator import generate_string_id
from src.services.document_extractor import DocumentExtractor, DocumentExtractionError

logger = get_logger(__name__)
router = APIRouter()

# 从环境变量读取配置
LOCAL_STORAGE_BASE_PATH = os.getenv("LOCAL_STORAGE_BASE_PATH", "./data/uploads")
LOCAL_STORAGE_BASE_URL = os.getenv("LOCAL_STORAGE_BASE_URL", "http://localhost:8000/api/v1/files")
LOCAL_STORAGE_MAX_FILE_SIZE = int(os.getenv("LOCAL_STORAGE_MAX_FILE_SIZE", "104857600"))  # 100MB
LOCAL_STORAGE_ALLOWED_EXTENSIONS = os.getenv("LOCAL_STORAGE_ALLOWED_EXTENSIONS", "")

# 初始化存储服务
def get_storage_service() -> LocalStorageService:
    """获取存储服务实例（依赖注入）"""
    allowed_extensions = None
    if LOCAL_STORAGE_ALLOWED_EXTENSIONS:
        allowed_extensions = [
            ext.strip()
            for ext in LOCAL_STORAGE_ALLOWED_EXTENSIONS.split(",")
            if ext.strip()
        ]

    return LocalStorageService(
        base_path=LOCAL_STORAGE_BASE_PATH,
        max_file_size=LOCAL_STORAGE_MAX_FILE_SIZE,
        allowed_extensions=allowed_extensions,
        base_url=LOCAL_STORAGE_BASE_URL
    )


# 初始化文件上传仓储
def get_file_repository() -> MongoFileUploadRepository:
    """获取文件上传仓储实例（依赖注入）"""
    return MongoFileUploadRepository()


# 初始化文档提取器
def get_document_extractor() -> DocumentExtractor:
    """获取文档提取器实例（依赖注入）"""
    return DocumentExtractor()


# === 请求/响应模型 ===

class UploadResponse(BaseModel):
    """文件上传响应"""
    success: bool = Field(..., description="是否成功")
    file_id: str = Field(..., description="文件唯一标识")
    original_filename: str = Field(..., description="原始文件名")
    stored_filename: str = Field(..., description="存储文件名")
    file_size: int = Field(..., description="文件大小(字节)")
    mime_type: str = Field(..., description="MIME类型")
    storage_path: str = Field(..., description="存储路径")
    storage_url: str = Field(..., description="访问URL")
    content_hash: str = Field(..., description="文件SHA256哈希")
    created_at: str = Field(..., description="上传时间")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "file_id": "1234567890123456789",
                "original_filename": "document.pdf",
                "stored_filename": "document_20240515_123456_789.pdf",
                "file_size": 1024000,
                "mime_type": "application/pdf",
                "storage_path": "2024/05/document_20240515_123456_789.pdf",
                "storage_url": "http://localhost:8000/api/v1/files/2024/05/document_20240515_123456_789.pdf",
                "content_hash": "a1b2c3d4...",
                "created_at": "2024-05-15T12:34:56.789Z"
            }
        }


class FileInfoResponse(BaseModel):
    """文件信息响应"""
    file_id: str = Field(..., description="文件唯一标识")
    original_filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小(字节)")
    mime_type: str = Field(..., description="MIME类型")
    storage_url: str = Field(..., description="访问URL")
    created_at: str = Field(..., description="上传时间")


class FileListResponse(BaseModel):
    """文件列表响应"""
    total: int = Field(..., description="文件总数")
    files: List[FileInfoResponse] = Field(..., description="文件列表")


class DeleteResponse(BaseModel):
    """删除响应"""
    success: bool = Field(..., description="是否成功")
    file_id: str = Field(..., description="文件唯一标识")
    message: str = Field(..., description="消息")


# === API端点 ===

@router.post("/upload", response_model=UploadResponse, summary="上传文件")
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    user_id: Optional[str] = Query(None, description="用户ID"),
    category: Optional[str] = Query(None, description="文件分类"),
    tags: Optional[str] = Query(None, description="文件标签（逗号分隔，例如：重要,合同,2024）"),
    storage_service: LocalStorageService = Depends(get_storage_service),
    file_repository: MongoFileUploadRepository = Depends(get_file_repository),
    document_extractor: DocumentExtractor = Depends(get_document_extractor)
):
    """
    上传文件到服务器

    **优化的工作流程：**
    1. 读取文件到内存
    2. **先提取文档内容（验证文件有效性）**
    3. 提取成功后才存储文件
    4. 保存元数据到 MongoDB

    - **file**: 要上传的文件（仅支持 PDF 和 DOCX）
    - **user_id**: 用户ID(可选)
    - **category**: 文件分类(可选)
    - **tags**: 文件标签，逗号分隔（可选，例如："重要,合同,2024"）

    返回文件信息,包括访问URL和提取的内容摘要。
    """
    try:
        logger.info(f"📤 开始上传文件: {file.filename}, 大小: {file.size} 字节")

        # 生成唯一文件ID
        file_id = generate_string_id()

        # 读取文件内容到内存
        content = await file.read()

        # ========================================
        # 🏷️  解析和验证标签
        # ========================================
        parsed_tags = []
        if tags:
            # 解析逗号分隔的标签
            parsed_tags = [
                tag.strip()
                for tag in tags.split(',')
                if tag.strip()  # 过滤空标签
            ]
            # 去重
            parsed_tags = list(dict.fromkeys(parsed_tags))
            # 限制标签数量（最多10个）
            if len(parsed_tags) > 10:
                parsed_tags = parsed_tags[:10]
            # 限制每个标签长度（最多20字符）
            parsed_tags = [tag[:20] for tag in parsed_tags]

            logger.info(f"📌 文件标签: {parsed_tags}")

        # ========================================
        # 🔥 关键优化：先提取内容，验证文件有效性
        # ========================================
        logger.info(f"📝 开始提取文档内容: {file.filename}")

        try:
            # 从内存中提取文档内容（不存储临时文件）
            extraction_result = await document_extractor.extract_from_bytes(
                file_content=content,
                filename=file.filename
            )

            if not extraction_result.get("success"):
                raise DocumentExtractionError(
                    extraction_result.get("error", "内容提取失败")
                )

            extracted_content = extraction_result.get("content", {})
            logger.info(
                f"✅ 内容提取成功: {file.filename} - "
                f"{extracted_content.get('word_count', 0)} 字"
            )

        except DocumentExtractionError as e:
            logger.error(f"❌ 内容提取失败: {file.filename} - {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"文件内容提取失败，无法上传: {str(e)}"
            )

        # ========================================
        # ✅ 内容提取成功，现在存储文件
        # ========================================
        file_content = BytesIO(content)

        # 生成存储路径(按日期组织: YYYY/MM/filename)
        now = datetime.now()
        date_path = now.strftime("%Y/%m")
        safe_filename = storage_service._generate_safe_filename(file.filename)
        destination_path = f"{date_path}/{safe_filename}"

        # 上传文件到存储
        storage_path, access_url = await storage_service.upload_file(
            file_content=file_content,
            destination_path=destination_path,
            content_type=file.content_type
        )

        # 计算文件哈希
        content_hash = storage_service.calculate_file_hash(content)

        # ========================================
        # 💾 创建文件上传实体，包含提取的内容和标签
        # ========================================
        # 提取标题：使用文件名（去掉扩展名）作为标题
        file_title = os.path.splitext(file.filename)[0] if file.filename else ""

        file_upload = FileUpload(
            file_id=file_id,
            original_filename=file.filename,
            stored_filename=safe_filename,
            title=file_title,                                    # 文件标题
            content=extracted_content.get("text", ""),           # 提取的正文内容
            file_size=len(content),
            mime_type=file.content_type or "application/octet-stream",
            storage_provider=StorageProviderEnum.LOCAL,
            storage_path=storage_path,
            storage_url=access_url,
            status=UploadStatus.COMPLETED,
            content_hash=content_hash,
            uploaded_by=user_id,
            upload_progress=100,
            created_at=now,
            updated_at=now,
            tags=parsed_tags
        )

        # ========================================
        # 🗄️ 保存到 MongoDB
        # ========================================
        await file_repository.create(file_upload)

        logger.info(f"✅ 文件上传完成: {file.filename} -> {access_url}")

        return UploadResponse(
            success=True,
            file_id=file_upload.file_id,
            original_filename=file_upload.original_filename,
            stored_filename=file_upload.stored_filename,
            file_size=file_upload.file_size,
            mime_type=file_upload.mime_type,
            storage_path=storage_path,
            storage_url=access_url,
            content_hash=content_hash,
            created_at=file_upload.created_at.isoformat()
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ 文件上传验证失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 文件上传失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.get("/files/{file_path:path}", summary="下载文件")
async def download_file(
    file_path: str,
    storage_service: LocalStorageService = Depends(get_storage_service)
):
    """
    下载文件

    - **file_path**: 文件路径(例如: 2024/05/document.pdf)

    返回文件内容流。
    """
    try:
        logger.info(f"开始下载文件: {file_path}")

        # 下载文件
        content = await storage_service.download_file(file_path)

        # 获取文件名(用于Content-Disposition)
        filename = os.path.basename(file_path)

        # 猜测MIME类型
        import mimetypes
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type is None:
            mime_type = "application/octet-stream"

        logger.info(f"文件下载成功: {file_path} ({len(content)} 字节)")

        # 返回文件流
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except FileNotFoundError:
        logger.warning(f"文件不存在: {file_path}")
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    except ValueError as e:
        logger.error(f"文件路径不安全: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"文件下载失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")


@router.delete(
    "/files/{file_id}",
    response_model=DeleteResponse,
    summary="删除文件",
    dependencies=[Depends(require_permissions("info:delete"))]
)
async def delete_file(
    file_id: str,
    storage_service: LocalStorageService = Depends(get_storage_service),
    file_repository: MongoFileUploadRepository = Depends(get_file_repository)
):
    """
    删除文件

    - **file_id**: 文件唯一标识

    返回删除结果。
    """
    try:
        logger.info(f"🗑️  开始删除文件: {file_id}")

        # 从数据库查询文件信息
        file_record = await file_repository.get_by_id(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")

        file_path = file_record.storage_path

        # 删除物理文件
        success = await storage_service.delete_file(file_path)

        if success:
            # 更新数据库状态
            file_record.status = UploadStatus.DELETED
            await file_repository.update(file_record)

            logger.info(f"✅ 文件删除成功: {file_id}")
            return DeleteResponse(
                success=True,
                file_id=file_id,
                message="文件删除成功"
            )
        else:
            raise HTTPException(status_code=500, detail="文件删除失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 文件删除失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件删除失败: {str(e)}")


@router.get("/files", response_model=FileListResponse, summary="获取文件列表")
async def list_files(
    user_id: Optional[str] = Query(None, description="用户ID筛选"),
    category: Optional[str] = Query(None, description="分类筛选"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    file_repository: MongoFileUploadRepository = Depends(get_file_repository)
):
    """
    获取文件列表

    - **user_id**: 按用户ID筛选(可选)
    - **category**: 按分类筛选(可选)
    - **limit**: 返回数量,默认50,最大100
    - **offset**: 偏移量,默认0

    返回文件列表。
    """
    try:
        logger.info(
            f"📋 查询文件列表: user_id={user_id}, category={category}, "
            f"limit={limit}, offset={offset}"
        )

        # 从数据库查询文件列表
        files = await file_repository.find_all(
            uploaded_by=user_id,
            status="completed",  # 只返回上传完成的文件
            limit=limit,
            skip=offset
        )

        # 统计总数
        total = await file_repository.count(
            uploaded_by=user_id,
            status="completed"
        )

        logger.info(f"✅ 查询完成,共 {total} 个文件")

        return FileListResponse(
            total=total,
            files=[
                FileInfoResponse(
                    file_id=f.file_id,
                    original_filename=f.original_filename,
                    file_size=f.file_size,
                    mime_type=f.mime_type,
                    storage_url=f.storage_url,
                    created_at=f.created_at.isoformat()
                )
                for f in files
            ]
        )

    except Exception as e:
        logger.error(f"❌ 查询文件列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/files/{file_id}/info", response_model=FileInfoResponse, summary="获取文件信息")
async def get_file_info(
    file_id: str,
    file_repository: MongoFileUploadRepository = Depends(get_file_repository)
):
    """
    获取文件信息

    - **file_id**: 文件唯一标识

    返回文件元数据。
    """
    try:
        logger.info(f"🔍 查询文件信息: {file_id}")

        # 从数据库查询文件信息
        file_record = await file_repository.get_by_id(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")

        logger.info(f"✅ 查询成功: {file_record.original_filename}")

        return FileInfoResponse(
            file_id=file_record.file_id,
            original_filename=file_record.original_filename,
            file_size=file_record.file_size,
            mime_type=file_record.mime_type,
            storage_url=file_record.storage_url,
            created_at=file_record.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 查询文件信息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

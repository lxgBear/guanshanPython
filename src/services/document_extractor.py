"""文档内容提取服务

提供 PDF 和 DOCX 文档的内容提取功能，保留格式信息。

支持格式:
- PDF: 使用 PyMuPDF (fitz) 提取
- DOCX: 使用 python-docx 提取

特性:
- 内存操作，无需临时文件
- 保留文档结构和格式信息
- 异步处理，提高性能
- 详细的错误处理和日志

Version: v1.0.0
"""

import asyncio
from typing import Dict, Any, BinaryIO
from io import BytesIO
from pathlib import Path

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from docx import Document
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentExtractionError(Exception):
    """文档提取异常"""
    pass


class DocumentExtractor:
    """文档内容提取器

    支持从内存中的二进制流提取文档内容，避免临时文件操作。
    """

    def __init__(self):
        """初始化文档提取器

        Raises:
            DocumentExtractionError: 如果必需的库未安装
        """
        if not PYMUPDF_AVAILABLE:
            logger.warning("⚠️ PyMuPDF 未安装，PDF 提取功能不可用")

        if not PYTHON_DOCX_AVAILABLE:
            logger.warning("⚠️ python-docx 未安装，DOCX 提取功能不可用")

        if not PYMUPDF_AVAILABLE and not PYTHON_DOCX_AVAILABLE:
            raise DocumentExtractionError(
                "缺少必需的库。请安装: pip install PyMuPDF python-docx"
            )

    async def extract_from_bytes(
        self,
        file_content: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """从字节流提取文档内容

        根据文件扩展名自动选择提取方法。

        Args:
            file_content: 文件二进制内容
            filename: 文件名（用于判断文件类型）

        Returns:
            提取结果字典，包含:
            - success: bool - 是否成功
            - content: dict - 提取的内容（成功时）
            - error: str - 错误信息（失败时）
            - file_type: str - 文件类型

        Raises:
            DocumentExtractionError: 不支持的文件类型或提取失败
        """
        file_extension = Path(filename).suffix.lower()

        try:
            if file_extension == '.pdf':
                if not PYMUPDF_AVAILABLE:
                    raise DocumentExtractionError("PyMuPDF 未安装，无法提取 PDF")
                content = await self.extract_pdf(file_content)
                return {
                    "success": True,
                    "content": content,
                    "file_type": "pdf"
                }

            elif file_extension in ['.docx', '.doc']:
                if not PYTHON_DOCX_AVAILABLE:
                    raise DocumentExtractionError("python-docx 未安装，无法提取 DOCX")
                content = await self.extract_docx(file_content)
                return {
                    "success": True,
                    "content": content,
                    "file_type": "docx"
                }

            else:
                raise DocumentExtractionError(
                    f"不支持的文件类型: {file_extension}。仅支持 .pdf, .docx"
                )

        except DocumentExtractionError:
            raise
        except Exception as e:
            logger.error(f"❌ 文档提取失败: {filename} - {str(e)}", exc_info=True)
            raise DocumentExtractionError(f"文档提取失败: {str(e)}")

    async def extract_pdf(self, file_content: bytes) -> Dict[str, Any]:
        """提取 PDF 文档内容

        使用 PyMuPDF 从内存中的 PDF 提取内容，保留格式信息。

        Args:
            file_content: PDF 文件二进制内容

        Returns:
            包含以下字段的字典:
            - total_pages: int - 总页数
            - text: str - 全文内容
            - pages: list - 每页详细信息
            - metadata: dict - PDF 元数据
            - has_images: bool - 是否包含图片
            - word_count: int - 总字数（近似）

        Raises:
            DocumentExtractionError: PDF 提取失败
        """
        try:
            # 在线程池中执行 PDF 解析（避免阻塞）
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                self._extract_pdf_sync,
                file_content
            )

            logger.info(f"✅ PDF 提取成功: {content['word_count']} 字")

            return content

        except Exception as e:
            logger.error(f"❌ PDF 提取失败: {str(e)}", exc_info=True)
            raise DocumentExtractionError(f"PDF 提取失败: {str(e)}")

    def _extract_pdf_sync(self, file_content: bytes) -> Dict[str, Any]:
        """同步 PDF 提取（在线程池中运行）

        Args:
            file_content: PDF 文件二进制内容

        Returns:
            提取的内容字典（简化版，只包含 text 和 word_count）
        """
        # 从字节流打开 PDF
        doc = fitz.open(stream=file_content, filetype="pdf")

        text_parts = []

        # 逐页提取文本内容
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text("text")
            if page_text.strip():
                text_parts.append(page_text)

        # 关闭文档
        doc.close()

        # 合并为单一文本字符串
        full_text = "\n\n".join(text_parts)

        return {
            "text": full_text,
            "word_count": len(full_text.split())
        }

    async def extract_docx(self, file_content: bytes) -> Dict[str, Any]:
        """提取 DOCX 文档内容

        使用 python-docx 从内存中的 DOCX 提取内容，保留格式信息。

        Args:
            file_content: DOCX 文件二进制内容

        Returns:
            包含以下字段的字典:
            - total_paragraphs: int - 总段落数
            - text: str - 全文内容
            - paragraphs: list - 段落详细信息
            - has_tables: bool - 是否包含表格
            - table_count: int - 表格数量
            - word_count: int - 总字数（近似）

        Raises:
            DocumentExtractionError: DOCX 提取失败
        """
        try:
            # 在线程池中执行 DOCX 解析（避免阻塞）
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                self._extract_docx_sync,
                file_content
            )

            logger.info(f"✅ DOCX 提取成功: {content['word_count']} 字")

            return content

        except Exception as e:
            logger.error(f"❌ DOCX 提取失败: {str(e)}", exc_info=True)
            raise DocumentExtractionError(f"DOCX 提取失败: {str(e)}")

    def _extract_docx_sync(self, file_content: bytes) -> Dict[str, Any]:
        """同步 DOCX 提取（在线程池中运行）

        Args:
            file_content: DOCX 文件二进制内容

        Returns:
            提取的内容字典（简化版，只包含 text 和 word_count）
        """
        # 从字节流打开 DOCX
        doc = Document(BytesIO(file_content))

        text_parts = []

        # 提取段落内容
        for para in doc.paragraphs:
            if para.text.strip():  # 跳过空段落
                text_parts.append(para.text)

        # 提取表格内容
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join([cell.text for cell in row.cells if cell.text.strip()])
                if row_text.strip():
                    text_parts.append(row_text)

        # 合并为单一文本字符串
        full_text = "\n".join(text_parts)

        return {
            "text": full_text,
            "word_count": len(full_text.split())
        }

    @staticmethod
    def validate_file_type(filename: str) -> bool:
        """验证文件类型是否支持

        Args:
            filename: 文件名

        Returns:
            是否支持该文件类型
        """
        supported_extensions = {'.pdf', '.docx', '.doc'}
        file_extension = Path(filename).suffix.lower()
        return file_extension in supported_extensions

    @staticmethod
    def get_supported_types() -> list:
        """获取支持的文件类型列表

        Returns:
            支持的文件扩展名列表
        """
        return ['.pdf', '.docx']

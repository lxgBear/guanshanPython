"""
领域实体单元测试
"""
import pytest
from uuid import UUID
from datetime import datetime

from src.core.domain.entities.document import Document, DocumentStatus


class TestDocument:
    """Document实体测试"""
    
    def test_create_document(self):
        """测试创建文档"""
        doc = Document(
            url="https://example.com",
            content="Test content",
            title="Test Document"
        )
        
        assert isinstance(doc.id, UUID)
        assert doc.url == "https://example.com"
        assert doc.content == "Test content"
        assert doc.title == "Test Document"
        assert doc.status == DocumentStatus.PENDING
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)
    
    def test_document_status_transitions(self):
        """测试文档状态转换"""
        doc = Document()
        
        # 初始状态应为PENDING
        assert doc.status == DocumentStatus.PENDING
        
        # 标记为处理中
        doc.mark_processing()
        assert doc.status == DocumentStatus.PROCESSING
        
        # 标记为已处理
        doc.mark_processed()
        assert doc.status == DocumentStatus.PROCESSED
        
        # 标记为失败
        doc.mark_failed("Error message")
        assert doc.status == DocumentStatus.FAILED
        assert doc.error == "Error message"
    
    def test_update_content(self):
        """测试更新文档内容"""
        doc = Document()
        original_updated_at = doc.updated_at
        
        doc.update_content(
            content="New content",
            markdown="# New Content",
            metadata={"key": "value"}
        )
        
        assert doc.content == "New content"
        assert doc.markdown == "# New Content"
        assert doc.metadata == {"key": "value"}
        assert doc.updated_at > original_updated_at
    
    def test_is_valid(self):
        """测试文档有效性验证"""
        # 空文档无效
        doc1 = Document()
        assert not doc1.is_valid()
        
        # 只有URL也无效
        doc2 = Document(url="https://example.com")
        assert not doc2.is_valid()
        
        # 有URL和内容才有效
        doc3 = Document(
            url="https://example.com",
            content="Content"
        )
        assert doc3.is_valid()
    
    def test_to_dict(self):
        """测试转换为字典"""
        doc = Document(
            url="https://example.com",
            content="Test content",
            title="Test Title",
            metadata={"key": "value"}
        )
        
        doc_dict = doc.to_dict()
        
        assert doc_dict["url"] == "https://example.com"
        assert doc_dict["content"] == "Test content"
        assert doc_dict["title"] == "Test Title"
        assert doc_dict["status"] == "pending"
        assert doc_dict["metadata"] == {"key": "value"}
        assert "id" in doc_dict
        assert "created_at" in doc_dict
        assert "updated_at" in doc_dict
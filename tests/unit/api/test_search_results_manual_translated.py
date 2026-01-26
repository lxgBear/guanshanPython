"""
翻译内容录入接口单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.api.v1.endpoints.search_results_manual import (
    TranslatedContentRequest,
    add_translated_content,
)
from src.core.domain.entities.auth import User


class TestTranslatedContentRequest:
    """TranslatedContentRequest 模型测试"""

    def test_valid_minimal_request(self):
        """测试最小有效请求"""
        request = TranslatedContentRequest(
            title="测试标题",
            content="测试内容"
        )
        assert request.title == "测试标题"
        assert request.content == "测试内容"
        assert request.url is None
        assert request.primary_category is None

    def test_valid_full_request(self):
        """测试完整请求"""
        request = TranslatedContentRequest(
            title="完整测试标题",
            content="完整测试内容",
            url="https://example.com",
            published_date=datetime(2026, 1, 26),
            primary_category="安全情报",
            secondary_category="类别",
            tertiary_category="东亚",
            tags=["标签1", "标签2"],
            notes="备注信息"
        )
        assert request.title == "完整测试标题"
        assert request.primary_category == "安全情报"
        assert len(request.tags) == 2

    def test_invalid_empty_title(self):
        """测试空标题应失败"""
        with pytest.raises(ValueError):
            TranslatedContentRequest(
                title="",
                content="测试内容"
            )

    def test_invalid_empty_content(self):
        """测试空内容应失败"""
        with pytest.raises(ValueError):
            TranslatedContentRequest(
                title="测试标题",
                content=""
            )


class TestAddTranslatedContent:
    """add_translated_content 端点测试"""

    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = MagicMock(spec=User)
        user.id = "test_user_123"
        return user

    @pytest.fixture
    def mock_db(self):
        """模拟数据库"""
        db = MagicMock()
        db.search_results = MagicMock()
        db.search_results.insert_one = AsyncMock(return_value=MagicMock())
        return db

    @pytest.mark.asyncio
    async def test_add_translated_content_success(self, mock_user, mock_db):
        """测试成功录入翻译内容"""
        request = TranslatedContentRequest(
            title="测试翻译内容",
            content="这是翻译后的内容，完整保存。",
            primary_category="安全情报",
            secondary_category="维稳",
            tertiary_category="东亚"
        )

        with patch(
            "src.api.v1.endpoints.search_results_manual.generate_string_id",
            side_effect=["task_123456", "result_789"]
        ):
            response = await add_translated_content(
                request=request,
                current_user=mock_user,
                db=mock_db
            )

        assert response.success is True
        assert response.message == "翻译内容录入成功"
        assert response.data["title"] == "测试翻译内容"

        # 验证数据库调用
        mock_db.search_results.insert_one.assert_called_once()
        inserted_data = mock_db.search_results.insert_one.call_args[0][0]

        # 验证字段映射
        assert inserted_data["user_id"] == "test_user_123"
        assert inserted_data["created_by"] == "test_user_123"
        assert inserted_data["snippet"] == "这是翻译后的内容，完整保存。"
        assert inserted_data["markdown_content"] == "这是翻译后的内容，完整保存。"
        assert inserted_data["source"] == "translated"
        assert inserted_data["language"] == "zh-CN"

        # 验证 metadata 分类格式
        assert inserted_data["metadata"]["category"]["大类"] == "安全情报"
        assert inserted_data["metadata"]["category"]["类别"] == "维稳"
        assert inserted_data["metadata"]["category"]["地域"] == "东亚"
        assert inserted_data["metadata"]["input_type"] == "translated"

    @pytest.mark.asyncio
    async def test_add_translated_content_minimal(self, mock_user, mock_db):
        """测试最小字段录入"""
        request = TranslatedContentRequest(
            title="最小测试",
            content="最小内容"
        )

        with patch(
            "src.api.v1.endpoints.search_results_manual.generate_string_id",
            side_effect=["task_min", "result_min"]
        ):
            response = await add_translated_content(
                request=request,
                current_user=mock_user,
                db=mock_db
            )

        assert response.success is True

        inserted_data = mock_db.search_results.insert_one.call_args[0][0]
        assert inserted_data["url"] == ""
        assert inserted_data["metadata"]["category"]["大类"] is None
        assert inserted_data["metadata"]["tags"] == []

    @pytest.mark.asyncio
    async def test_add_translated_content_with_tags(self, mock_user, mock_db):
        """测试带标签录入"""
        request = TranslatedContentRequest(
            title="带标签测试",
            content="带标签内容",
            tags=["标签A", "标签B", "标签C"],
            notes="这是备注"
        )

        with patch(
            "src.api.v1.endpoints.search_results_manual.generate_string_id",
            side_effect=["task_tags", "result_tags"]
        ):
            response = await add_translated_content(
                request=request,
                current_user=mock_user,
                db=mock_db
            )

        assert response.success is True

        inserted_data = mock_db.search_results.insert_one.call_args[0][0]
        assert inserted_data["metadata"]["tags"] == ["标签A", "标签B", "标签C"]
        assert inserted_data["metadata"]["notes"] == "这是备注"

"""
数据源管理接口认证测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.v1.endpoints.data_source_management import (
    CreateDataSourceRequest,
    create_data_source,
)
from src.core.domain.entities.auth.user import User


class TestCreateDataSourceRequest:
    """CreateDataSourceRequest 模型测试"""

    def test_valid_request_without_created_by(self):
        """测试不含 created_by 的有效请求"""
        request = CreateDataSourceRequest(
            title="测试数据源",
            description="测试描述"
        )
        assert request.title == "测试数据源"
        assert request.description == "测试描述"
        # created_by 字段已移除，不应存在于 model_fields
        assert 'created_by' not in request.model_fields

    def test_valid_request_with_categories(self):
        """测试带分类的有效请求"""
        request = CreateDataSourceRequest(
            title="测试数据源",
            description="测试描述",
            primary_category="安全情报",
            secondary_category="维稳",
            tertiary_category="东亚",
            metadata={
                "category": {
                    "大类": "安全情报",
                    "类别": "维稳",
                    "地域": "东亚"
                }
            }
        )
        assert request.primary_category == "安全情报"
        assert request.metadata["category"]["大类"] == "安全情报"


class TestCreateDataSource:
    """create_data_source 端点测试"""

    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = MagicMock(spec=User)
        user.id = "test_user_123"
        user.is_active = True
        user.is_locked = False
        return user

    @pytest.fixture
    def mock_service(self):
        """模拟数据源服务"""
        service = MagicMock()
        mock_data_source = MagicMock()
        mock_data_source.to_dict.return_value = {
            "id": "ds_123",
            "title": "测试数据源",
            "created_by": "test_user_123"
        }
        service.create_data_source = AsyncMock(return_value=mock_data_source)
        return service

    @pytest.mark.asyncio
    async def test_create_data_source_uses_jwt_user(self, mock_user, mock_service):
        """测试 created_by 从 JWT Token 获取"""
        request = CreateDataSourceRequest(
            title="测试数据源",
            description="测试描述"
        )

        response = await create_data_source(
            request=request,
            current_user=mock_user,
            service=mock_service
        )

        assert response["success"] is True

        # 验证 service 调用时使用了 current_user.id
        mock_service.create_data_source.assert_called_once()
        call_kwargs = mock_service.create_data_source.call_args.kwargs
        assert call_kwargs["created_by"] == "test_user_123"

    @pytest.mark.asyncio
    async def test_create_data_source_with_metadata_category(self, mock_user, mock_service):
        """测试带 metadata.category 的创建"""
        request = CreateDataSourceRequest(
            title="测试数据源",
            description="测试描述",
            primary_category="安全情报",
            metadata={
                "source_type": "file",
                "category": {
                    "大类": "安全情报",
                    "类别": "维稳",
                    "地域": "东亚"
                }
            }
        )

        response = await create_data_source(
            request=request,
            current_user=mock_user,
            service=mock_service
        )

        assert response["success"] is True

        call_kwargs = mock_service.create_data_source.call_args.kwargs
        assert call_kwargs["metadata"]["category"]["大类"] == "安全情报"

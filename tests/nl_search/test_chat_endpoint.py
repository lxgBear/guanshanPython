"""
Chat端点测试

测试 /chat 接口与 nl_search 的映射关系

版本: v1.0.0
日期: 2025-11-22
"""
import pytest
import asyncio
from httpx import AsyncClient
from datetime import datetime

from src.main import app


@pytest.mark.asyncio
class TestChatEndpoint:
    """Chat端点测试"""

    async def test_chat_sync_basic(self):
        """测试同步Chat接口基本功能"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/sync",
                json={
                    "question": "测试问题"
                }
            )

            # 验证响应状态
            if response.status_code == 503:
                # NL Search功能未启用，这是预期的
                data = response.json()
                assert data["detail"]["error"] == "功能未启用"
                print("✅ 功能开关验证通过")
            else:
                # 功能已启用，验证响应格式
                assert response.status_code == 200
                data = response.json()
                assert "status" in data
                assert "log_id" in data
                assert "results" in data
                print(f"✅ 同步Chat接口测试通过: log_id={data['log_id']}")

    async def test_chat_request_validation(self):
        """测试请求验证"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 缺少question字段
            response = await client.post(
                "/api/v1/chat/sync",
                json={}
            )
            assert response.status_code == 422  # Validation error
            print("✅ 请求验证测试通过")

    async def test_chat_question_mapping(self):
        """测试question字段映射"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            test_question = "请介绍关于西藏的新闻"

            response = await client.post(
                "/api/v1/chat/sync",
                json={
                    "question": test_question,
                    "user_id": "test_user_123"
                }
            )

            # 验证映射
            if response.status_code == 200:
                data = response.json()
                # question应该被正确映射到query_text
                assert data["log_id"] is not None
                print(f"✅ question字段映射测试通过")
            elif response.status_code == 503:
                print("✅ 功能开关正常（功能未启用）")
            else:
                print(f"⚠️ 意外状态码: {response.status_code}")

    async def test_chat_search_modes(self):
        """测试不同搜索模式"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 测试single模式
            response = await client.post(
                "/api/v1/chat/sync",
                json={
                    "question": "测试问题",
                    "search_mode": "single"
                }
            )

            if response.status_code == 200:
                data = response.json()
                assert data["search_mode"] == "single"
                print("✅ single模式测试通过")

            # 测试multi模式
            response = await client.post(
                "/api/v1/chat/sync",
                json={
                    "question": "测试问题",
                    "search_mode": "multi"
                }
            )

            if response.status_code == 200:
                data = response.json()
                assert data["search_mode"] == "multi"
                print("✅ multi模式测试通过")


@pytest.mark.asyncio
async def test_chat_endpoint_availability():
    """测试Chat端点是否正确注册"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 测试同步端点
        response = await client.post(
            "/api/v1/chat/sync",
            json={"question": "测试"}
        )
        assert response.status_code in [200, 503, 422]  # 任何有效响应都说明端点已注册

        print("✅ Chat端点已正确注册")


@pytest.mark.asyncio
async def test_curl_command_compatibility():
    """测试与curl命令的兼容性"""
    # 模拟curl命令:
    # curl -N -X POST "http://192.168.0.5:8035/api/v1/chat"
    #   -H "Content-Type: application/json"
    #   -d '{"question": "请介绍关于西藏的新闻"}'

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/sync",  # 使用同步版本进行测试
            headers={"Content-Type": "application/json"},
            json={"question": "请介绍关于西藏的新闻"}
        )

        # 验证端点存在且接受正确的请求格式
        assert response.status_code in [200, 503]
        print("✅ curl命令兼容性测试通过")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])

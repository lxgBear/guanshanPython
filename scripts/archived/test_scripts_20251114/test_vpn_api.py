"""
VPN API 测试脚本
测试 VPN 管理功能的完整流程
"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1/vpn"


async def test_vpn_api():
    """测试 VPN API 完整流程"""

    async with httpx.AsyncClient() as client:
        print("=" * 60)
        print("VPN API 测试开始")
        print("=" * 60)

        # 1. 创建 VPN 连接
        print("\n1️⃣  创建 VPN 连接配置...")
        create_data = {
            "connection_name": "Hancens VPN",
            "server_host": "hancens.top",
            "server_port": 1194,
            "config_file_path": "/vpn/lxg.ovpn",
            "protocol": "udp",
            "created_by": "test_user"
        }

        response = await client.post(f"{BASE_URL}/connections", json=create_data)
        if response.status_code == 200:
            connection = response.json()
            connection_id = connection["connection_id"]
            print(f"✅ 创建成功！连接ID: {connection_id}")
            print(f"   连接名称: {connection['connection_name']}")
            print(f"   服务器: {connection['server_host']}:{connection['server_port']}")
        else:
            print(f"❌ 创建失败: {response.text}")
            return

        # 2. 查询所有连接
        print("\n2️⃣  查询所有 VPN 连接...")
        response = await client.get(f"{BASE_URL}/connections")
        if response.status_code == 200:
            connections = response.json()
            print(f"✅ 查询成功！共 {len(connections)} 个连接")
            for conn in connections:
                print(f"   - {conn['connection_name']} ({conn['connection_id']})")
        else:
            print(f"❌ 查询失败: {response.text}")

        # 3. 获取指定连接
        print(f"\n3️⃣  获取连接详情 ({connection_id})...")
        response = await client.get(f"{BASE_URL}/connections/{connection_id}")
        if response.status_code == 200:
            connection = response.json()
            print(f"✅ 获取成功！")
            print(f"   连接名称: {connection['connection_name']}")
            print(f"   状态: {connection['status']}")
            print(f"   总连接次数: {connection['total_connections']}")
        else:
            print(f"❌ 获取失败: {response.text}")

        # 4. 连接 VPN
        print(f"\n4️⃣  连接 VPN ({connection_id})...")
        connect_data = {"connection_id": connection_id}
        response = await client.post(f"{BASE_URL}/connect", json=connect_data)
        if response.status_code == 200:
            log = response.json()
            print(f"✅ 连接成功！")
            print(f"   日志ID: {log['log_id']}")
            print(f"   分配IP: {log['ip_address']}")
            print(f"   开始时间: {log['started_at']}")
        else:
            print(f"❌ 连接失败: {response.text}")

        # 模拟使用 VPN
        print("\n⏳ 模拟使用 VPN 中（3秒）...")
        await asyncio.sleep(3)

        # 5. 断开 VPN
        print(f"\n5️⃣  断开 VPN ({connection_id})...")
        disconnect_data = {
            "connection_id": connection_id,
            "duration_seconds": 3,
            "bytes_sent": 1024000,
            "bytes_received": 2048000
        }
        response = await client.post(f"{BASE_URL}/disconnect", json=disconnect_data)
        if response.status_code == 200:
            log = response.json()
            print(f"✅ 断开成功！")
            print(f"   连接时长: {log['duration_seconds']} 秒")
            print(f"   发送数据: {log['bytes_sent']} 字节")
            print(f"   接收数据: {log['bytes_received']} 字节")
        else:
            print(f"❌ 断开失败: {response.text}")

        # 6. 查询连接日志
        print(f"\n6️⃣  查询连接日志 ({connection_id})...")
        response = await client.get(f"{BASE_URL}/connections/{connection_id}/logs?limit=10")
        if response.status_code == 200:
            logs = response.json()
            print(f"✅ 查询成功！共 {len(logs)} 条日志")
            for log in logs:
                print(f"   - {log['action']} | {log['status']} | {log['started_at']}")
        else:
            print(f"❌ 查询失败: {response.text}")

        # 7. 查询连接统计
        print(f"\n7️⃣  查询连接统计 ({connection_id})...")
        response = await client.get(f"{BASE_URL}/connections/{connection_id}/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ 查询成功！")
            print(f"   总连接次数: {stats['total_connections']}")
            print(f"   总发送数据: {stats['total_bytes_sent']} 字节")
            print(f"   总接收数据: {stats['total_bytes_received']} 字节")
            print(f"   平均时长: {stats['avg_duration']} 秒")
        else:
            print(f"❌ 查询失败: {response.text}")

        print("\n" + "=" * 60)
        print("VPN API 测试完成！")
        print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_vpn_api())
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()

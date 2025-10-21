"""
测试新的 MongoDB 数据库连接
数据库: guanshan
用户: guanshan
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime


async def test_new_mongodb():
    """测试新的 MongoDB 配置"""

    print("\n" + "=" * 60)
    print("测试新 MongoDB 数据库 - VPN 功能初始化")
    print("=" * 60)

    # 新数据库配置
    DB_HOST = "hancens.top"
    DB_PORT = 27017
    DB_NAME = "guanshan"
    DB_USER = "guanshan"
    DB_PASS = "5iSFspPkCLG5cRiD"

    # 构建连接字符串
    MONGO_URL = f"mongodb://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?authSource={DB_NAME}"

    print(f"\n📍 连接信息:")
    print(f"   服务器: {DB_HOST}:{DB_PORT}")
    print(f"   数据库: {DB_NAME}")
    print(f"   用户: {DB_USER}")
    print(f"\n⚠️  当前 MongoDB 监听: 127.0.0.1 (仅本地)")
    print(f"   需要修改为: 0.0.0.0 (允许远程)")

    try:
        # 尝试连接
        print(f"\n1️⃣  正在连接...")
        client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000
        )

        await asyncio.wait_for(client.admin.command('ping'), timeout=10.0)
        print("✅ 数据库连接成功！")

        db = client[DB_NAME]

        # 查看现有集合
        print(f"\n2️⃣  查看数据库集合...")
        collections = await db.list_collection_names()
        print(f"   集合数量: {len(collections)}")
        if collections:
            for coll in collections:
                count = await db[coll].count_documents({})
                print(f"   - {coll}: {count} 个文档")
        else:
            print("   (数据库为空)")

        # 创建 VPN 索引
        print(f"\n3️⃣  创建 VPN 数据库索引...")

        # VPN 连接配置
        print("   创建 vpn_connections 索引...")
        vpn_conn = db.vpn_connections
        await vpn_conn.create_index("connection_id", unique=True)
        await vpn_conn.create_index("created_by")
        await vpn_conn.create_index("status")
        await vpn_conn.create_index("server_host")
        await vpn_conn.create_index("created_at")
        print("   ✅ vpn_connections")

        # VPN 日志
        print("   创建 vpn_connection_logs 索引...")
        vpn_logs = db.vpn_connection_logs
        await vpn_logs.create_index("connection_id")
        await vpn_logs.create_index("action")
        await vpn_logs.create_index("status")
        await vpn_logs.create_index("started_at")
        await vpn_logs.create_index([("connection_id", 1), ("started_at", -1)])
        print("   ✅ vpn_connection_logs")

        # 验证索引
        print(f"\n4️⃣  验证索引...")
        conn_indexes = await vpn_conn.list_indexes().to_list(length=100)
        log_indexes = await vpn_logs.list_indexes().to_list(length=100)
        print(f"   vpn_connections: {len(conn_indexes)} 个索引")
        print(f"   vpn_connection_logs: {len(log_indexes)} 个索引")

        # 测试写入
        print(f"\n5️⃣  测试数据写入...")
        test_id = f"test_{int(datetime.utcnow().timestamp())}"
        test_doc = {
            "connection_id": test_id,
            "connection_name": "测试 VPN 连接",
            "server_host": "hancens.top",
            "server_port": 1194,
            "protocol": "udp",
            "config_file_path": "/vpn/lxg.ovpn",
            "cipher": "AES-128-GCM",
            "auth_method": "SHA256",
            "status": "inactive",
            "is_enabled": True,
            "created_by": "system_test",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "total_connections": 0,
            "metadata": {}
        }

        await vpn_conn.insert_one(test_doc)
        print(f"   ✅ 插入: {test_id}")

        # 测试查询
        found = await vpn_conn.find_one({"connection_id": test_id})
        if found:
            print(f"   ✅ 查询: {found['connection_name']}")

        # 测试更新
        await vpn_conn.update_one(
            {"connection_id": test_id},
            {"$set": {"status": "active"}, "$inc": {"total_connections": 1}}
        )
        updated = await vpn_conn.find_one({"connection_id": test_id})
        print(f"   ✅ 更新: status={updated['status']}, count={updated['total_connections']}")

        # 清理测试数据
        await vpn_conn.delete_one({"connection_id": test_id})
        print(f"   ✅ 清理完成")

        # 最终统计
        print(f"\n6️⃣  数据库统计...")
        conn_count = await vpn_conn.count_documents({})
        log_count = await vpn_logs.count_documents({})
        print(f"   vpn_connections: {conn_count} 个文档")
        print(f"   vpn_connection_logs: {log_count} 个文档")

        print("\n" + "=" * 60)
        print("✅ VPN 数据库初始化完成！")
        print("=" * 60)

        print("\n💾 项目配置 (.env):")
        print(f"MONGODB_URL=mongodb://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?authSource={DB_NAME}")
        print(f"MONGODB_DB_NAME={DB_NAME}")

        print("\n🚀 下一步:")
        print("   1. 更新 .env 文件")
        print("   2. 重启应用")
        print("   3. 访问 http://localhost:8000/docs 测试 VPN API")

        client.close()

    except asyncio.TimeoutError:
        print("\n❌ 连接超时！")
        print("\n原因: MongoDB 监听在 127.0.0.1，无法从外部访问")
        print("\n解决方案：")
        print("=" * 60)
        print("在宝塔面板修改 MongoDB 配置:")
        print("1. 数据库 → MongoDB → 配置修改")
        print("2. 找到 bindIp 或 net.bindIp")
        print("3. 修改为:")
        print("   net:")
        print("     bindIp: 0.0.0.0")
        print("     port: 27017")
        print("4. 保存并重启 MongoDB")
        print("5. 重新运行此脚本")
        print("=" * 60)
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_new_mongodb())

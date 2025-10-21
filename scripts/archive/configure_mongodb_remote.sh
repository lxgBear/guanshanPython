#!/bin/bash

# MongoDB 远程访问配置脚本
# 在宝塔服务器上运行此脚本

echo "========================================"
echo "配置 MongoDB 允许远程访问"
echo "========================================"

# 查找 MongoDB 配置文件
echo -e "\n1️⃣  查找 MongoDB 配置文件..."

CONFIG_PATHS=(
    "/etc/mongod.conf"
    "/etc/mongodb.conf"
    "/www/server/mongodb/config.conf"
    "/usr/local/mongodb/conf/mongod.conf"
)

CONFIG_FILE=""
for path in "${CONFIG_PATHS[@]}"; do
    if [ -f "$path" ]; then
        CONFIG_FILE="$path"
        echo "✅ 找到配置文件: $CONFIG_FILE"
        break
    fi
done

if [ -z "$CONFIG_FILE" ]; then
    echo "❌ 未找到 MongoDB 配置文件"
    echo "请手动查找: find / -name mongod.conf 2>/dev/null"
    exit 1
fi

# 备份配置文件
echo -e "\n2️⃣  备份配置文件..."
BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo "✅ 备份到: $BACKUP_FILE"

# 显示当前配置
echo -e "\n3️⃣  当前 bindIp 配置:"
grep -E "bindIp|bind_ip" "$CONFIG_FILE" || echo "未找到 bindIp 配置"

# 修改 bindIp
echo -e "\n4️⃣  修改 bindIp 为 0.0.0.0..."

# 方法1: 修改 YAML 格式的配置 (bindIp: 127.0.0.1)
sed -i 's/bindIp: 127.0.0.1/bindIp: 0.0.0.0/g' "$CONFIG_FILE"

# 方法2: 修改旧格式配置 (bind_ip = 127.0.0.1)
sed -i 's/bind_ip = 127.0.0.1/bind_ip = 0.0.0.0/g' "$CONFIG_FILE"
sed -i 's/bind_ip=127.0.0.1/bind_ip=0.0.0.0/g' "$CONFIG_FILE"

# 验证修改
echo -e "\n5️⃣  验证修改后的配置:"
grep -E "bindIp|bind_ip" "$CONFIG_FILE"

# 重启 MongoDB
echo -e "\n6️⃣  重启 MongoDB 服务..."

# 尝试不同的重启命令
if command -v systemctl &> /dev/null; then
    systemctl restart mongod || systemctl restart mongodb
    echo "✅ MongoDB 重启完成 (systemctl)"
elif command -v service &> /dev/null; then
    service mongod restart || service mongodb restart
    echo "✅ MongoDB 重启完成 (service)"
else
    echo "⚠️  请手动重启 MongoDB 服务"
fi

# 等待服务启动
sleep 3

# 验证 MongoDB 运行状态
echo -e "\n7️⃣  验证 MongoDB 状态..."

if command -v systemctl &> /dev/null; then
    systemctl status mongod --no-pager | head -10
fi

# 检查监听端口
echo -e "\n8️⃣  检查端口监听..."
netstat -tuln | grep 27017 || ss -tuln | grep 27017

echo -e "\n========================================"
echo "✅ 配置完成！"
echo "========================================"

echo -e "\n📊 验证结果:"
echo "如果看到: 0.0.0.0:27017 - 表示配置成功"
echo "如果看到: 127.0.0.1:27017 - 表示需要手动检查"

echo -e "\n🔍 如果配置未生效，请检查:"
echo "1. MongoDB 服务是否重启成功"
echo "2. 配置文件是否正确修改"
echo "3. 是否有其他配置覆盖了 bindIp"

#!/bin/bash

# VPN数据库连接诊断脚本
# 用于排查VPN连接后数据库无法访问的问题

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}\n"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# 1. VPN接口检查
print_header "1. VPN接口状态检查"

if ifconfig | grep -q "utun"; then
    print_success "VPN接口已创建"

    # 查找有IP地址的utun接口
    VPN_INTERFACE=$(ifconfig | grep -B 1 "inet 10\." | grep "^utun" | awk '{print $1}' | sed 's/://' | head -1)

    if [ -n "$VPN_INTERFACE" ]; then
        print_success "找到VPN接口: $VPN_INTERFACE"
        VPN_IP=$(ifconfig "$VPN_INTERFACE" | grep "inet " | awk '{print $2}')
        VPN_GATEWAY=$(ifconfig "$VPN_INTERFACE" | grep "inet " | awk '{print $4}')
        print_info "  本地IP: $VPN_IP"
        print_info "  网关IP: $VPN_GATEWAY"
    else
        print_error "未找到配置了IP地址的VPN接口"
        exit 1
    fi
else
    print_error "未检测到VPN接口"
    print_info "请先连接VPN"
    exit 1
fi

# 2. VPN路由检查
print_header "2. VPN路由配置检查"

print_info "VPN相关路由:"
netstat -rn | grep utun | grep -v "fe80\|ff0" | while read line; do
    echo "  $line"
done

# 检查关键路由
if netstat -rn | grep -q "192.168.0.*utun"; then
    print_success "192.168.0.0/24 路由已配置"
else
    print_warning "192.168.0.0/24 路由未找到"
fi

if netstat -rn | grep -q "10.*utun"; then
    print_success "10.0.0.0/8 路由已配置"
else
    print_warning "10.0.0.0/8 路由未找到"
fi

# 3. VPN网关连通性测试
print_header "3. VPN网关连通性测试"

if ping -c 3 "$VPN_GATEWAY" > /dev/null 2>&1; then
    print_success "VPN网关 $VPN_GATEWAY 可访问"
else
    print_error "VPN网关 $VPN_GATEWAY 不可访问"
    print_info "这可能表示VPN连接有问题"
fi

# 4. DNS解析测试
print_header "4. DNS解析测试"

DB_HOST="hancens.top"
DB_IP=$(nslookup "$DB_HOST" 2>/dev/null | grep -A 1 "Name:" | grep "Address:" | awk '{print $2}' | head -1)

if [ -n "$DB_IP" ]; then
    print_success "数据库域名解析成功: $DB_HOST -> $DB_IP"

    # 检查是否是内网IP
    if [[ "$DB_IP" =~ ^192\.168\. ]] || [[ "$DB_IP" =~ ^10\. ]] || [[ "$DB_IP" =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]; then
        print_info "  这是内网IP地址"
    else
        print_info "  这是公网IP地址"
        print_warning "  数据库可能需要在内网IP上访问"
    fi
else
    print_error "域名解析失败: $DB_HOST"
fi

# 5. 数据库端口扫描
print_header "5. 数据库端口连通性测试"

# 测试公网IP
if [ -n "$DB_IP" ]; then
    print_info "测试公网IP: $DB_IP:27017"
    if timeout 3 nc -zv "$DB_IP" 27017 2>&1 | grep -q "succeeded"; then
        print_success "端口 $DB_IP:27017 可访问"
    else
        print_error "端口 $DB_IP:27017 不可访问或超时"
    fi
fi

# 测试常见内网IP
print_info "\n测试常见内网IP地址..."

TEST_IPS=(
    "$VPN_GATEWAY"
    "192.168.0.1"
    "192.168.0.10"
    "192.168.0.100"
    "192.168.0.200"
    "10.0.0.1"
    "10.0.0.10"
    "10.8.0.2"
    "10.8.0.10"
)

FOUND_DB=false

for test_ip in "${TEST_IPS[@]}"; do
    if timeout 1 nc -zv "$test_ip" 27017 2>&1 | grep -q "succeeded"; then
        print_success "找到MongoDB服务: $test_ip:27017"
        FOUND_DB=true
        echo "$test_ip" > /tmp/vpn_mongodb_ip.txt
        break
    fi
done

if [ "$FOUND_DB" = false ]; then
    print_warning "在常见内网IP上未找到MongoDB服务"
    print_info "您可能需要:"
    print_info "  1. 向网络管理员确认数据库实际IP地址"
    print_info "  2. 检查VPN服务器是否配置了正确的路由"
    print_info "  3. 确认数据库服务器防火墙规则"
fi

# 6. VPN配置文件分析
print_header "6. VPN配置文件分析"

VPN_CONFIG="/Users/lanxionggao/Documents/guanshanPython/vpn/lxg.ovpn"

if [ -f "$VPN_CONFIG" ]; then
    print_success "VPN配置文件存在"

    print_info "\n配置详情:"
    echo "  服务器: $(grep "^remote " "$VPN_CONFIG" | awk '{print $2":"$3}')"
    echo "  协议: $(grep "^proto " "$VPN_CONFIG" | awk '{print $2}')"

    if grep -q "route-nopull" "$VPN_CONFIG"; then
        print_warning "配置使用了 route-nopull (不自动拉取服务器路由)"
        print_info "  手动配置的路由:"
        grep "^route " "$VPN_CONFIG" | while read line; do
            echo "    $line"
        done
    fi
else
    print_warning "VPN配置文件不存在: $VPN_CONFIG"
fi

# 7. 建议和下一步
print_header "7. 故障排查建议"

if [ "$FOUND_DB" = true ]; then
    print_success "诊断完成: 找到可访问的MongoDB服务"
    MONGODB_IP=$(cat /tmp/vpn_mongodb_ip.txt)
    print_info "\n建议操作:"
    print_info "  1. 更新 .env 文件，使用发现的IP地址:"
    echo -e "     ${GREEN}MONGODB_URL=mongodb://app_user:密码@${MONGODB_IP}:27017/intelligent_system?authSource=intelligent_system${NC}"
    print_info "  2. 运行数据库连接测试脚本验证"
    rm -f /tmp/vpn_mongodb_ip.txt
else
    print_warning "诊断完成: 未找到可访问的MongoDB服务"
    print_info "\n建议操作:"
    print_info "  1. 联系服务器管理员确认:"
    print_info "     - 数据库服务器的实际IP地址"
    print_info "     - VPN用户是否有访问数据库的权限"
    print_info "     - 数据库服务器防火墙规则"
    print_info "  2. 检查VPN服务器日志:"
    print_info "     - 确认路由推送配置"
    print_info "     - 查看是否有访问限制"
    print_info "  3. 尝试从VPN网关 ($VPN_GATEWAY) 执行:"
    print_info "     ssh admin@$VPN_GATEWAY"
    print_info "     然后在服务器上测试数据库连接"
fi

print_header "诊断完成"

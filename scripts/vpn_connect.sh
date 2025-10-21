#!/bin/bash

# VPN 连接管理脚本 - macOS OpenVPN
# 用于连接到hancens.top VPN服务器以访问线上数据库

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
VPN_CONFIG="/Users/lanxionggao/Documents/guanshanPython/vpn/lxg.ovpn"
VPN_NAME="hancens_vpn"
LOG_FILE="/tmp/openvpn_${VPN_NAME}.log"
PID_FILE="/tmp/openvpn_${VPN_NAME}.pid"

# 函数：打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 函数：检查OpenVPN是否已安装
check_openvpn() {
    print_info "检查OpenVPN安装状态..."

    if command -v openvpn &> /dev/null; then
        OPENVPN_VERSION=$(openvpn --version | head -n 1)
        print_success "OpenVPN已安装: $OPENVPN_VERSION"
        return 0
    else
        print_error "OpenVPN未安装"
        print_info "安装方法:"
        print_info "  方法1: brew install openvpn"
        print_info "  方法2: 下载Tunnelblick https://tunnelblick.net/"
        return 1
    fi
}

# 函数：检查配置文件
check_config() {
    print_info "检查VPN配置文件..."

    if [ ! -f "$VPN_CONFIG" ]; then
        print_error "配置文件不存在: $VPN_CONFIG"
        return 1
    fi

    # 检查配置文件关键信息
    if grep -q "remote hancens.top" "$VPN_CONFIG"; then
        print_success "配置文件有效"
        print_info "  服务器: $(grep 'remote ' "$VPN_CONFIG" | awk '{print $2":"$3}')"
        print_info "  协议: $(grep 'proto ' "$VPN_CONFIG" | awk '{print $2}')"
        return 0
    else
        print_error "配置文件格式错误"
        return 1
    fi
}

# 函数：检查VPN是否已连接
check_vpn_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_success "VPN已连接 (PID: $PID)"

            # 检查tun接口
            if ifconfig | grep -q "utun"; then
                print_info "VPN接口状态:"
                ifconfig | grep -A 5 "utun" | grep "inet " || echo "  未获取到IP地址"
            fi

            return 0
        else
            print_warning "VPN进程已停止，但PID文件仍存在"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        print_info "VPN未连接"
        return 1
    fi
}

# 函数：连接VPN
connect_vpn() {
    print_info "正在连接VPN..."

    # 检查是否已连接
    if check_vpn_status > /dev/null 2>&1; then
        print_warning "VPN已经连接，无需重复连接"
        return 0
    fi

    # 检查依赖
    check_openvpn || return 1
    check_config || return 1

    # 启动OpenVPN（后台运行）
    print_info "启动OpenVPN客户端..."
    print_warning "需要sudo权限以创建VPN接口"

    # 使用sudo运行OpenVPN
    sudo openvpn \
        --config "$VPN_CONFIG" \
        --daemon \
        --log "$LOG_FILE" \
        --writepid "$PID_FILE" \
        --verb 3

    # 等待连接建立
    print_info "等待VPN连接建立..."
    for i in {1..15}; do
        sleep 2

        # 检查PID文件
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                # 检查是否获取到IP
                if ifconfig | grep -A 5 "utun" | grep -q "inet "; then
                    print_success "VPN连接成功!"

                    # 显示连接信息
                    print_info "VPN信息:"
                    ifconfig | grep -A 5 "utun" | grep "inet " | awk '{print "  本地IP: " $2}'

                    # 显示路由信息
                    print_info "VPN路由:"
                    netstat -rn | grep "utun" | head -5

                    return 0
                fi
            fi
        fi

        echo -n "."
    done

    echo ""
    print_error "VPN连接超时"
    print_info "查看日志: $LOG_FILE"
    return 1
}

# 函数：断开VPN
disconnect_vpn() {
    print_info "正在断开VPN连接..."

    if [ ! -f "$PID_FILE" ]; then
        print_warning "VPN未连接"
        return 0
    fi

    PID=$(cat "$PID_FILE")

    if ps -p "$PID" > /dev/null 2>&1; then
        print_info "终止OpenVPN进程 (PID: $PID)..."
        sudo kill "$PID"
        sleep 2

        # 强制终止
        if ps -p "$PID" > /dev/null 2>&1; then
            print_warning "使用强制终止..."
            sudo kill -9 "$PID"
        fi

        rm -f "$PID_FILE"
        print_success "VPN已断开"
    else
        print_warning "VPN进程已停止"
        rm -f "$PID_FILE"
    fi
}

# 函数：查看VPN日志
show_log() {
    if [ ! -f "$LOG_FILE" ]; then
        print_warning "日志文件不存在: $LOG_FILE"
        return 1
    fi

    print_info "VPN连接日志 (最后50行):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tail -50 "$LOG_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# 函数：测试数据库连接
test_database() {
    print_info "测试数据库连接..."

    # 检查VPN是否已连接
    if ! check_vpn_status > /dev/null 2>&1; then
        print_error "请先连接VPN"
        return 1
    fi

    # 测试MongoDB连接
    print_info "测试MongoDB连接 (hancens.top:27017)..."
    if nc -zv hancens.top 27017 2>&1 | grep -q "succeeded"; then
        print_success "MongoDB端口可访问"
    else
        print_error "MongoDB端口不可访问"
        print_info "可能原因:"
        print_info "  1. VPN路由未正确配置"
        print_info "  2. 防火墙阻止连接"
        print_info "  3. 数据库服务未启动"
    fi
}

# 函数：显示帮助
show_help() {
    cat << EOF
${GREEN}VPN连接管理脚本${NC}

用法:
    $0 [命令]

命令:
    connect     连接到VPN
    disconnect  断开VPN连接
    status      查看VPN连接状态
    test        测试数据库连接
    log         查看VPN日志
    help        显示此帮助信息

示例:
    $0 connect      # 连接VPN
    $0 status       # 查看状态
    $0 test         # 测试数据库
    $0 disconnect   # 断开VPN

配置:
    VPN配置文件: $VPN_CONFIG
    日志文件: $LOG_FILE
    PID文件: $PID_FILE

EOF
}

# 主函数
main() {
    case "${1:-help}" in
        connect|start)
            connect_vpn
            ;;
        disconnect|stop)
            disconnect_vpn
            ;;
        status)
            check_vpn_status
            ;;
        test)
            test_database
            ;;
        log|logs)
            show_log
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"

#!/bin/bash

# 本地启动脚本
# 自动检查并启动所需服务

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

# 项目目录
PROJECT_DIR="/Users/lanxionggao/Documents/guanshanPython"
cd "$PROJECT_DIR"

print_header "关山智能系统 - 本地启动"

# 1. 检查并停止现有服务
print_info "检查现有服务..."
EXISTING_PIDS=$(ps aux | grep "uvicorn src.main:app" | grep -v grep | awk '{print $2}')
if [ -n "$EXISTING_PIDS" ]; then
    print_warning "发现运行中的服务，正在停止..."
    kill $EXISTING_PIDS 2>/dev/null || true
    sleep 2
    print_success "已停止现有服务"
fi

# 2. 检查MongoDB
print_header "检查MongoDB服务"

MONGODB_RUNNING=false

# 检查Docker MongoDB容器
if command -v docker &> /dev/null; then
    if docker ps 2>/dev/null | grep -q "guanshan_mongodb"; then
        print_success "MongoDB容器已运行"
        MONGODB_RUNNING=true
    else
        print_info "尝试启动MongoDB容器..."

        # 检查Docker是否运行
        if docker ps &> /dev/null; then
            docker-compose -f docker-compose.mongodb.yml up -d
            sleep 5

            if docker ps | grep -q "guanshan_mongodb"; then
                print_success "MongoDB容器启动成功"
                MONGODB_RUNNING=true
            else
                print_error "MongoDB容器启动失败"
            fi
        else
            print_warning "Docker未运行"
            print_info "  提示: 可以打开Docker Desktop后重新运行此脚本"
            print_info "  或者使用降级模式启动（部分功能不可用）"
        fi
    fi
else
    print_warning "Docker未安装"
fi

# 检查本地MongoDB进程
if [ "$MONGODB_RUNNING" = false ]; then
    if ps aux | grep mongod | grep -v grep > /dev/null; then
        print_success "本地MongoDB进程已运行"
        MONGODB_RUNNING=true
    fi
fi

if [ "$MONGODB_RUNNING" = false ]; then
    print_warning "MongoDB未运行"
    print_info "应用将以降级模式启动（数据库功能不可用）"

    read -p "是否继续启动应用？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "已取消启动"
        exit 0
    fi
fi

# 3. 检查环境配置
print_header "检查环境配置"

if [ ! -f ".env" ]; then
    print_error ".env 文件不存在"
    print_info "正在从 .env.example 创建..."
    cp .env.example .env
    print_success "已创建 .env 文件"
    print_warning "请检查并更新 .env 中的配置"
fi

# 检查关键配置
if grep -q "your-api-key-here" .env 2>/dev/null; then
    print_warning ".env 文件包含默认值，请更新API密钥"
fi

print_success "环境配置检查完成"

# 4. 启动应用
print_header "启动FastAPI应用"

print_info "启动参数:"
echo "  - Host: 0.0.0.0"
echo "  - Port: 8000"
echo "  - Reload: 是"
echo "  - API文档: http://localhost:8000/api/docs"
echo ""

print_info "启动中..."

# 使用python -m uvicorn确保使用正确的Python环境
python -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info

# 如果uvicorn退出
print_warning "应用已停止"

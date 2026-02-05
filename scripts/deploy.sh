#!/bin/bash

# 部署脚本 - 关山智能系统
# 用于本地开发和测试环境的部署

set -e  # 遇到错误立即退出

echo "========================================="
echo "关山智能系统 - 部署脚本"
echo "========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查环境
check_requirements() {
    echo -e "${YELLOW}检查系统要求...${NC}"
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker未安装${NC}"
        exit 1
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}错误: Docker Compose未安装${NC}"
        exit 1
    fi
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: Python 3未安装${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ 系统要求检查通过${NC}"
}

# 设置环境变量
setup_environment() {
    echo -e "${YELLOW}设置环境变量...${NC}"
    
    # 检查.env文件
    if [ ! -f .env ]; then
        echo -e "${RED}错误: .env文件不存在${NC}"
        echo "请从.env.example创建.env文件并配置API密钥"
        exit 1
    fi
    
    # 加载环境变量
    export $(cat .env | grep -v '^#' | xargs)
    
    # 验证Firecrawl API密钥
    if [ -z "$FIRECRAWL_API_KEY" ] || [ "$FIRECRAWL_API_KEY" == "your-firecrawl-api-key-here" ]; then
        echo -e "${RED}错误: 请在.env文件中配置有效的FIRECRAWL_API_KEY${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ 环境变量设置完成${NC}"
}

# 安装Python依赖
install_dependencies() {
    echo -e "${YELLOW}安装Python依赖...${NC}"
    
    # 创建虚拟环境（如果不存在）
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo -e "${GREEN}✓ 虚拟环境创建完成${NC}"
    fi
    
    # 激活虚拟环境并安装依赖
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # 安装开发依赖（用于测试）
    if [ -f requirements-dev.txt ]; then
        pip install -r requirements-dev.txt
    fi
    
    echo -e "${GREEN}✓ Python依赖安装完成${NC}"
}

# 清理旧容器和镜像
cleanup_docker() {
    echo -e "${YELLOW}清理旧容器和镜像...${NC}"

    # 停止并移除旧容器（包括孤立容器）
    docker-compose down --remove-orphans

    # 移除项目相关的停止容器
    echo "移除停止的容器..."
    docker container prune -f --filter "label=com.docker.compose.project" 2>/dev/null || true

    # 移除悬空镜像（<none> 标签的镜像）
    echo "移除悬空镜像..."
    docker image prune -f 2>/dev/null || true

    # 移除旧的项目镜像（可选，确保使用最新代码）
    echo "移除旧的应用镜像..."
    docker images | grep "guanshan" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true

    echo -e "${GREEN}✓ 清理完成${NC}"
}

# 启动Docker服务
start_services() {
    echo -e "${YELLOW}启动Docker服务...${NC}"

    # 先执行清理
    cleanup_docker

    # 强制重建镜像（不使用缓存）
    echo "强制重建镜像（不使用缓存）..."
    docker-compose build --no-cache --pull

    # 启动服务
    echo "启动服务..."
    docker-compose up -d --force-recreate

    # 等待服务启动
    echo "等待服务启动..."
    sleep 10

    # 检查服务状态
    docker-compose ps

    # 显示容器日志（最后20行）
    echo -e "${YELLOW}最近日志:${NC}"
    docker-compose logs --tail=20 app

    echo -e "${GREEN}✓ Docker服务启动完成${NC}"
}

# 运行测试
run_tests() {
    echo -e "${YELLOW}运行测试...${NC}"
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 运行pytest
    if pytest --version &> /dev/null; then
        pytest tests/unit -v
        echo -e "${GREEN}✓ 单元测试通过${NC}"
    else
        echo -e "${YELLOW}警告: pytest未安装，跳过测试${NC}"
    fi
}

# 健康检查
health_check() {
    echo -e "${YELLOW}执行健康检查...${NC}"
    
    # 检查API健康状态
    HEALTH_URL="http://localhost:8000/health"
    
    # 尝试多次连接
    for i in {1..5}; do
        if curl -f -s $HEALTH_URL > /dev/null 2>&1; then
            echo -e "${GREEN}✓ API服务健康检查通过${NC}"
            curl -s $HEALTH_URL | python3 -m json.tool
            break
        else
            if [ $i -eq 5 ]; then
                echo -e "${RED}✗ API服务健康检查失败${NC}"
                exit 1
            fi
            echo "等待API服务启动... (尝试 $i/5)"
            sleep 3
        fi
    done
    
    # 检查其他服务
    echo -e "${YELLOW}检查其他服务状态...${NC}"
    
    # MongoDB
    if docker exec guanshan-mongodb mongosh --eval "db.runCommand({ ping: 1 })" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ MongoDB运行正常${NC}"
    else
        echo -e "${RED}✗ MongoDB连接失败${NC}"
    fi
    
    # Redis
    if docker exec guanshan-redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis运行正常${NC}"
    else
        echo -e "${RED}✗ Redis连接失败${NC}"
    fi
    
    # RabbitMQ
    if curl -s http://localhost:15672 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ RabbitMQ管理界面可访问${NC}"
    else
        echo -e "${YELLOW}警告: RabbitMQ管理界面无法访问${NC}"
    fi
}

# 显示访问信息
show_info() {
    echo ""
    echo "========================================="
    echo -e "${GREEN}部署完成！${NC}"
    echo "========================================="
    echo ""
    echo "服务访问地址:"
    echo "  - API文档: http://localhost:8000/api/docs"
    echo "  - 健康检查: http://localhost:8000/health"
    echo "  - RabbitMQ管理界面: http://localhost:15672 (guest/guest)"
    echo ""
    echo "运行命令:"
    echo "  - 查看日志: docker-compose logs -f app"
    echo "  - 停止服务: docker-compose down"
    echo "  - 重启服务: docker-compose restart"
    echo ""
}

# 快速启动（使用缓存，不清理）
quick_start() {
    echo -e "${YELLOW}快速启动（使用缓存）...${NC}"

    # 停止旧容器
    docker-compose down

    # 使用缓存构建并启动
    docker-compose up -d --build

    # 等待服务启动
    echo "等待服务启动..."
    sleep 10

    # 检查服务状态
    docker-compose ps

    echo -e "${GREEN}✓ 快速启动完成${NC}"
}

# 仅重启应用容器
restart_app() {
    echo -e "${YELLOW}重启应用容器...${NC}"
    docker-compose restart app
    sleep 5
    docker-compose logs --tail=30 app
    echo -e "${GREEN}✓ 应用重启完成${NC}"
}

# 查看实时日志
view_logs() {
    echo -e "${YELLOW}查看实时日志 (Ctrl+C 退出)...${NC}"
    docker-compose logs -f app
}

# 显示使用帮助
show_help() {
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  (无参数)    完整部署（清理 + 强制重建 + 测试）"
    echo "  quick       快速部署（使用缓存）"
    echo "  restart     仅重启应用容器"
    echo "  logs        查看实时日志"
    echo "  clean       仅清理旧容器和镜像"
    echo "  health      仅执行健康检查"
    echo "  help        显示此帮助"
    echo ""
}

# 主函数
main() {
    check_requirements
    setup_environment
    install_dependencies
    start_services
    run_tests
    health_check
    show_info
}

# 根据参数执行不同操作
case "${1:-}" in
    quick)
        check_requirements
        setup_environment
        quick_start
        health_check
        show_info
        ;;
    restart)
        restart_app
        ;;
    logs)
        view_logs
        ;;
    clean)
        cleanup_docker
        ;;
    health)
        health_check
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        main
        ;;
esac
#!/bin/bash

# ============================================================
# 关山智能系统 - 部署脚本
# 支持本地开发、测试环境和生产环境部署
# ============================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 配置变量
DOCKER_IMAGE="guanshan-app"
CONTAINER_NAME="guanshan-app"
HEALTH_URL="http://localhost:8000/health"
MAX_RETRIES=10
RETRY_INTERVAL=6
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ============================================================
# 工具函数
# ============================================================

log_info() {
    echo -e "${BLUE}$(date '+%H:%M:%S')${NC} ${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${BLUE}$(date '+%H:%M:%S')${NC} ${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${BLUE}$(date '+%H:%M:%S')${NC} ${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${CYAN}==> $1${NC}"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 未安装"
        return 1
    fi
    return 0
}

# 健康检查
health_check() {
    curl -sf --max-time 10 $HEALTH_URL > /dev/null 2>&1
}

# 等待服务健康
wait_for_healthy() {
    local retries=$1
    local interval=$2

    for i in $(seq 1 $retries); do
        if health_check; then
            log_info "健康检查通过 (尝试 $i/$retries)"
            return 0
        fi
        log_info "等待服务启动... ($i/$retries)"
        sleep $interval
    done
    return 1
}

# ============================================================
# 核心功能
# ============================================================

# 检查系统要求
check_requirements() {
    log_step "检查系统要求"

    local missing=0

    check_command docker || missing=1
    check_command curl || missing=1

    if [ $missing -eq 1 ]; then
        log_error "请先安装缺失的依赖"
        exit 1
    fi

    # 检查 Docker 是否运行
    if ! docker info &> /dev/null; then
        log_error "Docker 服务未运行"
        exit 1
    fi

    log_info "系统要求检查通过 ✓"
}

# 检查环境变量
check_environment() {
    log_step "检查环境变量"

    if [ ! -f .env ]; then
        log_error ".env 文件不存在"
        echo "请从 .env.example 创建 .env 文件"
        exit 1
    fi

    # 加载环境变量
    set -a
    source .env
    set +a

    # 检查关键配置
    local missing=0

    if [ -z "$MONGODB_URL" ]; then
        log_warn "MONGODB_URL 未配置"
    fi

    if [ -z "$FIRECRAWL_API_KEY" ] || [ "$FIRECRAWL_API_KEY" == "your-firecrawl-api-key-here" ]; then
        log_warn "FIRECRAWL_API_KEY 未配置或使用默认值"
    fi

    log_info "环境变量检查完成 ✓"
}

# 备份当前镜像
backup_image() {
    log_step "备份当前镜像"

    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        log_info "创建备份: ${DOCKER_IMAGE}:backup_$TIMESTAMP"
        docker commit $CONTAINER_NAME ${DOCKER_IMAGE}:backup_$TIMESTAMP 2>/dev/null || true
        docker tag $DOCKER_IMAGE ${DOCKER_IMAGE}:backup 2>/dev/null || true
        log_info "备份完成 ✓"
    else
        log_info "没有运行中的容器，跳过备份"
    fi
}

# 清理旧资源
cleanup_docker() {
    log_step "清理旧资源"

    # 停止旧容器
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        log_info "停止旧容器..."
        docker stop $CONTAINER_NAME 2>/dev/null || true
    fi

    # 移除旧容器
    if docker ps -aq -f name=$CONTAINER_NAME | grep -q .; then
        log_info "移除旧容器..."
        docker rm $CONTAINER_NAME 2>/dev/null || true
    fi

    # 清理悬空镜像
    log_info "清理悬空镜像..."
    docker image prune -f 2>/dev/null || true

    # 清理旧备份（保留最近3个）
    log_info "清理旧备份..."
    docker images ${DOCKER_IMAGE} --format "{{.Tag}}" | grep "^backup_" | sort -r | tail -n +4 | xargs -r -I {} docker rmi ${DOCKER_IMAGE}:{} 2>/dev/null || true

    log_info "清理完成 ✓"
}

# 构建镜像
build_image() {
    local no_cache=$1

    log_step "构建 Docker 镜像"

    local build_args=""
    if [ "$no_cache" = "true" ]; then
        build_args="--no-cache --pull"
        log_info "强制重建模式（不使用缓存）"
    fi

    log_info "开始构建..."
    if ! docker build $build_args -t $DOCKER_IMAGE .; then
        log_error "镜像构建失败！"
        return 1
    fi

    log_info "镜像构建完成 ✓"
    docker images $DOCKER_IMAGE --format "table {{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
}

# 启动容器
start_container() {
    log_step "启动容器"

    log_info "启动新容器..."
    docker run -d \
        --name $CONTAINER_NAME \
        --env-file .env \
        --add-host=host.docker.internal:host-gateway \
        -p 8000:8000 \
        --restart unless-stopped \
        --memory=2g \
        --cpus=2 \
        --health-cmd="curl -f http://localhost:8000/health || exit 1" \
        --health-interval=60s \
        --health-timeout=10s \
        --health-retries=3 \
        --health-start-period=60s \
        -l "deploy.timestamp=$TIMESTAMP" \
        $DOCKER_IMAGE

    log_info "容器已启动 ✓"
}

# 回滚到备份
rollback() {
    log_step "执行回滚"

    # 收集诊断日志
    log_info "收集诊断日志..."
    docker logs $CONTAINER_NAME --tail 50 2>/dev/null || true

    # 停止失败的容器
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true

    # 使用备份镜像回滚
    if docker images ${DOCKER_IMAGE}:backup -q | grep -q .; then
        log_info "使用备份镜像回滚..."
        docker tag ${DOCKER_IMAGE}:backup $DOCKER_IMAGE

        docker run -d \
            --name $CONTAINER_NAME \
            --env-file .env \
            --add-host=host.docker.internal:host-gateway \
            -p 8000:8000 \
            --restart unless-stopped \
            --memory=2g \
            --cpus=2 \
            $DOCKER_IMAGE

        if wait_for_healthy 5 5; then
            log_info "回滚成功！ ✓"
            return 0
        else
            log_error "回滚后服务仍然不健康！"
            return 1
        fi
    else
        log_error "没有备份镜像可用于回滚！"
        return 1
    fi
}

# 验证部署
verify_deployment() {
    log_step "验证部署"

    # 等待 gunicorn 启动
    log_info "等待 gunicorn 启动（多 worker 模式需要更长时间）..."
    sleep 45

    # 健康检查
    log_info "执行健康检查..."
    if ! wait_for_healthy $MAX_RETRIES $RETRY_INTERVAL; then
        log_error "健康检查失败！"
        return 1
    fi

    # 验证API响应
    log_info "验证 API 响应..."
    local response=$(curl -s $HEALTH_URL)
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"

    log_info "部署验证通过 ✓"
}

# 显示服务状态
show_status() {
    log_step "服务状态"

    echo ""
    echo -e "${CYAN}容器状态:${NC}"
    docker ps -f name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    echo ""
    echo -e "${CYAN}镜像信息:${NC}"
    docker images $DOCKER_IMAGE --format "table {{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

    echo ""
    echo -e "${CYAN}资源使用:${NC}"
    docker stats $CONTAINER_NAME --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || true

    echo ""
    echo -e "${CYAN}访问地址:${NC}"
    echo "  - API文档: http://localhost:8000/api/docs"
    echo "  - 健康检查: http://localhost:8000/health"
    echo ""
}

# 查看日志
view_logs() {
    local lines=${1:-100}
    docker logs $CONTAINER_NAME --tail $lines -f
}

# ============================================================
# 部署模式
# ============================================================

# 完整部署（清理 + 强制重建）
full_deploy() {
    log_step "开始完整部署"
    echo "========================================="
    echo -e "${GREEN}关山智能系统 - 完整部署${NC}"
    echo "========================================="

    check_requirements
    check_environment
    backup_image
    cleanup_docker

    if ! build_image "true"; then
        log_error "构建失败，尝试回滚..."
        rollback
        exit 1
    fi

    start_container

    if ! verify_deployment; then
        log_error "部署验证失败，尝试回滚..."
        rollback
        exit 1
    fi

    show_status

    echo ""
    log_info "========================================="
    log_info "部署成功！ ✅"
    log_info "========================================="
}

# 快速部署（使用缓存）
quick_deploy() {
    log_step "开始快速部署"
    echo "========================================="
    echo -e "${GREEN}关山智能系统 - 快速部署${NC}"
    echo "========================================="

    check_requirements
    check_environment
    backup_image
    cleanup_docker

    if ! build_image "false"; then
        log_error "构建失败，尝试回滚..."
        rollback
        exit 1
    fi

    start_container

    if ! verify_deployment; then
        log_error "部署验证失败，尝试回滚..."
        rollback
        exit 1
    fi

    show_status

    log_info "快速部署成功！ ✅"
}

# 仅重启容器
restart_only() {
    log_step "重启容器"

    docker restart $CONTAINER_NAME

    log_info "等待服务启动..."
    sleep 30

    if ! wait_for_healthy $MAX_RETRIES $RETRY_INTERVAL; then
        log_error "重启后健康检查失败！"
        exit 1
    fi

    show_status
    log_info "重启完成！ ✅"
}

# 显示帮助
show_help() {
    echo "关山智能系统 - 部署脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  (无参数)    完整部署（清理 + 强制重建 + 验证）"
    echo "  quick       快速部署（使用缓存构建）"
    echo "  restart     仅重启容器"
    echo "  rollback    回滚到上一个版本"
    echo "  status      显示服务状态"
    echo "  logs [n]    查看日志（默认最后100行）"
    echo "  clean       仅清理旧资源"
    echo "  health      仅执行健康检查"
    echo "  help        显示此帮助"
    echo ""
    echo "示例:"
    echo "  $0              # 完整部署"
    echo "  $0 quick        # 快速部署"
    echo "  $0 logs 50      # 查看最后50行日志"
    echo ""
}

# ============================================================
# 主入口
# ============================================================

case "${1:-}" in
    quick)
        quick_deploy
        ;;
    restart)
        restart_only
        ;;
    rollback)
        rollback
        ;;
    status)
        show_status
        ;;
    logs)
        view_logs ${2:-100}
        ;;
    clean)
        check_requirements
        cleanup_docker
        ;;
    health)
        if health_check; then
            log_info "健康检查通过 ✓"
            curl -s $HEALTH_URL | python3 -m json.tool
        else
            log_error "健康检查失败 ✗"
            exit 1
        fi
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        full_deploy
        ;;
esac

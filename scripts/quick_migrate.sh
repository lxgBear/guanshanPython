#!/bin/bash
#
# 数据库迁移快速启动脚本
# Quick Migration Script
#
# 功能：引导用户完成数据库迁移的完整流程
#
# 使用方法：
#   bash scripts/quick_migrate.sh
#

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# 打印函数
print_header() {
    echo -e "\n${BOLD}${CYAN}========================================${RESET}"
    echo -e "${BOLD}${CYAN}$1${RESET}"
    echo -e "${BOLD}${CYAN}========================================${RESET}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${RESET}"
}

print_error() {
    echo -e "${RED}✗ $1${RESET}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${RESET}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${RESET}"
}

print_step() {
    echo -e "\n${BOLD}${CYAN}[$1/$2] $3${RESET}\n"
}

# 检查Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 未安装"
        echo "请先安装 Python 3.8+"
        exit 1
    fi
    print_success "Python 3 已安装"
}

# 检查依赖
check_dependencies() {
    print_info "检查Python依赖..."
    if python3 -c "import motor, pymongo" 2>/dev/null; then
        print_success "依赖包已安装"
    else
        print_warning "依赖包未完全安装"
        echo "正在安装依赖..."
        pip install motor pymongo python-dotenv pydantic-settings
    fi
}

# 检查.env文件
check_env_file() {
    if [ ! -f ".env" ]; then
        print_error ".env 文件不存在"
        print_info "请复制 .env.production.example 为 .env"
        echo ""
        echo "命令："
        echo "  cp .env.production.example .env"
        echo ""
        exit 1
    fi
    print_success ".env 文件存在"
}

# 检查密码
check_password() {
    if grep -q "YOUR_PASSWORD_HERE" .env; then
        print_error "检测到未填写的MongoDB密码"
        echo ""
        print_warning "请按以下步骤操作："
        echo ""
        echo "1. 编辑 .env 文件"
        echo "   vim .env"
        echo ""
        echo "2. 找到第37行，将 YOUR_PASSWORD_HERE 替换为实际的MongoDB密码"
        echo "   MONGODB_URL=mongodb://guanshan:YOUR_PASSWORD_HERE@hancens.top:40717/?authSource=guanshan"
        echo "                                    ^^^^^^^^^^^^^^^"
        echo "                                    替换这里"
        echo ""
        echo "3. 保存文件后重新运行此脚本"
        echo ""
        print_info "如果密码包含特殊字符，需要URL编码："
        echo "   @ → %40"
        echo "   : → %3A"
        echo "   / → %2F"
        echo "   # → %23"
        echo ""
        exit 1
    fi
    print_success "MongoDB密码已配置"
}

# 检查本地MongoDB
check_local_mongodb() {
    print_info "检查本地MongoDB服务..."
    if nc -z localhost 27017 2>/dev/null; then
        print_success "本地MongoDB服务运行中"
    else
        print_warning "本地MongoDB服务未运行"
        print_info "尝试启动MongoDB..."

        # 尝试Docker方式
        if command -v docker &> /dev/null; then
            if [ -f "docker-compose.mongodb.yml" ]; then
                docker-compose -f docker-compose.mongodb.yml up -d
                sleep 3
                if nc -z localhost 27017; then
                    print_success "MongoDB Docker容器已启动"
                fi
            fi
        fi

        # 再次检查
        if ! nc -z localhost 27017; then
            print_error "无法连接到本地MongoDB"
            echo ""
            echo "请手动启动MongoDB服务："
            echo "  - macOS: brew services start mongodb-community"
            echo "  - Docker: docker-compose -f docker-compose.mongodb.yml up -d"
            echo ""
            exit 1
        fi
    fi
}

# 主流程
main() {
    print_header "数据库迁移快速启动向导"

    # 步骤1: 检查环境
    print_step 1 6 "检查环境"
    check_python
    check_dependencies
    check_env_file
    check_password
    check_local_mongodb

    # 步骤2: 测试生产数据库连接
    print_step 2 6 "测试生产数据库连接"
    print_info "正在测试连接到 hancens.top:40717..."
    echo ""

    if python3 scripts/test_production_database.py; then
        print_success "生产数据库连接测试通过"
    else
        print_error "生产数据库连接测试失败"
        echo ""
        print_warning "请检查："
        echo "  1. .env 文件中的密码是否正确"
        echo "  2. 密码中的特殊字符是否已URL编码"
        echo "  3. 网络是否可以访问 hancens.top"
        echo "  4. 防火墙是否开放了40717端口"
        echo ""
        echo "故障排查："
        echo "  ping hancens.top"
        echo "  nc -zv hancens.top 40717"
        echo ""
        exit 1
    fi

    # 步骤3: 备份本地数据
    print_step 3 6 "备份本地数据"
    print_warning "强烈建议在迁移前备份本地数据"
    echo ""
    read -p "是否现在备份本地数据? (y/n): " backup_choice

    if [ "$backup_choice" = "y" ] || [ "$backup_choice" = "Y" ]; then
        print_info "开始备份..."
        echo ""
        if python3 scripts/backup_database.py; then
            print_success "备份完成"
        else
            print_error "备份失败"
            read -p "是否继续迁移? (y/n): " continue_choice
            if [ "$continue_choice" != "y" ] && [ "$continue_choice" != "Y" ]; then
                print_info "迁移已取消"
                exit 0
            fi
        fi
    else
        print_warning "跳过备份步骤"
    fi

    # 步骤4: 预览迁移计划
    print_step 4 6 "预览迁移计划"
    print_info "运行干运行模式，预览将要迁移的数据..."
    echo ""

    python3 scripts/migrate_database.py --all --dry-run --skip-backup

    echo ""
    read -p "确认迁移计划，是否继续? (yes/no): " confirm_choice

    if [ "$confirm_choice" != "yes" ]; then
        print_info "迁移已取消"
        exit 0
    fi

    # 步骤5: 执行迁移
    print_step 5 6 "执行数据迁移"
    print_info "开始迁移数据到生产数据库..."
    echo ""

    if python3 scripts/migrate_database.py --all --skip-backup; then
        print_success "数据迁移完成"
    else
        print_error "数据迁移失败"
        echo ""
        echo "请查看错误信息并重试"
        exit 1
    fi

    # 步骤6: 验证和总结
    print_step 6 6 "完成"
    print_header "迁移完成总结"

    print_success "数据库迁移成功完成！"
    echo ""
    echo "${BOLD}下一步操作：${RESET}"
    echo ""
    echo "1. 启动应用测试"
    echo "   python src/main.py"
    echo ""
    echo "2. 访问API文档"
    echo "   http://localhost:8000/api/docs"
    echo ""
    echo "3. 测试主要功能"
    echo "   curl http://localhost:8000/health"
    echo ""
    echo "${BOLD}相关文档：${RESET}"
    echo "  - 迁移指南: docs/DATABASE_MIGRATION_GUIDE.md"
    echo "  - 生产配置: docs/PRODUCTION_DATABASE_SETUP.md"
    echo "  - 启动指南: STARTUP_GUIDE.md"
    echo ""
    print_success "所有步骤完成！"
}

# 运行主流程
main

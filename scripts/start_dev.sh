#!/bin/bash

# 开发环境快速启动脚本
# 不使用Docker，直接运行FastAPI应用

set -e

echo "========================================="
echo "关山智能系统 - 开发环境启动"
echo "========================================="

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: Python 3未安装${NC}"
    exit 1
fi

# 检查.env文件
if [ ! -f .env ]; then
    echo -e "${RED}错误: .env文件不存在${NC}"
    echo "请从.env.example创建.env文件并配置API密钥"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ 虚拟环境创建完成${NC}"
fi

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
source venv/bin/activate

# 安装依赖
echo -e "${YELLOW}安装依赖...${NC}"
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓ 依赖安装完成${NC}"

# 创建logs目录
mkdir -p logs

# 启动应用
echo -e "${GREEN}启动FastAPI应用...${NC}"
echo ""
echo "应用访问地址:"
echo "  - API文档: http://localhost:8000/api/docs"
echo "  - 健康检查: http://localhost:8000/health"
echo "  - API根路径: http://localhost:8000"
echo ""
echo "按 Ctrl+C 停止应用"
echo ""

# 运行应用
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
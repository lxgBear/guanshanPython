# 多阶段构建 - 优化镜像大小
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 使用国内镜像源安装Python依赖
RUN pip install --no-cache-dir --user -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 最终镜像
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/appuser/.local/bin:$PATH

# 安装curl用于健康检查（更轻量，避免Python进程堆积）
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd -m -u 1000 appuser

# 设置工作目录
WORKDIR /app

# 从builder阶段复制依赖
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# 复制应用代码
COPY --chown=appuser:appuser . .

# 创建必要的目录并设置权限
RUN mkdir -p /app/logs /app/data && chown -R appuser:appuser /app/logs /app/data

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查 - 使用curl更轻量，避免Python进程堆积
# interval=60s: 降低检查频率
# timeout=5s: 缩短超时时间
# start-period=30s: 给gunicorn更多启动时间
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动应用 - 使用多worker模式避免长时间运行的任务阻塞其他请求
# 使用 gunicorn + uvicorn workers 组合，更适合生产环境
# workers=4: 支持4个并发请求处理
# timeout=300: 5分钟超时，适应长时间运行的LangGraph搜索任务
CMD ["gunicorn", "src.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "300", "--graceful-timeout", "30", "--keep-alive", "5"]

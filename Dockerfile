# 使用官方Python镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置pip镜像源和超时时间
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com \
    PIP_TIMEOUT=300

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY bot.py .
COPY config.py.example config.py

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建下载目录
RUN mkdir -p /app/downloads

# 运行机器人
CMD ["python", "bot.py"] 
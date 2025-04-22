#!/bin/bash

# 检查.env文件是否存在，不存在则从示例文件复制
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env file from .env.example"
        cp .env.example .env
        echo "Please edit .env file and set your BOT_TOKEN and ADMIN_USER_ID"
        exit 1
    else
        echo "Error: .env.example file not found"
        exit 1
    fi
fi

# 检查是否安装了Docker和Docker Compose
if ! command -v docker &> /dev/null; then
    echo "Error: Docker not installed. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose not installed. Please install Docker Compose first."
    exit 1
fi

# 检查BOT_TOKEN和ADMIN_USER_ID是否配置
if grep -q "BOT_TOKEN=your_bot_token_here" .env; then
    echo "Error: BOT_TOKEN not configured. Please edit .env file."
    exit 1
fi

if grep -q "ADMIN_USER_ID=your_user_id_here" .env; then
    echo "Error: ADMIN_USER_ID not configured. Please edit .env file."
    exit 1
fi

# 创建下载目录
mkdir -p downloads

# 构建并启动容器
echo "Building and starting YouTube Download Bot..."
docker compose up -d --build

echo "Bot is now running in the background."
echo "To check logs: docker compose logs -f"
echo "To stop the bot: docker compose down" 
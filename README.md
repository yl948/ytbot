# YouTube Download Bot

基于 yt-dlp 的 Telegram YouTube 视频下载机器人。

## 功能

- 支持 YouTube 视频和 Shorts 下载
- 自动选择最佳质量
- 自动生成 Emby/Plex 元数据
- 支持并发下载
- 支持代理设置

## 快速开始

1. 创建 docker-compose.yml:

```yaml
version: '3'

services:
  bot:
    image: ainxxy/ytbot:latest-amd64  # 使用特定架构的标签
    container_name: ytbot
    restart: unless-stopped
    volumes:
      - ./downloads:/app/downloads  # 下载目录
    environment:
      - BOT_TOKEN=your_bot_token    # Telegram Bot Token
      - ADMIN_USER_ID=your_user_id  # 管理员 ID
      - HTTP_PROXY=your_proxy       # 代理设置(可选)
      - HTTPS_PROXY=your_proxy      # 代理设置(可选)
    network_mode: "host"
```

2. 启动服务:
```bash
docker-compose up -d
```

## 支持架构

AMD64:
```bash
docker pull ainxxy/ytbot:latest-amd64
```

ARM64:
```bash
docker pull ainxxy/ytbot:latest-arm64
```

## 命令列表

- `/start` - 启动机器人
- `/help` - 显示帮助信息
- `/status` - 显示状态
- `/toggle_quality` - 切换质量选择
- `/queue` - 查看下载队列
- `/concurrent` - 设置并发数量

## 许可证

MIT License
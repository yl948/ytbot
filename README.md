# YTBot - Telegram YouTube 下载机器人

一个功能强大的Telegram机器人，可以下载YouTube视频，支持多种分辨率选择、自动下载和队列管理。

## 功能特色

- 🎬 支持YouTube视频和Shorts下载
- 🎯 手动选择视频质量
- ⚙️ 自动下载指定分辨率（当设置默认分辨率时）
- 📊 下载进度实时显示
- 📁 自动归类保存视频文件
- 🖼️ 自动下载视频缩略图
- 📝 自动生成NFO元数据文件（兼容Emby/Plex）
- 🔄 并发下载管理
- 🔄 自动重试机制

## 使用Docker（推荐）

### 配置环境变量

首先，创建并配置环境变量：

```bash
# 克隆仓库
git clone https://github.com/yl948/ytbot.git
cd ytbot

# 创建环境变量文件
touch .env

# 编辑.env文件
nano .env  # 或使用任何文本编辑器
```

需要配置的环境变量包括Telegram Bot Token(从@BotFather获取)和管理员用户ID(从@userinfobot获取)，如果在中国使用还需要配置HTTP代理。

### 使用预构建镜像

```bash
# 使用docker命令运行
docker run -d \
  --name ytbot \
  --restart unless-stopped \
  -v $(pwd)/downloads:/app/downloads \
  --env-file .env \
  ainxxy/ytbot:latest
```

### 使用docker-compose

克隆示例配置文件并进行修改：

```bash
# 复制示例配置文件
cp docker-compose.yml.example docker-compose.yml

# 编辑配置文件
nano docker-compose.yml  # 或使用任何文本编辑器
```

`docker-compose.yml`文件示例：

```yaml
services:
  ytbot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ytbot
    restart: unless-stopped
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - ADMIN_USER_ID=${ADMIN_USER_ID}
      - DOWNLOAD_PATH=/app/downloads
      # 如果需要代理，取消下面两行的注释并填入代理地址
      # - HTTP_PROXY=${HTTP_PROXY}
      # - HTTPS_PROXY=${HTTPS_PROXY}
    volumes:
      - ./downloads:/app/downloads
    network_mode: "host"
```

你可以选择使用预构建镜像或本地构建：

1. 使用预构建镜像：
```yaml
# 修改docker-compose.yml中的build部分为image
services:
  ytbot:
    image: ainxxy/ytbot:latest
    # 或者指定架构
    # image: ainxxy/ytbot:latest-amd64
    # image: ainxxy/ytbot:latest-arm64
```

2. 使用本地构建（默认配置）：
```yaml
services:
  ytbot:
    build:
      context: .
      dockerfile: Dockerfile
```

然后启动容器：

```bash
docker-compose up -d
```

### 查看日志和状态

```bash
# 查看日志
docker logs ytbot

# 实时跟踪日志
docker logs -f ytbot

# 检查容器状态
docker ps | grep ytbot
```

## 手动安装

### 环境要求

- Python 3.7+
- FFmpeg
- 网络连接

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/yl948/ytbot.git
cd ytbot
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 创建`.env`文件并配置
```
BOT_TOKEN=你的Telegram机器人Token
ADMIN_USER_ID=你的Telegram用户ID
DOWNLOAD_PATH=./downloads
HTTP_PROXY=http://proxy:port（可选）
HTTPS_PROXY=http://proxy:port（可选）
```

4. 启动机器人
```bash
python bot.py
```

## 使用方法

### 基本命令

在Telegram中与机器人交互:
- `/start` - 启动机器人
- `/help` - 显示帮助信息
- `/status` - 查看机器人状态
- `/toggle_quality` - 切换质量选择模式
- `/resolution` - 设置默认分辨率
- `/queue` - 查看下载队列
- `/concurrent` - 设置并发下载数量

### 下载视频

1. 发送YouTube链接给机器人
2. 如启用了手动选择质量，点击选择所需分辨率
3. 如已设置默认分辨率，机器人会自动下载指定分辨率的视频
4. 等待下载完成

### 设置默认分辨率

1. 发送 `/resolution` 命令
2. 从列表中选择想要的默认分辨率
3. 选择后，发送YouTube链接时会自动下载该分辨率（如果可用）

## 注意事项

- 该机器人默认仅允许管理员使用
- 下载的视频会自动保存在配置的下载目录中
- 支持的链接格式: youtube.com, youtu.be
- 在中国使用时，通常需要配置代理

## 网络配置说明

### 主机网络模式

默认配置使用`network_mode: "host"`，这在Linux环境下效果最好，特别是需要使用宿主机代理的情况。

### 桥接网络模式

如果遇到网络连接问题，可以尝试使用桥接网络模式：

```yaml
services:
  ytbot:
    # 删除 network_mode: "host" 行
    # 添加以下配置
    network_mode: "bridge"
    # 如果需要使用宿主机代理，可以使用host.docker.internal
    environment:
      # ...其他环境变量
      - HTTP_PROXY=http://host.docker.internal:7890
      - HTTPS_PROXY=http://host.docker.internal:7890
```

## 自定义构建

### 使用GitHub Actions构建（推荐）

本项目配置了GitHub Actions工作流，可以构建多架构Docker镜像：

1. Fork本仓库到您的GitHub账号
2. 在仓库设置中添加DockerHub密钥:
   - 访问 `Settings > Secrets and variables > Actions`
   - 添加 `DOCKERHUB_USERNAME`: 您的Docker Hub用户名
   - 添加 `DOCKERHUB_TOKEN`: Docker Hub访问令牌
3. 手动触发构建:
   - 访问仓库的 `Actions` 标签页
   - 选择 `Docker Build and Push` 工作流
   - 点击 `Run workflow` 按钮
   - 输入版本号（例如：1.0.0, 1.1.0）
   - 选择是否同时发布为latest标签
   - 点击 `Run workflow` 开始构建
4. 构建完成后，镜像将发布到Docker Hub:
   - 指定版本: `ainxxy/ytbot:1.0.0`
   - latest标签: `ainxxy/ytbot:latest`

### 本地构建

如果您想在本地构建Docker镜像，可以使用以下命令：

```bash
# 构建多架构镜像（需要设置Docker Buildx）
docker buildx build --platform linux/amd64,linux/arm64 -t ainxxy/ytbot:1.0.0 .

# 仅构建当前平台镜像
docker build -t ainxxy/ytbot:1.0.0 .
```

## 许可证

[MIT](LICENSE)
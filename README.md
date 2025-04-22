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

### 使用预构建镜像（支持AMD64和ARM64）

```bash
# 创建.env文件
cp .env.example .env
# 编辑.env文件填入你的Telegram机器人Token和用户ID
nano .env

# 运行容器
docker run -d \
  --name ytbot \
  --restart unless-stopped \
  -v $(pwd)/downloads:/app/downloads \
  --env-file .env \
  yl948/ytbot:latest
```

### 使用docker-compose

```bash
# 创建.env文件
cp .env.example .env
# 编辑.env文件填入你的Telegram机器人Token和用户ID
nano .env

# 启动容器
docker-compose up -d
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

## 自定义构建

如果您想自己构建Docker镜像，可以使用以下命令：

```bash
# 构建多架构镜像（需要设置Docker Buildx）
docker buildx build --platform linux/amd64,linux/arm64 -t yourusername/ytbot:latest .

# 仅构建当前平台镜像
docker build -t yourusername/ytbot:latest .
```

## 许可证

[MIT](LICENSE)
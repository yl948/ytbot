import os
import logging
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
from config import (BOT_TOKEN, DOWNLOAD_PATH, SUPPORTED_URLS, ADMIN_USER_ID, 
                   HTTP_PROXY, HTTPS_PROXY, enable_quality_selection,
                   download_queue, is_downloading)
import time
import asyncio
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import threading
import psutil  # 需要添加到 requirements.txt
from telegram.request import HTTPXRequest
from telegram.ext import HTTPXRequest as ExtHTTPRequest

# 设置日志
logging.basicConfig(
    format='%(asctime)s - [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO,
    encoding='utf-8'
)

# 创建logger
logger = logging.getLogger("YouTube_Bot")
logger.setLevel(logging.INFO)

# 设置 httpx 和 telegram 的日志级别为 WARNING，减少不必要的日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext._application").setLevel(logging.WARNING)

# 设置 yt-dlp 的日志级别为 WARNING，减少不必要的日志
logging.getLogger("yt_dlp").setLevel(logging.WARNING)

# 设置标准输出编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加配置
MAX_CONCURRENT_DOWNLOADS = 3  # 默认值
concurrent_downloads = MAX_CONCURRENT_DOWNLOADS  # 当前值
download_semaphore = threading.Semaphore(MAX_CONCURRENT_DOWNLOADS)
thread_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)

class ChineseLogger:
    """自定义中文日志处理器"""
    def __init__(self, logger):
        self.logger = logger

    def debug(self, msg):
        # 翻译常见的英文日志消息
        msg = self._translate_message(msg)
        self.logger.debug(msg)

    def info(self, msg):
        msg = self._translate_message(msg)
        self.logger.info(msg)

    def warning(self, msg):
        msg = self._translate_message(msg)
        self.logger.warning(msg)

    def error(self, msg):
        msg = self._translate_message(msg)
        self.logger.error(msg)

    def _translate_message(self, msg):
        translations = {
            'Downloading webpage': '正在获取网页信息',
            'Downloading tv client config': '正在获取TV客户端配置',
            'Downloading player': '正在获取播放器',
            'Downloading tv player API JSON': '正在获取TV播放器API',
            'Downloading ios player API JSON': '正在获取iOS播放器API',
            'Downloading m3u8 information': '正在获取m3u8信息',
            'Downloading MPD manifest': '正在获取MPD清单',
            'Downloading API JSON': '正在获取API数据',
            'Downloading thumbnail': '正在下载缩略图',
            'Downloading subtitles': '正在下载字幕',
            'Downloading video': '正在下载视频',
            'Downloading audio': '正在下载音频',
            'Merging formats': '正在合并音视频',
            'Writing video thumbnail': '正在保存视频封面',
            'has already been downloaded': '已经下载过了',
            'Finished downloading playlist': '播放列表下载完成',
            'Download completed': '下载完成'
        }
        
        for eng, chn in translations.items():
            if eng in msg:
                return msg.replace(eng, chn)
        return msg

class DownloadProgress:
    def __init__(self, status_message):
        self.status_message = status_message
        self.download_finished = False
        self.current_title = None
        self.last_progress = -1
        self.start_time = time.time()
        self.task_id = f"Task-{int(time.time() * 1000)}"[-6:]  # 生成唯一任务ID
        self.download_phase = "video"  # 当前下载阶段：video, audio, merging
        self.download_started = False
        
    def progress_hook(self, d):
        """下载回调"""
        try:
            status = d['status']
            
            if status == 'downloading':
                if not self.current_title:
                    self.current_title = d['filename'].split('/')[-1].split(' - ')[0]  # 只取视频标题部分
                
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded_bytes = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)
                
                if total_bytes:
                    progress = (downloaded_bytes / total_bytes) * 100
                    current_progress = int(progress)
                    speed_mb = speed / (1024 * 1024) if speed else 0
                    
                    # 确定当前下载阶段
                    if d.get('info_dict', {}).get('format_id', '').startswith('bestvideo'):
                        phase = "视频流"
                    elif d.get('info_dict', {}).get('format_id', '').startswith('bestaudio'):
                        phase = "音频流"
                    else:
                        phase = "合并文件"
                    
                    # 在日志中显示开始下载信息
                    if not self.download_started:
                        logger.info(f"开始下载: {self.current_title} ({phase})")
                        self.download_started = True
                    
                    # 每隔20%更新一次日志，显示下载阶段
                    if current_progress % 20 == 0 and current_progress != self.last_progress:
                        logger.info(f"下载{phase}: {current_progress}% - {speed_mb:.1f}MB/s")
                        self.last_progress = current_progress
                
            elif status == 'finished':
                if not self.download_finished:
                    self.download_finished = True
                    logger.info(f"下载完成: {self.current_title}")
                
            elif status == 'error':
                logger.error(f"下载出错: {d.get('error', '未知错误')}")
                
        except Exception as e:
            logger.error(f"进度更新出错: {str(e)}")
            
    def _get_progress_bar(self, percentage, length=20):
        """生成进度条"""
        filled = int(length * percentage / 100)
        bar = '=' * filled + '-' * (length - filled)
        return f"[{bar}]"

def is_valid_url(url: str) -> bool:
    """检查URL是否为支持的格式"""
    try:
        # 检查是否包含支持的域名
        if not any(site in url.lower() for site in SUPPORTED_URLS):
            return False
            
        # 检查是否是完整的YouTube链接
        if 'youtube.com/watch?v=' in url:
            video_id = url.split('watch?v=')[1].split('&')[0]
            return len(video_id) == 11  # YouTube视频ID通常是11个字符
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
            return len(video_id) == 11
        elif 'youtube.com/shorts/' in url:  # 添加对 Shorts 的支持
            video_id = url.split('shorts/')[1].split('?')[0]
            return len(video_id) == 11
            
        return False
        
    except Exception:
        return False

async def check_admin(update: Update) -> bool:
    """检查用户是否是管理员"""
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_USER_ID):
        await update.message.reply_text("⛔️ 抱歉，你没有使用此机器人的权限。")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    logger.info(f"收到 /start 命令 from user {update.effective_user.id}")
    
    if not await check_admin(update):
        logger.warning(f"非管理员用户 {update.effective_user.id} 尝试使用机器人")
        return
        
    try:
        await update.message.reply_text(
            "👋 你好! 我是一个YouTube视频下载机器人。\n"
            "只需要发送YouTube视频链接给我，我就会帮你下载视频。\n"
            "支持的链接格式: youtube.com"
        )
        logger.info(f"成功响应 /start 命令 to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"处理 /start 命令时出错: {str(e)}")
        raise

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    logger.info(f"收到 /help 命令 from user {update.effective_user.id}")
    
    if not await check_admin(update):
        return
        
    proxy_status = '已启用 ✅' if HTTP_PROXY else '未启用 ❌'
    proxy_address = HTTP_PROXY if HTTP_PROXY else 'N/A'
    
    quality_mode = "手动选择" if enable_quality_selection else "自动最高质量"
    
    help_text = f"""
📖 使用说明

🤖 基本命令:
/start - 启动机器人
/help - 显示此帮助信息
/status - 显示机器人状态

📥 下载视频:
1. 直接发送YouTube视频链接给我
2. {quality_mode}下载质量
3. 等待下载完成

🔗 支持的链接格式:
- https://www.youtube.com/watch?v=...

📁 下载内容:
- 视频文件 ({quality_mode})
- NFO元数据文件 (用于Emby/Plex)
- 视频封面图片

💾 保存位置:
{DOWNLOAD_PATH}

⚙️ 其他信息:
- 代理状态: {proxy_status}
- 代理地址: {proxy_address}
- 质量选择: {quality_mode}
"""

    await update.message.reply_text(help_text)
    logger.info(f"成功响应 /help 命令 to user {update.effective_user.id}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /status 命令"""
    logger.info(f"收到 /status 命令 from user {update.effective_user.id}")
    
    if not await check_admin(update):
        return

    # 检查下载目录
    if not os.path.exists(DOWNLOAD_PATH):
        status_text = "❌ 下载目录不存在！"
    else:
        # 获取目录信息
        total_videos = len([d for d in os.listdir(DOWNLOAD_PATH) if os.path.isdir(os.path.join(DOWNLOAD_PATH, d))])
        total_size = sum(os.path.getsize(os.path.join(dirpath,filename)) 
                        for dirpath, dirnames, filenames in os.walk(DOWNLOAD_PATH) 
                        for filename in filenames)
        
        status_text = f"""
📊 机器人状态

🎥 已下载视频: {total_videos} 个
💾 总占用空间: {total_size / (1024*1024*1024):.2f} GB

📁 下载目录: {DOWNLOAD_PATH}
🌐 代理状态: {'已启用 ✅' if HTTP_PROXY else '未启用 ❌'}
🔗 代理地址: {HTTP_PROXY if HTTP_PROXY else 'N/A'}

⚡️ 机器人运行正常
"""
    
    await update.message.reply_text(status_text)
    logger.info(f"成功响应 /status 命令 to user {update.effective_user.id}")

async def list_formats(url, proxy=None, status_message=None):
    """获取视频可用的格式列表"""
    logger.info(f"开始获取视频格式列表: {url}")
    
    ydl_opts = {
        'proxy': proxy,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,  # 添加超时设置
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("正在提取视频信息...")
            info = ydl.extract_info(url, download=False)
            logger.info(f"成功获取视频信息: {info.get('title', '')}")
            
            formats = []
            seen = set()
            
            # 获取音频流大小
            logger.info("正在获取音频流信息...")
            best_audio = next((f for f in info['formats'] 
                             if f.get('vcodec') == 'none' 
                             and f.get('acodec') != 'none'
                             and f.get('filesize', 0) > 0), None)
            
            # 过滤并整理格式列表
            logger.info("正在处理视频格式列表...")
            format_dict = {}  # 用于存储每个分辨率的最佳格式
            
            for f in info['formats']:
                if f.get('vcodec') != 'none' and f.get('height'):
                    height = f.get('height', 0)
                    key = f"{height}p"
                    
                    # 获取视频大小
                    filesize = f.get('filesize', 0)
                    if filesize == 0:
                        continue
                    
                    # 如果视频流没有音频，加上音频大小
                    if f.get('acodec') == 'none' and best_audio:
                        filesize += best_audio.get('filesize', 0)
                    
                    filesize_mb = round(filesize / (1024 * 1024), 1)
                    
                    # 更新格式字典，保留每个分辨率中最佳的格式
                    if key not in format_dict or filesize > format_dict[key]['filesize']:
                        format_dict[key] = {
                            'format_id': f['format_id'],
                            'key': key,
                            'height': height,
                            'filesize': filesize,
                            'filesize_mb': filesize_mb,
                            'url': url,
                            'title': info['title']
                        }
            
            # 将字典转换为列表
            formats = list(format_dict.values())
            
            # 按分辨率排序
            formats.sort(key=lambda x: x['height'], reverse=True)
            
            # 记录找到的格式，只显示分辨率
            for fmt in formats:
                logger.info(f"分辨率: {fmt['key']}")
            
            # 添加最佳质量选项
            if formats:
                best_format = formats[0].copy()
                best_format.update({
                    'format_id': 'best',
                    'key': 'best'
                })
                formats.insert(0, best_format)
            
            return formats, info['title']
            
    except Exception as e:
        logger.error(f"获取格式列表失败: {str(e)}")
        raise

async def process_download_queue(context: ContextTypes.DEFAULT_TYPE):
    """处理下载队列"""
    global is_downloading
    
    if not download_queue:
        is_downloading = False
        return
        
    is_downloading = True
    
    try:
        tasks = []
        # 同时处理多个下载任务
        while len(tasks) < concurrent_downloads and download_queue:
            task = download_queue[0]  # 先不移除任务
            
            # 创建下载任务
            download_task = asyncio.create_task(
                start_download(
                    task['message'],
                    task['url'],
                    task['format_id'],
                    task['title']
                )
            )
            tasks.append(download_task)
            download_queue.pop(0)  # 任务开始后再移除
            
        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks)
            
    except Exception as e:
        logger.error(f"Queue processing error: {str(e)}")
    finally:
        # 如果还有任务，继续处理
        if download_queue:
            await asyncio.sleep(1)  # 短暂延迟避免CPU过载
            await process_download_queue(context)
        else:
            is_downloading = False

async def add_to_queue(message, url, format_id, title):
    """添加下载任务到队列"""
    queue_position = len(download_queue) + 1
    
    # 添加到队列
    download_queue.append({
        'message': message,
        'url': url,
        'format_id': format_id,
        'title': title
    })
    
    # 显示队列位置
    await message.edit_text(
        f"⏳ 已加入下载队列\n\n"
        f"📹 {title}\n"
        f"📊 队列位置: {queue_position}\n"
        f"⌛️ 等待下载..."
    )
    
    # 如果没有正在下载的任务，开始处理队列
    if not is_downloading:
        asyncio.create_task(process_download_queue(None))

async def download_and_send_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理视频链接"""
    if not await check_admin(update):
        return
        
    url = update.message.text.strip()
    
    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ 无效的链接格式！\n\n"
            "请发送正确的 YouTube 视频链接，例如：\n"
            "✅ https://www.youtube.com/watch?v=xxxxxxxxxxx\n"
            "✅ https://youtu.be/xxxxxxxxxxx\n"
            "✅ https://youtube.com/shorts/xxxxxxxxxxx\n\n"
            "其中 'xxxxxxxxxxx' 是11位的视频ID"
        )
        return

    status_message = await update.message.reply_text("⏳ 正在获取视频信息...")
    
    # 添加重试次数
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 检查是否是 Shorts 视频
            is_shorts = 'shorts' in url
            
            if is_shorts or not enable_quality_selection:
                # Shorts 视频或禁用质量选择时直接使用最高质量
                await add_to_queue(
                    status_message,
                    url,
                    'best',
                    '获取中...'
                )
            else:
                # 普通视频且启用质量选择时显示质量选择
                formats, video_title = await asyncio.wait_for(
                    list_formats(url, HTTP_PROXY, status_message),
                    timeout=60  # 设置60秒超时
                )
                
                # 保存格式信息到 context.bot_data
                context.bot_data['download_info'] = {
                    'url': url,
                    'title': video_title,
                    'formats': {f['format_id']: f for f in formats}
                }
                
                buttons = []
                for fmt in formats:
                    if fmt['format_id'] == 'best':
                        label = "🎯 最佳质量"
                    else:
                        label = f"🎬 {fmt['key']}"
                    
                    callback_data = f"dl_{fmt['format_id']}"
                    buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])
                
                reply_markup = InlineKeyboardMarkup(buttons)
                
                await status_message.edit_text(
                    f"🎥 视频: {video_title}\n\n"
                    "请选择下载质量:",
                    reply_markup=reply_markup
                )
            
            # 如果成功，跳出循环
            break
            
        except asyncio.TimeoutError:
            retry_count += 1
            if retry_count < max_retries:
                await status_message.edit_text(
                    f"⚠️ 获取视频信息超时，正在重试 ({retry_count}/{max_retries})..."
                )
                await asyncio.sleep(2)  # 等待2秒后重试
            else:
                await status_message.edit_text(
                    "❌ 获取视频信息失败：连接超时\n"
                    "请检查网络连接或稍后重试"
                )
                logger.error(f"获取视频信息失败，已重试 {max_retries} 次")
                return
                
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            await status_message.edit_text(f"❌ 获取视频信息失败: {str(e)}")
            return

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮回调"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data.startswith('dl_'):
            format_id = query.data[3:]
            download_info = context.bot_data.get('download_info', {})
            
            if download_info:
                # 记录用户选择的格式
                selected_format = next((f for f in download_info.get('formats', {}).values() 
                                     if f['format_id'] == format_id), None)
                if selected_format:
                    logger.info(f"用户选择下载格式: {selected_format.get('key', '未知分辨率')}")
                
                # 添加到下载队列
                await add_to_queue(
                    query.message,
                    download_info['url'],
                    format_id,
                    download_info['title']
                )
                # 清理数据
                context.bot_data.pop('download_info', None)
            else:
                await query.message.edit_text("❌ 下载信息已过期，请重新发送视频链接")
            
        elif query.data.startswith('setdl_'):
            # 处理并发下载数量设置
            global concurrent_downloads, thread_pool, download_semaphore
            new_value = int(query.data.split('_')[1])
            
            # 更新设置
            concurrent_downloads = new_value
            # 重新创建线程池和信号量
            if thread_pool:
                thread_pool.shutdown(wait=True)
            thread_pool = ThreadPoolExecutor(max_workers=concurrent_downloads)
            download_semaphore = threading.Semaphore(concurrent_downloads)
            
            await query.message.edit_text(
                f"✅ 已更新并发下载数量\n\n"
                f"当前同时下载数: {concurrent_downloads}"
            )
            
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        await query.message.edit_text(f"❌ 处理失败: {str(e)}")

async def start_download(message, url, format_id, video_title):
    """开始下载指定格式的视频"""
    status_message = await message.edit_text("⏳ 正在准备下载...")
    progress_handler = DownloadProgress(status_message)
    
    try:
        # 记录下载目录信息
        logger.info(f"下载目录: {DOWNLOAD_PATH}")
        logger.info(f"下载目录是否存在: {os.path.exists(DOWNLOAD_PATH)}")
        logger.info(f"下载目录权限: {oct(os.stat(DOWNLOAD_PATH).st_mode)[-3:]}")
        
        # 设置代理
        proxy_config = {}
        if HTTP_PROXY:
            proxy_config['proxy'] = HTTP_PROXY
        
        # 先获取视频信息
        with yt_dlp.YoutubeDL({'proxy': HTTP_PROXY} if HTTP_PROXY else {}) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info['title']
            
            # 获取分辨率信息
            selected_format = None
            for f in info['formats']:
                if f['format_id'] == format_id or (format_id == 'best' and f == info['formats'][-1]):
                    selected_format = f
                    break
            
            # 获取分辨率信息
            if selected_format:
                height = selected_format.get('height', 0)
                # 简化分辨率显示
                if height >= 2160:
                    resolution = "4K"
                elif height >= 1440:
                    resolution = "2K"
                elif height >= 1080:
                    resolution = "1080p"
                elif height >= 720:
                    resolution = "720p"
                elif height >= 480:
                    resolution = "480p"
                elif height >= 360:
                    resolution = "360p"
                elif height >= 240:
                    resolution = "240p"
                else:
                    resolution = f"{height}p"
            else:
                resolution = "未知"
            
            # 检查是否存在相同分辨率的文件
            video_folder = os.path.join(DOWNLOAD_PATH, video_title)
            if os.path.exists(video_folder):
                existing_files = [f for f in os.listdir(video_folder) 
                                if f.endswith(('.mp4', '.webm', '.mkv')) 
                                and resolution in f]
                
                if existing_files:
                    logger.info(f"跳过下载: {video_title} - {resolution} 已存在")
                    await status_message.edit_text(f"⏭️ 跳过下载：该视频的 {resolution} 版本已存在")
                    return
            
            # 创建新的视频目录
            os.makedirs(video_folder, exist_ok=True)
            
            # 设置下载格式
            if format_id == 'best':
                format_opt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                format_opt = f'{format_id}+bestaudio[ext=m4a]/best'
            
            ydl_opts = {
                'format': format_opt,
                'outtmpl': f'{video_folder}/%(title)s - {resolution}.%(ext)s',
                'noplaylist': True,
                'writethumbnail': True,
                'write_all_thumbnails': False,
                'convert_thumbnails': 'jpg',
                'proxy': HTTP_PROXY if HTTP_PROXY else None,
                'quiet': False,
                'no_warnings': True,
                'postprocessors': [
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    },
                    {
                        'key': 'FFmpegThumbnailsConvertor',
                        'format': 'jpg',
                        'when': 'before_dl'
                    },
                    {
                        # 使用 FFmpegVideoRemuxer 而不是 FFmpegVideoConvertor
                        'key': 'FFmpegVideoRemuxer',
                        'preferedformat': 'mp4',
                    }
                ],
                'merge_output_format': 'mp4',
                'logger': ChineseLogger(logger),
                'progress_hooks': [progress_handler.progress_hook],
                'postprocessor_hooks': [progress_handler.progress_hook]
            }
        
        logger.info(f"开始下载视频: {video_title} - {resolution}")
        await status_message.edit_text(f"🔍 开始下载: {video_title}")
        
        # 在新线程池中运行下载任务
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(thread_pool, download_video, ydl_opts, url)
        
        # 查找实际下载的视频文件
        video_files = [f for f in os.listdir(video_folder) if f.endswith(('.mp4', '.webm', '.mkv'))]
        if not video_files:
            raise Exception("未找到下载的视频文件")
        
        # 获取最新下载的视频文件（按修改时间排序）
        video_files.sort(key=lambda x: os.path.getmtime(os.path.join(video_folder, x)), reverse=True)
        video_path = os.path.join(video_folder, video_files[0])
        video_filename = os.path.splitext(video_files[0])[0]  # 获取视频文件名（不含扩展名）
        
        # 等待文件写入完成
        await asyncio.sleep(2)
        
        # 获取视频信息
        video_size = os.path.getsize(video_path)
        logger.info(f"视频文件大小: {format_size(video_size)}")
        
        # 生成NFO文件
        nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<movie>
    <title>{info['title']}</title>
    <originaltitle>{info['title']}</originaltitle>
    <sorttitle>{info['title']}</sorttitle>
    <year>{info.get('upload_date', '')[:4]}</year>
    <plot>{info.get('description', '')}</plot>
    <runtime>{int(info.get('duration', 0) / 60)}</runtime>
    <thumb>{info.get('thumbnail', '')}</thumb>
    <genre>YouTube</genre>
    <studio>YouTube</studio>
    <director>{info.get('uploader', '')}</director>
    <premiered>{info.get('upload_date', '')}</premiered>
    <source>YouTube</source>
    <uniqueid type="YouTube" default="true">{info['id']}</uniqueid>
    <trailer>{url}</trailer>
</movie>"""
        
        # 保存NFO文件，使用与视频相同的文件名
        nfo_path = os.path.join(video_folder, f"{video_filename}.nfo")
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
            
        # 重命名下载的缩略图
        thumb_files = [f for f in os.listdir(video_folder) if f.endswith('.jpg')]
        if thumb_files:
            old_thumb_path = os.path.join(video_folder, thumb_files[0])
            new_thumb_path = os.path.join(video_folder, "poster.jpg")
            os.rename(old_thumb_path, new_thumb_path)
        
        # 检查字幕文件
        subtitle_files = [f for f in os.listdir(video_folder) if f.endswith(('.srt', '.vtt'))]
        has_subtitles = len(subtitle_files) > 0

        # 在日志中显示详细信息
        logger.info("=" * 50)
        logger.info(f"✅ 下载完成: {video_title}")
        logger.info(f"📊 分辨率: {resolution} - {format_size(video_size)}")
        logger.info(f"📁 保存路径: {video_folder}")
        logger.info(f"📝 元数据文件: {'已生成' if os.path.exists(nfo_path) else '未生成'}")
        logger.info(f"🖼 封面图片: {'已下载' if os.path.exists(os.path.join(video_folder, 'poster.jpg')) else '未下载'}")
        logger.info("=" * 50)
        
        # 只在 Telegram 发送简单的完成通知
        await status_message.edit_text(
            f"✅ 下载完成！\n\n"
            f"📹 {video_title}\n"
            f"📊 分辨率: {resolution}\n"
            f"💾 大小: {format_size(video_size)}\n"
            f"📝 元数据: {'✅' if os.path.exists(nfo_path) else '❌'}\n"
            f"🖼 封面图: {'✅' if os.path.exists(os.path.join(video_folder, 'poster.jpg')) else '❌'}"
        )
            
        # 在视频下载完成后添加检查
        has_video, has_audio = check_video_audio(video_path)
        if not has_audio:
            logger.warning(f"警告：视频 {video_path} 没有音频流！")
        
    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        await status_message.edit_text(f"❌ 下载失败: {str(e)}")

def check_video_audio(video_path):
    """检查视频是否包含音频流"""
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path]
    try:
        output = subprocess.check_output(cmd)
        streams = json.loads(output)['streams']
        has_video = any(s['codec_type'] == 'video' for s in streams)
        has_audio = any(s['codec_type'] == 'audio' for s in streams)
        return has_video, has_audio
    except Exception as e:
        logger.error(f"检查视频音频流失败: {str(e)}")
        return True, False

def download_video(ydl_opts, url):
    """在线程池中运行下载任务"""
    with download_semaphore:  # 使用信号量控制并发数
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

async def toggle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换质量选择模式"""
    logger.info(f"收到 /toggle_quality 命令 from user {update.effective_user.id}")
    
    if not await check_admin(update):
        return
    
    global enable_quality_selection
    enable_quality_selection = not enable_quality_selection
    
    mode = "启用" if enable_quality_selection else "禁用"
    await update.message.reply_text(
        f"✅ 已{mode}质量选择\n\n"
        f"当前模式: {'手动选择质量 🎯' if enable_quality_selection else '自动最高质量 ⚡️'}\n"
        "发送视频链接开始下载"
    )
    logger.info(f"成功响应 /toggle_quality 命令 to user {update.effective_user.id}，当前模式: {mode}")

async def set_commands(application: Application):
    """设置机器人命令菜单"""
    commands = [
        ("start", "启动机器人"),
        ("help", "显示帮助信息"),
        ("status", "显示机器人状态"),
        ("toggle_quality", "切换质量选择模式"),
        ("queue", "显示下载队列"),
        ("concurrent", "设置并发下载数量")  # 新增命令
    ]
    
    try:
        await application.bot.set_my_commands(
            [BotCommand(command, description) for command, description in commands]
        )
        logger.info("✅ 机器人命令菜单设置成功")
    except Exception as e:
        logger.error(f"❌ 设置命令菜单失败: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理错误"""
    logger.error(f"更新 {update} 导致错误 {context.error}")
    error_message = f"发生错误: {str(context.error)}"
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ 抱歉，发生了一些错误。请稍后重试。"
        )

def format_size(bytes):
    """格式化文件大小，使用1000为基数"""
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(bytes)
    unit_index = 0
    
    while size >= 1000.0 and unit_index < len(units) - 1:
        size /= 1000.0
        unit_index += 1
    
    # 统一使用一位小数
    return f"{size:.1f} {units[unit_index]}"

async def queue_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示下载队列状态"""
    logger.info(f"收到 /queue 命令 from user {update.effective_user.id}")
    
    if not await check_admin(update):
        return
        
    if not download_queue and not is_downloading:
        await update.message.reply_text("📭 下载队列为空")
        return
        
    status_text = "📋 下载队列状态:\n\n"
    
    # 显示正在下载的任务
    if is_downloading:
        status_text += "⏳ 正在下载:\n"
        for i, task in enumerate(download_queue[:concurrent_downloads], 1):
            status_text += f"{i}. {task['title']}\n"
        
    # 显示等待中的任务
    if len(download_queue) > concurrent_downloads:
        status_text += "\n⌛️ 等待下载:\n"
        for i, task in enumerate(download_queue[concurrent_downloads:], concurrent_downloads + 1):
            status_text += f"{i}. {task['title']}\n"
    
    await update.message.reply_text(status_text)
    logger.info(f"成功响应 /queue 命令 to user {update.effective_user.id}")

def get_recommended_concurrent_downloads():
    """根据服务器配置推荐并发下载数"""
    try:
        # 获取CPU核心数
        cpu_count = psutil.cpu_count()
        # 获取可用内存(GB)
        memory_gb = psutil.virtual_memory().available / (1024 * 1024 * 1024)
        
        if cpu_count <= 1 and memory_gb < 2:
            return 2  # 低配服务器
        elif cpu_count <= 2 and memory_gb < 4:
            return 3  # 中配服务器
        elif cpu_count <= 4 and memory_gb < 8:
            return 4  # 中高配服务器
        else:
            return 6  # 高配服务器
            
    except Exception as e:
        logger.error(f"获取服务器配置失败: {str(e)}")
        return 3  # 默认值

async def set_concurrent_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置并发下载数量"""
    if not await check_admin(update):
        return
        
    try:
        recommended = get_recommended_concurrent_downloads()
        
        # 如果没有提供参数，显示当前设置
        if not context.args:
            buttons = [
                [
                    InlineKeyboardButton("1", callback_data="setdl_1"),
                    InlineKeyboardButton("2", callback_data="setdl_2"),
                    InlineKeyboardButton("3", callback_data="setdl_3"),
                ],
                [
                    InlineKeyboardButton("4", callback_data="setdl_4"),
                    InlineKeyboardButton("5", callback_data="setdl_5"),
                    InlineKeyboardButton("6", callback_data="setdl_6"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            # 获取服务器信息
            cpu_count = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().available / (1024 * 1024 * 1024)
            
            await update.message.reply_text(
                f"🔧 并发下载设置\n\n"
                f"当前同时下载数: {concurrent_downloads}\n"
                f"推荐下载数: {recommended}\n\n"
                f"服务器配置:\n"
                f"CPU核心数: {cpu_count}\n"
                f"可用内存: {memory_gb:.1f}GB\n\n"
                f"请选择新的并发下载数量:",
                reply_markup=reply_markup
            )
            return
            
    except Exception as e:
        logger.error(f"设置并发下载数量失败: {str(e)}")
        await update.message.reply_text(f"❌ 设置失败: {str(e)}")

def main():
    """主函数"""
    logger.info("🤖 YouTube下载机器人正在启动...")
    
    # 创建下载目录
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    logger.info(f"📁 下载目录: {DOWNLOAD_PATH}")
    
    try:
        # 创建自定义请求对象，增加连接池大小和超时时间
        request = HTTPXRequest(
            connection_pool_size=8,  # 增加连接池大小
            connect_timeout=30.0,    # 连接超时时间
            read_timeout=30.0,       # 读取超时时间
            write_timeout=30.0,      # 写入超时时间
            pool_timeout=3.0,        # 池超时时间
        )
        
        # 创建应用时使用自定义请求对象
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .request(request)
            .get_updates_request(
                ExtHTTPRequest(
                    connection_pool_size=8,
                    connect_timeout=30.0,
                    read_timeout=30.0,
                    write_timeout=30.0,
                    pool_timeout=3.0,
                )
            )
            .build()
        )
        
        logger.info("✅ Telegram Bot API 连接成功")

        # 添加处理程序
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("toggle_quality", toggle_quality))
        application.add_handler(CommandHandler("queue", queue_status))
        application.add_handler(CommandHandler("concurrent", set_concurrent_downloads))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send_video))
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # 添加错误处理器
        application.add_error_handler(error_handler)
        
        logger.info("✅ 命令处理程序注册完成")

        # 设置命令菜单
        asyncio.get_event_loop().run_until_complete(set_commands(application))

        # 启动机器人
        logger.info("🚀 机器人开始运行...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"启动失败: {str(e)}")
        raise

if __name__ == '__main__':
    main() 
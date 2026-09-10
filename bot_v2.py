import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path

import boto3
from botocore.client import Config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
import yt_dlp

TOKEN = os.environ.get("BOT_TOKEN")
MAX_FILE_SIZE = 49 * 1024 * 1024
LINK_EXPIRES = 24 * 60 * 60
URL_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+", re.I)
YOUTUBE_EXTRACTOR_ARGS = {"youtube": {"player_client": ["android", "web_safari"]}}


def get_url(text):
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(".,)>]}\"'") if m else None


def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": YOUTUBE_EXTRACTOR_ARGS,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
        },
    }


def extract_info(url):
    with yt_dlp.YoutubeDL({**base_opts(), "skip_download": True}) as ydl:
        return ydl.extract_info(url, download=False)


def get_s3_client():
    required = ["S3_BUCKET_NAME", "S3_REGION", "S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY"]
    missing = [x for x in required if not os.environ.get(x)]
    if missing:
        raise RuntimeError("Object Storage configuration is missing: " + ", ".join(missing))
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        region_name=os.environ["S3_REGION"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
    )


def upload_and_get_link(file_path, title, mode):
    s3 = get_s3_client()
    ext = ".mp3" if mode == "audio" else ".mp4"
    key = f"downloads/{safe_name(title)}-{os.urandom(6).hex()}{ext}"
    content_type = "audio/mpeg" if mode == "audio" else "video/mp4"
    s3.upload_file(file_path, os.environ["S3_BUCKET_NAME"], key, ExtraArgs={"ContentType": content_type})
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": os.environ["S3_BUCKET_NAME"], "Key": key},
        ExpiresIn=LINK_EXPIRES,
    )


async def start(update, context):
    await update.message.reply_text("🎬 YouTube Downloader\n\nلینک ویدیو از YouTube را بفرست.")


async def handle_url(update, context):
    url = get_url(update.message.text)
    if not url:
        return await update.message.reply_text("❌ لطفاً یک لینک معتبر YouTube بفرست.")
    msg = await update.message.reply_text("🔎 در حال بررسی ویدیو...")
    try:
        info = await asyncio.to_thread(extract_info, url)
        context.user_data.update(yt_url=url, yt_info=info)
        title = info.get("title", "YouTube video")
        d = info.get("duration")
        dt = f"\n⏱ مدت: {d//60}:{d%60:02d}" if d else ""
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎥 ویدیو MP4", callback_data="video")],
            [InlineKeyboardButton("🎵 صدا MP3", callback_data="audio")],
        ])
        await msg.edit_text(f"🎬 {title}{dt}\n\nفرمت را انتخاب کن:", reply_markup=kb)
    except Exception as e:
        await msg.edit_text(f"❌ نتونستم اطلاعات ویدیو را بگیرم.\n{type(e).__name__}: {str(e)[:300]}")


def download_media(url, mode):
    wd = tempfile.mkdtemp(prefix="ytbot_")
    out = os.path.join(wd, "%(title).80s.%(ext)s")
    common = {**base_opts(), "outtmpl": out, "restrictfilenames": True, "retries": 3, "fragment_retries": 3}
    if mode == "audio":
        opts = {
            **common,
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
        }
    else:
        opts = {**common, "format": "best[ext=mp4][height<=720]/best[height<=720]/best", "merge_output_format": "mp4"}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        files = [p for p in Path(wd).iterdir() if p.is_file()]
        if not files:
            raise RuntimeError("فایل دانلودشده پیدا نشد")
        ext = ".mp3" if mode == "audio" else ".mp4"
        pref = [p for p in files if p.suffix.lower() == ext]
        return {"path": str(pref[0] if pref else files[0]), "title": info.get("title", "youtube")}
    except Exception:
        shutil.rmtree(wd, ignore_errors=True)
        raise


async def button(update, context):
    q = update.callback_query
    await q.answer()
    url = context.user_data.get("yt_url")
    info = context.user_data.get("yt_info")
    if not url or not info:
        return await q.edit_message_text("❌ لینک منقضی شده. دوباره لینک را بفرست.")

    mode = q.data
    await q.edit_message_text("⏳ دانلود شروع شد؛ لطفاً صبر کن...")
    await context.bot.send_chat_action(q.message.chat_id, ChatAction.UPLOAD_DOCUMENT)
    file_path = None
    try:
        r = await asyncio.to_thread(download_media, url, mode)
        file_path = r["path"]
        title = r["title"]
        size = os.path.getsize(file_path)

        if size > MAX_FILE_SIZE:
            await q.message.reply_text("📦 فایل بزرگ است؛ در حال آپلود روی فضای ابری...")
            link = await asyncio.to_thread(upload_and_get_link, file_path, title, mode)
            await q.message.reply_text(
                "✅ فایل آماده شد!\n\n"
                "📥 حجم فایل: " + f"{size / (1024 * 1024):.1f} MB" + "\n"
                "⏳ لینک تا ۲۴ ساعت معتبر است:\n" + link
            )
            return

        with open(file_path, "rb") as f:
            if mode == "audio":
                await q.message.reply_audio(audio=f, filename=f"{safe_name(title)}.mp3", title=title[:64])
            else:
                await q.message.reply_video(video=f, filename=f"{safe_name(title)}.mp4", supports_streaming=True)
        await q.message.reply_text("✅ آماده شد! لینک بعدی را بفرست.")
    except Exception as e:
        await q.message.reply_text(f"❌ دانلود/آپلود انجام نشد.\n{str(e)[:500]}")
    finally:
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
                shutil.rmtree(Path(file_path).parent, ignore_errors=True)
            except Exception:
                pass


def safe_name(n):
    return (re.sub(r"[\\/:*?\"<>|\n\r]+", "_", n).strip()[:80] or "youtube")


async def error_handler(update, context):
    print(f"Bot error: {context.error!r}")


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(video|audio)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_error_handler(error_handler)
    print("YouTube Telegram bot v3 started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

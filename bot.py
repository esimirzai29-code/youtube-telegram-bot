import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
import yt_dlp

TOKEN = os.environ.get("BOT_TOKEN")
MAX_FILE_SIZE = 49 * 1024 * 1024

URL_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+", re.I)


def get_url(text: str) -> str | None:
    match = URL_RE.search(text or "")
    return match.group(0).rstrip(".,)>]}\"'") if match else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 YouTube Downloader\n\n"
        "لینک ویدیو از YouTube را بفرست تا گزینه‌های دانلود را بهت نشان بدهم.\n\n"
        "مثال:\nhttps://www.youtube.com/watch?v=..."
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = get_url(update.message.text)
    if not url:
        await update.message.reply_text("❌ لطفاً یک لینک معتبر YouTube بفرست.")
        return

    msg = await update.message.reply_text("🔎 در حال بررسی ویدیو...")
    try:
        info = await asyncio.to_thread(extract_info, url)
        context.user_data["yt_url"] = url
        context.user_data["yt_info"] = info

        title = info.get("title", "YouTube video")
        duration = info.get("duration")
        duration_text = f"\n⏱ مدت: {duration // 60}:{duration % 60:02d}" if duration else ""
        text = f"🎬 {title}{duration_text}\n\nفرمت را انتخاب کن:"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎥 ویدیو MP4", callback_data="video")],
            [InlineKeyboardButton("🎵 صدا MP3", callback_data="audio")],
        ])
        await msg.edit_text(text, reply_markup=keyboard)
    except Exception as exc:
        await msg.edit_text(f"❌ نتونستم اطلاعات ویدیو را بگیرم.\n\n{type(exc).__name__}: {str(exc)[:300]}")


def extract_info(url: str):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.user_data.get("yt_url")
    info = context.user_data.get("yt_info")
    if not url or not info:
        await query.edit_message_text("❌ لینک منقضی شده. دوباره لینک را بفرست.")
        return

    mode = query.data
    await query.edit_message_text("⏳ دانلود شروع شد؛ لطفاً صبر کن...")
    await context.bot.send_chat_action(query.message.chat_id, ChatAction.UPLOAD_DOCUMENT)

    file_path = None
    try:
        result = await asyncio.to_thread(download_media, url, mode)
        file_path = result["path"]
        title = result["title"]
        size = os.path.getsize(file_path)

        if size > MAX_FILE_SIZE:
            await query.message.reply_text(
                f"❌ فایل {size / 1024 / 1024:.1f}MB است و برای ارسال توسط این ربات بیش از حد بزرگ است.\n"
                "یک کیفیت پایین‌تر انتخاب کن."
            )
            return

        with open(file_path, "rb") as f:
            if mode == "audio":
                await query.message.reply_audio(audio=f, filename=f"{safe_name(title)}.mp3", title=title[:64])
            else:
                await query.message.reply_video(video=f, filename=f"{safe_name(title)}.mp4", supports_streaming=True)

        await query.message.reply_text("✅ آماده شد! لینک بعدی را بفرست.")
    except Exception as exc:
        await query.message.reply_text(f"❌ دانلود انجام نشد.\n{str(exc)[:500]}")
    finally:
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
                shutil.rmtree(Path(file_path).parent, ignore_errors=True)
            except Exception:
                pass


def safe_name(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\n\r]+", "_", name).strip()
    return name[:80] or "youtube"


def download_media(url: str, mode: str):
    workdir = tempfile.mkdtemp(prefix="ytbot_")
    outtmpl = os.path.join(workdir, "%(title).80s.%(ext)s")
    common = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "restrictfilenames": True,
        "retries": 3,
        "fragment_retries": 3,
        # Prefer a playable format, but always fall back instead of failing
        # when a particular YouTube format combination is unavailable.
        "ignoreerrors": False,
    }

    if mode == "audio":
        opts = {
            **common,
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
        }
    else:
        # Robust selector: prefer <=720p video+audio, then a progressive
        # <=720p stream, then any single best stream. This avoids the
        # 'Requested format is not available' failure on videos that do not
        # expose the exact MP4/height combination.
        opts = {
            **common,
            "format": "bv*[height<=720]+ba/b[height<=720]/b",
            "merge_output_format": "mp4",
        }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("yt-dlp نتوانست این ویدیو را دانلود کند")
            title = info.get("title", "youtube")
    except Exception as first_error:
        # Final fallback for unusual YouTube format manifests.
        if mode != "audio":
            fallback = {**common, "format": "best", "merge_output_format": "mp4"}
            with yt_dlp.YoutubeDL(fallback) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise first_error
                title = info.get("title", "youtube")
        else:
            raise

    files = [p for p in Path(workdir).iterdir() if p.is_file()]
    if not files:
        shutil.rmtree(workdir, ignore_errors=True)
        raise RuntimeError("فایل دانلودشده پیدا نشد")

    ext = ".mp3" if mode == "audio" else ".mp4"
    preferred = [p for p in files if p.suffix.lower() == ext]
    path = preferred[0] if preferred else files[0]
    return {"path": str(path), "title": title}


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Bot error: {context.error!r}")


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(video|audio)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_error_handler(error_handler)
    print("YouTube Telegram bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

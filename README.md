# YouTube Telegram Downloader

Telegram bot for downloading YouTube videos as MP4 or audio as MP3.

## Features
- YouTube URL detection
- MP4 video download (up to 720p preference)
- MP3 audio extraction
- Temporary files are deleted after sending
- `BOT_TOKEN` is read from an environment variable
- Railway-ready Docker deployment

## Railway
1. Connect this GitHub repository to Railway.
2. Deploy the service using the included `Dockerfile`.
3. Add an environment variable named `BOT_TOKEN` containing your Telegram BotFather token.
4. Redeploy.

Do not commit your Telegram token to GitHub.

## Usage
Send `/start`, then send a YouTube URL and choose Video or Audio.

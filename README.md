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

## Website (تک‌نوشت blog)

A Persian (RTL) static blog lives in [`site/`](site/) — 4 pages, dark/light mode,
live search, categories, tags, bookmarks, likes and comments (localStorage).

Serve it locally:

```bash
cd site
python3 -m http.server 8000
```

### Deploy the website to Railway (separate service)

The bot keeps using the root `Dockerfile`. The website has its own
[`site/Dockerfile`](site/Dockerfile) + [`site/railway.toml`](site/railway.toml).

1. In Railway, create a **new service** (`+ New` → `GitHub Repo`) from this repository.
2. Open the new service → **Settings** → **Source**:
   - **Root Directory** = `site`
   - **Branch** = the branch containing `site/` (e.g. `main` after merge)
3. Deploy (builder `DOCKERFILE` is picked up automatically from `site/railway.toml`).
4. Open the service → **Networking** → **Generate Domain** to get a public URL.

No environment variables are needed for the website.

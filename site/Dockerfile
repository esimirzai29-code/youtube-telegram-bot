# تک‌نوشت | Static website image for Railway
# This Dockerfile is ONLY for the website service.
# The Telegram bot keeps using the Dockerfile in the repo root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY index.html article.html about.html contact.html ./
COPY css/ ./css/
COPY js/ ./js/

EXPOSE 8000

# Railway injects $PORT at runtime; default to 8000 for local runs
CMD ["sh", "-c", "python -m http.server ${PORT:-8000} --bind 0.0.0.0"]

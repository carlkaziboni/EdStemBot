# askEd Live: public audience Q&A, quiz and presenter page.
#
# Image contents: only the live-mode runtime (no torch, no course PDFs, no EdStem token).
# The approved-docs index and the embedding model are built into the image so the first
# attendee never waits on a download, and a redeploy never depends on a persistent index.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_MODE=live \
    EMBEDDING_BACKEND=fastembed \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache \
    CHROMA_PERSIST_DIR=/app/chroma_db \
    LLM_PROVIDER=claude \
    DASHBOARD_HOST=0.0.0.0 \
    DASHBOARD_PORT=8000 \
    DATABASE_URL=sqlite+aiosqlite:////data/asked.db

WORKDIR /app

# Dependencies first so this layer is cached when only code or documents change.
COPY requirements-live.txt .
RUN pip install -r requirements-live.txt

COPY . .

# Build the approved-docs index (data/about/*.md + README.md) and download the embedding model.
RUN python scripts/ingest_about.py

# Run unprivileged. /data is where Render mounts the persistent disk for SQLite; the
# entrypoint fixes its ownership at start-up because mounted disks are root-owned.
RUN useradd --system --uid 10001 --home-dir /app app \
    && mkdir -p /data \
    && chown -R app:app /app /data \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000
# Render injects PORT; fall back to 8000 for local `docker run`.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8000'), timeout=4)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "bot/main.py"]

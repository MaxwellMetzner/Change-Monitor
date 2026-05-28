FROM node:22-trixie-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.11-slim-trixie AS runtime

LABEL org.opencontainers.image.title="Change Monitor" \
      org.opencontainers.image.description="Web page and element change monitor with Pushover notifications" \
      org.opencontainers.image.source="https://github.com/max1234565/Change-Monitor" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade \
        pip==26.1.1 \
        setuptools==82.0.1 \
        wheel==0.47.0 \
    && python -m pip install --no-cache-dir -r /app/backend/requirements.txt

RUN python -m playwright install --with-deps chromium \
    && apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

COPY backend /app/backend
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend
RUN DATA_DIR=/tmp/change-monitor-install-check \
    CHANGE_MONITOR_STRICT_INSTALL_CHECK=1 \
    python -m pytest tests \
    && rm -rf /tmp/change-monitor-install-check

RUN mkdir -p /data /ms-playwright \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app /data /ms-playwright

VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

USER appuser

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

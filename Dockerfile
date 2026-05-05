FROM node:22-bookworm-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Change Monitor" \
      org.opencontainers.image.description="Web page and element change monitor with Pushover notifications" \
      org.opencontainers.image.source="https://github.com/max1234565/changemonitor" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY backend /app/backend
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

RUN mkdir -p /data /ms-playwright \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app /data /ms-playwright

VOLUME ["/data"]
EXPOSE 8000

USER appuser

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

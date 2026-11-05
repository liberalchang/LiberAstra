# syntax=docker/dockerfile:1
# LiberAstra 单镜像：前端构建 + Python 运行时（ffmpeg、中文字体、Playwright Chromium）。

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
# 文档源在仓库 site/docs-src，前端构建时用 import.meta.glob 打进 dist
COPY site/docs-src /site/docs-src
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    LIBERASTRA_DATA_DIR=/data \
    LIBERASTRA_STATIC_DIR=/app/static \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend \
    && site=$(python -c "import liberastra, pathlib; print(pathlib.Path(liberastra.__file__).resolve().parents[1])") \
    && cp -a backend/templates "$site/templates" \
    && cp -a backend/prompts "$site/prompts" \
    && cp -a backend/workflows "$site/workflows" \
    && playwright install --with-deps chromium \
    && rm -rf ./backend /var/lib/apt/lists/*

COPY --from=frontend /build/dist ./static

EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["astra", "serve"]

# syntax=docker/dockerfile:1
# LiberAstra 单镜像：前端构建 + Python 运行时（ffmpeg + 中文字体）。
# full 变体（Playwright / HTML 模板帧）在 M4 提供。

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
# 使用文档在仓库 docs/，页面用相对路径引用，构建时放到镜像里对应位置
COPY docs/使用文档.md /docs/使用文档.md
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    LIBERASTRA_DATA_DIR=/data \
    LIBERASTRA_STATIC_DIR=/app/static

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend \
    && rm -rf ./backend

COPY --from=frontend /build/dist ./static

EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["astra", "serve"]

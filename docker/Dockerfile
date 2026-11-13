# syntax=docker/dockerfile:1
# LiberAstra 单镜像：前端构建 + Python 运行时（ffmpeg、中文字体、Playwright Chromium）。

# 基础镜像可通过 --build-arg 换成国内 registry 镜像；默认 Docker Hub。
ARG NODE_IMAGE=node:22-alpine
ARG PYTHON_IMAGE=python:3.11-slim

FROM ${NODE_IMAGE} AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
# 文档源在仓库 site/docs-src：旧版 markdown 内嵌 + embed-manual 构建 VitePress 到 dist/manual
COPY site/docs-src /site/docs-src
RUN npm run build

FROM ${PYTHON_IMAGE} AS runtime

# 默认使用清华 PyPI；海外或私有源可用 --build-arg 覆盖。
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_DEFAULT_TIMEOUT=120
ARG PIP_RETRIES=10

# Playwright 浏览器包默认走 cdn.playwright.dev，国内可切 npmmirror。
ARG PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright

ENV PYTHONUNBUFFERED=1 \
    LIBERASTRA_DATA_DIR=/data \
    LIBERASTRA_STATIC_DIR=/app/static \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST} \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=${PIP_DEFAULT_TIMEOUT} \
    PIP_RETRIES=${PIP_RETRIES}

# Debian 官方源在部分网络下极慢；构建时切到国内镜像（可用环境变量覆盖）。
ARG APT_MIRROR=mirrors.aliyun.com
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s/deb.debian.org/${APT_MIRROR}/g; s/security.debian.org/${APT_MIRROR}/g" /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i "s/deb.debian.org/${APT_MIRROR}/g; s/security.debian.org/${APT_MIRROR}/g" /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk libatomic1; \
    rm -rf /var/lib/apt/lists/*

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

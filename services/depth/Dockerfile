# 深度图服务镜像。推理依赖 CUDA，部署在局域网显卡主机上。
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LIBER_DEPTH_MODELS_DIR=/models \
    LIBER_DEPTH_RESULTS_DIR=/data/results \
    LIBER_DEPTH_DEVICE=cuda \
    LIBER_DEPTH_MODEL=dpt_swin2_large_384

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn python-multipart opencv-python-headless timm

COPY engine.py server.py ./
EXPOSE 5556
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5556"]

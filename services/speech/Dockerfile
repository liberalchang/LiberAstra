# 语音服务镜像。推理依赖 CUDA，部署在局域网显卡主机上。
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    HUGGINGFACE_HUB_CACHE=/models \
    LIBER_SPEECH_RESULTS_DIR=/data/results \
    LIBER_SPEECH_DEVICE=auto

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# chatterbox-tts 可能改写 torch，装完后再钉回 CUDA 版。
# 基础镜像自带的 torchvision 0.20 对不上这个 torch，transformers 导入 LlamaModel 会失败。
# 语音合成不用 torchvision，直接卸掉。
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps qwen-asr \
    && pip install --no-cache-dir "transformers==5.2.0" \
    && pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cu124 \
    && pip uninstall -y torchvision

COPY engine.py server.py ./
EXPOSE 5555
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5555"]

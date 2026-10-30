"""Liber Depth HTTP 服务。默认 0.0.0.0:5556。

主服务通过 liber_depth Provider 调用，不在主进程里加载 MiDaS。
"""

from __future__ import annotations

import base64
import os
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from engine import default_device, default_model, engine, results_dir, scan_models

app = FastAPI(title="Liber Depth", version="1.0.0")


def _safe_name(filename: str) -> str:
    """只保留文件名，避免路径穿越。"""
    name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="文件名无效")
    return name


def _check_key(authorization: str | None) -> None:
    expected = os.environ.get("LIBER_DEPTH_API_KEY", "").strip()
    if not expected:
        return
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="API Key 不正确")


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    payload = engine.health()
    payload["service"] = "liber-depth"
    return payload


@app.get("/api/v1/models")
def models() -> dict[str, Any]:
    found = scan_models()
    return {
        "default_model": default_model(),
        "models": [{"id": item["id"], "label": item["label"]} for item in found],
    }


@app.post("/api/v1/depth/convert")
async def convert(
    image: UploadFile = File(...),
    model: str = Form(""),
    device: str = Form(""),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    _check_key(authorization)
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        filename, png = engine.convert(
            content,
            image.filename or "image.png",
            model or None,
            device or default_device(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"深度图生成失败: {exc}") from exc
    filename = _safe_name(filename)
    out = results_dir() / filename
    if out.exists():
        stem = out.stem
        suffix = out.suffix
        index = 2
        while (results_dir() / f"{stem}_{index}{suffix}").exists():
            index += 1
        filename = f"{stem}_{index}{suffix}"
        out = results_dir() / filename
    out.write_bytes(png)
    return {
        "filename": filename,
        "png_base64": base64.b64encode(png).decode("ascii"),
    }


@app.get("/api/v1/results/{filename}")
def result_file(filename: str) -> FileResponse:
    safe = _safe_name(filename)
    path = results_dir() / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, media_type="image/png", filename=safe)

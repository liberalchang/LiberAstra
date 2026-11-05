"""E2E 种子：在临时数据目录写入不同功能的 job/asset，供历史与上传测试使用。"""

from __future__ import annotations

import io
import uuid

from PIL import Image
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Job, User
from liberastra.storage import save_bytes


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (120, 180, 240)).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png()


def _add(
    db,
    owner_id: int,
    *,
    kind: str,
    function: str,
    asset_kind: str,
    label: str,
    ext: str,
    content: bytes,
    mime: str,
    hidden: bool = False,
    with_job: bool = True,
) -> Asset:
    job_id = None
    if with_job:
        job = Job(
            kind=kind,
            function=function,
            status="succeeded",
            owner_id=owner_id,
            params={},
            outputs=[],
        )
        db.add(job)
        db.flush()
        job_id = job.id
    rel = f"outputs/e2e-seed/{uuid.uuid4().hex}.{ext}"
    save_bytes(content, rel)
    asset = Asset(
        kind=asset_kind,
        path=rel,
        owner_id=owner_id,
        job_id=job_id,
        hidden=hidden,
        size=len(content),
        mime=mime,
        meta={"name": label, "source_name": f"{label}.{ext}"},
    )
    db.add(asset)
    db.flush()
    return asset


def main() -> None:
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None, "E2E 管理员尚未创建"
        _add(
            db,
            user.id,
            kind="image.generate",
            function="image.generate",
            asset_kind="image",
            label="E2E 生成图",
            ext="png",
            content=PNG,
            mime="image/png",
        )
        _add(
            db,
            user.id,
            kind="image.edit",
            function="image.i2i",
            asset_kind="image",
            label="E2E 图生图",
            ext="png",
            content=PNG,
            mime="image/png",
        )
        _add(
            db,
            user.id,
            kind="image.edit",
            function="image.upscale",
            asset_kind="image",
            label="E2E 图片增强",
            ext="png",
            content=PNG,
            mime="image/png",
        )
        _add(
            db,
            user.id,
            kind="media.concat",
            function="media.concat",
            asset_kind="image",
            label="E2E 拼接",
            ext="png",
            content=PNG,
            mime="image/png",
        )
        _add(
            db,
            user.id,
            kind="tts.synthesize",
            function="tts.synthesize",
            asset_kind="audio",
            label="E2E 语音",
            ext="mp3",
            content=b"ID3E2E",
            mime="audio/mpeg",
        )
        _add(
            db,
            user.id,
            kind="vc.convert",
            function="vc.convert",
            asset_kind="audio",
            label="E2E 换音",
            ext="mp3",
            content=b"ID3E2EVC",
            mime="audio/mpeg",
        )
        _add(
            db,
            user.id,
            kind="asr.transcribe",
            function="asr.transcribe",
            asset_kind="subtitle",
            label="E2E 字幕",
            ext="srt",
            content=b"1\n00:00:00,000 --> 00:00:01,000\nE2E\n",
            mime="text/plain",
        )
        _add(
            db,
            user.id,
            kind="video.quick",
            function="video.quick",
            asset_kind="text",
            label="E2E 分镜文本",
            ext="txt",
            content=b"E2E storyboard",
            mime="text/plain",
        )
        _add(
            db,
            user.id,
            kind="video.quick",
            function="video.quick",
            asset_kind="video",
            label="E2E 快速视频",
            ext="mp4",
            content=b"E2E-VIDEO",
            mime="video/mp4",
        )
        _add(
            db,
            user.id,
            kind="",
            function="",
            asset_kind="image",
            label="E2E 隐藏输入",
            ext="png",
            content=PNG,
            mime="image/png",
            hidden=True,
            with_job=False,
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()

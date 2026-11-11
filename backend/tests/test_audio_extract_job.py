"""音频提取任务：从视频截固定长度尾音，产出可复用的音频资产。"""

from __future__ import annotations

import asyncio
import shutil
import uuid

import pytest
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.media import ffmpeg
from liberastra.models import Asset, Job, User
from liberastra.services.media_jobs import run_extract_audio_job
from liberastra.storage import resolve

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="需要 ffmpeg")


class _Ctx:
    def report(self, *_args, **_kwargs) -> None:
        pass

    def cancelled(self) -> bool:
        return False


def test_extract_audio_job_writes_tail_asset(client, auth_header) -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        source_rel = "uploads/audio_extract_test.mp4"
        source = resolve(source_rel)
        source.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(
            ffmpeg._run(
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=1.2",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(source),
            )
        )
        source_asset = Asset(kind="video", path=source_rel, owner_id=user.id, origin="output")
        db.add(source_asset)
        db.commit()
        db.refresh(source_asset)
        job = Job(
            id=str(uuid.uuid4()),
            kind="media.extract_audio",
            status="running",
            owner_id=user.id,
            params={
                "asset_id": source_asset.id,
                "mode": "tail",
                "seconds": 0.4,
                "visible": False,
            },
        )
        db.add(job)
        db.commit()

        outputs = asyncio.run(run_extract_audio_job(db, job, _Ctx()))
        assert outputs[0]["kind"] == "audio"
        result = db.get(Asset, outputs[0]["asset_id"])
        assert result is not None and result.kind == "audio"
        assert result.meta["tool_id"] == "audio_extract"
        assert result.meta["mode"] == "tail"
        duration = asyncio.run(ffmpeg.probe_duration(resolve(result.path)))
        assert 0.2 < duration < 0.6
    finally:
        db.close()

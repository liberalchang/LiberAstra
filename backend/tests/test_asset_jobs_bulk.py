"""素材库「工作」：批量下载与删除任务文件夹。"""

from __future__ import annotations

import io
import uuid
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Job, User
from liberastra.storage import resolve, save_bytes


def _create_job_with_files(
    kind: str,
    assets: list[tuple[str, str, bool]],
    *,
    status: str = "succeeded",
    owner_id: int | None = None,
) -> tuple[str, list[int]]:
    db = SessionLocal()
    try:
        if owner_id is None:
            user = db.scalars(select(User)).first()
            assert user is not None
            owner_id = user.id
        job = Job(kind=kind, status=status, owner_id=owner_id, params={}, outputs=[])
        db.add(job)
        db.flush()
        asset_ids: list[int] = []
        for asset_kind, name, hidden in assets:
            rel = f"outputs/{job.id}/{name}"
            content = f"{job.id}:{name}".encode()
            save_bytes(content, rel)
            asset = Asset(
                kind=asset_kind,
                path=rel,
                owner_id=owner_id,
                job_id=job.id,
                hidden=hidden,
                size=len(content),
                meta={},
            )
            db.add(asset)
            db.flush()
            asset_ids.append(asset.id)
        db.commit()
        return job.id, asset_ids
    finally:
        db.close()


def test_asset_jobs_bulk_download_only_visible_assets(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    job_id, _ = _create_job_with_files(
        f"test.assetjobs.zip.{uuid.uuid4().hex}",
        [
            ("audio", "voice.mp3", False),
            ("subtitle", "subtitles.srt", False),
            ("text", "hidden.txt", True),
        ],
    )
    response = client.post(
        "/api/v1/assets/jobs/download",
        json={"job_ids": [job_id]},
        headers=auth_header,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
    assert any(name.endswith("/voice.mp3") for name in names)
    assert any(name.endswith("/subtitles.srt") for name in names)
    assert not any(name.endswith("hidden.txt") for name in names)


def test_asset_jobs_bulk_delete_removes_job_assets_and_files(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    job_id, asset_ids = _create_job_with_files(
        f"test.assetjobs.delete.{uuid.uuid4().hex}",
        [
            ("audio", "voice.mp3", False),
            ("subtitle", "subtitles.srt", False),
            ("text", "hidden.txt", True),
        ],
    )
    keep_job_id, keep_asset_ids = _create_job_with_files(
        f"test.assetjobs.keep.{uuid.uuid4().hex}",
        [("image", "keep.png", False)],
    )

    response = client.post(
        "/api/v1/assets/jobs/delete",
        json={"job_ids": [job_id]},
        headers=auth_header,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"jobs": 1, "assets": 3}

    db = SessionLocal()
    try:
        assert db.get(Job, job_id) is None
        assert db.get(Job, keep_job_id) is not None
        for asset_id in asset_ids:
            assert db.get(Asset, asset_id) is None
        for asset_id in keep_asset_ids:
            assert db.get(Asset, asset_id) is not None
    finally:
        db.close()
    assert not resolve(f"outputs/{job_id}/voice.mp3").exists()
    assert resolve(f"outputs/{keep_job_id}/keep.png").is_file()


def test_asset_jobs_bulk_delete_rejects_active_jobs(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    job_id, asset_ids = _create_job_with_files(
        f"test.assetjobs.running.{uuid.uuid4().hex}",
        [("audio", "voice.mp3", False)],
        status="running",
    )
    response = client.post(
        "/api/v1/assets/jobs/delete",
        json={"job_ids": [job_id]},
        headers=auth_header,
    )
    assert response.status_code == 409, response.text
    db = SessionLocal()
    try:
        assert db.get(Job, job_id) is not None
        assert db.get(Asset, asset_ids[0]) is not None
    finally:
        db.close()


def test_asset_jobs_bulk_actions_reject_unknown_jobs(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/assets/jobs/download",
        json={"job_ids": [str(uuid.uuid4())]},
        headers=auth_header,
    )
    assert response.status_code == 404, response.text
    response = client.post(
        "/api/v1/assets/jobs/delete",
        json={"job_ids": [str(uuid.uuid4())]},
        headers=auth_header,
    )
    assert response.status_code == 404, response.text

"""浏览器直链下载：短时令牌只放行对应的资产或任务压缩包。"""

from __future__ import annotations

import io
import uuid
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.core.security import create_download_token
from liberastra.models import Asset, Job, User
from liberastra.storage import save_bytes


def _create_asset(name: str, content: bytes) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        rel = f"outputs/download-token/{uuid.uuid4().hex}/{name}"
        save_bytes(content, rel)
        asset = Asset(
            kind="text",
            path=rel,
            owner_id=user.id,
            size=len(content),
            mime="text/plain",
            meta={},
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset.id, rel
    finally:
        db.close()


def _create_job_with_file(name: str, content: bytes) -> tuple[str, str]:
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        job = Job(kind=f"test.download.{uuid.uuid4().hex}", status="succeeded", owner_id=user.id)
        db.add(job)
        db.flush()
        rel = f"outputs/{job.id}/{name}"
        save_bytes(content, rel)
        db.add(
            Asset(
                kind="text",
                path=rel,
                owner_id=user.id,
                job_id=job.id,
                size=len(content),
                mime="text/plain",
                meta={},
            )
        )
        db.commit()
        return job.id, rel
    finally:
        db.close()


def test_asset_download_token_serves_file_without_auth_header(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    asset_id, _ = _create_asset("hello.txt", b"hello download")
    token_response = client.post(
        f"/api/v1/assets/{asset_id}/download-token",
        headers=auth_header,
    )
    assert token_response.status_code == 200, token_response.text
    url = token_response.json()["url"]

    response = client.get(url)
    assert response.status_code == 200, response.text
    assert response.content == b"hello download"


def test_asset_download_token_is_bound_to_asset_id(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    asset_id, _ = _create_asset("bound.txt", b"bound")
    other_id, _ = _create_asset("other.txt", b"other")
    url = client.post(
        f"/api/v1/assets/{asset_id}/download-token",
        headers=auth_header,
    ).json()["url"]
    token = url.split("token=", 1)[1]

    response = client.get(
        f"/api/v1/assets/{other_id}/download",
        params={"token": token},
    )
    assert response.status_code == 403, response.text


def test_asset_download_token_rejects_invalid_and_expired_tokens(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    asset_id, _ = _create_asset("expired.txt", b"expired")
    invalid = client.get(
        f"/api/v1/assets/{asset_id}/download",
        params={"token": "not-a-token"},
    )
    assert invalid.status_code == 403, invalid.text

    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        owner_id = user.id
    finally:
        db.close()
    expired = create_download_token(
        str(owner_id),
        kind="asset",
        payload={"asset_id": asset_id},
        expires_minutes=-1,
    )
    response = client.get(
        f"/api/v1/assets/{asset_id}/download",
        params={"token": expired},
    )
    assert response.status_code == 403, response.text


def test_asset_download_token_requires_owned_asset(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    response = client.post("/api/v1/assets/999999/download-token", headers=auth_header)
    assert response.status_code == 404, response.text


def test_jobs_download_token_serves_zip_without_auth_header(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    job_id, rel = _create_job_with_file("voice.txt", b"job download")
    token_response = client.post(
        "/api/v1/assets/jobs/download-token",
        json={"job_ids": [job_id]},
        headers=auth_header,
    )
    assert token_response.status_code == 200, token_response.text
    url = token_response.json()["url"]

    response = client.get(url)
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == 1
        assert names[0].endswith("/voice.txt")
        assert archive.read(names[0]) == b"job download"
    assert rel.endswith("/voice.txt")

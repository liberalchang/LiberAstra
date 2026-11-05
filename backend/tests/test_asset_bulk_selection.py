"""资产页批量操作：隐藏筛选、转正、删除和 ZIP 下载。"""

from __future__ import annotations

import io
import uuid
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.core.security import hash_password
from liberastra.models import Asset, Job, User
from liberastra.storage import resolve, save_bytes


def _create_job_with_assets(
    assets: list[tuple[str, str, bool, dict]],
    *,
    owner_id: int | None = None,
) -> tuple[str, list[int]]:
    db = SessionLocal()
    try:
        if owner_id is None:
            user = db.scalars(select(User)).first()
            assert user is not None
            owner_id = user.id
        job = Job(
            kind=f"test.assets.bulk.{uuid.uuid4().hex}",
            status="succeeded",
            owner_id=owner_id,
            params={},
            outputs=[],
        )
        db.add(job)
        db.flush()
        asset_ids: list[int] = []
        for asset_kind, name, hidden, meta in assets:
            rel = f"outputs/{job.id}/{uuid.uuid4().hex}-{name}"
            content = f"{job.id}:{name}".encode()
            save_bytes(content, rel)
            asset = Asset(
                kind=asset_kind,
                path=rel,
                owner_id=owner_id,
                job_id=job.id,
                hidden=hidden,
                size=len(content),
                meta=meta,
            )
            db.add(asset)
            db.flush()
            asset_ids.append(asset.id)
        db.commit()
        return job.id, asset_ids
    finally:
        db.close()


def _create_other_user() -> int:
    db = SessionLocal()
    try:
        user = User(
            username=f"other-{uuid.uuid4().hex[:8]}",
            password_hash=hash_password("other-pass-123"),
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


def test_list_assets_hidden_only_returns_only_hidden(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    _, asset_ids = _create_job_with_assets(
        [
            ("text", "visible.txt", False, {}),
            ("text", "hidden.txt", True, {}),
        ]
    )
    visible_id, hidden_id = asset_ids

    response = client.get("/api/v1/assets?hidden_only=true", headers=auth_header)
    assert response.status_code == 200, response.text
    returned = {asset["id"] for asset in response.json()}
    assert hidden_id in returned
    assert visible_id not in returned

    response = client.get("/api/v1/assets", headers=auth_header)
    assert response.status_code == 200, response.text
    returned = {asset["id"] for asset in response.json()}
    assert visible_id in returned
    assert hidden_id not in returned


def test_bulk_publish_unhides_assets_and_drops_canvas_temp(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    _, asset_ids = _create_job_with_assets(
        [
            ("image", "a.png", True, {"canvas_temp": True, "canvas_id": "c1"}),
            ("image", "b.png", True, {"canvas_temp": True, "canvas_node": "n1"}),
        ]
    )
    response = client.post(
        "/api/v1/assets/publish",
        json={"asset_ids": asset_ids},
        headers=auth_header,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"assets": 2}

    db = SessionLocal()
    try:
        first = db.get(Asset, asset_ids[0])
        second = db.get(Asset, asset_ids[1])
        assert first is not None and second is not None
        assert first.hidden is False and second.hidden is False
        assert first.meta == {"canvas_id": "c1"}
        assert second.meta == {"canvas_node": "n1"}
    finally:
        db.close()


def test_bulk_delete_removes_assets_and_files_but_keeps_job(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    job_id, asset_ids = _create_job_with_assets(
        [
            ("text", "delete-a.txt", False, {}),
            ("text", "delete-b.txt", False, {}),
        ]
    )
    _, keep_asset_ids = _create_job_with_assets([("text", "keep.txt", False, {})])
    keep_id = keep_asset_ids[0]

    db = SessionLocal()
    try:
        deleted_paths = [resolve(db.get(Asset, asset_id).path) for asset_id in asset_ids]
    finally:
        db.close()

    response = client.post(
        "/api/v1/assets/delete",
        json={"asset_ids": asset_ids},
        headers=auth_header,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"assets": 2}

    db = SessionLocal()
    try:
        assert db.get(Job, job_id) is not None
        for asset_id in asset_ids:
            assert db.get(Asset, asset_id) is None
        keep = db.get(Asset, keep_id)
        assert keep is not None
        keep_path = resolve(keep.path)
    finally:
        db.close()
    assert keep_path.is_file()
    assert not any(path.exists() for path in deleted_paths)
    assert resolve(f"outputs/{job_id}").is_dir()


def test_selection_download_zip_deduplicates_names_and_includes_hidden(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    _, asset_ids = _create_job_with_assets(
        [
            ("text", "one.txt", False, {"name": "same"}),
            ("text", "two.txt", True, {"name": "same"}),
        ]
    )
    token_response = client.post(
        "/api/v1/assets/selection/download-token",
        json={"asset_ids": asset_ids},
        headers=auth_header,
    )
    assert token_response.status_code == 200, token_response.text
    url = token_response.json()["url"]
    assert url.startswith("/api/v1/assets/selection/download?token=")

    response = client.get(url)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
    assert len(names) == 2
    assert "missing.txt" not in names
    assert any("(2)" in name for name in names)


def test_bulk_asset_actions_reject_unknown_and_foreign_assets(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/assets/delete",
        json={"asset_ids": [999999999]},
        headers=auth_header,
    )
    assert response.status_code == 404, response.text

    other_user_id = _create_other_user()
    _, foreign_ids = _create_job_with_assets(
        [("text", "foreign.txt", False, {})],
        owner_id=other_user_id,
    )
    response = client.post(
        "/api/v1/assets/publish",
        json={"asset_ids": foreign_ids},
        headers=auth_header,
    )
    assert response.status_code == 404, response.text
    response = client.post(
        "/api/v1/assets/selection/download-token",
        json={"asset_ids": foreign_ids},
        headers=auth_header,
    )
    assert response.status_code == 404, response.text
    db = SessionLocal()
    try:
        assert db.get(Asset, foreign_ids[0]) is not None
    finally:
        db.close()


def test_selection_download_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/assets/selection/download",
        params={"token": "not-a-token"},
    )
    assert response.status_code == 403, response.text


def test_bulk_asset_actions_require_non_empty_selection(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/assets/delete",
        json={"asset_ids": []},
        headers=auth_header,
    )
    assert response.status_code == 422, response.text

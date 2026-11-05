"""资产来源：上传、任务产出与资产库可见性。"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.models import User
from liberastra.storage import create_asset, resolve, save_bytes


def _asset_ids(client: TestClient, auth_header: dict[str, str], **params: object) -> set[int]:
    response = client.get("/api/v1/assets", headers=auth_header, params=params)
    assert response.status_code == 200, response.text
    return {asset["id"] for asset in response.json()}


def test_upload_assets_record_origin(client: TestClient, auth_header: dict[str, str]) -> None:
    visible = client.post(
        "/api/v1/uploads?as_asset=true&kind=image",
        headers=auth_header,
        files={"file": ("library.png", b"library-bytes", "image/png")},
    )
    assert visible.status_code == 201, visible.text
    visible_id = visible.json()["asset_id"]
    detail = client.get(f"/api/v1/assets/{visible_id}", headers=auth_header)
    assert detail.status_code == 200, detail.text
    assert detail.json()["origin"] == "upload"

    hidden = client.post(
        "/api/v1/uploads?as_asset=true&kind=image&hidden=true",
        headers=auth_header,
        files={"file": ("canvas.png", b"canvas-bytes", "image/png")},
    )
    assert hidden.status_code == 201, hidden.text
    hidden_id = hidden.json()["asset_id"]
    detail = client.get(f"/api/v1/assets/{hidden_id}", headers=auth_header)
    assert detail.status_code == 200, detail.text
    assert detail.json()["origin"] == "canvas"


def test_job_outputs_default_to_output_origin(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        rel = f"outputs/origin-test/{uuid.uuid4().hex}.txt"
        save_bytes(b"output", rel)
        asset = create_asset(db, kind="text", rel_path=rel, owner_id=user.id)
        assert asset.origin == "output"
        asset_id = asset.id
        path = resolve(asset.path)
    finally:
        db.close()

    assert asset_id in _asset_ids(client, auth_header)
    detail = client.get(f"/api/v1/assets/{asset_id}", headers=auth_header)
    assert detail.status_code == 200, detail.text
    assert detail.json()["origin"] == "output"
    path.unlink(missing_ok=True)


def test_character_assets_are_hidden_from_asset_lists(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    from tests.test_characters import _sheet

    created = client.post(
        "/api/v1/characters",
        headers=auth_header,
        data={"name": "来源测试角色", "description": "黑长直", "auto_split": "true"},
        files={"turnaround": ("sheet.png", _sheet(), "image/png")},
    )
    assert created.status_code == 201, created.text
    character_id = created.json()["id"]

    front = client.post(f"/api/v1/characters/{character_id}/asset/front", headers=auth_header)
    assert front.status_code == 200, front.text
    asset_id = front.json()["id"]
    assert front.json()["origin"] == "character"

    assert asset_id not in _asset_ids(client, auth_header, include_hidden="true")
    assert asset_id not in _asset_ids(
        client, auth_header, include_hidden="true", hidden_only="true"
    )
    assert asset_id not in _asset_ids(client, auth_header, kind="image", include_hidden="true")

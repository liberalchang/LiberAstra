"""素材库按任务聚合：job 文件夹、隐藏资源、分页与 job_id 过滤。"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Job, User


def _create_job_with_assets(
    kind: str,
    assets: list[tuple[str, bool]],
) -> tuple[str, list[int]]:
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        job = Job(kind=kind, status="succeeded", owner_id=user.id, params={}, outputs=[])
        db.add(job)
        db.flush()
        asset_ids: list[int] = []
        for asset_kind, hidden in assets:
            asset = Asset(
                kind=asset_kind,
                path=f"outputs/{job.id}/{asset_kind}-{uuid.uuid4().hex}",
                owner_id=user.id,
                job_id=job.id,
                hidden=hidden,
                meta={},
            )
            db.add(asset)
            db.flush()
            asset_ids.append(asset.id)
        db.commit()
        return job.id, asset_ids
    finally:
        db.close()


def test_asset_jobs_group_visible_assets(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    kind = f"test.assetjobs.{uuid.uuid4().hex}"
    job_id, asset_ids = _create_job_with_assets(
        kind,
        [("audio", False), ("subtitle", False), ("subtitle", True)],
    )

    response = client.get(
        "/api/v1/assets/jobs",
        params={"job_kind": kind},
        headers=auth_header,
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["job_id"] == job_id
    assert row["job_kind"] == kind
    assert row["asset_count"] == 2
    assert set(row["kinds"]) == {"audio", "subtitle"}

    detail = client.get(
        "/api/v1/assets",
        params={"job_id": job_id},
        headers=auth_header,
    )
    assert detail.status_code == 200, detail.text
    assert {item["id"] for item in detail.json()} == {asset_ids[0], asset_ids[1]}


def test_asset_jobs_skips_hidden_only_jobs(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    kind = f"test.assetjobs.hidden.{uuid.uuid4().hex}"
    _create_job_with_assets(kind, [("audio", True)])

    response = client.get(
        "/api/v1/assets/jobs",
        params={"job_kind": kind},
        headers=auth_header,
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_asset_jobs_paginates(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    kind = f"test.assetjobs.page.{uuid.uuid4().hex}"
    job_ids = [
        _create_job_with_assets(kind, [("image", False)])[0]
        for _ in range(3)
    ]

    first = client.get(
        "/api/v1/assets/jobs",
        params={"job_kind": kind, "limit": 2, "offset": 0},
        headers=auth_header,
    )
    second = client.get(
        "/api/v1/assets/jobs",
        params={"job_kind": kind, "limit": 2, "offset": 2},
        headers=auth_header,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    page_one = {row["job_id"] for row in first.json()}
    page_two = {row["job_id"] for row in second.json()}
    assert len(page_one) == 2
    assert len(page_two) == 1
    assert page_one | page_two == set(job_ids)


def test_assets_job_id_filter_ignores_other_jobs(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    kind = f"test.assetjobs.detail.{uuid.uuid4().hex}"
    first_id, first_assets = _create_job_with_assets(kind, [("audio", False)])
    _second_id, second_assets = _create_job_with_assets(kind, [("audio", False)])

    response = client.get(
        "/api/v1/assets",
        params={"job_id": first_id},
        headers=auth_header,
    )
    assert response.status_code == 200, response.text
    returned = {item["id"] for item in response.json()}
    assert returned == set(first_assets)
    assert returned.isdisjoint(second_assets)

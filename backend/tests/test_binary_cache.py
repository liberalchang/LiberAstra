"""认证二进制内容的缓存头回归。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_bgm_content_requires_revalidation(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/bgm",
        files={"file": ("bed.mp3", b"ID3test", "audio/mpeg")},
        headers=auth_header,
    )
    assert created.status_code == 201
    name = created.json()["name"]
    content = client.get(f"/api/v1/bgm/{name}/content", headers=auth_header)
    assert content.status_code == 200
    assert content.headers["cache-control"] == "private, no-cache"
    assert client.delete(f"/api/v1/bgm/{name}", headers=auth_header).status_code == 204

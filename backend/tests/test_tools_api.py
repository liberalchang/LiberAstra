"""外部拼接工具 API：输出进入资源库，任务可追踪。"""

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image


def _png(color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(client: TestClient, headers: dict[str, str], color: str) -> int:
    response = client.post(
        "/api/v1/uploads?as_asset=true&kind=image",
        files={"file": ("tool.png", _png(color), "image/png")},
        headers=headers,
    )
    assert response.status_code in (200, 201), response.text
    return int(response.json()["asset_id"])


def test_concat_tool_creates_visible_asset(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    first = _upload(client, auth_header, "red")
    second = _upload(client, auth_header, "blue")

    response = client.post(
        "/api/v1/tools/concat?wait=true",
        json={
            "kind": "image",
            "asset_ids": [first, second],
            "layout": "horizontal",
            "gap": 4,
            "gap_color": "#FFFFFF",
        },
        headers=auth_header,
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "succeeded"
    asset_id = next(item["asset_id"] for item in job["outputs"] if item["type"] == "asset")

    asset = client.get(f"/api/v1/assets/{asset_id}", headers=auth_header)
    assert asset.status_code == 200
    assert asset.json()["hidden"] is False
    assert asset.json()["meta"]["tool_id"] == "image_concat"


def test_concat_tool_rejects_wrong_media_kind(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    image_id = _upload(client, auth_header, "green")
    response = client.post(
        "/api/v1/tools/concat?wait=true",
        json={"kind": "video", "asset_ids": [image_id]},
        headers=auth_header,
    )
    assert response.status_code == 400

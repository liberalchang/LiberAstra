"""资产缩略图与模板预览磁盘缓存。"""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from liberastra.core.db import SessionLocal
from liberastra.media.thumbs import list_asset_thumbs
from liberastra.models import User
from liberastra.storage import create_asset, save_bytes


def _png(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), (20, 40, 80)).save(buf, format="PNG")
    return buf.getvalue()


def _owner_id() -> int:
    db = SessionLocal()
    try:
        owner = db.query(User).first()
        assert owner is not None
        return owner.id
    finally:
        db.close()


def _image_asset(name: str, width: int = 960, height: int = 640) -> int:
    rel = f"outputs/thumbs/{name}.png"
    save_bytes(_png(width, height), rel)
    db = SessionLocal()
    try:
        asset = create_asset(db, kind="image", rel_path=rel, owner_id=_owner_id())
        return asset.id
    finally:
        db.close()


def test_image_thumb_is_webp_and_reused(client: TestClient, auth_header: dict[str, str]) -> None:
    asset_id = _image_asset("wide")
    url = f"/api/v1/assets/{asset_id}/thumb"
    first = client.get(url, headers=auth_header)
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("image/webp")
    with Image.open(BytesIO(first.content)) as image:
        assert max(image.size) <= 480
        assert image.size[0] == 480
    cached_files = list_asset_thumbs(asset_id)
    assert len(cached_files) == 1
    cached = cached_files[0]
    assert cached.stat().st_size > 0
    stamp = cached.stat().st_mtime_ns
    second = client.get(url, headers=auth_header)
    assert second.status_code == 200
    assert second.content == first.content
    assert cached.stat().st_mtime_ns == stamp


def test_thumb_follows_replaced_file(client: TestClient, auth_header: dict[str, str]) -> None:
    """源文件换成另一张图后，不能继续返回第一次缓存的缩略图。"""
    asset_id = _image_asset("repaint")
    url = f"/api/v1/assets/{asset_id}/thumb"
    first = client.get(url, headers=auth_header)
    assert first.status_code == 200
    buf = BytesIO()
    Image.new("RGB", (200, 200), (240, 10, 10)).save(buf, format="PNG")
    save_bytes(buf.getvalue(), "outputs/thumbs/repaint.png")
    second = client.get(url, headers=auth_header)
    assert second.status_code == 200
    assert second.content != first.content
    with Image.open(BytesIO(second.content)) as image:
        red, green, blue = image.getpixel((image.width // 2, image.height // 2))
        assert red > 200 and green < 40 and blue < 40
    assert len(list_asset_thumbs(asset_id)) == 1


def test_non_visual_asset_has_no_thumb(client: TestClient, auth_header: dict[str, str]) -> None:
    rel = "outputs/thumbs/note.txt"
    save_bytes(b"hello", rel)
    db = SessionLocal()
    try:
        asset = create_asset(db, kind="text", rel_path=rel, owner_id=_owner_id())
        asset_id = asset.id
    finally:
        db.close()
    resp = client.get(f"/api/v1/assets/{asset_id}/thumb", headers=auth_header)
    assert resp.status_code == 400


def test_delete_asset_removes_thumb(client: TestClient, auth_header: dict[str, str]) -> None:
    asset_id = _image_asset("gone")
    assert client.get(f"/api/v1/assets/{asset_id}/thumb", headers=auth_header).status_code == 200
    assert list_asset_thumbs(asset_id)
    deleted = client.delete(f"/api/v1/assets/{asset_id}", headers=auth_header)
    assert deleted.status_code == 204
    assert list_asset_thumbs(asset_id) == []


def test_template_preview_hits_disk_cache(
    client: TestClient, auth_header: dict[str, str], monkeypatch
) -> None:
    listed = client.get("/api/v1/templates", headers=auth_header)
    assert listed.status_code == 200
    item = listed.json()[0]
    calls = {"n": 0}

    async def fake_render(
        html: str,
        *,
        width: int,
        height: int,
        fmt: str = "png",
        adjust: dict | None = None,
    ) -> bytes:
        calls["n"] += 1
        buf = BytesIO()
        Image.new("RGB", (width, height), (12, 34, 56)).save(buf, format="JPEG", quality=70)
        return buf.getvalue()

    monkeypatch.setattr("liberastra.api.routes.templates.render_html", fake_render)
    url = f"/api/v1/templates/{item['aspect']}/{item['name']}/preview"
    first = client.get(url, headers=auth_header)
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("image/webp")
    with Image.open(BytesIO(first.content)) as image:
        assert max(image.size) <= 480
    second = client.get(url, headers=auth_header)
    assert second.status_code == 200
    assert second.content == first.content
    assert calls["n"] == 1

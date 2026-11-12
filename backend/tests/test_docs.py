"""交互式 API 文档走本机 Swagger；使用文档走 VitePress /manual/。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from liberastra.main import ManualStaticFiles


def test_docs_page_uses_local_swagger(client: TestClient) -> None:
    page = client.get("/docs")
    assert page.status_code == 200
    assert "/swagger/swagger-ui-bundle.js" in page.text
    assert "/swagger/swagger-ui.css" in page.text
    assert "cdn.jsdelivr.net" not in page.text

    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    assert spec.json()["openapi"]
    assert spec.json()["paths"]


def test_manual_static_clean_urls(tmp_path: Path) -> None:
    """VitePress cleanUrls：目录首页与无后缀路径要落到对应 .html。"""
    manual = tmp_path / "manual"
    manual.mkdir()
    (manual / "index.html").write_text("<html><body>manual-home</body></html>", encoding="utf-8")
    (manual / "install.html").write_text("<html><body>manual-install</body></html>", encoding="utf-8")
    nested = manual / "guides"
    nested.mkdir()
    (nested / "image.html").write_text("<html><body>manual-image</body></html>", encoding="utf-8")

    app = FastAPI()
    app.mount("/manual", ManualStaticFiles(directory=manual, html=False), name="manual")
    client = TestClient(app)

    home = client.get("/manual/")
    assert home.status_code == 200
    assert "manual-home" in home.text

    page = client.get("/manual/install")
    assert page.status_code == 200
    assert "manual-install" in page.text

    nested_page = client.get("/manual/guides/image")
    assert nested_page.status_code == 200
    assert "manual-image" in nested_page.text

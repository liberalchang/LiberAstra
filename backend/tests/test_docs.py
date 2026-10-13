"""交互式 API 文档走本机 Swagger 资源，不依赖境外 CDN。"""

from fastapi.testclient import TestClient


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

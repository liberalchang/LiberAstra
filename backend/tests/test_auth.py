"""鉴权 API 集成测试：初始化、登录、JWT、API Token 生命周期。"""

from fastapi.testclient import TestClient


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_setup_login_me(client: TestClient, admin_credentials: dict[str, str]) -> None:
    assert client.get("/api/v1/auth/status").json() == {"initialized": False}

    resp = client.post("/api/v1/auth/setup", json=admin_credentials)
    assert resp.status_code == 201
    assert resp.json()["username"] == "admin"
    assert resp.json()["is_admin"] is True

    # 重复初始化被拒绝
    assert client.post("/api/v1/auth/setup", json=admin_credentials).status_code == 409
    assert client.get("/api/v1/auth/status").json() == {"initialized": True}

    # 错误密码
    bad = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert bad.status_code == 401

    ok = client.post("/api/v1/auth/login", json=admin_credentials)
    assert ok.status_code == 200
    token = ok.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    # 无凭据 / 伪造凭据
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer fake"}).status_code == 401
    )


def test_api_token_lifecycle(client: TestClient, auth_header: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/tokens", json={"name": "cli", "expires_in_days": 30}, headers=auth_header
    )
    assert created.status_code == 201
    body = created.json()
    assert body["token"].startswith("astra_")
    assert body["expires_at"] is not None

    # 明文 token 可以调用 API
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200

    # 列表不泄露明文
    tokens = client.get("/api/v1/tokens", headers=auth_header).json()
    assert len(tokens) == 1
    assert "token" not in tokens[0]

    # 吊销后失效
    assert client.delete(f"/api/v1/tokens/{body['id']}", headers=auth_header).status_code == 204
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['token']}"}
        ).status_code
        == 401
    )

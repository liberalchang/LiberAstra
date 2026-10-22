"""pytest 公共夹具。必须在导入 liberastra 之前固定数据目录（settings 有 lru_cache）。"""

from __future__ import annotations

import os
import tempfile

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="liberastra-test-")
os.environ["LIBERASTRA_DATA_DIR"] = _TEST_DATA_DIR
os.environ["LIBERASTRA_SECRET_KEY"] = "test-secret-key-padded-to-32-bytes!!"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from liberastra.main import create_app  # noqa: E402


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """初始化测试必须先跑。client 是整个进程共用的，别的用例会先创建管理员。"""
    early = [item for item in items if item.name == "test_setup_login_me"]
    if not early:
        return
    rest = [item for item in items if item.name != "test_setup_login_me"]
    items[:] = early + rest


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="session")
def admin_credentials() -> dict[str, str]:
    return {"username": "admin", "password": "admin-pass-123"}


@pytest.fixture(scope="session")
def auth_header(client: TestClient, admin_credentials: dict[str, str]) -> dict[str, str]:
    resp = client.post("/api/v1/auth/setup", json=admin_credentials)
    assert resp.status_code in (201, 409)
    resp = client.post("/api/v1/auth/login", json=admin_credentials)
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

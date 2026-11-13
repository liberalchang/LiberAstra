from __future__ import annotations

import pytest
import server
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LIBER_SPEECH_FILES_DIR", str(tmp_path / "files"))
    monkeypatch.delenv("LIBER_SPEECH_API_KEY", raising=False)
    monkeypatch.setenv("LIBER_SPEECH_MAX_UPLOAD_BYTES", "0")
    monkeypatch.setenv("LIBER_SPEECH_MAX_MEDIA_SECONDS", "0")
    server._FILE_STORE = None
    return TestClient(server.app)


def test_upload_and_delete_without_size_limit(client: TestClient) -> None:
    data = b"x" * (2 * 1024 * 1024)
    response = client.post(
        "/api/v2/files",
        files={"file": ("a.wav", data, "audio/wav")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["file_id"].startswith("f_")
    assert body["filename"] == "a.wav"
    assert body["size"] == len(data)
    assert body["sha256"]
    assert body["expires_at"]

    deleted = client.delete(f"/api/v2/files/{body['file_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    missing = client.delete(f"/api/v2/files/{body['file_id']}")
    assert missing.status_code == 404


def test_help_endpoints(client: TestClient) -> None:
    all_help = client.get("/api/v2/help")
    assert all_help.status_code == 200
    assert set(all_help.json()["functions"]) == {"tts", "asr", "vc"}

    function_help = client.get("/api/v2/help/tts")
    assert function_help.status_code == 200
    assert function_help.json()["endpoint"]["path"] == "/api/v2/tts/synthesize"

    model_help = client.get("/api/v2/help/tts/turbo")
    assert model_help.status_code == 200
    payload = model_help.json()
    assert payload["model"] == "turbo"
    assert "unsupported_parameters" in payload
    assert any(item["name"] == "exaggeration" for item in payload["unsupported_parameters"])

    query_help = client.get("/api/v2/help?function=vc&model=seed-vc")
    assert query_help.status_code == 200
    assert query_help.json()["model"] == "seed-vc"

    common_only = client.get("/api/v2/help/asr/qwen3-asr-1.7b?include=model")
    assert common_only.status_code == 200
    names = {item["name"] for item in common_only.json()["parameters"]}
    assert "max_inference_batch_size" in names
    assert "file_id" not in names

    markdown = client.get("/api/v2/help?format=markdown")
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert "# Liber Speech Help" in markdown.text

    assert client.get("/api/v2/help/nope").status_code == 404
    assert client.get("/api/v2/help/tts/nope").status_code == 404
    assert client.get("/api/v2/help?format=xml").status_code == 400


def test_models_v2(client: TestClient) -> None:
    response = client.get("/api/v2/models")
    assert response.status_code == 200
    models = response.json()["models"]
    assert set(models) == {"tts", "asr", "vc"}
    turbo = next(item for item in models["tts"] if item["id"] == "turbo")
    assert turbo["params_url"] == "/api/v2/help/tts/turbo"
    assert "top_k" in turbo["supports"]

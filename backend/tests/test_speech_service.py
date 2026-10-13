"""语音服务 HTTP 契约：不加载模型。"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

SPEECH_DIR = Path(__file__).resolve().parents[2] / "services" / "speech"
sys.path.insert(0, str(SPEECH_DIR))

import engine  # noqa: E402
import server  # noqa: E402


def test_resolve_device_cpu() -> None:
    assert engine.resolve_device("cpu") == "cpu"


def test_health_auth_and_result_name(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("LIBER_SPEECH_RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("LIBER_SPEECH_API_KEY", "secret")
    client = TestClient(server.app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["asr_ready"] is False
    assert body["tts_ready"] is False

    denied = client.post("/api/v1/tts/synthesize", data={"text": "你好", "language": "zh"})
    assert denied.status_code == 401

    missing = client.get("/api/v1/results/notes.txt", headers={"Authorization": "Bearer secret"})
    assert missing.status_code == 400

from __future__ import annotations

import pytest
import server
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LIBER_SPEECH_FILES_DIR", str(tmp_path / "files"))
    monkeypatch.setenv("LIBER_SPEECH_RESULTS_DIR", str(tmp_path / "results"))
    monkeypatch.delenv("LIBER_SPEECH_API_KEY", raising=False)
    server._FILE_STORE = None
    return TestClient(server.app)


def _upload(client: TestClient) -> str:
    response = client.post(
        "/api/v2/files",
        files={"file": ("input.wav", b"audio", "audio/wav")},
    )
    return response.json()["file_id"]


def test_asr_v2_json_and_params(client: TestClient, monkeypatch) -> None:
    captured: dict = {}

    def fake_transcribe(audio_path: str, *, language, task, model=None, **params):
        captured.update(
            {
                "audio_path": audio_path,
                "language": language,
                "task": task,
                "model": model,
                "params": params,
            }
        )
        return {
            "text": "你好",
            "chunks": [{"start": 0.0, "end": 1.0, "text": "你好"}],
            "words": [{"start": 0.0, "end": 1.0, "text": "你好"}],
            "language": "zh",
            "model": "large-v3",
        }

    monkeypatch.setattr(server.engine, "default_asr_model", lambda: "large-v3")
    monkeypatch.setattr(server.engine, "transcribe", fake_transcribe)
    file_id = _upload(client)
    response = client.post(
        "/api/v2/asr/transcribe",
        json={
            "file_id": file_id,
            "model": "large-v3",
            "language": "zh",
            "timestamps": "word",
            "vad_filter": True,
            "initial_prompt": "LiberAstra",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "你好"
    assert body["words"][0]["text"] == "你好"
    assert captured["params"]["timestamps"] == "word"
    assert captured["params"]["vad_filter"] is True
    assert captured["params"]["initial_prompt"] == "LiberAstra"
    assert body["meta"]["parameters"]["timestamps"] == "word"


def test_asr_v2_text_and_srt(client: TestClient, monkeypatch) -> None:
    def fake_transcribe(*args, **kwargs):
        return {
            "text": "你好",
            "chunks": [{"start": 0.0, "end": 1.5, "text": "你好"}],
            "words": [],
            "language": "zh",
            "model": "large-v3",
        }

    monkeypatch.setattr(server.engine, "default_asr_model", lambda: "large-v3")
    monkeypatch.setattr(server.engine, "transcribe", fake_transcribe)
    file_id = _upload(client)

    text = client.post(
        "/api/v2/asr/transcribe",
        json={"file_id": file_id, "model": "large-v3", "response_format": "text"},
    )
    assert text.status_code == 200
    assert text.headers["content-type"].startswith("text/plain")
    assert text.text == "你好"

    srt = client.post(
        "/api/v2/asr/transcribe",
        json={"file_id": file_id, "model": "large-v3", "response_format": "srt"},
    )
    assert srt.status_code == 200
    assert "00:00:00,000 --> 00:00:01,500" in srt.text


def test_asr_v2_missing_file(client: TestClient) -> None:
    response = client.post(
        "/api/v2/asr/transcribe",
        json={"file_id": "f_" + "0" * 32, "model": "large-v3"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "file_not_found"


def test_asr_v2_qwen_translate_rejected(client: TestClient) -> None:
    file_id = _upload(client)
    response = client.post(
        "/api/v2/asr/transcribe",
        json={
            "file_id": file_id,
            "model": "qwen3-asr-1.7b",
            "task": "translate",
        },
    )
    assert response.status_code == 400
    errors = response.json()["detail"]["errors"]
    assert any(item["param"] == "task" for item in errors)

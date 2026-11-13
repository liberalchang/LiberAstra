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


def _mock_engine(monkeypatch, captured: dict) -> None:
    def fake_synthesize(text: str, **kwargs):
        captured["text"] = text
        captured["kwargs"] = kwargs
        return [0.0], 24000

    monkeypatch.setattr(server.engine, "default_tts_model", lambda: "multilingual_v3")
    monkeypatch.setattr(server.engine, "synthesize", fake_synthesize)
    monkeypatch.setattr(server, "_save_wav", lambda path, sample_rate, wav: path.write_bytes(b"wav"))


def test_tts_v2_applies_params_and_postprocess(client: TestClient, monkeypatch) -> None:
    captured: dict = {}
    _mock_engine(monkeypatch, captured)
    speed_calls: list[float] = []
    norm_calls: list[float] = []
    monkeypatch.setattr(
        server.postprocess, "apply_speed", lambda path, speed: speed_calls.append(speed)
    )
    monkeypatch.setattr(
        server.postprocess,
        "apply_loudnorm",
        lambda path, target_lufs: norm_calls.append(target_lufs),
    )

    response = client.post(
        "/api/v2/tts/synthesize",
        json={
            "text": "你好",
            "model": "multilingual_v3",
            "language": "zh",
            "exaggeration": 0.7,
            "cfg_weight": 0.3,
            "speed": 0.9,
            "normalize_loudness": True,
            "target_lufs": -16,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["audio_url"].startswith("/api/v1/results/tts-")
    assert captured["text"] == "你好"
    assert captured["kwargs"]["exaggeration"] == 0.7
    assert captured["kwargs"]["cfg_weight"] == 0.3
    assert "speed" not in captured["kwargs"]
    assert "normalize_loudness" not in captured["kwargs"]
    assert speed_calls == [0.9]
    assert norm_calls == [-16.0]
    assert body["meta"]["parameters"]["speed"] == 0.9


def test_tts_v2_turbo_unsupported(client: TestClient) -> None:
    response = client.post(
        "/api/v2/tts/synthesize",
        json={"text": "hello", "model": "turbo", "exaggeration": 0.7},
    )
    assert response.status_code == 400
    errors = response.json()["detail"]["errors"]
    assert any(item["code"] == "unsupported_parameter" for item in errors)


def test_tts_v2_missing_prompt_file(client: TestClient) -> None:
    response = client.post(
        "/api/v2/tts/synthesize",
        json={
            "text": "hello",
            "model": "multilingual_v3",
            "prompt_file_id": "f_" + "0" * 32,
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "file_not_found"


def test_tts_v2_slices_prompt(client: TestClient, monkeypatch) -> None:
    captured: dict = {}
    _mock_engine(monkeypatch, captured)
    sliced: dict = {}

    def fake_slice(source, target, start, duration=None):
        sliced["start"] = start
        sliced["duration"] = duration
        target.write_bytes(b"ref")
        return target

    monkeypatch.setattr(server.postprocess, "slice_audio", fake_slice)
    upload = client.post(
        "/api/v2/files",
        files={"file": ("ref.wav", b"reference", "audio/wav")},
    )
    file_id = upload.json()["file_id"]
    response = client.post(
        "/api/v2/tts/synthesize",
        json={
            "text": "你好",
            "model": "multilingual_v3",
            "prompt_file_id": file_id,
            "ref_start": 1.0,
            "ref_duration": 2.0,
        },
    )
    assert response.status_code == 200
    assert sliced == {"start": 1.0, "duration": 2.0}
    assert captured["kwargs"]["audio_prompt"].endswith("ref.wav")

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


def _upload(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v2/files",
        files={"file": (name, b"audio", "audio/wav")},
    )
    return response.json()["file_id"]


def test_vc_v2_params_and_model_difference(client: TestClient, monkeypatch) -> None:
    captured: dict = {}

    def fake_convert(source, *, model, prompt, segments, **kwargs):
        captured.update(
            {
                "source": source,
                "model": model,
                "prompt": prompt,
                "segments": segments,
                "kwargs": kwargs,
            }
        )
        return [0.0], 24000

    monkeypatch.setattr(server.engine, "default_vc_model", lambda: "seed-vc")
    monkeypatch.setattr(server.engine, "convert", fake_convert)
    monkeypatch.setattr(
        server, "_save_audio", lambda path, audio, sample_rate: path.write_bytes(b"wav")
    )
    monkeypatch.setattr(server.postprocess, "apply_loudnorm", lambda path, target: path)
    monkeypatch.setattr(server.postprocess, "apply_resample", lambda path, rate: path)

    source_id = _upload(client, "source.wav")
    prompt_id = _upload(client, "ref.wav")
    response = client.post(
        "/api/v2/vc/convert",
        json={
            "file_id": source_id,
            "prompt_file_id": prompt_id,
            "model": "seed-vc",
            "segments": [{"start": 0.0, "end": 1.0}],
            "diffusion_steps": 20,
            "seed": 42,
            "normalize_loudness": True,
            "output_sample_rate": 16000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["audio_url"].startswith("/api/v1/results/vc-")
    assert captured["model"] == "seed-vc"
    assert captured["segments"] == [{"start": 0.0, "end": 1.0}]
    assert captured["kwargs"]["diffusion_steps"] == 20
    assert captured["kwargs"]["seed"] == 42
    assert "normalize_loudness" not in captured["kwargs"]
    assert "output_sample_rate" not in captured["kwargs"]
    assert body["meta"]["sample_rate"] == 16000


def test_vc_v2_chatterbox_rejects_seed_params(client: TestClient) -> None:
    source_id = _upload(client, "source.wav")
    prompt_id = _upload(client, "ref.wav")
    response = client.post(
        "/api/v2/vc/convert",
        json={
            "file_id": source_id,
            "prompt_file_id": prompt_id,
            "model": "chatterbox",
            "diffusion_steps": 20,
        },
    )
    assert response.status_code == 400
    errors = response.json()["detail"]["errors"]
    assert any(item["code"] == "unsupported_parameter" for item in errors)


def test_vc_v2_missing_prompt_file(client: TestClient) -> None:
    source_id = _upload(client, "source.wav")
    response = client.post(
        "/api/v2/vc/convert",
        json={
            "file_id": source_id,
            "prompt_file_id": "f_" + "0" * 32,
            "model": "seed-vc",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "file_not_found"


def test_vc_v2_convert_all_conflict(client: TestClient) -> None:
    source_id = _upload(client, "source.wav")
    prompt_id = _upload(client, "ref.wav")
    response = client.post(
        "/api/v2/vc/convert",
        json={
            "file_id": source_id,
            "prompt_file_id": prompt_id,
            "model": "seed-vc",
            "convert_all": True,
            "segments": [{"start": 0.0, "end": 1.0}],
        },
    )
    assert response.status_code == 400
    errors = response.json()["detail"]["errors"]
    assert any(item["code"] == "conflict_parameter" for item in errors)

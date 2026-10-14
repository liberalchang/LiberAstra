"""TTS / ASR 任务、音色库与 OpenAI 兼容 /v1/audio/* 集成测试。"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from liberastra.providers.base import ASRResult, ASRSegment


@pytest.fixture()
def tts_provider(client: TestClient, auth_header: dict[str, str]) -> int:
    resp = client.post(
        "/api/v1/providers",
        json={"name": "mock-tts", "type": "openai_tts", "base_url": "http://mock/v1"},
        headers=auth_header,
    )
    assert resp.status_code == 201
    return resp.json()["id"]  # noqa: RET504


@pytest.fixture()
def asr_provider(client: TestClient, auth_header: dict[str, str]) -> int:
    resp = client.post(
        "/api/v1/providers",
        json={"name": "mock-asr", "type": "openai_stt", "base_url": "http://mock/v1"},
        headers=auth_header,
    )
    assert resp.status_code == 201
    return resp.json()["id"]  # noqa: RET504


class _FakeTTS:
    async def synthesize(self, *, text: str, voice: str, **kwargs) -> bytes:
        await asyncio.sleep(0)
        return f"AUDIO:{voice}:{text}".encode()


class _FakeASR:
    async def transcribe(self, *, file_path: str, **kwargs) -> ASRResult:
        await asyncio.sleep(0)
        return ASRResult(
            text="你好世界",
            segments=[ASRSegment(0.0, 1.0, "你好"), ASRSegment(1.0, 2.0, "世界")],
            language="zh",
        )


def test_tts_job_and_asset(
    client: TestClient,
    auth_header: dict[str, str],
    tts_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.services import tts as tts_service

    monkeypatch.setattr(tts_service, "build_tts_adapter", lambda record: _FakeTTS())

    resp = client.post(
        "/api/v1/tts?wait=true",
        json={"provider_id": tts_provider, "voice": "af_heart", "text": "你好", "format": "mp3"},
        headers=auth_header,
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    output = job["outputs"][0]
    assert output["type"] == "asset"

    content = client.get(f"/api/v1/assets/{output['asset_id']}/content", headers=auth_header)
    assert content.status_code == 200
    assert content.content == "AUDIO:af_heart:你好".encode()

    assets = client.get("/api/v1/assets?kind=audio", headers=auth_header).json()
    assert any(a["id"] == output["asset_id"] for a in assets)


def test_asr_job_subtitle_export(
    client: TestClient,
    auth_header: dict[str, str],
    asr_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.services import asr as asr_service

    monkeypatch.setattr(asr_service, "build_asr_adapter", lambda record: _FakeASR())

    resp = client.post(
        "/api/v1/asr?wait=true",
        files={"file": ("a.wav", b"RIFFfake-audio", "audio/wav")},
        data={"provider_id": str(asr_provider), "language": "zh", "formats": "srt"},
        headers=auth_header,
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    assert job["outputs"][0]["content"] == "你好世界"

    # 单文件输出：一个任务只产出一个资产，按所选格式
    asset_outputs = [o for o in job["outputs"] if o["type"] == "asset"]
    assert len(asset_outputs) == 1
    assert asset_outputs[0]["format"] == "srt"
    assert asset_outputs[0]["kind"] == "subtitle"

    srt_output = asset_outputs[0]
    content = client.get(f"/api/v1/assets/{srt_output['asset_id']}/content", headers=auth_header)
    assert content.status_code == 200
    assert "00:00:00,000 --> 00:00:01,000" in content.text
    assert "世界" in content.text


def test_asr_job_format_priority(
    client: TestClient,
    auth_header: dict[str, str],
    asr_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """自动模式（默认 formats）按优先级 txt → json → srt → vtt 取第一个可用格式。"""
    from liberastra.services import asr as asr_service

    monkeypatch.setattr(asr_service, "build_asr_adapter", lambda record: _FakeASR())

    resp = client.post(
        "/api/v1/asr?wait=true",
        files={"file": ("a.wav", b"RIFFfake-audio", "audio/wav")},
        data={"provider_id": str(asr_provider)},
        headers=auth_header,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    asset_outputs = [o for o in job["outputs"] if o["type"] == "asset"]
    assert len(asset_outputs) == 1
    assert asset_outputs[0]["format"] == "txt"
    assert asset_outputs[0]["kind"] == "text"


def test_openai_compat_speech(
    client: TestClient,
    auth_header: dict[str, str],
    tts_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.api.routes import openai_audio

    monkeypatch.setattr(openai_audio, "build_tts_adapter", lambda record: _FakeTTS())

    resp = client.post(
        "/v1/audio/speech",
        json={"model": "tts-1", "input": "你好", "voice": "alloy", "response_format": "mp3"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == "AUDIO:alloy:你好".encode()


def test_openai_compat_transcriptions(
    client: TestClient,
    auth_header: dict[str, str],
    asr_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.api.routes import openai_audio

    monkeypatch.setattr(openai_audio, "build_asr_adapter", lambda record: _FakeASR())

    resp = client.post(
        "/v1/audio/transcriptions",
        files={"file": ("a.wav", b"RIFFfake", "audio/wav")},
        data={"model": "whisper-1", "response_format": "srt"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert "-->" in resp.text


def test_voice_library_crud(client: TestClient, auth_header: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/voices",
        files={"file": ("ref.wav", b"RIFFreference", "audio/wav")},
        data={"name": "我的音色", "ref_text": "参考文本", "tags": "男声,中文"},
        headers=auth_header,
    )
    assert created.status_code == 201
    voice = created.json()
    assert voice["tags"] == ["男声", "中文"]
    assert voice["ref_audio_path"].startswith("voices/")

    assert client.post(f"/api/v1/voices/{voice['id']}/default", headers=auth_header).json()[
        "is_default"
    ] is True

    listing = client.get("/api/v1/voices", headers=auth_header).json()
    assert any(v["id"] == voice["id"] for v in listing)

    assert client.delete(f"/api/v1/voices/{voice['id']}", headers=auth_header).status_code == 204


def test_tts_with_voice_record(
    client: TestClient,
    auth_header: dict[str, str],
    tts_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.services import tts as tts_service

    monkeypatch.setattr(tts_service, "build_tts_adapter", lambda record: _FakeTTS())

    voice = client.post(
        "/api/v1/voices",
        data={"name": "af_heart", "voice_id": "cloud-voice-42"},
        headers=auth_header,
    ).json()
    resp = client.post(
        "/api/v1/tts?wait=true",
        json={"provider_id": tts_provider, "voice_record_id": voice["id"], "text": "测试"},
        headers=auth_header,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    # 音色库的 voice_id 优先于名称传给 Provider
    assert job["params"]["voice"] == "cloud-voice-42"

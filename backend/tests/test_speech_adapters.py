"""字幕导出与 TTS/ASR 适配器契约测试（MockTransport）。"""

import asyncio

import httpx

from liberastra.media.subtitles import to_json, to_srt, to_txt, to_vtt
from liberastra.providers.asr.openai_stt import OpenAISTT
from liberastra.providers.base import ASRResult, ASRSegment, ProviderError
from liberastra.providers.speech.liber_speech import LiberSpeech, language_from_voice
from liberastra.providers.tts.openai_tts import OpenAITTS

RESULT = ASRResult(
    text="你好世界",
    segments=[ASRSegment(0.0, 1.5, "你好"), ASRSegment(1.5, 3.0, "世界")],
    language="zh",
)


def test_subtitle_exporters() -> None:
    assert to_txt(RESULT) == "你好世界\n"

    srt = to_srt(RESULT)
    assert "1\n00:00:00,000 --> 00:00:01,500\n你好" in srt
    assert "00:00:01,500 --> 00:00:03,000\n世界" in srt

    vtt = to_vtt(RESULT)
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.500 --> 00:00:03.000" in vtt

    import json

    data = json.loads(to_json(RESULT))
    assert data["segments"][1]["text"] == "世界"
    assert data["language"] == "zh"


def test_openai_tts_adapter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/audio/speech":
            assert request.headers["Authorization"] == "Bearer k"
            return httpx.Response(200, content=b"audio-bytes")
        if request.url.path == "/v1/audio/voices":
            return httpx.Response(200, json={"voices": ["af_heart", "am_adam"]})
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OpenAITTS("http://mock/v1", "k", client=client)
            audio = await adapter.synthesize(text="你好", voice="af_heart", fmt="mp3")
            assert audio == b"audio-bytes"
            assert await adapter.list_voices() == ["af_heart", "am_adam"]
            assert "2 个" in await adapter.test()

    asyncio.run(run())


def test_openai_tts_error_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OpenAITTS("http://mock/v1", client=client)
            try:
                await adapter.synthesize(text="x", voice="v")
            except ProviderError as exc:
                assert "500" in str(exc)
            else:
                raise AssertionError("应抛出 ProviderError")

    asyncio.run(run())


def test_openai_stt_adapter(tmp_path) -> None:  # noqa: ANN001
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/audio/transcriptions":
            return httpx.Response(
                200,
                json={
                    "text": "你好世界",
                    "language": "zh",
                    "segments": [
                        {"start": 0.0, "end": 1.0, "text": "你好"},
                        {"start": 1.0, "end": 2.0, "text": "世界"},
                    ],
                },
            )
        return httpx.Response(404)

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFfake")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OpenAISTT("http://mock/v1", client=client)
            result = await adapter.transcribe(file_path=str(audio), language="zh")
            assert result.text == "你好世界"
            assert len(result.segments) == 2
            assert result.segments[1].end == 2.0
            assert result.language == "zh"

    asyncio.run(run())


def test_language_from_voice() -> None:
    assert language_from_voice("zh") == "zh"
    assert language_from_voice("zh-CN-XiaoxiaoNeural") == "zh"
    assert language_from_voice("alloy", "en-US") == "en"


def test_liber_speech_tts_and_asr(tmp_path) -> None:  # noqa: ANN001
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/health":
            return httpx.Response(200, json={"status": "ok", "asr_ready": False, "tts_ready": True})
        if request.url.path == "/api/v1/tts/synthesize":
            assert request.headers["Authorization"] == "Bearer speech-key"
            return httpx.Response(200, json={"audio_url": "/api/v1/results/a.wav", "meta": {}})
        if request.url.path == "/api/v1/results/a.wav":
            return httpx.Response(200, content=b"wav-bytes")
        if request.url.path == "/api/v1/asr/transcribe":
            return httpx.Response(
                200,
                json={
                    "text": "你好世界",
                    "chunks": [{"start": 0.0, "end": 1.2, "text": "你好"}],
                    "meta": {"language": "zh"},
                },
            )
        return httpx.Response(404, text=request.url.path)

    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFFfake")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = LiberSpeech("http://speech:5555", "speech-key", client=client)
            assert "TTS 已加载" in await adapter.test()
            assert await adapter.synthesize(text="你好", voice="zh", fmt="wav") == b"wav-bytes"
            result = await adapter.transcribe(file_path=str(audio), language="zh")
            assert result.text == "你好世界"
            assert result.segments[0].end == 1.2

    asyncio.run(run())

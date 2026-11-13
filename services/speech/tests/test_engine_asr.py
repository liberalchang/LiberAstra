from __future__ import annotations

import engine
import pytest


def test_whisper_kwargs_timestamps_and_filters() -> None:
    kwargs = engine._whisper_kwargs(
        {
            "timestamps": "word",
            "beam_size": 3,
            "vad_filter": True,
            "initial_prompt": "LiberAstra",
            "hotwords": "Chatterbox",
            "max_new_tokens": 128,
        }
    )
    assert kwargs["word_timestamps"] is True
    assert kwargs["beam_size"] == 3
    assert kwargs["vad_filter"] is True
    assert kwargs["initial_prompt"] == "LiberAstra"
    assert kwargs["max_new_tokens"] == 128
    assert "timestamps" not in kwargs
    assert "response_format" not in kwargs


def test_whisper_kwargs_none_timestamps() -> None:
    kwargs = engine._whisper_kwargs({"timestamps": "none"})
    assert kwargs["without_timestamps"] is True


def test_whisper_kwargs_rejects_unknown_and_bad_timestamps() -> None:
    with pytest.raises(ValueError, match="timestamps"):
        engine._whisper_kwargs({"timestamps": "words"})
    with pytest.raises(ValueError, match="不支持参数"):
        engine._whisper_kwargs({"not_a_param": 1})


def test_qwen_kwargs() -> None:
    kwargs = engine._qwen_kwargs(
        {"timestamps": "word", "max_new_tokens": 1024, "max_inference_batch_size": 8}
    )
    assert kwargs == {
        "timestamps": "word",
        "return_time_stamps": True,
        "max_new_tokens": 1024,
        "max_inference_batch_size": 8,
    }
    assert engine._qwen_kwargs({"timestamps": "none"})["return_time_stamps"] is False


def test_qwen_kwargs_rejects_whisper_only_params() -> None:
    with pytest.raises(ValueError, match="Qwen3-ASR 不支持参数"):
        engine._qwen_kwargs({"vad_filter": True})


def test_transcribe_dispatches_params(monkeypatch) -> None:
    calls: dict[str, tuple] = {}

    def fake_whisper(*args):
        calls["whisper"] = args
        return {"text": "", "chunks": [], "words": []}

    def fake_qwen(*args):
        calls["qwen"] = args
        return {"text": "", "chunks": [], "words": []}

    monkeypatch.setattr(engine, "_transcribe_whisper", fake_whisper)
    monkeypatch.setattr(engine, "_transcribe_qwen", fake_qwen)
    monkeypatch.setattr(engine, "_drop_tts", lambda: None)
    monkeypatch.setattr(engine, "_drop_asr", lambda: None)

    engine.transcribe(
        "a.wav",
        language="zh",
        task="transcribe",
        model="large-v3",
        timestamps="word",
        beam_size=3,
    )
    assert calls["whisper"][0] == "a.wav"
    assert calls["whisper"][4]["timestamps"] == "word"
    assert calls["whisper"][4]["beam_size"] == 3

    engine.transcribe(
        "a.wav",
        language="zh",
        task="transcribe",
        model="qwen3-asr-1.7b",
        timestamps="word",
    )
    assert calls["qwen"][3]["timestamps"] == "word"

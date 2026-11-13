from __future__ import annotations

import engine
import pytest


class FakeTTS:
    sr = 24000

    def __init__(self) -> None:
        self.text: str | None = None
        self.kwargs: dict = {}

    def generate(self, text: str, **kwargs):
        self.text = text
        self.kwargs = kwargs
        return [0.0]


def _install(monkeypatch) -> FakeTTS:
    fake = FakeTTS()
    monkeypatch.setattr(engine, "_load_tts", lambda model_id: fake)
    monkeypatch.setattr(engine, "_drop_tts", lambda: None)
    monkeypatch.setattr(engine, "_drop_asr", lambda: None)
    return fake


def test_multilingual_parameters(monkeypatch) -> None:
    fake = _install(monkeypatch)
    wav, sample_rate = engine.synthesize(
        "你好",
        model="multilingual_v3",
        language="zh",
        audio_prompt=None,
        exaggeration=0.7,
        cfg_weight=0.3,
        temperature=0.8,
        repetition_penalty=1.2,
        min_p=0.05,
        top_p=0.9,
    )
    assert wav == [0.0]
    assert sample_rate == 24000
    assert fake.text == "你好"
    assert fake.kwargs == {
        "audio_prompt_path": None,
        "language_id": "zh",
        "exaggeration": 0.7,
        "cfg_weight": 0.3,
        "temperature": 0.8,
        "repetition_penalty": 1.2,
        "min_p": 0.05,
        "top_p": 0.9,
    }


def test_turbo_parameters(monkeypatch) -> None:
    fake = _install(monkeypatch)
    engine.synthesize(
        "hello",
        model="turbo",
        language="en",
        audio_prompt=None,
        temperature=0.7,
        top_p=0.9,
        top_k=500,
        norm_loudness=False,
    )
    assert "language_id" not in fake.kwargs
    assert fake.kwargs["top_k"] == 500
    assert fake.kwargs["norm_loudness"] is False
    assert "exaggeration" not in fake.kwargs


def test_standard_has_no_language_id(monkeypatch) -> None:
    fake = _install(monkeypatch)
    engine.synthesize(
        "hello",
        model="standard",
        language="en",
        audio_prompt=None,
        exaggeration=0.4,
    )
    assert "language_id" not in fake.kwargs
    assert fake.kwargs["exaggeration"] == 0.4


def test_unsupported_parameters_are_rejected(monkeypatch) -> None:
    _install(monkeypatch)
    with pytest.raises(ValueError, match="exaggeration"):
        engine.synthesize(
            "hello",
            model="turbo",
            language="en",
            audio_prompt=None,
            exaggeration=0.5,
        )
    with pytest.raises(ValueError, match="top_k"):
        engine.synthesize(
            "你好",
            model="multilingual_v3",
            language="zh",
            audio_prompt=None,
            top_k=100,
        )

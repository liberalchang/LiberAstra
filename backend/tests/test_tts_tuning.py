from __future__ import annotations

from liberastra.services.tts_tuning import (
    supports_emotion_model,
    tts_options,
    tuning_at,
)


def test_advanced_off_returns_no_options() -> None:
    assert tts_options({"advanced": False}, True) == {}


def test_linked_presets() -> None:
    assert tuning_at(0) == {"speed": 0.9, "exaggeration": 0.35, "cfg_weight": 0.55}
    assert tuning_at(1) == {"speed": 1.15, "exaggeration": 0.9, "cfg_weight": 0.35}
    middle = tuning_at(0.5)
    assert 1.0 < middle["speed"] < 1.05
    assert 0.5 < middle["exaggeration"] < 0.65


def test_linked_and_independent_options() -> None:
    linked = tts_options(
        {"advanced": True, "linked": True, "expressiveness": 1},
        True,
    )
    assert linked == {"speed": 1.15, "exaggeration": 0.9, "cfg_weight": 0.35}

    independent = tts_options(
        {
            "advanced": True,
            "linked": False,
            "speed": 0.9,
            "exaggeration": 0.7,
            "cfgWeight": 0.3,
        },
        True,
    )
    assert independent == {"speed": 0.9, "exaggeration": 0.7, "cfg_weight": 0.3}


def test_turbo_only_speed() -> None:
    options = tts_options(
        {"advanced": True, "linked": True, "expressiveness": 1, "speed": 0.9},
        supports_emotion_model("turbo"),
    )
    assert options == {"speed": 0.9}
    assert supports_emotion_model("turbo") is False
    assert supports_emotion_model("nano") is False
    assert supports_emotion_model("multilingual_v3") is True

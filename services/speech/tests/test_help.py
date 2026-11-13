from __future__ import annotations

import help_api
import pytest


def test_build_all() -> None:
    payload = help_api.build_help()
    assert payload["schema_version"] == "1.0"
    assert set(payload["functions"]) == {"tts", "asr", "vc"}
    assert payload["service_limits"]["unlimited"] is True
    assert "error_codes" in payload
    assert "runtime_versions" in payload


def test_function_help() -> None:
    payload = help_api.build_help("tts")
    common = {p["name"] for p in payload["common_parameters"]}
    assert "speed" in common
    assert "normalize_loudness" in common
    assert "exaggeration" not in common
    models = {m["id"] for m in payload["models"]}
    assert {"multilingual_v3", "turbo", "nano"} <= models
    assert payload["endpoint"]["path"] == "/api/v2/tts/synthesize"


def test_model_help_tts_turbo() -> None:
    payload = help_api.build_help("tts", "turbo")
    names = {p["name"] for p in payload["parameters"]}
    assert "top_k" in names
    assert "norm_loudness" in names
    assert "exaggeration" not in names
    unsupported = {item["name"] for item in payload["unsupported_parameters"]}
    assert "exaggeration" in unsupported
    assert payload["examples"]["body"]["model"] == "turbo"
    assert payload["model_limits"] == {}


def test_model_help_asr_qwen() -> None:
    payload = help_api.build_help("asr", "qwen3-asr-1.7b")
    names = {p["name"] for p in payload["parameters"]}
    assert "max_new_tokens" in names
    assert "max_inference_batch_size" in names
    assert "vad_filter" not in names
    unsupported = {item["name"] for item in payload["unsupported_parameters"]}
    assert "vad_filter" in unsupported
    assert payload["model_limits"]["max_new_tokens"] == 512
    assert payload["model_limits"]["max_inference_batch_size"] == 4


def test_model_help_vc_chatterbox() -> None:
    payload = help_api.build_help("vc", "chatterbox")
    unsupported = {item["name"] for item in payload["unsupported_parameters"]}
    assert "diffusion_steps" in unsupported
    assert payload["model_limits"]["ref_audio_seconds"] == 10
    assert payload["service_limits"]["max_media_seconds"] == 0


def test_include_filter() -> None:
    payload = help_api.build_help("tts", "multilingual_v3", include="model")
    names = {p["name"] for p in payload["parameters"]}
    assert "exaggeration" in names
    assert "speed" not in names
    assert "unsupported_parameters" not in payload
    assert "examples" not in payload
    assert "error_codes" not in payload


def test_unknown_function_model_and_include() -> None:
    with pytest.raises(ValueError):
        help_api.build_help("nope")
    with pytest.raises(ValueError):
        help_api.build_help("tts", "nope")
    with pytest.raises(ValueError):
        help_api.build_help("tts", include="nope")
    with pytest.raises(ValueError):
        help_api.build_help(model="turbo")


def test_markdown() -> None:
    text = help_api.render_markdown(help_api.build_help("asr", "large-v3"))
    assert "# asr / large-v3" in text
    assert "beam_size" in text
    assert "vad_filter" in text

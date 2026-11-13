from __future__ import annotations

import math

import pytest
import validation


def _codes(exc: validation.ParamValidationError) -> list[str]:
    return [issue.code for issue in exc.issues]


def test_tts_defaults_are_applied() -> None:
    got = validation.validate("tts", "multilingual_v3", {"text": "你好"})
    assert got.values["text"] == "你好"
    assert got.values["format"] == "wav"
    assert got.values["speed"] == 1.0
    assert got.values["exaggeration"] == 0.5
    assert got.values["cfg_weight"] == 0.5
    assert got.values["top_p"] == 1.0
    assert got.values["strict"] is True


def test_turbo_defaults_and_unsupported_parameter() -> None:
    got = validation.validate("tts", "turbo", {"text": "hello"})
    assert got.values["top_p"] == 0.95
    assert got.values["top_k"] == 1000
    assert "exaggeration" not in got.values

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate("tts", "turbo", {"text": "hello", "exaggeration": 0.7})
    assert "unsupported_parameter" in _codes(info.value)
    assert info.value.help_url == "/api/v2/help/tts/turbo"


def test_unknown_parameter_strict_and_non_strict() -> None:
    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate("tts", "multilingual_v3", {"text": "你好", "foo": 1})
    assert "unknown_parameter" in _codes(info.value)

    got = validation.validate(
        "tts", "multilingual_v3", {"text": "你好", "foo": 1}, strict=False
    )
    assert "foo" not in got.values
    assert any("foo" in warning for warning in got.warnings)


def test_type_range_and_enum_errors() -> None:
    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate("tts", "multilingual_v3", {"text": "你好", "speed": "abc"})
    assert "invalid_type" in _codes(info.value)

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate("tts", "multilingual_v3", {"text": "你好", "speed": 3})
    assert "out_of_range" in _codes(info.value)

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate("tts", "multilingual_v3", {"text": "你好", "format": "mp4"})
    assert "invalid_enum" in _codes(info.value)

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate("tts", "multilingual_v3", {"text": "你好", "speed": math.nan})
    assert "invalid_type" in _codes(info.value)


def test_required_parameter() -> None:
    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate("tts", "multilingual_v3", {})
    assert "missing_parameter" in _codes(info.value)


def test_asr_defaults_and_model_differences() -> None:
    got = validation.validate("asr", "large-v3", {"file_id": "f_input"})
    assert got.values["beam_size"] == 5
    assert got.values["vad_filter"] is False
    assert got.values["timestamps"] == "segment"
    assert "max_inference_batch_size" not in got.values

    got = validation.validate("asr", "qwen3-asr-1.7b", {"file_id": "f_input"})
    assert got.values["max_new_tokens"] == 512
    assert got.values["max_inference_batch_size"] == 4
    assert "vad_filter" not in got.values

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "asr", "qwen3-asr-1.7b", {"file_id": "f_input", "task": "translate"}
        )
    assert "invalid_value" in _codes(info.value)

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "asr", "qwen3-asr-1.7b", {"file_id": "f_input", "vad_filter": True}
        )
    assert "unsupported_parameter" in _codes(info.value)


def test_asr_cross_field_rules() -> None:
    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "asr",
            "large-v3",
            {"file_id": "f_input", "hotwords": "LiberAstra", "prefix": "前文"},
        )
    assert "conflict_parameter" in _codes(info.value)

    got = validation.validate(
        "asr",
        "large-v3",
        {"file_id": "f_input", "vad_parameters": {"threshold": 0.5}},
    )
    assert any("vad_filter" in warning for warning in got.warnings)

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "asr",
            "large-v3",
            {"file_id": "f_input", "vad_parameters": {"unknown_key": 1}},
        )
    assert "unknown_parameter" in _codes(info.value)


def test_asr_bool_and_timestamps_coercion() -> None:
    got = validation.validate(
        "asr",
        "large-v3",
        {"file_id": "f_input", "vad_filter": "true", "timestamps": "word"},
    )
    assert got.values["vad_filter"] is True
    assert got.values["timestamps"] == "word"

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "asr", "large-v3", {"file_id": "f_input", "timestamps": "words"}
        )
    assert "invalid_enum" in _codes(info.value)


def test_vc_defaults_and_model_differences() -> None:
    got = validation.validate("vc", "seed-vc", {"file_id": "f_in", "prompt_file_id": "f_ref"})
    assert got.values["diffusion_steps"] == 10
    assert got.values["inference_cfg_rate"] == 0.7
    assert got.values["n_quantizers"] == 3
    assert got.values["max_window"] == 20
    assert "seed" not in got.values

    got = validation.validate(
        "vc", "chatterbox", {"file_id": "f_in", "prompt_file_id": "f_ref"}
    )
    assert "diffusion_steps" not in got.values
    assert "seed" not in got.values

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "vc",
            "chatterbox",
            {"file_id": "f_in", "prompt_file_id": "f_ref", "diffusion_steps": 20},
        )
    assert "unsupported_parameter" in _codes(info.value)


def test_vc_segments_and_cross_field_rules() -> None:
    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "vc",
            "seed-vc",
            {
                "file_id": "f_in",
                "prompt_file_id": "f_ref",
                "convert_all": True,
                "segments": [{"start": 0, "end": 1}],
            },
        )
    assert "conflict_parameter" in _codes(info.value)

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "vc",
            "seed-vc",
            {
                "file_id": "f_in",
                "prompt_file_id": "f_ref",
                "segments": [{"start": 2, "end": 1}],
            },
        )
    assert "invalid_value" in _codes(info.value)

    got = validation.validate(
        "vc",
        "seed-vc",
        {
            "file_id": "f_in",
            "prompt_file_id": "f_ref",
            "segments": [{"start": 0, "end": 1.5}],
        },
    )
    assert got.values["segments"] == [{"start": 0.0, "end": 1.5}]


def test_vc_ref_duration_clamp_and_length_warning() -> None:
    got = validation.validate(
        "vc",
        "seed-vc",
        {"file_id": "f_in", "prompt_file_id": "f_ref", "ref_duration": 999},
    )
    assert got.values["ref_duration"] == 25.0
    assert any("ref_duration" in warning for warning in got.warnings)

    got = validation.validate(
        "vc",
        "chatterbox",
        {"file_id": "f_in", "prompt_file_id": "f_ref", "ref_duration": 999},
    )
    assert got.values["ref_duration"] == 10.0

    got = validation.validate(
        "vc",
        "seed-vc",
        {"file_id": "f_in", "prompt_file_id": "f_ref", "length_adjust": 1.1},
    )
    assert any("length_adjust" in warning for warning in got.warnings)


def test_vc_output_sample_rate() -> None:
    got = validation.validate(
        "vc",
        "seed-vc",
        {"file_id": "f_in", "prompt_file_id": "f_ref", "output_sample_rate": 44100},
    )
    assert got.values["output_sample_rate"] == 44100

    with pytest.raises(validation.ParamValidationError) as info:
        validation.validate(
            "vc",
            "seed-vc",
            {"file_id": "f_in", "prompt_file_id": "f_ref", "output_sample_rate": 100},
        )
    assert "out_of_range" in _codes(info.value)

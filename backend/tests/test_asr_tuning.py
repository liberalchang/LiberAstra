"""ASR 高级参数映射测试。"""

from __future__ import annotations

from liberastra.services.asr_tuning import asr_options


def test_advanced_off_sends_nothing() -> None:
    tuning = {"advanced": False, "timestamps": "word", "vad": True}
    assert asr_options(tuning, "large-v3") == {}


def test_whisper_maps_timestamps_vad_and_decoding() -> None:
    tuning = {
        "advanced": True,
        "timestamps": "word",
        "vad": True,
        "task": "translate",
        "beamSize": 8,
        "bestOf": 6,
        "temperature": "0, 0.2, 0.4",
        "noSpeechThreshold": 0.4,
        "compressionRatioThreshold": 2.2,
        "conditionOnPreviousText": False,
        "initialPrompt": "人名：张三",
        "hotwords": "LiberAstra 语音",
    }
    options = asr_options(tuning, "large-v3-turbo")
    assert options["timestamps"] == "word"
    assert options["vad_filter"] is True
    assert options["task"] == "translate"
    assert options["beam_size"] == 8
    assert options["best_of"] == 6
    assert options["temperature"] == [0.0, 0.2, 0.4]
    assert options["no_speech_threshold"] == 0.4
    assert options["compression_ratio_threshold"] == 2.2
    assert options["condition_on_previous_text"] is False
    assert options["initial_prompt"] == "人名：张三"
    assert options["hotwords"] == "LiberAstra 语音"


def test_qwen_skips_whisper_only_params_and_keeps_batch() -> None:
    tuning = {
        "advanced": True,
        "timestamps": "segment",
        "task": "translate",
        "vad": True,
        "beamSize": 8,
        "bestOf": 6,
        "initialPrompt": "术语",
        "hotwords": "热词",
        "qwenBatchSize": 8,
    }
    options = asr_options(tuning, "qwen3-asr-1.7b")
    assert options == {
        "timestamps": "segment",
        "max_inference_batch_size": 8,
    }


def test_blank_model_defaults_to_whisper_rules() -> None:
    tuning = {"advanced": True, "vad": True, "hotwords": "专有名词"}
    options = asr_options(tuning, "")
    assert options["vad_filter"] is True
    assert options["hotwords"] == "专有名词"


def test_extra_json_merges_and_overrides() -> None:
    tuning = {
        "advanced": True,
        "beamSize": 5,
        "extraJson": '{"beam_size": 9, "suppress_blank": false}',
    }
    options = asr_options(tuning, "large-v3")
    assert options["beam_size"] == 9
    assert options["suppress_blank"] is False


def test_extra_json_invalid_is_ignored() -> None:
    options = asr_options({"advanced": True, "extraJson": "{oops"}, "large-v3")
    assert "beam_size" not in options


def test_values_are_clamped() -> None:
    tuning = {
        "advanced": True,
        "beamSize": 999,
        "noSpeechThreshold": 5,
        "qwenBatchSize": 0,
    }
    options = asr_options(tuning, "large-v3")
    assert options["beam_size"] == 10
    assert options["no_speech_threshold"] == 1.0
    assert asr_options(tuning, "qwen3-asr-1.7b")["max_inference_batch_size"] == 1

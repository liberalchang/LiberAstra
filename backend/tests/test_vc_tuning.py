"""VC 高级参数映射测试。"""

from __future__ import annotations

from liberastra.services.vc_tuning import vc_options


def test_advanced_off_sends_nothing() -> None:
    assert vc_options({"advanced": False, "denoise": True}, "seed-vc") == {}


def test_chatterbox_common_postprocess_and_segments() -> None:
    tuning = {
        "advanced": True,
        "convertAll": True,
        "segmentPadding": 0.2,
        "mergeGap": 0.1,
        "minSegment": 0.05,
        "normalizeLoudness": True,
        "targetLufs": -18,
        "denoise": True,
        "outputSampleRate": 44100,
        "refStart": 1.5,
        "refDuration": 8,
        "seed": 42,
        "diffusionSteps": 20,
    }
    options = vc_options(tuning, "chatterbox")
    assert options == {
        "convert_all": True,
        "segment_padding": 0.2,
        "merge_gap": 0.1,
        "min_segment": 0.05,
        "normalize_loudness": True,
        "target_lufs": -18.0,
        "denoise": True,
        "output_sample_rate": 44100,
        "ref_start": 1.5,
        "ref_duration": 8.0,
    }


def test_seedvc_adds_generation_params() -> None:
    tuning = {
        "advanced": True,
        "seed": 42,
        "refMaxLen": 20,
        "diffusionSteps": 20,
        "inferenceCfgRate": 0.8,
        "nQuantizers": 4,
        "temperature": 1.1,
        "lengthAdjust": 1.02,
        "overlapFrameLen": 24,
        "maxWindow": 18,
        "context": 0.2,
        "fade": 0.03,
    }
    options = vc_options(tuning, "seed-vc")
    assert options["seed"] == 42
    assert options["ref_max_len"] == 20.0
    assert options["diffusion_steps"] == 20
    assert options["inference_cfg_rate"] == 0.8
    assert options["n_quantizers"] == 4
    assert options["temperature"] == 1.1
    assert options["length_adjust"] == 1.02
    assert options["overlap_frame_len"] == 24
    assert options["max_window"] == 18.0
    assert options["context"] == 0.2
    assert options["fade"] == 0.03


def test_seedvc_only_fields_are_skipped_for_chatterbox() -> None:
    tuning = {"advanced": True, "seed": 1, "diffusionSteps": 12, "refMaxLen": 20}
    assert vc_options(tuning, "chatterbox") == {}


def test_loudness_target_only_when_enabled() -> None:
    options = vc_options({"advanced": True, "targetLufs": -20}, "chatterbox")
    assert "target_lufs" not in options


def test_zero_sample_rate_is_omitted() -> None:
    options = vc_options({"advanced": True, "outputSampleRate": 0}, "chatterbox")
    assert "output_sample_rate" not in options


def test_extra_json_merges_and_overrides() -> None:
    tuning = {
        "advanced": True,
        "denoise": False,
        "extraJson": '{"denoise": true, "max_window": 12}',
    }
    options = vc_options(tuning, "seed-vc")
    assert options["denoise"] is True
    assert options["max_window"] == 12


def test_values_are_clamped() -> None:
    tuning = {
        "advanced": True,
        "diffusionSteps": 999,
        "inferenceCfgRate": -1,
        "outputSampleRate": 999999,
    }
    options = vc_options(tuning, "seed-vc")
    assert options["diffusion_steps"] == 50
    assert options["inference_cfg_rate"] == 0.0
    assert options["output_sample_rate"] == 192000

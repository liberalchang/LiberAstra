from __future__ import annotations

import math

import params
import pytest


def test_function_names() -> None:
    assert set(params.FUNCTIONS) == {"tts", "asr", "vc"}


@pytest.mark.parametrize("function", ["tts", "asr", "vc"])
def test_models_and_parameter_invariants(function: str) -> None:
    spec = params.get_function(function)
    assert spec.models
    assert len(spec.params) == len({p.name for p in spec.params})

    for model in spec.models:
        merged = params.merged_params(function, model)
        names = [p.name for p in merged]
        assert len(names) == len(set(names)), f"{function}/{model} 参数重复"

        for p in merged:
            default = params.effective_default(function, model, p.name)
            if default is None:
                continue
            if p.type in {"int", "float"}:
                assert not isinstance(default, bool) or p.type == "bool"
                assert not isinstance(default, float) or math.isfinite(default)
                if p.min is not None:
                    assert default >= p.min, f"{function}/{model}/{p.name} 默认值小于 min"
                if p.max is not None:
                    assert default <= p.max, f"{function}/{model}/{p.name} 默认值大于 max"
            if p.type == "enum":
                assert p.enum is not None
                assert default in p.enum, f"{function}/{model}/{p.name} 默认值不在枚举内"

        model_spec = spec.models[model]
        for name in model_spec.defaults:
            assert name in names, f"{function}/{model} 覆盖了不存在的参数 {name}"
        for name, reason in model_spec.unsupported.items():
            assert reason.strip(), f"{function}/{model}/{name} 缺少不支持原因"
            assert name not in names, f"{function}/{model}/{name} 同时被声明支持和不支持"


def test_tts_model_differences() -> None:
    assert set(params.model_ids("tts")) == {
        "multilingual_v3",
        "multilingual_v2",
        "standard",
        "turbo",
        "nano",
        "zh-cmn",
        "es-mx",
        "pt-br",
        "es-es",
        "pt-pt",
        "hi",
    }
    multi = {p.name for p in params.merged_params("tts", "multilingual_v3")}
    turbo = {p.name for p in params.merged_params("tts", "turbo")}
    assert {"exaggeration", "cfg_weight", "min_p"} <= multi
    assert {"exaggeration", "cfg_weight", "min_p"}.isdisjoint(turbo)
    assert {"top_k", "norm_loudness"} <= turbo
    assert "top_k" not in multi
    assert params.effective_default("tts", "multilingual_v3", "top_p") == 1.0
    assert params.effective_default("tts", "turbo", "top_p") == 0.95


def test_asr_model_differences() -> None:
    assert set(params.model_ids("asr")) == {
        "large-v3",
        "large-v3-turbo",
        "qwen3-asr-1.7b",
    }
    whisper = {p.name for p in params.merged_params("asr", "large-v3")}
    qwen = {p.name for p in params.merged_params("asr", "qwen3-asr-1.7b")}
    assert {"vad_filter", "beam_size", "initial_prompt", "hotwords"} <= whisper
    assert {"vad_filter", "beam_size", "initial_prompt", "hotwords"}.isdisjoint(qwen)
    assert "max_inference_batch_size" in qwen
    assert "max_inference_batch_size" not in whisper
    assert params.effective_default("asr", "qwen3-asr-1.7b", "max_new_tokens") == 512


def test_vc_model_differences() -> None:
    assert set(params.model_ids("vc")) == {"chatterbox", "seed-vc"}
    chatterbox = {p.name for p in params.merged_params("vc", "chatterbox")}
    seedvc = {p.name for p in params.merged_params("vc", "seed-vc")}
    assert "diffusion_steps" not in chatterbox
    assert "seed" not in chatterbox
    assert {"diffusion_steps", "seed", "inference_cfg_rate", "n_quantizers"} <= seedvc
    assert {"max_window", "context", "fade", "convert_all", "denoise"} <= chatterbox
    assert {"max_window", "context", "fade", "convert_all", "denoise"} <= seedvc
    assert params.get_model("vc", "chatterbox").ref_max_len == 10
    assert params.get_model("vc", "seed-vc").ref_max_len == 25


def test_model_aliases() -> None:
    assert params.resolve_model("tts", "multilingual") == "multilingual_v2"
    assert params.resolve_model("asr", "turbo") == "large-v3-turbo"
    assert params.resolve_model("asr", "faster-whisper-large-v3") == "large-v3"
    assert params.resolve_model("vc", "seed_vc") == "seed-vc"
    assert params.resolve_model("vc", "chatterbox-vc") == "chatterbox"
    with pytest.raises(ValueError):
        params.resolve_model("tts", "not-a-model")

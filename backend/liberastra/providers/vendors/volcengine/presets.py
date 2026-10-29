"""火山方舟与豆包语音的精选模型预设。远端列表没有标签时用这份表补齐。"""

from __future__ import annotations

from liberastra.providers.catalog import model_item

ARK_PRESETS = [
    model_item(
        "doubao-seed-1-6-251015",
        label="Seed 1.6",
        category="llm",
        sub_capabilities=["chat", "vision"],
    ),
    model_item(
        "doubao-seed-1-6-flash-250828",
        label="Seed 1.6 Flash",
        category="llm",
        sub_capabilities=["chat", "vision"],
        enabled=False,
    ),
    model_item(
        "doubao-seedream-5-0-lite-260128",
        label="Seedream 5.0 Lite",
        category="image",
        sub_capabilities=["t2i", "i2i_single", "i2i_multi"],
    ),
    model_item(
        "doubao-seedream-4-5-251128",
        label="Seedream 4.5",
        category="image",
        sub_capabilities=["t2i", "i2i_single", "i2i_multi"],
        enabled=False,
    ),
    model_item(
        "doubao-seedream-4-0-250828",
        label="Seedream 4.0",
        category="image",
        sub_capabilities=["t2i", "i2i_single", "i2i_multi"],
        enabled=False,
    ),
    model_item(
        "doubao-seedance-2-5-260628",
        label="Seedance 2.5",
        category="video",
        sub_capabilities=["t2v", "i2v_first", "i2v_flf", "v2v_ref"],
    ),
    model_item(
        "doubao-seedance-2-0-260128",
        label="Seedance 2.0",
        category="video",
        sub_capabilities=["t2v", "i2v_first", "i2v_flf", "v2v_ref"],
        enabled=False,
    ),
    model_item(
        "doubao-seedance-1-5-pro-251215",
        label="Seedance 1.5 Pro",
        category="video",
        sub_capabilities=["t2v", "i2v_first", "i2v_flf"],
        enabled=False,
    ),
]

SPEECH_PRESETS = [
    model_item(
        "doubao-seed-tts-2.0",
        label="豆包语音合成",
        category="tts",
        sub_capabilities=["tts"],
    ),
    model_item(
        "doubao-seed-asr-2.0",
        label="豆包语音识别",
        category="asr",
        sub_capabilities=["asr"],
    ),
]


def presets_for(provider_type: str) -> list[dict]:
    if provider_type == "volcengine_ark":
        return [dict(item) for item in ARK_PRESETS]
    if provider_type == "volcengine_speech":
        return [dict(item) for item in SPEECH_PRESETS]
    from liberastra.providers.vendors.cloud.presets import presets_for as cloud_presets

    return cloud_presets(provider_type)

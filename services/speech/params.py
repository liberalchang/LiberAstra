"""TTS / ASR / VC 参数与模型注册表。

Help、校验、默认值都从这里生成，避免文档和运行行为漂移。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

ParamType = Literal["str", "int", "float", "bool", "enum", "json"]
ParamScope = Literal["request", "model_load", "postprocess"]


@dataclass(frozen=True)
class ParamSpec:
    name: str
    type: ParamType
    default: Any = None
    required: bool = False
    min: float | None = None
    max: float | None = None
    enum: tuple[str, ...] | None = None
    description: str = ""
    advanced: bool = False
    scope: ParamScope = "request"
    models: tuple[str, ...] | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    kind: str
    defaults: Mapping[str, Any] = field(default_factory=dict)
    unsupported: Mapping[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    ref_max_len: float | None = None


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    endpoint: str
    content_type: str
    params: tuple[ParamSpec, ...]
    models: Mapping[str, ModelSpec]
    notes: tuple[str, ...] = ()


def _p(
    name: str,
    type: ParamType,
    default: Any = None,
    *,
    required: bool = False,
    min: float | None = None,
    max: float | None = None,
    enum: tuple[str, ...] | None = None,
    description: str = "",
    advanced: bool = False,
    scope: ParamScope = "request",
    models: tuple[str, ...] | None = None,
    aliases: tuple[str, ...] = (),
) -> ParamSpec:
    return ParamSpec(
        name=name,
        type=type,
        default=default,
        required=required,
        min=min,
        max=max,
        enum=enum,
        description=description,
        advanced=advanced,
        scope=scope,
        models=models,
        aliases=aliases,
    )


_TTS_MTL = (
    "multilingual_v3",
    "multilingual_v2",
    "zh-cmn",
    "es-mx",
    "pt-br",
    "es-es",
    "pt-pt",
    "hi",
)
_TTS_STANDARD = ("standard",)
_TTS_TURBO = ("turbo", "nano")
_TTS_ALL = _TTS_MTL + _TTS_STANDARD + _TTS_TURBO

_TTS_COMMON_UNSUPPORTED = {
    "seed": "Chatterbox TTS 不支持 seed，无法固定随机数",
    "pitch": "当前 TTS 模型没有 pitch 参数",
    "emotion": "当前 TTS 模型不提供离散情绪标签；可用参考音频影响语气",
}
_TTS_TURBO_UNSUPPORTED = {
    "exaggeration": "Turbo/Nano 忽略 exaggeration；请改用 temperature/top_p/top_k",
    "cfg_weight": "Turbo/Nano 忽略 cfg_weight",
    "min_p": "Turbo/Nano 忽略 min_p",
}
_TTS_NON_TURBO_UNSUPPORTED = {
    "top_k": "top_k 仅 Turbo/Nano 支持",
    "norm_loudness": "norm_loudness 仅 Turbo/Nano 支持",
}


def _tts_models() -> dict[str, ModelSpec]:
    def make(model_id: str, label: str, kind: str, **kwargs: Any) -> ModelSpec:
        unsupported = {**_TTS_COMMON_UNSUPPORTED, **kwargs.pop("unsupported", {})}
        return ModelSpec(id=model_id, label=label, kind=kind, unsupported=unsupported, **kwargs)

    models = [
        make(
            "multilingual_v3",
            "Chatterbox-Multilingual V3",
            "mtl",
            unsupported=_TTS_NON_TURBO_UNSUPPORTED,
        ),
        make(
            "multilingual_v2",
            "Chatterbox-Multilingual V2",
            "mtl",
            unsupported=_TTS_NON_TURBO_UNSUPPORTED,
        ),
        make("standard", "Chatterbox", "standard", unsupported=_TTS_NON_TURBO_UNSUPPORTED),
        make(
            "turbo",
            "Chatterbox-Turbo",
            "turbo",
            defaults={"top_p": 0.95},
            unsupported=_TTS_TURBO_UNSUPPORTED,
        ),
        make(
            "nano",
            "Chatterbox-Nano",
            "turbo",
            defaults={"top_p": 0.95},
            unsupported=_TTS_TURBO_UNSUPPORTED,
        ),
        make("zh-cmn", "Chinese (zh-CMN)", "pack", unsupported=_TTS_NON_TURBO_UNSUPPORTED),
        make("es-mx", "Latam Spanish", "pack", unsupported=_TTS_NON_TURBO_UNSUPPORTED),
        make("pt-br", "Brazilian Portuguese", "pack", unsupported=_TTS_NON_TURBO_UNSUPPORTED),
        make("es-es", "Spain Spanish", "pack", unsupported=_TTS_NON_TURBO_UNSUPPORTED),
        make("pt-pt", "Portugal Portuguese", "pack", unsupported=_TTS_NON_TURBO_UNSUPPORTED),
        make("hi", "Hindi", "pack", unsupported=_TTS_NON_TURBO_UNSUPPORTED),
    ]
    return {m.id: m for m in models}


_TTS_PARAMS = (
    _p("text", "str", required=True, description="要合成的文本"),
    _p("model", "str", description="TTS 模型 id；不传使用 LIBER_SPEECH_TTS_MODEL"),
    _p("language", "str", description="语言代码；多语言模型使用，单语言包会锁定语言"),
    _p(
        "format",
        "enum",
        "wav",
        enum=("wav", "ogg_opus"),
        description="输出容器格式",
    ),
    _p("prompt_file_id", "str", description="参考音频的 file_id，用于音色克隆"),
    _p(
        "speed",
        "float",
        1.0,
        min=0.5,
        max=2.0,
        scope="postprocess",
        description="语速倍率，ffmpeg atempo 后处理，保持音高",
    ),
    _p(
        "normalize_loudness",
        "bool",
        False,
        scope="postprocess",
        description="是否用 ffmpeg loudnorm 统一响度",
    ),
    _p(
        "target_lufs",
        "float",
        -16.0,
        min=-40.0,
        max=-5.0,
        scope="postprocess",
        description="响度归一目标 LUFS",
    ),
    _p("ref_start", "float", 0.0, min=0.0, description="参考音频起始秒"),
    _p("ref_duration", "float", 0.0, min=0.0, description="参考音频使用时长，0 表示完整"),
    _p("strict", "bool", True, description="未知参数是否报错；false 时降级为 warning"),
    _p(
        "exaggeration",
        "float",
        0.5,
        min=0.0,
        max=2.0,
        models=_TTS_MTL + _TTS_STANDARD,
        description="语气强度；越高越夸张，通常会略微加快语速",
    ),
    _p(
        "cfg_weight",
        "float",
        0.5,
        min=0.0,
        max=1.0,
        models=_TTS_MTL + _TTS_STANDARD,
        description="CFG 权重；影响参考音遵循度和节奏",
    ),
    _p(
        "temperature",
        "float",
        0.8,
        min=0.05,
        max=2.0,
        description="采样温度",
    ),
    _p(
        "repetition_penalty",
        "float",
        1.2,
        min=1.0,
        max=2.0,
        description="重复惩罚",
    ),
    _p(
        "min_p",
        "float",
        0.05,
        min=0.0,
        max=1.0,
        models=_TTS_MTL + _TTS_STANDARD,
        description="min-p 采样阈值",
    ),
    _p("top_p", "float", 1.0, min=0.0, max=1.0, description="top-p 采样阈值"),
    _p(
        "top_k",
        "int",
        1000,
        min=1,
        max=5000,
        models=_TTS_TURBO,
        description="top-k 采样阈值，仅 Turbo/Nano",
    ),
    _p(
        "norm_loudness",
        "bool",
        True,
        models=_TTS_TURBO,
        description="模型内部响度归一，仅 Turbo/Nano",
    ),
)

_ASR_WHISPER = ("large-v3", "large-v3-turbo")
_ASR_QWEN = ("qwen3-asr-1.7b",)
_ASR_ALL = _ASR_WHISPER + _ASR_QWEN
_WHISPER_ONLY = (
    "beam_size",
    "best_of",
    "patience",
    "length_penalty",
    "repetition_penalty",
    "no_repeat_ngram_size",
    "temperature",
    "compression_ratio_threshold",
    "log_prob_threshold",
    "no_speech_threshold",
    "condition_on_previous_text",
    "prompt_reset_on_temperature",
    "initial_prompt",
    "prefix",
    "hotwords",
    "suppress_blank",
    "suppress_tokens",
    "max_initial_timestamp",
    "prepend_punctuations",
    "append_punctuations",
    "multilingual",
    "vad_filter",
    "vad_parameters",
    "chunk_length",
    "clip_timestamps",
    "hallucination_silence_threshold",
    "language_detection_threshold",
    "language_detection_segments",
)
_ASR_QWEN_UNSUPPORTED = {
    name: "Qwen3-ASR 不支持该参数；请使用 large-v3 / large-v3-turbo"
    for name in _WHISPER_ONLY
}
_ASR_WHISPER_UNSUPPORTED = {
    "max_inference_batch_size": "max_inference_batch_size 仅 Qwen3-ASR 支持",
}


def _asr_models() -> dict[str, ModelSpec]:
    models = [
        ModelSpec(
            id="large-v3",
            label="faster-whisper large-v3",
            kind="whisper",
            unsupported=_ASR_WHISPER_UNSUPPORTED,
        ),
        ModelSpec(
            id="large-v3-turbo",
            label="faster-whisper large-v3-turbo",
            kind="whisper",
            unsupported=_ASR_WHISPER_UNSUPPORTED,
        ),
        ModelSpec(
            id="qwen3-asr-1.7b",
            label="Qwen3-ASR-1.7B",
            kind="qwen",
            defaults={"max_new_tokens": 512, "max_inference_batch_size": 4},
            unsupported=_ASR_QWEN_UNSUPPORTED,
            notes=("不支持 task=translate", "不支持 VAD、beam、热词和 initial_prompt"),
        ),
    ]
    return {m.id: m for m in models}


_ASR_PARAMS = (
    _p("file_id", "str", required=True, description="输入音频/视频的 file_id"),
    _p("model", "str", description="ASR 模型 id；不传使用 LIBER_SPEECH_ASR_MODEL"),
    _p("language", "str", description="语言代码；空表示自动检测"),
    _p(
        "task",
        "enum",
        "transcribe",
        enum=("transcribe", "translate"),
        description="转写或翻译；Qwen3-ASR 只支持 transcribe",
    ),
    _p(
        "timestamps",
        "enum",
        "segment",
        enum=("none", "segment", "word"),
        description="时间戳粒度；word 会在 chunks 之外返回 words",
    ),
    _p(
        "response_format",
        "enum",
        "json",
        enum=("json", "verbose_json", "text", "srt", "vtt"),
        description="响应格式",
        advanced=True,
    ),
    _p(
        "max_new_tokens",
        "int",
        min=1,
        max=32768,
        description="最大生成 token 数；Qwen 默认 512",
        advanced=True,
        scope="model_load",
    ),
    _p("strict", "bool", True, description="未知参数是否报错"),
    _p("beam_size", "int", 5, min=1, max=10, models=_ASR_WHISPER, description="beam search 宽度"),
    _p("best_of", "int", 5, min=1, max=10, models=_ASR_WHISPER, description="采样候选数"),
    _p("patience", "float", 1.0, min=0.0, max=5.0, models=_ASR_WHISPER, description="beam search patience"),
    _p(
        "length_penalty",
        "float",
        1.0,
        min=-2.0,
        max=2.0,
        models=_ASR_WHISPER,
        description="长度惩罚",
    ),
    _p(
        "repetition_penalty",
        "float",
        1.0,
        min=0.5,
        max=2.0,
        models=_ASR_WHISPER,
        description="重复惩罚",
    ),
    _p(
        "no_repeat_ngram_size",
        "int",
        0,
        min=0,
        max=10,
        models=_ASR_WHISPER,
        description="禁止重复的 n-gram 大小",
    ),
    _p(
        "temperature",
        "json",
        [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        models=_ASR_WHISPER,
        description="解码温度；可以是数字或数字数组",
        advanced=True,
    ),
    _p(
        "compression_ratio_threshold",
        "float",
        2.4,
        min=0.0,
        max=10.0,
        models=_ASR_WHISPER,
        description="压缩比阈值，用于过滤重复/幻觉",
    ),
    _p(
        "log_prob_threshold",
        "float",
        -1.0,
        min=-5.0,
        max=0.0,
        models=_ASR_WHISPER,
        description="平均对数概率阈值",
    ),
    _p(
        "no_speech_threshold",
        "float",
        0.6,
        min=0.0,
        max=1.0,
        models=_ASR_WHISPER,
        description="静音/非语音判定阈值",
    ),
    _p(
        "condition_on_previous_text",
        "bool",
        True,
        models=_ASR_WHISPER,
        description="是否把上一窗口文本作为上下文",
    ),
    _p(
        "prompt_reset_on_temperature",
        "float",
        0.5,
        min=0.0,
        max=1.0,
        models=_ASR_WHISPER,
        description="温度超过该值时重置 prompt",
        advanced=True,
    ),
    _p(
        "initial_prompt",
        "str",
        models=_ASR_WHISPER,
        description="初始提示词，用于人名、术语和标点风格",
    ),
    _p("prefix", "str", models=_ASR_WHISPER, description="用于续写的文本前缀"),
    _p(
        "hotwords",
        "str",
        models=_ASR_WHISPER,
        description="热词提示；与 prefix 互斥",
    ),
    _p(
        "suppress_blank",
        "bool",
        True,
        models=_ASR_WHISPER,
        description="是否抑制空白输出",
        advanced=True,
    ),
    _p(
        "suppress_tokens",
        "json",
        [-1],
        models=_ASR_WHISPER,
        description="要抑制的 token id 数组",
        advanced=True,
    ),
    _p(
        "max_initial_timestamp",
        "float",
        1.0,
        min=0.0,
        max=30.0,
        models=_ASR_WHISPER,
        description="首个时间戳的最大秒数",
        advanced=True,
    ),
    _p(
        "prepend_punctuations",
        "str",
        "\"'“¿([{-",
        models=_ASR_WHISPER,
        description="允许前置到词上的标点",
        advanced=True,
    ),
    _p(
        "append_punctuations",
        "str",
        "\"'.。,，!！?？:：”)]}、",
        models=_ASR_WHISPER,
        description="允许后置到词上的标点",
        advanced=True,
    ),
    _p(
        "multilingual",
        "bool",
        False,
        models=_ASR_WHISPER,
        description="启用多语言/代码切换处理",
        advanced=True,
    ),
    _p(
        "vad_filter",
        "bool",
        False,
        models=_ASR_WHISPER,
        description="是否先用 Silero VAD 去掉非语音段",
    ),
    _p(
        "vad_parameters",
        "json",
        models=_ASR_WHISPER,
        description="VAD 参数对象",
        advanced=True,
    ),
    _p(
        "chunk_length",
        "int",
        min=1,
        max=30,
        models=_ASR_WHISPER,
        description="分块长度",
        advanced=True,
    ),
    _p(
        "clip_timestamps",
        "json",
        "0",
        models=_ASR_WHISPER,
        description="只转写指定时间片段",
        advanced=True,
    ),
    _p(
        "hallucination_silence_threshold",
        "float",
        min=0.0,
        models=_ASR_WHISPER,
        description="静音段幻觉过滤阈值",
        advanced=True,
    ),
    _p(
        "language_detection_threshold",
        "float",
        0.5,
        min=0.0,
        max=1.0,
        models=_ASR_WHISPER,
        description="自动语言检测阈值",
        advanced=True,
    ),
    _p(
        "language_detection_segments",
        "int",
        1,
        min=1,
        max=10,
        models=_ASR_WHISPER,
        description="用于语言检测的段数",
        advanced=True,
    ),
    _p(
        "max_inference_batch_size",
        "int",
        4,
        min=1,
        max=32,
        models=_ASR_QWEN,
        description="Qwen 推理批大小",
        advanced=True,
        scope="model_load",
    ),
)

_VC_ALL = ("chatterbox", "seed-vc")
_VC_SEEDVC = ("seed-vc",)
_VC_COMMON_UNSUPPORTED = {
    "dereverb": "v1 未接入去混响模型",
    "pitch": "当前 VC 模型不支持变调",
    "semi_tone_shift": "当前 Seed-VC V1 配置不支持 F0/变调",
    "auto_f0_adjust": "当前 Seed-VC V1 配置不支持自动 F0",
    "f0_condition": "当前 Seed-VC V1 配置 f0_condition=false",
}
_VC_CHATTERBOX_UNSUPPORTED = {
    **_VC_COMMON_UNSUPPORTED,
    "seed": "Chatterbox VC 没有 seed；请使用 seed-vc",
    "diffusion_steps": "Chatterbox VC 没有 diffusion_steps；请使用 seed-vc",
    "inference_cfg_rate": "Chatterbox VC 没有 inference_cfg_rate；请使用 seed-vc",
    "n_quantizers": "Chatterbox VC 没有 n_quantizers；请使用 seed-vc",
    "temperature": "Chatterbox VC 没有采样温度；请使用 seed-vc",
    "length_adjust": "Chatterbox VC 没有 length_adjust；请使用 seed-vc",
    "overlap_frame_len": "Chatterbox VC 没有 overlap_frame_len；请使用 seed-vc",
    "ref_max_len": "Chatterbox VC 固定使用参考音频前 10 秒；用 ref_start/ref_duration 选择片段",
    "watermark": "Chatterbox VC 水印固定开启，没有开关",
}
_VC_SEEDVC_UNSUPPORTED = dict(_VC_COMMON_UNSUPPORTED)


def _vc_models() -> dict[str, ModelSpec]:
    models = [
        ModelSpec(
            id="chatterbox",
            label="Chatterbox VC",
            kind="chatterbox",
            unsupported=_VC_CHATTERBOX_UNSUPPORTED,
            notes=("参考音频只使用前 10 秒",),
            ref_max_len=10.0,
        ),
        ModelSpec(
            id="seed-vc",
            label="Seed-VC",
            kind="seedvc",
            unsupported=_VC_SEEDVC_UNSUPPORTED,
            notes=("参考音频默认最多 25 秒", "f0_condition=false，不支持变调"),
            ref_max_len=25.0,
        ),
    ]
    return {m.id: m for m in models}


_VC_PARAMS = (
    _p("file_id", "str", required=True, description="源音频/视频的 file_id"),
    _p("prompt_file_id", "str", required=True, description="目标音色参考音频的 file_id"),
    _p("model", "str", description="VC 模型 id；不传使用 LIBER_SPEECH_VC_MODEL"),
    _p(
        "segments",
        "json",
        description="要替换的区间数组，元素为 {start, end}；不传表示整段",
    ),
    _p("convert_all", "bool", False, description="忽略 segments，整段替换"),
    _p("segment_padding", "float", 0.0, min=0.0, description="每个分段前后扩展的秒数"),
    _p("merge_gap", "float", 0.05, min=0.0, description="相邻分段合并的最大间隔秒数"),
    _p("min_segment", "float", 0.02, min=0.0, description="最短分段秒数"),
    _p("ref_start", "float", 0.0, min=0.0, description="参考音频起始秒"),
    _p("ref_duration", "float", 0.0, min=0.0, description="参考音频使用时长，0 表示完整"),
    _p(
        "normalize_loudness",
        "bool",
        False,
        scope="postprocess",
        description="是否用 ffmpeg loudnorm 统一响度",
    ),
    _p(
        "target_lufs",
        "float",
        -16.0,
        min=-40.0,
        max=-5.0,
        scope="postprocess",
        description="响度归一目标 LUFS",
    ),
    _p(
        "denoise",
        "bool",
        False,
        scope="postprocess",
        description="是否用 ffmpeg afftdn 去底噪",
    ),
    _p(
        "output_sample_rate",
        "int",
        0,
        min=0,
        max=192000,
        scope="postprocess",
        description="输出采样率；0 跟随源文件",
    ),
    _p("strict", "bool", True, description="未知参数是否报错"),
    _p(
        "seed",
        "int",
        min=0,
        max=2147483647,
        models=_VC_SEEDVC,
        description="随机种子，用于复现",
    ),
    _p(
        "diffusion_steps",
        "int",
        10,
        min=1,
        max=50,
        models=_VC_SEEDVC,
        description="Seed-VC diffusion 步数",
    ),
    _p(
        "inference_cfg_rate",
        "float",
        0.7,
        min=0.0,
        max=2.0,
        models=_VC_SEEDVC,
        description="Seed-VC CFG 强度",
    ),
    _p(
        "n_quantizers",
        "int",
        3,
        min=1,
        max=8,
        models=_VC_SEEDVC,
        description="Seed-VC 量化器数量",
    ),
    _p(
        "temperature",
        "float",
        1.0,
        min=0.1,
        max=2.0,
        models=_VC_SEEDVC,
        description="Seed-VC 采样温度",
    ),
    _p(
        "max_window",
        "float",
        20.0,
        min=5.0,
        max=30.0,
        models=_VC_ALL,
        description="外层分段窗口秒数",
    ),
    _p(
        "context",
        "float",
        0.15,
        min=0.0,
        max=0.5,
        models=_VC_ALL,
        description="分段接缝上下文秒数",
    ),
    _p(
        "fade",
        "float",
        0.02,
        min=0.0,
        max=0.1,
        models=_VC_ALL,
        description="分段接缝淡入淡出秒数",
    ),
    _p(
        "ref_max_len",
        "float",
        25.0,
        min=5.0,
        max=30.0,
        models=_VC_SEEDVC,
        description="Seed-VC 参考音频最大使用秒数",
    ),
    _p(
        "length_adjust",
        "float",
        1.0,
        min=0.9,
        max=1.1,
        models=_VC_SEEDVC,
        description="时间轴缩放；换音建议保持 1.0",
    ),
    _p(
        "overlap_frame_len",
        "int",
        16,
        min=4,
        max=64,
        models=_VC_SEEDVC,
        description="Seed-VC 内部分块重叠帧数",
    ),
)

FUNCTIONS: dict[str, FunctionSpec] = {
    "tts": FunctionSpec(
        name="tts",
        endpoint="/api/v2/tts/synthesize",
        content_type="application/json",
        params=_TTS_PARAMS,
        models=_tts_models(),
        notes=(
            "speed 和 normalize_loudness 是服务端后处理，不属于模型参数",
            "Turbo/Nano 忽略 exaggeration、cfg_weight、min_p",
        ),
    ),
    "asr": FunctionSpec(
        name="asr",
        endpoint="/api/v2/asr/transcribe",
        content_type="application/json",
        params=_ASR_PARAMS,
        models=_asr_models(),
        notes=(
            "Qwen3-ASR 只支持 transcribe，不支持 VAD、beam、热词和 initial_prompt",
            "timestamps=word 时返回 chunks 和 words",
        ),
    ),
    "vc": FunctionSpec(
        name="vc",
        endpoint="/api/v2/vc/convert",
        content_type="application/json",
        params=_VC_PARAMS,
        models=_vc_models(),
        notes=(
            "不做服务级时长/大小限制",
            "Chatterbox VC 参考音频只用前 10 秒；Seed-VC 默认最多 25 秒",
            "dereverb、pitch、说话人分离不在 v1 范围",
        ),
    ),
}

MODEL_ALIASES: dict[str, dict[str, str]] = {
    "tts": {"multilingual": "multilingual_v2"},
    "asr": {
        "turbo": "large-v3-turbo",
        "faster-whisper-large-v3": "large-v3",
        "systran/faster-whisper-large-v3": "large-v3",
        "faster-whisper-large-v3-turbo": "large-v3-turbo",
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo": "large-v3-turbo",
        "qwen3-asr": "qwen3-asr-1.7b",
    },
    "vc": {
        "chatterbox-vc": "chatterbox",
        "seed_vc": "seed-vc",
        "seedvc": "seed-vc",
        "seed-vc-v1": "seed-vc",
    },
}


def get_function(function: str) -> FunctionSpec:
    try:
        return FUNCTIONS[function]
    except KeyError as exc:
        raise ValueError(f"未知功能 {function}；可选 {', '.join(FUNCTIONS)}") from exc


def model_ids(function: str) -> tuple[str, ...]:
    return tuple(get_function(function).models)


def resolve_model(function: str, model: str | None) -> str:
    raw = (model or "").strip()
    if not raw:
        raise ValueError("必须指定模型")
    spec = get_function(function)
    key = raw.lower()
    canonical = MODEL_ALIASES.get(function, {}).get(key, raw)
    if canonical in spec.models:
        return canonical
    for model_id in spec.models:
        if model_id.lower() == canonical.lower():
            return model_id
    raise ValueError(f"功能 {function} 不支持模型 {model}；可选 {', '.join(spec.models)}")


def get_model(function: str, model: str) -> ModelSpec:
    canonical = resolve_model(function, model)
    return get_function(function).models[canonical]


def merged_params(function: str, model: str) -> tuple[ParamSpec, ...]:
    get_model(function, model)
    return tuple(
        p for p in get_function(function).params if p.models is None or model in p.models
    )


def effective_default(function: str, model: str, name: str) -> Any:
    model_spec = get_model(function, model)
    for p in merged_params(function, model):
        if p.name == name:
            return model_spec.defaults.get(name, p.default)
    raise KeyError(f"{function}/{model} 不支持参数 {name}")


def unsupported_params(function: str, model: str) -> dict[str, str]:
    return dict(get_model(function, model).unsupported)

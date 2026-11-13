"""语音引擎：ASR 用 faster-whisper，TTS 用 Chatterbox 的 11 个模型包。

模型包在首次合成时下载。同时只保留一个已加载的 TTS 引擎，换包时丢掉旧对象。
"""

from __future__ import annotations

import importlib.util
import math
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path
from threading import Lock
from typing import Any

# 23 种多语言 language_id，与主服务 LiberSpeech 保持一致。
LANGS_23: tuple[str, ...] = (
    "ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja", "ko",
    "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh",
)

_BASE_REPO = "ResembleAI/chatterbox"
_BASE_FILES = (
    "ve.pt",
    "conds.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "Cangjie5_TC.json",
)

# 旧请求里的 multilingual 等同 Multilingual V2。
ALIASES = {"multilingual": "multilingual_v2"}

# id -> 加载方式。kind: mtl / turbo / standard / pack。
_SPECS: dict[str, dict] = {
    "multilingual_v3": {
        "label": "Chatterbox-Multilingual V3",
        "group": "multilingual",
        "languages": LANGS_23,
        "kind": "mtl",
        "t3": "v3",
    },
    "multilingual_v2": {
        "label": "Chatterbox-Multilingual V2",
        "group": "multilingual",
        "languages": LANGS_23,
        "kind": "mtl",
        "t3": "v2",
    },
    "turbo": {
        "label": "Chatterbox-Turbo",
        "group": "english",
        "languages": ("en",),
        "kind": "turbo",
        "nano": False,
    },
    "nano": {
        "label": "Chatterbox-Nano",
        "group": "english",
        "languages": ("en",),
        "kind": "turbo",
        "nano": True,
    },
    "standard": {
        "label": "Chatterbox",
        "group": "english",
        "languages": ("en",),
        "kind": "standard",
    },
    "zh-cmn": {
        "label": "Chinese (zh-CMN)",
        "group": "pack",
        "languages": ("zh",),
        "kind": "pack",
        "repo": "ResembleAI/Chatterbox-Multilingual-zh-cmn",
        "t3": "t3_zh_cmn.safetensors",
    },
    "es-mx": {
        "label": "Latam Spanish",
        "group": "pack",
        "languages": ("es",),
        "kind": "pack",
        "repo": "ResembleAI/Chatterbox-Multilingual-es-mx-latam",
        "t3": "t3_es_mx_latam.safetensors",
    },
    "pt-br": {
        "label": "Brazilian Portuguese",
        "group": "pack",
        "languages": ("pt",),
        "kind": "pack",
        "repo": "ResembleAI/Chatterbox-Multilingual-pt-br",
        "t3": "t3_pt_br.safetensors",
    },
    "es-es": {
        "label": "Spain Spanish",
        "group": "pack",
        "languages": ("es",),
        "kind": "pack",
        "repo": "ResembleAI/Chatterbox-Multilingual-es-es",
        "t3": "t3_es_es.safetensors",
    },
    "pt-pt": {
        "label": "Portugal Portuguese",
        "group": "pack",
        "languages": ("pt",),
        "kind": "pack",
        "repo": "ResembleAI/Chatterbox-Multilingual-pt-pt",
        "t3": "t3_pt_pt.safetensors",
    },
    "hi": {
        "label": "Hindi",
        "group": "pack",
        "languages": ("hi",),
        "kind": "pack",
        "repo": "ResembleAI/Chatterbox-Multilingual-hi",
        "t3": "t3_hi.safetensors",
    },
}

_lock = Lock()
_asr = None
_asr_name = ""
_tts = None
_tts_id = ""


def resolve_device(choice: str | None = None) -> str:
    """显式传入 cpu 或 cuda 时直接使用。否则读 LIBER_SPEECH_DEVICE，auto 在有显卡时用 cuda。"""
    if choice is None:
        choice = os.getenv("LIBER_SPEECH_DEVICE", "auto")
    choice = choice.strip().lower()
    if choice in {"cpu", "cuda"}:
        return choice
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def resolve_model(model: str) -> str:
    """把别名解析成目录里的 id。未知 id 抛出 ValueError。"""
    key = ALIASES.get((model or "").strip(), (model or "").strip())
    if key not in _SPECS:
        raise ValueError(f"未知模型 {model}")
    return key


def default_tts_model() -> str:
    """服务环境变量里的默认 TTS。别名会展开；未知值原样返回，合成时再报错。"""
    raw = os.getenv("LIBER_SPEECH_TTS_MODEL", "multilingual_v3").strip() or "multilingual_v3"
    return ALIASES.get(raw, raw)


def tts_catalog() -> list[dict]:
    """供设置页使用的模型包列表。"""
    return [
        {
            "id": model_id,
            "label": spec["label"],
            "group": spec["group"],
            "languages": list(spec["languages"]),
        }
        for model_id, spec in _SPECS.items()
    ]


# 对外模型 id。别名在请求里展开，空值回退到 LIBER_SPEECH_ASR_MODEL。
_ASR_CANONICAL = ("large-v3", "large-v3-turbo", "qwen3-asr-1.7b")
_ASR_ALIASES = {
    "turbo": "large-v3-turbo",
    "faster-whisper-large-v3": "large-v3",
    "faster-whisper-large-v3-turbo": "large-v3-turbo",
    "systran/faster-whisper-large-v3": "large-v3",
    "systran/faster-whisper-large-v3-turbo": "large-v3-turbo",
    # faster-whisper 官方把 large-v3-turbo 指到这个仓库，Systran 没有同名权重。
    "mobiuslabsgmbh/faster-whisper-large-v3-turbo": "large-v3-turbo",
    "qwen3-asr": "qwen3-asr-1.7b",
    "qwen/qwen3-asr-1.7b": "qwen3-asr-1.7b",
}
# ISO 语言代码 -> Qwen3-ASR 要求的英文语言名。
_QWEN_LANG = {
    "zh": "Chinese",
    "en": "English",
    "yue": "Cantonese",
    "ar": "Arabic",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "id": "Indonesian",
    "it": "Italian",
    "ko": "Korean",
    "ru": "Russian",
    "th": "Thai",
    "vi": "Vietnamese",
    "ja": "Japanese",
    "tr": "Turkish",
    "hi": "Hindi",
    "ms": "Malay",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "cs": "Czech",
    "fil": "Filipino",
    "tl": "Filipino",
    "fa": "Persian",
    "el": "Greek",
    "ro": "Romanian",
    "hu": "Hungarian",
    "mk": "Macedonian",
}
_QWEN_TO_ISO = {name.lower(): code for code, name in _QWEN_LANG.items()}
_CHUNK_BREAKS = set("。！？；，,.;!?、")


def asr_catalog() -> list[dict[str, str]]:
    """可选识别模型。空请求回退到环境变量。"""
    return [
        {"id": "large-v3", "label": "faster-whisper large-v3"},
        {"id": "large-v3-turbo", "label": "faster-whisper large-v3-turbo"},
        {"id": "qwen3-asr-1.7b", "label": "Qwen3-ASR-1.7B"},
    ]


def default_asr_model() -> str:
    """环境变量里的默认识别模型 id。本地目录会折回 large-v3 这类标准名。"""
    model_id = _canonical_asr_id(os.getenv("LIBER_SPEECH_ASR_MODEL", "large-v3"))
    if not _is_filesystem_model(model_id):
        return model_id
    name = Path(model_id).name
    if name.lower().startswith("qwen3-asr"):
        return "qwen3-asr-1.7b"
    name = name.removeprefix("faster-whisper-")
    return name if name in _ASR_CANONICAL else model_id


def resolve_asr_model(model: str | None) -> str:
    """未传入时用 LIBER_SPEECH_ASR_MODEL。返回标准 id 或本地目录。"""
    raw = (model or "").strip()
    if raw.lower() in {"", "default", "whisper", "whisper-1"}:
        raw = os.getenv("LIBER_SPEECH_ASR_MODEL", "large-v3").strip() or "large-v3"
    return _canonical_asr_id(raw)


def _canonical_asr_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text or any(ch in text for ch in "\r\n"):
        raise ValueError("ASR 模型名无效")
    if _is_filesystem_model(text):
        path = Path(text)
        if (path / "model.bin").is_file() or (path / "config.json").is_file():
            return str(path)
        raise ValueError(
            "ASR 本地目录里需要有 model.bin（faster-whisper）或 config.json（Qwen3-ASR）。"
        )
    key = text.lower()
    if key.startswith("faster-whisper-"):
        key = _ASR_ALIASES.get(key, key[len("faster-whisper-") :])
    key = _ASR_ALIASES.get(key, key)
    if key not in _ASR_CANONICAL:
        raise ValueError(
            "ASR 模型只支持 large-v3、large-v3-turbo、qwen3-asr-1.7b，或对应的本地目录。"
        )
    return key


def _is_filesystem_model(name: str) -> bool:
    return name.startswith(("/", "\\")) or (len(name) > 2 and name[1] == ":")


def _asr_kind(model_id: str) -> str:
    path = Path(model_id)
    if path.is_dir():
        # faster-whisper 的目录里同时有 model.bin 和 config.json。有 model.bin 就走 CTranslate2。
        if (path / "model.bin").is_file():
            return "whisper"
        return "qwen"
    if model_id == "qwen3-asr-1.7b":
        return "qwen"
    return "whisper"


def configured_models() -> list[dict[str, str]]:
    """当前配置的 ASR / TTS 模型名。语言代码不是模型。"""
    asr = default_asr_model()
    tts = default_tts_model()
    label = _SPECS.get(tts, {}).get("label", tts)
    asr_label = asr if asr == "qwen3-asr-1.7b" else f"faster-whisper-{asr}"
    return [
        {"name": asr_label, "role": "ASR"},
        {"name": label, "role": "TTS"},
    ]


def asr_ready() -> bool:
    return _asr is not None


def tts_ready() -> bool:
    return _tts is not None


def _release_cuda() -> None:
    import gc

    gc.collect()
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _drop_tts() -> None:
    """丢掉当前引擎，并尽量交还显存。"""
    global _tts, _tts_id
    _tts = None
    _tts_id = ""
    _release_cuda()


def _drop_asr() -> None:
    """换识别模型前丢掉旧的 faster-whisper，避免两份权重同时占着显存。"""
    global _asr, _asr_name
    _asr = None
    _asr_name = ""
    _release_cuda()


def _place(src: Path, dest: Path) -> None:
    """把缓存文件放进组装目录。优先硬链接，失败再复制。不改 Hugging Face 缓存本身。"""
    if dest.exists() or dest.is_symlink():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def _assemble_pack(spec: dict, model_id: str) -> Path:
    """单语言包：底座来自 ResembleAI/chatterbox，权重来自语言包仓库。"""
    from huggingface_hub import hf_hub_download

    root = Path(os.environ.get("HF_HOME", ".")) / "liber-speech-packs" / model_id
    root.mkdir(parents=True, exist_ok=True)
    for name in _BASE_FILES:
        src = Path(hf_hub_download(repo_id=_BASE_REPO, filename=name))
        _place(src, root / name)
    t3_name = spec["t3"]
    _place(Path(hf_hub_download(repo_id=spec["repo"], filename=t3_name)), root / t3_name)
    s3gen = Path(hf_hub_download(repo_id=spec["repo"], filename="s3gen_v3.pt"))
    _place(s3gen, root / "s3gen_v3.pt")
    _place(s3gen, root / "s3gen.pt")
    return root


def _build_tts(model_id: str, device: str):
    spec = _SPECS[model_id]
    kind = spec["kind"]
    if kind == "mtl":
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        return ChatterboxMultilingualTTS.from_pretrained(device, t3_model=spec["t3"])
    if kind == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        return ChatterboxTurboTTS.from_pretrained(device, nano=spec["nano"])
    if kind == "standard":
        from chatterbox.tts import ChatterboxTTS

        return ChatterboxTTS.from_pretrained(device)
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    ckpt = _assemble_pack(spec, model_id)
    return ChatterboxMultilingualTTS.from_local(str(ckpt), device, t3_model=spec["t3"])


def _load_tts(model_id: str):
    """调用方已持有 _lock。同一时间只留一个引擎。"""
    global _tts, _tts_id
    if _tts is not None and _tts_id == model_id:
        return _tts
    _drop_tts()
    _tts = _build_tts(model_id, resolve_device())
    _tts_id = model_id
    return _tts


def _language_code(language: str | None) -> str:
    return (language or "").strip().split("-")[0].lower()


def _checked_language(spec: dict, language: str | None) -> str | None:
    """按模型包决定要不要传 language_id。不匹配则报错。"""
    code = _language_code(language)
    allowed = spec["languages"]
    kind = spec["kind"]
    if kind == "mtl":
        if code not in allowed:
            raise ValueError(f"语言 {language or '（空）'} 不在该模型支持的 23 种语言内")
        return code
    fixed = allowed[0]
    if code and code != fixed:
        raise ValueError(f"该模型只支持 {fixed}")
    if kind == "pack":
        return fixed
    return None


def synthesize(
    text: str,
    *,
    model: str,
    language: str | None,
    audio_prompt: str | None,
    exaggeration: float | None = None,
    cfg_weight: float | None = None,
    temperature: float | None = None,
    repetition_penalty: float | None = None,
    min_p: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    norm_loudness: bool | None = None,
) -> tuple[object, int]:
    """返回 (waveform tensor, sample_rate)。结束后释放 TTS 显存。"""
    model_id = resolve_model(model)
    spec = _SPECS[model_id]
    language_id = _checked_language(spec, language)
    with _lock:
        _drop_asr()
        try:
            tts = _load_tts(model_id)
            kwargs: dict = {"audio_prompt_path": audio_prompt}
            if language_id:
                kwargs["language_id"] = language_id
            if spec["kind"] == "turbo":
                for name, value in (
                    ("exaggeration", exaggeration),
                    ("cfg_weight", cfg_weight),
                    ("min_p", min_p),
                ):
                    if value is not None:
                        raise ValueError(f"模型 {model_id} 不支持 {name}")
                for name, value in (
                    ("temperature", temperature),
                    ("repetition_penalty", repetition_penalty),
                    ("top_p", top_p),
                    ("top_k", top_k),
                    ("norm_loudness", norm_loudness),
                ):
                    if value is not None:
                        kwargs[name] = value
            else:
                for name, value in (
                    ("top_k", top_k),
                    ("norm_loudness", norm_loudness),
                ):
                    if value is not None:
                        raise ValueError(f"模型 {model_id} 不支持 {name}")
                for name, value in (
                    ("exaggeration", exaggeration),
                    ("cfg_weight", cfg_weight),
                    ("temperature", temperature),
                    ("repetition_penalty", repetition_penalty),
                    ("min_p", min_p),
                    ("top_p", top_p),
                ):
                    if value is not None:
                        kwargs[name] = value
            try:
                wav = tts.generate(text, **kwargs)
            except AssertionError as exc:
                message = str(exc)
                if "5 seconds" in message:
                    raise ValueError("Turbo / Nano 的参考音频需要长于 5 秒") from exc
                raise ValueError(message) from exc
            sample_rate = int(tts.sr)
            if hasattr(wav, "detach"):
                wav = wav.detach().cpu().clone()
            return wav, sample_rate
        finally:
            _drop_tts()


def transcribe(
    audio_path: str,
    *,
    language: str | None,
    task: str,
    model: str | None = None,
    **params: Any,
) -> dict:
    """转写。model 为空时用环境变量。结束后释放识别模型显存。"""
    model_id = resolve_asr_model(model)
    kind = _asr_kind(model_id)
    if kind == "qwen" and (task or "transcribe") == "translate":
        raise ValueError("Qwen3-ASR 不支持语音翻译，请改用 large-v3")
    with _lock:
        _drop_tts()
        try:
            if kind == "qwen":
                return _transcribe_qwen(audio_path, language, model_id, params)
            return _transcribe_whisper(audio_path, language, task, model_id, params)
        finally:
            _drop_asr()


def _whisper_load_target(model_id: str) -> str:
    """平铺目录优先，否则把别名交给 faster-whisper 去 Hugging Face 缓存里找。"""
    if _is_filesystem_model(model_id):
        return model_id
    flat = Path(os.environ.get("HF_HOME", "/models")) / f"faster-whisper-{model_id}"
    if (flat / "model.bin").is_file():
        return str(flat)
    return model_id


_WHISPER_PARAM_NAMES = frozenset(
    {
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
        "max_new_tokens",
    }
)
_QWEN_PARAM_NAMES = frozenset(
    {"timestamps", "max_new_tokens", "max_inference_batch_size", "response_format"}
)


def _whisper_kwargs(params: dict[str, Any]) -> dict[str, Any]:
    timestamps = params.get("timestamps", "segment")
    if timestamps not in {"none", "segment", "word"}:
        raise ValueError(f"未知 timestamps 粒度 {timestamps}")
    kwargs: dict[str, Any] = {}
    if timestamps == "none":
        kwargs["without_timestamps"] = True
    elif timestamps == "word":
        kwargs["word_timestamps"] = True
    for name in _WHISPER_PARAM_NAMES:
        value = params.get(name)
        if value is not None:
            kwargs[name] = value
    unknown = set(params) - _WHISPER_PARAM_NAMES - {"timestamps", "response_format"}
    if unknown:
        raise ValueError(f"faster-whisper 不支持参数 {', '.join(sorted(unknown))}")
    return kwargs


def _qwen_kwargs(params: dict[str, Any]) -> dict[str, Any]:
    timestamps = params.get("timestamps", "segment")
    if timestamps not in {"none", "segment", "word"}:
        raise ValueError(f"未知 timestamps 粒度 {timestamps}")
    unknown = set(params) - _QWEN_PARAM_NAMES
    if unknown:
        raise ValueError(f"Qwen3-ASR 不支持参数 {', '.join(sorted(unknown))}")
    return {
        "timestamps": timestamps,
        "return_time_stamps": timestamps != "none",
        "max_new_tokens": int(params.get("max_new_tokens", 512)),
        "max_inference_batch_size": int(params.get("max_inference_batch_size", 4)),
    }


def _transcribe_whisper(
    audio_path: str,
    language: str | None,
    task: str,
    model_id: str,
    params: dict[str, Any] | None = None,
) -> dict:
    global _asr, _asr_name
    from faster_whisper import WhisperModel

    target = _whisper_load_target(model_id)
    _asr = WhisperModel(target, device=resolve_device(), compute_type="float16")
    _asr_name = model_id
    kwargs = _whisper_kwargs(params or {})
    segments, info = _asr.transcribe(
        audio_path, language=language or None, task=task, **kwargs
    )
    chunks: list[dict[str, Any]] = []
    words_all: list[dict[str, Any]] = []
    for segment in segments:
        chunk: dict[str, Any] = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
        }
        segment_words = getattr(segment, "words", None)
        if segment_words:
            words = [
                {
                    "start": word.start,
                    "end": word.end,
                    "text": word.word,
                    "probability": word.probability,
                }
                for word in segment_words
            ]
            chunk["words"] = words
            words_all.extend(words)
        chunks.append(chunk)
    public = model_id if not _is_filesystem_model(model_id) else Path(model_id).name
    return {
        "text": "".join(c["text"] for c in chunks).strip(),
        "chunks": chunks,
        "words": words_all,
        "language": info.language,
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "duration_after_vad": getattr(info, "duration_after_vad", None),
        "model": public,
    }


def _qwen_language(language: str | None) -> str | None:
    raw = (language or "").strip()
    if not raw:
        return None
    code = raw.split("-")[0].lower()
    if code in _QWEN_LANG:
        return _QWEN_LANG[code]
    titled = raw[:1].upper() + raw[1:].lower()
    if titled in set(_QWEN_LANG.values()):
        return titled
    raise ValueError(f"Qwen3-ASR 不支持语言 {language}")


def _iso_from_qwen(language: str | None) -> str | None:
    raw = (language or "").split(",")[0].strip()
    if not raw:
        return None
    return _QWEN_TO_ISO.get(raw.lower(), raw.lower())


def _local_or_repo(flat_name: str, repo_id: str) -> str:
    """平铺目录里有 config.json 就用本地路径，否则用仓库 id 走 Hugging Face 缓存。"""
    flat = Path(os.environ.get("HF_HOME", "/models")) / flat_name
    if (flat / "config.json").is_file():
        return str(flat)
    return repo_id


def _aggregate_qwen_chunks(items: object) -> list[dict]:
    """字词级时间戳按标点或停顿收成句子，结构与 faster-whisper 的 chunks 一致。"""
    chunks: list[dict] = []
    buf: list[str] = []
    start: float | None = None
    end = 0.0
    prev_end: float | None = None

    def flush() -> None:
        nonlocal buf, start, prev_end
        text = "".join(buf).strip()
        if text and start is not None:
            chunks.append({"start": start, "end": end, "text": text})
        buf = []
        start = None
        prev_end = None

    for item in items or []:
        text = str(getattr(item, "text", "") or "")
        if not text:
            continue
        item_start = float(getattr(item, "start_time", 0.0) or 0.0)
        item_end = float(getattr(item, "end_time", item_start) or item_start)
        if prev_end is not None and item_start - prev_end > 0.6 and buf:
            flush()
        if start is None:
            start = item_start
        buf.append(text)
        end = item_end
        prev_end = item_end
        if text[-1] in _CHUNK_BREAKS:
            flush()
    flush()
    return chunks


def _ensure_qwen_transformers_compat() -> None:
    """qwen-asr 0.0.6 按 transformers 4.57 编写。5.2 删了装饰器，也不再登记 default RoPE。"""
    import torch
    import transformers.modeling_rope_utils as rope_utils
    from transformers.utils import generic

    if not hasattr(generic, "check_model_inputs"):

        def check_model_inputs(func=None):
            def decorator(fn):
                return fn

            if func is None:
                return decorator
            return decorator(func)

        generic.check_model_inputs = check_model_inputs

    if "default" not in rope_utils.ROPE_INIT_FUNCTIONS:

        def _compute_default_rope_parameters(config, device=None, seq_len=None, **rope_kwargs):
            # 与 transformers 4.57 的 default RoPE 相同：theta 与 head 维度决定频率。
            if rope_kwargs:
                base = rope_kwargs["base"]
                dim = rope_kwargs["dim"]
            else:
                base = config.rope_theta
                partial = getattr(config, "partial_rotary_factor", 1.0)
                head_dim = getattr(config, "head_dim", None) or config.hidden_size // config.num_attention_heads
                dim = int(head_dim * partial)
            inv_freq = 1.0 / (
                base ** (torch.arange(0, dim, 2, dtype=torch.int64).to(device=device, dtype=torch.float) / dim)
            )
            return inv_freq, 1.0

        rope_utils.ROPE_INIT_FUNCTIONS["default"] = _compute_default_rope_parameters

    # transformers 5.2 不再给每个 config 自动放 pad_token_id，Qwen thinker 初始化会读它。
    from qwen_asr.core.transformers_backend.configuration_qwen3_asr import (
        Qwen3ASRThinkerConfig,
    )

    if getattr(Qwen3ASRThinkerConfig, "_liber_pad_patched", False):
        return
    original_init = Qwen3ASRThinkerConfig.__init__

    def _thinker_init(self, *args, **kwargs):
        pad_token_id = kwargs.get("pad_token_id")
        original_init(self, *args, **kwargs)
        try:
            object.__getattribute__(self, "pad_token_id")
        except AttributeError:
            self.pad_token_id = pad_token_id

    Qwen3ASRThinkerConfig.__init__ = _thinker_init
    Qwen3ASRThinkerConfig._liber_pad_patched = True

    # transformers 5.2 在初始化 RoPE buffer 时会调用这个方法，qwen-asr 的类里没有。
    import qwen_asr.core.transformers_backend.modeling_qwen3_asr as qwen_modeling

    def compute_default_rope_parameters(self, config, device=None, **kwargs):
        return self.rope_init_fn(config, device)

    for cls in vars(qwen_modeling).values():
        if (
            isinstance(cls, type)
            and "RotaryEmbedding" in cls.__name__
            and "compute_default_rope_parameters" not in cls.__dict__
        ):
            cls.compute_default_rope_parameters = compute_default_rope_parameters

    # qwen-asr 传入 fix_mistral_regex，transformers 5.2 又原样展开 kwargs，会重复传参。
    from transformers import AutoProcessor

    if not getattr(AutoProcessor, "_liber_mistral_patched", False):
        original_processor = AutoProcessor.from_pretrained

        def _processor_from_pretrained(*args, **kwargs):
            kwargs.pop("fix_mistral_regex", None)
            return original_processor(*args, **kwargs)

        AutoProcessor.from_pretrained = staticmethod(_processor_from_pretrained)
        AutoProcessor._liber_mistral_patched = True


def _transcribe_qwen(
    audio_path: str,
    language: str | None,
    model_id: str,
    params: dict[str, Any] | None = None,
) -> dict:
    global _asr, _asr_name
    import torch

    options = _qwen_kwargs(params or {})
    _ensure_qwen_transformers_compat()
    from qwen_asr import Qwen3ASRModel

    if _is_filesystem_model(model_id):
        asr_path = model_id
    else:
        asr_path = _local_or_repo("Qwen3-ASR-1.7B", "Qwen/Qwen3-ASR-1.7B")
    aligner = os.getenv("LIBER_SPEECH_QWEN_ALIGNER_MODEL", "").strip()
    if not aligner:
        aligner = _local_or_repo("Qwen3-ForcedAligner-0.6B", "Qwen/Qwen3-ForcedAligner-0.6B")
    device = "cuda:0" if resolve_device() == "cuda" else "cpu"
    dtype = torch.float16
    if device.startswith("cuda") and torch.cuda.is_bf16_supported():
        dtype = torch.bfloat16
    _asr = Qwen3ASRModel.from_pretrained(
        asr_path,
        dtype=dtype,
        device_map=device,
        max_inference_batch_size=options["max_inference_batch_size"],
        max_new_tokens=options["max_new_tokens"],
        forced_aligner=aligner,
        forced_aligner_kwargs={"dtype": dtype, "device_map": device},
    )
    _asr_name = "qwen3-asr-1.7b"
    qwen_language = _qwen_language(language)
    results = _asr.transcribe(
        audio=audio_path,
        language=qwen_language,
        return_time_stamps=options["return_time_stamps"],
    )
    first = results[0] if results else None
    text = str(getattr(first, "text", "") or "").strip()
    stamps = getattr(first, "time_stamps", None) if first is not None else None
    items = list(stamps) if stamps is not None else []
    chunks = _aggregate_qwen_chunks(items) if options["return_time_stamps"] else []
    if not chunks and text:
        chunks = [{"start": 0.0, "end": 0.0, "text": text}]
    words: list[dict[str, Any]] = []
    if options["timestamps"] == "word":
        for item in items:
            word = str(getattr(item, "text", "") or "")
            if not word:
                continue
            start = float(getattr(item, "start_time", 0.0) or 0.0)
            end = float(getattr(item, "end_time", start) or start)
            words.append({"start": start, "end": end, "text": word})
    detected = _iso_from_qwen(getattr(first, "language", None) if first is not None else None)
    return {
        "text": text or "".join(c["text"] for c in chunks).strip(),
        "chunks": chunks,
        "words": words,
        "language": detected or (language or None),
        "language_probability": None,
        "duration": None,
        "duration_after_vad": None,
        "model": "qwen3-asr-1.7b",
    }


# ---------------------------------------------------------------------------
# Voice conversion (VC)
# ---------------------------------------------------------------------------

_VC_SPECS: dict[str, dict[str, str]] = {
    "chatterbox": {"label": "Chatterbox VC", "kind": "chatterbox"},
    "seed-vc": {"label": "Seed-VC", "kind": "seedvc"},
}
_VC_ALIASES = {
    "chatterbox-vc": "chatterbox",
    "seed_vc": "seed-vc",
    "seedvc": "seed-vc",
    "seed-vc-v1": "seed-vc",
}
_CHATTERBOX_SR = 24000
_SEEDVC_SR = 22050
_VC_MAX_WINDOW_S = 20.0
_VC_CONTEXT_S = 0.15
_VC_FADE_S = 0.02
_DEMUCS_CHECKPOINT = "955717e8-8726e21a.th"

_vc: dict[str, Any] | None = None
_vc_id = ""
_separator: Any | None = None


def vc_catalog() -> list[dict[str, str]]:
    return [{"id": model_id, "label": spec["label"]} for model_id, spec in _VC_SPECS.items()]


def default_vc_model() -> str:
    raw = os.getenv("LIBER_SPEECH_VC_MODEL", "chatterbox").strip().lower() or "chatterbox"
    return _VC_ALIASES.get(raw, raw)


def resolve_vc_model(model: str | None) -> str:
    raw = (model or "").strip().lower()
    if raw in {"", "default"}:
        raw = default_vc_model()
    key = _VC_ALIASES.get(raw, raw)
    if key not in _VC_SPECS:
        raise ValueError("VC 模型只支持 chatterbox、seed-vc")
    return key


def _models_root() -> Path:
    return Path(os.getenv("HF_HOME", "/models"))


def _model_dir(env_name: str, default_name: str) -> Path:
    raw = os.getenv(env_name, "").strip()
    return Path(raw) if raw else _models_root() / default_name


def _chatterbox_vc_dir() -> Path:
    raw = os.getenv("LIBER_SPEECH_CHATTERBOX_VC_DIR", "").strip()
    if raw:
        path = Path(raw)
    else:
        root = _models_root() / "models--ResembleAI--chatterbox" / "snapshots"
        candidates = sorted(
            (item for item in root.glob("*") if (item / "s3gen.safetensors").is_file()),
            key=lambda item: item.stat().st_mtime,
        )
        if not candidates:
            raise FileNotFoundError(f"找不到 Chatterbox VC 权重: {root}/*/s3gen.safetensors")
        path = candidates[-1]
    if not (path / "s3gen.safetensors").is_file():
        raise FileNotFoundError(f"缺少 Chatterbox VC 权重: {path / 's3gen.safetensors'}")
    return path


def _seedvc_dirs() -> dict[str, Path]:
    return {
        "model": _model_dir("LIBER_SPEECH_SEEDVC_DIR", "Seed-VC"),
        "whisper": _model_dir("LIBER_SPEECH_WHISPER_SMALL_DIR", "whisper-small"),
        "campplus": _model_dir("LIBER_SPEECH_CAMPPLUS_DIR", "campplus"),
        "bigvgan": _model_dir("LIBER_SPEECH_BIGVGAN_DIR", "bigvgan_v2_22khz_80band_256x"),
    }


def _demucs_dir() -> Path:
    return _model_dir("LIBER_SPEECH_DEMUCS_DIR", "demucs")


def _demucs_checkpoints() -> list[Path]:
    root = _demucs_dir()
    return sorted(root.rglob("*.th")) if root.is_dir() else []


def separate_available() -> bool:
    """Demucs 依赖和本地权重都在时才开放「分离背景音」。"""
    if importlib.util.find_spec("demucs") is None:
        return False
    root = _demucs_dir()
    return (root / "hubconf.py").is_file() or bool(_demucs_checkpoints())


def _ensure_demucs_compat() -> Path:
    """把上传目录里的 htdemucs 权重放到 torch.hub 期望的缓存名，离线也能加载。"""
    import torch

    target = Path(os.getenv("TORCH_HOME", str(_models_root()))) / "hub" / "checkpoints" / _DEMUCS_CHECKPOINT
    torch.hub.set_dir(str(target.parent.parent))
    if target.is_file():
        return target
    candidates = _demucs_checkpoints()
    if not candidates:
        raise FileNotFoundError(
            f"找不到 Demucs 权重: {_demucs_dir()}/*.th（期望 {_DEMUCS_CHECKPOINT}）"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(candidates[0], target)
    except OSError:
        shutil.copy2(candidates[0], target)
    return target


def _drop_vc() -> None:
    global _vc, _vc_id
    _vc = None
    _vc_id = ""
    _release_cuda()


def _drop_separator() -> None:
    global _separator
    _separator = None
    _release_cuda()


def _install_dac_stub() -> None:
    """Seed-VC 的 length_regulator 在 import 时引用 dac；当前配置不会实例化它。"""
    import importlib.machinery

    if "dac.nn.quantize" in sys.modules:
        return
    try:
        if importlib.util.find_spec("dac") is not None:
            return
    except (ImportError, ValueError):
        pass

    dac = types.ModuleType("dac")
    dac.__path__ = []  # type: ignore[attr-defined]
    dac.__spec__ = importlib.machinery.ModuleSpec("dac", loader=None, is_package=True)
    dac_nn = types.ModuleType("dac.nn")
    dac_nn.__path__ = []  # type: ignore[attr-defined]
    dac_nn.__spec__ = importlib.machinery.ModuleSpec("dac.nn", loader=None, is_package=True)
    quantize = types.ModuleType("dac.nn.quantize")
    quantize.__spec__ = importlib.machinery.ModuleSpec("dac.nn.quantize", loader=None)

    class VectorQuantize:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("dac 未安装；当前 VC 模型不需要 vector_quantize")

    quantize.VectorQuantize = VectorQuantize  # type: ignore[attr-defined]
    dac.nn = dac_nn  # type: ignore[attr-defined]
    dac_nn.quantize = quantize  # type: ignore[attr-defined]
    sys.modules["dac"] = dac
    sys.modules["dac.nn"] = dac_nn
    sys.modules["dac.nn.quantize"] = quantize


def _seedvc_source_dir() -> Path:
    return Path(__file__).resolve().parent / "third_party" / "seed_vc"


def _ensure_seedvc_compat() -> Path:
    root = _seedvc_source_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"缺少 Seed-VC 源码: {root}")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    _install_dac_stub()
    return root


def _load_chatterbox_vc(device: str) -> Any:
    from chatterbox.vc import ChatterboxVC

    return ChatterboxVC.from_local(str(_chatterbox_vc_dir()), device)


def _load_seedvc_models(device: str) -> dict[str, Any]:
    _ensure_seedvc_compat()
    import torch
    import yaml
    from modules.audio import mel_spectrogram
    from modules.bigvgan import bigvgan
    from modules.campplus.DTDNN import CAMPPlus
    from modules.commons import build_model, load_checkpoint, recursive_munch
    from transformers import AutoFeatureExtractor, WhisperModel

    dirs = _seedvc_dirs()
    model_dir = dirs["model"]
    whisper_dir = dirs["whisper"]
    campplus_dir = dirs["campplus"]
    bigvgan_dir = dirs["bigvgan"]
    checkpoint = model_dir / "DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth"
    config_path = model_dir / "config_dit_mel_seed_uvit_whisper_small_wavenet.yml"
    campplus_path = campplus_dir / "campplus_cn_common.bin"
    required = (
        checkpoint,
        config_path,
        campplus_path,
        whisper_dir / "model.safetensors",
        bigvgan_dir / "config.json",
        bigvgan_dir / "bigvgan_generator.pt",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少 Seed-VC 权重: " + ", ".join(missing))

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    params = recursive_munch(config["model_params"])
    params.dit_type = "DiT"
    params.speech_tokenizer.name = str(whisper_dir)
    params.style_encoder.campplus_path = str(campplus_path)
    params.vocoder.name = str(bigvgan_dir)
    model = build_model(params, stage="DiT")
    hop_length = int(config["preprocess_params"]["spect_params"]["hop_length"])
    sr = int(config["preprocess_params"]["sr"])
    model, _, _, _ = load_checkpoint(
        model,
        None,
        str(checkpoint),
        load_only_params=True,
        ignore_modules=[],
        is_distributed=False,
    )
    for key in model:
        model[key].eval()
        model[key].to(device)
    model.cfm.estimator.setup_caches(max_batch_size=1, max_seq_length=8192)

    dtype = torch.float16 if device.startswith("cuda") else torch.float32
    whisper_model = WhisperModel.from_pretrained(str(whisper_dir), torch_dtype=dtype).to(device)
    del whisper_model.decoder
    feature_extractor = AutoFeatureExtractor.from_pretrained(str(whisper_dir))
    mask_features = getattr(whisper_model, "_mask_input_features", None)

    def semantic_fn(waves_16k: Any) -> Any:
        inputs = feature_extractor(
            [waves_16k.squeeze(0).cpu().numpy()],
            return_tensors="pt",
            return_attention_mask=True,
            sampling_rate=16000,
        )
        features = inputs.input_features
        if mask_features is not None:
            features = mask_features(features, attention_mask=inputs.attention_mask)
        features = features.to(
            device=whisper_model.encoder.device,
            dtype=whisper_model.encoder.dtype,
        )
        with torch.no_grad():
            outputs = whisper_model.encoder(
                features,
                head_mask=None,
                output_attentions=False,
                output_hidden_states=False,
                return_dict=True,
            )
        hidden = outputs.last_hidden_state.to(torch.float32)
        return hidden[:, : waves_16k.size(-1) // 320 + 1]

    campplus_model = CAMPPlus(feat_dim=80, embedding_size=192)
    campplus_model.load_state_dict(torch.load(str(campplus_path), map_location="cpu"))
    campplus_model.eval().to(device)

    bigvgan_model = bigvgan.BigVGAN(
        bigvgan.load_hparams_from_json(str(bigvgan_dir / "config.json")),
        use_cuda_kernel=False,
    )
    generator_state = torch.load(str(bigvgan_dir / "bigvgan_generator.pt"), map_location="cpu")
    try:
        bigvgan_model.load_state_dict(generator_state["generator"])
    except RuntimeError:
        bigvgan_model.remove_weight_norm()
        bigvgan_model.load_state_dict(generator_state["generator"])
    bigvgan_model.remove_weight_norm()
    bigvgan_model = bigvgan_model.eval().to(device)

    spect = config["preprocess_params"]["spect_params"]
    mel_fn_args = {
        "n_fft": int(spect["n_fft"]),
        "win_size": int(spect["win_length"]),
        "hop_size": int(spect["hop_length"]),
        "num_mels": int(spect["n_mels"]),
        "sampling_rate": sr,
        "fmin": float(spect.get("fmin", 0) or 0),
        "fmax": None if str(spect.get("fmax", "None")) == "None" else 8000,
        "center": False,
    }

    def to_mel(wave: Any) -> Any:
        return mel_spectrogram(wave, **mel_fn_args)

    return {
        "model": model,
        "semantic_fn": semantic_fn,
        "vocoder_fn": bigvgan_model,
        "campplus_model": campplus_model,
        "to_mel": to_mel,
        "sr": sr,
        "hop_length": hop_length,
    }


def _load_vc(model_id: str, device: str) -> dict[str, Any]:
    global _vc, _vc_id
    if _vc is not None and _vc_id == model_id:
        return _vc
    _drop_vc()
    if model_id == "chatterbox":
        _vc = {
            "kind": "chatterbox",
            "model": _load_chatterbox_vc(device),
            "sr": _CHATTERBOX_SR,
            "device": device,
        }
    else:
        loaded = _load_seedvc_models(device)
        loaded["kind"] = "seedvc"
        loaded["device"] = device
        _vc = loaded
    _vc_id = model_id
    return _vc


def _normalize_segments(
    segments: list[dict[str, Any]] | None,
    duration: float,
    *,
    merge_gap: float = 0.05,
    min_segment: float = 0.02,
) -> list[tuple[float, float]]:
    if segments is None:
        return [(0.0, duration)]
    raw: list[tuple[float, float]] = []
    for item in segments:
        if isinstance(item, dict):
            start, end = item.get("start"), item.get("end")
        else:
            try:
                start, end = item[0], item[1]
            except (TypeError, IndexError, KeyError):
                continue
        try:
            start = max(0.0, min(duration, float(start)))
            end = max(0.0, min(duration, float(end)))
        except (TypeError, ValueError):
            continue
        if end - start >= min_segment:
            raw.append((start, end))
    raw.sort()
    merged: list[tuple[float, float]] = []
    for start, end in raw:
        if merged and start - merged[-1][1] < merge_gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _split_segment(start: float, end: float, max_window: float) -> list[tuple[float, float]]:
    length = end - start
    if length <= max_window:
        return [(start, end)]
    count = max(2, math.ceil(length / max_window))
    step = length / count
    return [(start + index * step, start + (index + 1) * step) for index in range(count)]


def _plan_windows(
    segments: list[tuple[float, float]],
    duration: float,
    *,
    max_window: float = _VC_MAX_WINDOW_S,
    context: float = _VC_CONTEXT_S,
) -> list[tuple[float, float, float, float]]:
    """返回 (窗口起点, 窗口终点, 写回起点, 写回终点)。"""
    windows: list[tuple[float, float, float, float]] = []
    for index, (start, end) in enumerate(segments):
        left = segments[index - 1][1] if index > 0 else 0.0
        right = segments[index + 1][0] if index + 1 < len(segments) else duration
        for piece_start, piece_end in _split_segment(start, end, max_window):
            win_start = max(piece_start - context, left, 0.0)
            win_end = min(piece_end + context, right, duration)
            if win_end - win_start >= 0.02:
                windows.append((win_start, win_end, piece_start, piece_end))
    return windows


def _resample(audio: Any, source_sr: int, target_sr: int) -> Any:
    import librosa

    if source_sr == target_sr:
        return audio
    return librosa.resample(audio, orig_sr=source_sr, target_sr=target_sr)


def _fit_length(audio: Any, length: int) -> Any:
    import numpy as np

    if length <= 0:
        return np.zeros(0, dtype=np.float32)
    if len(audio) >= length:
        return audio[:length]
    return np.pad(audio, (0, length - len(audio))).astype(np.float32)


def _fade_edges(audio: Any, sample_rate: int, fade_seconds: float = _VC_FADE_S) -> None:
    import numpy as np

    fade = min(int(fade_seconds * sample_rate), len(audio) // 2)
    if fade <= 0:
        return
    ramp = (np.cos(np.linspace(np.pi, 0, fade)) + 1.0) / 2.0
    audio[:fade] *= ramp
    audio[-fade:] *= ramp[::-1]


def _crossfade(chunk1: Any, chunk2: Any, overlap: int) -> Any:
    import numpy as np

    overlap = max(0, min(overlap, len(chunk1), len(chunk2)))
    if overlap == 0:
        return np.concatenate([chunk1, chunk2])
    fade_out = np.cos(np.linspace(0, np.pi / 2, overlap)) ** 2
    fade_in = np.cos(np.linspace(np.pi / 2, 0, overlap)) ** 2
    chunk2 = chunk2.copy()
    chunk2[:overlap] = chunk2[:overlap] * fade_in + chunk1[-overlap:] * fade_out
    return chunk2


def _chatterbox_convert(vc: dict[str, Any], window_path: Path) -> tuple[Any, int]:
    import numpy as np

    wave = vc["model"].generate(str(window_path))
    if hasattr(wave, "detach"):
        wave = wave.detach().cpu().numpy()
    audio = np.asarray(wave, dtype=np.float32).squeeze()
    return audio, int(_CHATTERBOX_SR)


def _seedvc_convert(
    window_path: Path,
    prompt: str,
    models: dict[str, Any],
    *,
    diffusion_steps: int = 10,
    inference_cfg_rate: float = 0.7,
    n_quantizers: int = 3,
    temperature: float = 1.0,
    length_adjust: float = 1.0,
    overlap_frame_len: int = 16,
) -> tuple[Any, int]:
    import librosa
    import numpy as np
    import torch
    import torchaudio

    device = models["device"]
    sr = int(models["sr"])
    hop_length = int(models["hop_length"])
    if not hasattr(torch, "autocast"):
        pass

    source_audio = librosa.load(str(window_path), sr=sr)[0]
    ref_audio = librosa.load(prompt, sr=sr)[0]
    if not len(source_audio):
        raise ValueError("源音频为空")
    if not len(ref_audio):
        raise ValueError("参考音频为空")

    source = torch.tensor(source_audio).unsqueeze(0).float().to(device)
    reference = torch.tensor(ref_audio[: sr * 25]).unsqueeze(0).float().to(device)
    source_16k = torchaudio.functional.resample(source, sr, 16000)
    reference_16k = torchaudio.functional.resample(reference, sr, 16000)
    semantic_fn = models["semantic_fn"]
    s_alt = semantic_fn(source_16k)
    s_ori = semantic_fn(reference_16k)

    mel_fn = models["to_mel"]
    mel = mel_fn(source.float())
    mel2 = mel_fn(reference.float())
    target_lengths = torch.LongTensor(
        [max(1, int(mel.size(2) * length_adjust))]
    ).to(mel.device)
    target2_lengths = torch.LongTensor([mel2.size(2)]).to(mel2.device)

    feat2 = torchaudio.compliance.kaldi.fbank(
        reference_16k,
        num_mel_bins=80,
        dither=0,
        sample_frequency=16000,
    )
    feat2 = feat2 - feat2.mean(dim=0, keepdim=True)
    feat2 = feat2.to(device)
    style2 = models["campplus_model"](feat2.unsqueeze(0))

    model = models["model"]
    cond, _, _, _, _ = model.length_regulator(
        s_alt, ylens=target_lengths, n_quantizers=n_quantizers, f0=None
    )
    prompt_condition, _, _, _, _ = model.length_regulator(
        s_ori, ylens=target2_lengths, n_quantizers=n_quantizers, f0=None
    )

    max_context_window = sr // hop_length * 30
    overlap_wave_len = overlap_frame_len * hop_length
    max_source_window = max_context_window - mel2.size(2)
    if max_source_window <= 0:
        raise ValueError("参考音频过长，Seed-VC 没有可用上下文窗口")

    processed_frames = 0
    generated: list[Any] = []
    previous = None
    vocoder = models["vocoder_fn"]
    while processed_frames < cond.size(1):
        chunk_cond = cond[:, processed_frames : processed_frames + max_source_window]
        is_last = processed_frames + max_source_window >= cond.size(1)
        cat_condition = torch.cat([prompt_condition, chunk_cond], dim=1)
        with torch.autocast(
            device_type=device,
            dtype=torch.float16,
            enabled=device.startswith("cuda"),
        ):
            vc_target = model.cfm.inference(
                cat_condition,
                torch.LongTensor([cat_condition.size(1)]).to(mel2.device),
                mel2,
                style2,
                None,
                diffusion_steps,
                temperature=temperature,
                inference_cfg_rate=inference_cfg_rate,
            )
            vc_target = vc_target[:, :, mel2.size(-1):]
        with torch.no_grad():
            vc_wave = vocoder(vc_target.float()).squeeze()
        vc_wave = vc_wave[None, :]
        if processed_frames == 0:
            if is_last:
                generated.append(vc_wave[0].cpu().numpy())
                break
            generated.append(vc_wave[0, :-overlap_wave_len].cpu().numpy())
            previous = vc_wave[0, -overlap_wave_len:]
            processed_frames += vc_target.size(2) - overlap_frame_len
        elif is_last:
            generated.append(
                _crossfade(previous.cpu().numpy(), vc_wave[0].cpu().numpy(), overlap_wave_len)
            )
            processed_frames += vc_target.size(2) - overlap_frame_len
            break
        else:
            generated.append(
                _crossfade(
                    previous.cpu().numpy(),
                    vc_wave[0, :-overlap_wave_len].cpu().numpy(),
                    overlap_wave_len,
                )
            )
            previous = vc_wave[0, -overlap_wave_len:]
            processed_frames += vc_target.size(2) - overlap_frame_len

    if not generated:
        raise ValueError("Seed-VC 没有生成音频")
    audio = np.concatenate([item.reshape(-1) for item in generated]).astype(np.float32)
    return audio, sr


def _pad_segments(
    segments: list[tuple[float, float]], duration: float, padding: float
) -> list[tuple[float, float]]:
    if padding <= 0:
        return segments
    padded = [
        {"start": max(0.0, start - padding), "end": min(duration, end + padding)}
        for start, end in segments
    ]
    return _normalize_segments(padded, duration, merge_gap=0.0, min_segment=0.0)


def _prepare_reference(
    prompt: Path,
    *,
    ref_start: float,
    ref_duration: float,
    ref_max_len: float | None,
    temp_dir: Path,
) -> Path:
    import librosa
    import soundfile as sf

    audio, sample_rate = librosa.load(str(prompt), sr=None, mono=True)
    if not len(audio) or sample_rate <= 0:
        raise ValueError("参考音频为空")
    total = len(audio) / float(sample_rate)
    start = max(0.0, min(ref_start, total))
    duration = ref_duration if ref_duration > 0 else max(0.0, total - start)
    if ref_max_len is not None:
        duration = min(duration, ref_max_len)
    if start <= 0 and duration >= total:
        return prompt
    end = min(total, start + duration)
    if end <= start:
        raise ValueError("参考音频切片为空")
    target = temp_dir / f"reference{Path(prompt).suffix or '.wav'}"
    sf.write(
        target,
        audio[int(start * sample_rate) : int(end * sample_rate)],
        sample_rate,
        subtype="PCM_16",
    )
    return target


def convert(
    source: str,
    *,
    model: str | None,
    prompt: str | None,
    segments: list[dict[str, Any]] | None,
    convert_all: bool = False,
    segment_padding: float = 0.0,
    merge_gap: float = 0.05,
    min_segment: float = 0.02,
    ref_start: float = 0.0,
    ref_duration: float = 0.0,
    ref_max_len: float | None = None,
    seed: int | None = None,
    diffusion_steps: int = 10,
    inference_cfg_rate: float = 0.7,
    n_quantizers: int = 3,
    temperature: float = 1.0,
    max_window: float = _VC_MAX_WINDOW_S,
    context: float = _VC_CONTEXT_S,
    fade: float = _VC_FADE_S,
    length_adjust: float = 1.0,
    overlap_frame_len: int = 16,
) -> tuple[Any, int]:
    """按分段换音，未覆盖区间保留原始输入。返回 (音频数组, 采样率)。"""
    import librosa
    import numpy as np
    import soundfile as sf

    model_id = resolve_vc_model(model)
    if not prompt or not Path(prompt).is_file():
        raise ValueError("参考音频不存在")
    if convert_all:
        if segments:
            raise ValueError("convert_all=true 时不能同时传 segments")
        segments = None
    audio, sample_rate = librosa.load(source, sr=None, mono=True)
    audio = np.asarray(audio, dtype=np.float32)
    if not len(audio):
        raise ValueError("源音频为空")
    duration = len(audio) / float(sample_rate)
    normalized = _normalize_segments(
        segments, duration, merge_gap=merge_gap, min_segment=min_segment
    )
    normalized = _pad_segments(normalized, duration, segment_padding)
    if not normalized:
        raise ValueError("没有可用的换音分段")
    windows = _plan_windows(normalized, duration, max_window=max_window, context=context)
    if not windows:
        raise ValueError("没有可用的换音分段")

    device = resolve_device()
    reference_max = (
        10.0 if model_id == "chatterbox" else (ref_max_len if ref_max_len is not None else 25.0)
    )
    with _lock:
        _drop_tts()
        _drop_asr()
        try:
            if seed is not None:
                import torch

                torch.manual_seed(int(seed))
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(int(seed))
            vc = _load_vc(model_id, device)
            with tempfile.TemporaryDirectory(prefix="liber-vc-") as temp:
                temp_dir = Path(temp)
                reference = _prepare_reference(
                    Path(prompt),
                    ref_start=ref_start,
                    ref_duration=ref_duration,
                    ref_max_len=reference_max,
                    temp_dir=temp_dir,
                )
                if model_id == "chatterbox":
                    vc["model"].set_target_voice(str(reference))
                output = audio.copy()
                for index, (win_start, win_end, seg_start, seg_end) in enumerate(windows):
                    window_path = temp_dir / f"window-{index:04d}.wav"
                    start_sample = max(0, round(win_start * sample_rate))
                    end_sample = min(len(audio), round(win_end * sample_rate))
                    sf.write(
                        window_path,
                        audio[start_sample:end_sample],
                        sample_rate,
                        subtype="PCM_16",
                    )
                    if model_id == "chatterbox":
                        converted, converted_sr = _chatterbox_convert(vc, window_path)
                    else:
                        converted, converted_sr = _seedvc_convert(
                            window_path,
                            str(reference),
                            vc,
                            diffusion_steps=diffusion_steps,
                            inference_cfg_rate=inference_cfg_rate,
                            n_quantizers=n_quantizers,
                            temperature=temperature,
                            length_adjust=length_adjust,
                            overlap_frame_len=overlap_frame_len,
                        )
                    converted = _resample(
                        np.asarray(converted, dtype=np.float32), converted_sr, sample_rate
                    )
                    window_len = max(0, round((win_end - win_start) * sample_rate))
                    converted = _fit_length(converted, window_len)
                    crop_start = round((seg_start - win_start) * sample_rate)
                    crop_end = round((seg_end - win_start) * sample_rate)
                    crop = converted[crop_start:crop_end]
                    write_start = max(0, round(seg_start * sample_rate))
                    write_end = min(len(output), round(seg_end * sample_rate))
                    crop = _fit_length(crop, write_end - write_start)
                    _fade_edges(crop, sample_rate, fade)
                    output[write_start:write_end] = crop
            return output, sample_rate
        finally:
            _drop_vc()


def separate(source: str) -> tuple[Any, Any, int]:
    """用 Demucs 分离 vocals / accompaniment，返回两个 [channels, samples] 数组。"""
    import numpy as np
    import torchaudio
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    if not separate_available():
        raise ValueError("Demucs 不可用：缺少依赖或 /models/demucs 权重")
    device = resolve_device()
    with _lock:
        _drop_tts()
        _drop_asr()
        try:
            _ensure_demucs_compat()
            model = get_model("htdemucs")
            model.to(device)
            model.eval()
            _separator = model
            wave, sr = torchaudio.load(source)
            if wave.size(0) == 1:
                wave = wave.repeat(2, 1)
            if sr != model.samplerate:
                wave = torchaudio.functional.resample(wave, sr, model.samplerate)
            ref = wave.mean(0)
            wave = (wave - ref.mean()) / (ref.std() + 1e-8)
            sources = apply_model(
                model,
                wave[None],
                device=device,
                shifts=1,
                split=True,
                overlap=0.25,
                progress=False,
            )[0]
            sources = sources * ref.std() + ref.mean()
            vocals = sources[model.sources.index("vocals")]
            accompaniment = sources.sum(0) - vocals
            return (
                vocals.detach().cpu().numpy().astype(np.float32),
                accompaniment.detach().cpu().numpy().astype(np.float32),
                int(model.samplerate),
            )
        finally:
            _drop_separator()

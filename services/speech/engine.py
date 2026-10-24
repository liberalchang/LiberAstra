"""语音引擎：ASR 用 faster-whisper，TTS 用 Chatterbox 的 11 个模型包。

模型包在首次合成时下载。同时只保留一个已加载的 TTS 引擎，换包时丢掉旧对象。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from threading import Lock

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
    raw = os.getenv("LIBER_SPEECH_TTS_MODEL", "multilingual").strip() or "multilingual"
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


def configured_models() -> list[dict[str, str]]:
    """当前配置的 ASR / TTS 模型名。语言代码不是模型。"""
    asr = os.getenv("LIBER_SPEECH_ASR_MODEL", "large-v3")
    tts = default_tts_model()
    label = _SPECS.get(tts, {}).get("label", tts)
    return [
        {"name": f"faster-whisper-{asr}", "role": "ASR"},
        {"name": label, "role": "TTS"},
    ]


def asr_ready() -> bool:
    return _asr is not None


def tts_ready() -> bool:
    return _tts is not None


def _drop_tts() -> None:
    """丢掉当前引擎，并尽量交还显存。"""
    global _tts, _tts_id
    _tts = None
    _tts_id = ""
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


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
    """同一时间只留一个引擎。模型没变时复用。"""
    global _tts, _tts_id
    with _lock:
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
) -> tuple[object, int]:
    """返回 (waveform tensor, sample_rate)。"""
    model_id = resolve_model(model)
    spec = _SPECS[model_id]
    language_id = _checked_language(spec, language)
    engine = _load_tts(model_id)
    kwargs: dict = {"audio_prompt_path": audio_prompt}
    if language_id:
        kwargs["language_id"] = language_id
    try:
        wav = engine.generate(text, **kwargs)
    except AssertionError as exc:
        message = str(exc)
        if "5 seconds" in message:
            raise ValueError("Turbo / Nano 的参考音频需要长于 5 秒") from exc
        raise ValueError(message) from exc
    return wav, int(engine.sr)


def transcribe(audio_path: str, *, language: str | None, task: str) -> dict:
    """faster-whisper 转写。language 为空时自动识别。"""
    global _asr, _asr_name
    name = os.getenv("LIBER_SPEECH_ASR_MODEL", "large-v3")
    with _lock:
        if _asr is None or _asr_name != name:
            from faster_whisper import WhisperModel

            _asr = WhisperModel(name, device=resolve_device(), compute_type="float16")
            _asr_name = name
        model = _asr
    segments, info = model.transcribe(audio_path, language=language or None, task=task)
    chunks = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    return {
        "text": "".join(c["text"] for c in chunks).strip(),
        "chunks": chunks,
        "language": info.language,
    }

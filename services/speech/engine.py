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
    if name.startswith("faster-whisper-"):
        name = name[len("faster-whisper-") :]
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
                return _transcribe_qwen(audio_path, language, model_id)
            return _transcribe_whisper(audio_path, language, task, model_id)
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


def _transcribe_whisper(audio_path: str, language: str | None, task: str, model_id: str) -> dict:
    global _asr, _asr_name
    from faster_whisper import WhisperModel

    target = _whisper_load_target(model_id)
    _asr = WhisperModel(target, device=resolve_device(), compute_type="float16")
    _asr_name = model_id
    segments, info = _asr.transcribe(audio_path, language=language or None, task=task)
    chunks = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    public = model_id if not _is_filesystem_model(model_id) else Path(model_id).name
    return {
        "text": "".join(c["text"] for c in chunks).strip(),
        "chunks": chunks,
        "language": info.language,
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
    import transformers.utils.generic as generic

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
    from qwen_asr.core.transformers_backend.configuration_qwen3_asr import Qwen3ASRThinkerConfig

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
        if isinstance(cls, type) and "RotaryEmbedding" in cls.__name__:
            if "compute_default_rope_parameters" not in cls.__dict__:
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


def _transcribe_qwen(audio_path: str, language: str | None, model_id: str) -> dict:
    global _asr, _asr_name
    import torch

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
        max_inference_batch_size=4,
        max_new_tokens=512,
        forced_aligner=aligner,
        forced_aligner_kwargs={"dtype": dtype, "device_map": device},
    )
    _asr_name = "qwen3-asr-1.7b"
    qwen_language = _qwen_language(language)
    results = _asr.transcribe(
        audio=audio_path,
        language=qwen_language,
        return_time_stamps=True,
    )
    first = results[0] if results else None
    text = str(getattr(first, "text", "") or "").strip()
    stamps = getattr(first, "time_stamps", None) if first is not None else None
    items = list(stamps) if stamps is not None else []
    chunks = _aggregate_qwen_chunks(items)
    if not chunks and text:
        chunks = [{"start": 0.0, "end": 0.0, "text": text}]
    detected = _iso_from_qwen(getattr(first, "language", None) if first is not None else None)
    return {
        "text": text or "".join(c["text"] for c in chunks).strip(),
        "chunks": chunks,
        "language": detected or (language or None),
        "model": "qwen3-asr-1.7b",
    }

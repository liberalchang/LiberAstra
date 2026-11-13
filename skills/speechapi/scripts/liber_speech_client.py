from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

DEFAULT_TIMEOUT = 120
# 首次合成要加载 Chatterbox，短超时会在模型还没就绪时断开。
TTS_TIMEOUT = 600

# 局域网地址不要走系统代理。
_session = requests.Session()
_session.trust_env = False

VALID_TTS_FORMATS = {"wav", "ogg", "ogg_opus"}
VALID_ASR_OUTPUTS = {"json", "text", "srt", "vtt"}
VALID_API_VERSIONS = {"auto", "v1", "v2"}
V1_TTS_FIELDS = {"text", "model", "language", "format"}
V1_ASR_FIELDS = {"language", "task", "model"}

_version_cache: dict[str, str] = {}


class ConfigError(RuntimeError):
    """Raised when configuration is invalid."""


class ApiError(RuntimeError):
    """Raised when API request fails."""


def _request(
    method: str, url: str, *, retries: int = 0, **kwargs: Any
) -> requests.Response:
    """使用不走代理的 session 发请求；连接错误/超时/5xx 可重试。"""
    delay = 0.8
    for attempt in range(retries + 1):
        try:
            response = _session.request(method, url, **kwargs)
        except (requests.ConnectionError, requests.Timeout):
            if attempt >= retries:
                raise
            time.sleep(delay)
            delay *= 2
            continue
        if response.status_code >= 500 and attempt < retries:
            time.sleep(delay)
            delay *= 2
            continue
        return response
    raise ApiError("request failed")


def split_api_base(base_url: str) -> tuple[str, str]:
    """把 .../api/v1、.../api/v2 或裸地址拆成 (origin, version_hint)。"""
    raw = (base_url or "").strip().rstrip("/")
    for version in ("v2", "v1"):
        suffix = f"/api/{version}"
        if raw.endswith(suffix):
            return raw[: -len(suffix)], version
    return raw, "auto"


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config_json(config_path: Path) -> dict[str, Any]:
    default_config = {
        "asr": {"language": "zh", "task": "transcribe", "model": "default", "options": {}},
        "tts": {
            "model": "multilingual_v3",
            "language": "zh",
            "format": "wav",
            "audio_prompt_path": "default",
            "options": {},
        },
        "vc": {"model": "seed-vc", "convert_all": True, "options": {}},
        "global": {
            "voice_summary_limit": 100,
            "default_clone_audio": "tmp/clone.wav",
            "telegram_tts_format": "ogg_opus",
            "asr_output": "json",
            "api_version": "auto",
        },
    }

    if not config_path.exists():
        return default_config

    try:
        user_config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigError(f"Failed to load config.json: {exc}") from exc

    merged_config = copy.deepcopy(default_config)
    for section in ("asr", "tts", "vc", "global"):
        if not isinstance(user_config.get(section), dict):
            continue
        for key, value in user_config[section].items():
            if key == "timestamp":
                key = "timestamps"
            if key == "options" and isinstance(value, dict):
                merged_config[section].setdefault("options", {}).update(value)
            else:
                merged_config[section][key] = value

    return merged_config


def load_env(
    base_url_override: str | None = None,
    api_key_override: str | None = None,
    config_path_override: str | None = None,
    api_version_override: str | None = None,
) -> dict[str, Any]:
    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent

    base_url = (base_url_override or os.getenv("LIBER_API_BASE_URL", "")).strip().rstrip("/")
    api_key = (api_key_override or os.getenv("LIBER_API_KEY", "")).strip()

    if not base_url or not api_key:
        openclaw_env_path = Path.home() / ".openclaw" / ".env"
        load_dotenv(openclaw_env_path)
        base_url = (base_url_override or os.getenv("LIBER_API_BASE_URL", "")).strip().rstrip("/")
        api_key = (api_key_override or os.getenv("LIBER_API_KEY", "")).strip()

    if not base_url or not api_key:
        for candidate in (skill_dir / ".env", Path.cwd() / ".env"):
            load_dotenv(candidate)
            base_url = (base_url_override or os.getenv("LIBER_API_BASE_URL", "")).strip().rstrip("/")
            api_key = (api_key_override or os.getenv("LIBER_API_KEY", "")).strip()
            if base_url and api_key:
                break

    if not base_url:
        raise ConfigError(
            "Missing LIBER_API_BASE_URL. Please set it in environment variables, "
            "~/.openclaw/.env, or local .env file"
        )
    if not api_key:
        raise ConfigError(
            "Missing LIBER_API_KEY. Please set it in environment variables, "
            "~/.openclaw/.env, or local .env file"
        )

    if config_path_override:
        config_json = load_config_json(Path(config_path_override))
    else:
        config_path = (
            Path.home() / ".openclaw" / "workspace" / "config" / "speechapi_config.json"
        )
        if config_path.exists():
            config_json = load_config_json(config_path)
        else:
            local_config = skill_dir / "speechapi_config.json"
            if not local_config.exists():
                local_config = skill_dir / "config.json"
            config_json = load_config_json(local_config)

    origin, hint = split_api_base(base_url)
    configured = (
        api_version_override
        or os.getenv("LIBER_API_VERSION", "")
        or config_json["global"].get("api_version")
        or "auto"
    ).strip().lower()
    if configured not in VALID_API_VERSIONS:
        configured = "auto"
    api_version = hint if configured == "auto" and hint in {"v1", "v2"} else configured

    return {
        "base_url": base_url,
        "origin": origin,
        "api_version": api_version,
        "api_key": api_key,
        "config_json": config_json,
        "skill_dir": skill_dir,
    }


def build_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def process_parameter(value: Any) -> Any:
    if value == "default" or value is None:
        return None
    return value


def _section_payload(
    config: dict[str, Any],
    section: str,
    overrides: dict[str, Any],
    *,
    skip: tuple[str, ...] = (),
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    section_config = config["config_json"][section]
    for key, value in section_config.items():
        if key in skip or key == "options":
            continue
        processed = process_parameter(value)
        if processed is not None:
            payload[key] = processed

    merged_options = dict(section_config.get("options") or {})
    for key, value in overrides.items():
        if value is not None:
            merged_options[key] = value
    for key, value in merged_options.items():
        processed = process_parameter(value)
        if processed is not None:
            payload[key] = processed
    return payload


def build_asr_payload(config: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    return _section_payload(config, "asr", overrides)


def build_tts_payload(config: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    return _section_payload(config, "tts", overrides, skip=("audio_prompt_path",))


def build_vc_payload(config: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    return _section_payload(config, "vc", overrides)


def ensure_v1_compatible(function: str, payload: dict[str, Any]) -> None:
    allowed = V1_TTS_FIELDS if function == "tts" else V1_ASR_FIELDS
    extra = sorted(set(payload) - allowed)
    if extra:
        raise ConfigError(
            f"服务端是 v1，不支持参数 {', '.join(extra)}；请升级语音服务或显式使用 --api-version v2"
        )


def resolve_api_version(
    config: dict[str, Any],
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> str:
    configured = str(config.get("api_version") or "auto").lower()
    if configured in {"v1", "v2"}:
        return configured

    origin = config["origin"]
    if origin in _version_cache:
        version = _version_cache[origin]
        config["api_version"] = version
        return version

    version = "v1"
    try:
        response = _request(
            "GET",
            f"{origin}/api/v2/help",
            headers=build_headers(config["api_key"]),
            timeout=timeout or DEFAULT_TIMEOUT,
            retries=retries,
        )
        if response.status_code == 200:
            version = "v2"
    except requests.RequestException:
        version = "v1"
    _version_cache[origin] = version
    config["api_version"] = version
    return version


def api_url(config: dict[str, Any], path: str, *, version: str | None = None) -> str:
    resolved = version or resolve_api_version(config)
    return f"{config['origin']}/api/{resolved}/{path.lstrip('/')}"


def resolve_clone_audio(config: dict[str, Any], override: str | None = None) -> Path | None:
    tts_audio_prompt = config["config_json"]["tts"].get("audio_prompt_path")
    clone_audio_config = config["config_json"]["global"].get("default_clone_audio")
    raw_value = override if override is not None else tts_audio_prompt

    if raw_value in (None, "default"):
        raw_value = clone_audio_config
    if raw_value is None:
        return None

    value = str(raw_value).strip()
    if not value or value.lower() == "none" or value == "default":
        return None

    path = Path(value)
    if not path.is_absolute():
        path = config["skill_dir"] / value

    return path if path.exists() and path.is_file() else None


def upload_file(
    config: dict[str, Any],
    path: Path,
    *,
    version: str | None = None,
    timeout: float | None = None,
    retries: int = 0,
) -> str:
    if (version or resolve_api_version(config)) != "v2":
        raise ConfigError("文件上传需要语音服务 /api/v2")
    with path.open("rb") as handle:
        response = _request(
            "POST",
            api_url(config, "files"),
            headers=build_headers(config["api_key"]),
            files={"file": (path.name, handle)},
            timeout=timeout or TTS_TIMEOUT,
            retries=retries,
        )
    _raise_for_status(response, "file upload failed")
    file_id = response.json().get("file_id")
    if not isinstance(file_id, str) or not file_id.strip():
        raise ApiError("file upload returned empty file_id")
    return file_id


def audio_extension(fmt: str) -> str:
    """ogg_opus 的文件后缀是 .ogg。"""
    if fmt in {"ogg", "ogg_opus"}:
        return "ogg"
    return "wav"


def download_audio_file(
    config: dict[str, Any],
    audio_url: str,
    output_path: str | None = None,
    fmt: str = "wav",
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> Path | None:
    try:
        if audio_url.startswith("http"):
            full_url = audio_url
        else:
            full_url = f"{config['origin']}{audio_url}"

        if output_path:
            target_path = Path(output_path)
        else:
            results_dir = config["skill_dir"] / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = results_dir / f"tts_{timestamp}.{audio_extension(fmt)}"

        target_path.parent.mkdir(parents=True, exist_ok=True)
        response = _request(
            "GET",
            full_url,
            headers=build_headers(config["api_key"]),
            timeout=timeout or DEFAULT_TIMEOUT,
            retries=retries,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type.lower():
            raise ApiError(f"Server returned error: {response.text[:500]}")

        target_path.write_bytes(response.content)
        if target_path.stat().st_size == 0:
            raise ApiError("Downloaded file is empty")
        return target_path
    except requests.RequestException:
        raise
    except Exception as exc:
        raise ApiError(f"Failed to download audio file: {exc}") from exc


def check_health(
    config: dict[str, Any], *, timeout: float | None = None, retries: int = 0
) -> dict[str, Any]:
    response = _request(
        "GET",
        f"{config['origin']}/api/v1/health",
        headers=build_headers(config["api_key"]),
        timeout=timeout or DEFAULT_TIMEOUT,
        retries=retries,
    )
    _raise_for_status(response, "health check failed")
    return response.json()


def list_models(
    config: dict[str, Any], *, timeout: float | None = None, retries: int = 0
) -> dict[str, Any]:
    version = resolve_api_version(config)
    response = _request(
        "GET",
        api_url(config, "models", version=version),
        headers=build_headers(config["api_key"]),
        timeout=timeout or DEFAULT_TIMEOUT,
        retries=retries,
    )
    _raise_for_status(response, "models request failed")
    return response.json()


def fetch_help(
    config: dict[str, Any],
    function: str | None = None,
    model: str | None = None,
    *,
    include: str | None = None,
    fmt: str = "json",
    timeout: float | None = None,
    retries: int = 0,
) -> dict[str, Any] | str:
    if model and not function:
        raise ValueError("指定 model 时必须同时指定 function")
    if fmt not in {"json", "markdown"}:
        raise ValueError(f"Invalid help format: {fmt}")
    if resolve_api_version(config) != "v2":
        raise ConfigError("Help 接口需要语音服务 /api/v2")

    path = "help"
    if function:
        path += f"/{function}"
        if model:
            path += f"/{model}"
    params: dict[str, str] = {"format": fmt}
    if include:
        params["include"] = include
    response = _request(
        "GET",
        api_url(config, path),
        headers=build_headers(config["api_key"]),
        params=params,
        timeout=timeout or DEFAULT_TIMEOUT,
        retries=retries,
    )
    _raise_for_status(response, "help request failed")
    return response.text if fmt == "markdown" else response.json()


def transcribe_file(
    audio_path: str,
    language: str | None = None,
    task: str | None = None,
    model: str | None = None,
    output: str | None = None,
    options: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    retries: int = 0,
) -> dict[str, Any] | str:
    config = load_env(base_url, api_key)
    file_path = Path(audio_path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    default_output = (
        str(config["config_json"]["global"].get("asr_output", "json")).strip().lower()
        or "json"
    )
    output_mode = (output or default_output).strip().lower()
    if output_mode not in VALID_ASR_OUTPUTS:
        raise ValueError(f"Invalid ASR output mode: {output_mode}")

    overrides = {"language": language, "task": task, "model": model}
    overrides.update(options or {})
    payload = build_asr_payload(config, overrides)
    version = resolve_api_version(config)

    if version == "v2":
        payload["file_id"] = upload_file(config, file_path, version=version)
        if output_mode != "json":
            payload["response_format"] = output_mode
        response = _request(
            "POST",
            api_url(config, "asr/transcribe", version=version),
            headers=build_headers(config["api_key"]),
            json=payload,
            timeout=timeout or TTS_TIMEOUT,
            retries=retries,
        )
        _raise_for_status(response, "ASR transcription failed")
        if output_mode != "json":
            text = response.text
            if not text.strip():
                raise ApiError("ASR succeeded but returned empty text")
            return text
        result = response.json()
    else:
        ensure_v1_compatible("asr", payload)
        with file_path.open("rb") as handle:
            response = _request(
                "POST",
                api_url(config, "asr/transcribe", version=version),
                headers=build_headers(config["api_key"]),
                data=payload,
                files={"file": (file_path.name, handle)},
                timeout=timeout or TTS_TIMEOUT,
                retries=retries,
            )
        _raise_for_status(response, "ASR transcription failed")
        result = response.json()

    text = result.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise ApiError("ASR succeeded but returned empty text")
    return text if output_mode == "text" else result


def synthesize_text(
    text: str,
    language: str | None = None,
    model: str | None = None,
    fmt: str | None = None,
    clone_audio: str | None = None,
    telegram: bool = False,
    output_path: str | None = None,
    options: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    retries: int = 0,
) -> dict[str, Any]:
    config = load_env(base_url, api_key)
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        raise ValueError("TTS text must not be empty")

    default_format = str(config["config_json"]["tts"].get("format", "wav")).strip() or "wav"
    telegram_format = (
        str(config["config_json"]["global"].get("telegram_tts_format", "ogg_opus")).strip()
        or "ogg_opus"
    )
    effective_format = telegram_format if telegram else (fmt or default_format)
    if effective_format not in VALID_TTS_FORMATS:
        raise ValueError(f"Invalid TTS format: {effective_format}")

    overrides = {
        "text": cleaned_text,
        "language": language,
        "model": model,
        "format": effective_format,
    }
    overrides.update(options or {})
    payload = build_tts_payload(config, overrides)
    version = resolve_api_version(config)
    clone_path = resolve_clone_audio(config, clone_audio)

    if version == "v2":
        if clone_path is not None:
            payload["prompt_file_id"] = upload_file(config, clone_path, version=version)
        response = _request(
            "POST",
            api_url(config, "tts/synthesize", version=version),
            headers=build_headers(config["api_key"]),
            json=payload,
            timeout=timeout or TTS_TIMEOUT,
            retries=retries,
        )
    else:
        ensure_v1_compatible("tts", payload)
        files = None
        if clone_path is not None:
            with clone_path.open("rb") as handle:
                files = {"prompt": (clone_path.name, handle)}
                response = _request(
                    "POST",
                    api_url(config, "tts/synthesize", version=version),
                    headers=build_headers(config["api_key"]),
                    data=payload,
                    files=files,
                    timeout=timeout or TTS_TIMEOUT,
                    retries=retries,
                )
        else:
            response = _request(
                "POST",
                api_url(config, "tts/synthesize", version=version),
                headers=build_headers(config["api_key"]),
                data=payload,
                timeout=timeout or TTS_TIMEOUT,
                retries=retries,
            )

    _raise_for_status(response, "TTS synthesis failed")
    result = response.json()
    audio_url = result.get("audio_url", "")
    if not isinstance(audio_url, str) or not audio_url.strip():
        raise ApiError("TTS succeeded but returned empty audio_url")

    local_path = download_audio_file(
        config,
        audio_url,
        output_path,
        effective_format,
        timeout=timeout,
        retries=retries,
    )
    if local_path:
        result["local_path"] = str(local_path)
    return result


def convert_voice(
    source_path: str,
    prompt_path: str,
    model: str | None = None,
    convert_all: bool | None = None,
    segments: list[dict[str, float]] | None = None,
    output_path: str | None = None,
    options: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    retries: int = 0,
) -> dict[str, Any]:
    config = load_env(base_url, api_key)
    if resolve_api_version(config) != "v2":
        raise ConfigError("换音需要语音服务 /api/v2")

    source = Path(source_path)
    prompt = Path(prompt_path)
    if not source.is_file():
        raise FileNotFoundError(f"Source audio not found: {source}")
    if not prompt.is_file():
        raise FileNotFoundError(f"Prompt audio not found: {prompt}")

    overrides = {
        "model": model,
        "convert_all": convert_all,
        "segments": segments,
    }
    overrides.update(options or {})
    payload = build_vc_payload(config, overrides)
    payload["file_id"] = upload_file(config, source)
    payload["prompt_file_id"] = upload_file(config, prompt)
    response = _request(
        "POST",
        api_url(config, "vc/convert"),
        headers=build_headers(config["api_key"]),
        json=payload,
        timeout=timeout or TTS_TIMEOUT,
        retries=retries,
    )
    _raise_for_status(response, "VC conversion failed")
    result = response.json()
    audio_url = result.get("audio_url", "")
    if not isinstance(audio_url, str) or not audio_url.strip():
        raise ApiError("VC succeeded but returned empty audio_url")

    if output_path is None:
        results_dir = config["skill_dir"] / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(results_dir / f"vc_{timestamp}.wav")
    local_path = download_audio_file(
        config,
        audio_url,
        output_path,
        "wav",
        timeout=timeout,
        retries=retries,
    )
    if local_path:
        result["local_path"] = str(local_path)
    return result


def _raise_for_status(response: requests.Response, message: str) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:1000]
        raise ApiError(f"{message}: HTTP {response.status_code}: {detail}") from exc


AUDIO_SUFFIXES = {
    ".wav",
    ".mp3",
    ".ogg",
    ".opus",
    ".flac",
    ".m4a",
    ".aac",
    ".mp4",
}


def expand_audio_paths(paths: list[str]) -> list[Path]:
    """展开目录；保留显式文件路径，交给 transcribe_file 校验。"""
    expanded: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            expanded.extend(
                sorted(
                    item
                    for item in path.iterdir()
                    if item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES
                )
            )
        else:
            expanded.append(path)
    return expanded


def _exit_code(exc: Exception) -> int:
    if isinstance(exc, (ConfigError, FileNotFoundError, ValueError, TypeError)):
        return 2
    if isinstance(exc, requests.RequestException):
        return 3
    if isinstance(exc, ApiError):
        return 4
    return 1


def _json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--params 不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TypeError("--params 必须是 JSON 对象")
    return data


def _segments_object(raw: str | None) -> list[dict[str, float]] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--segments 不是合法 JSON: {exc}") from exc
    if not isinstance(data, list):
        raise TypeError("--segments 必须是 JSON 数组")
    return data


def main() -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", default=None)
    common.add_argument("--api-key", default=None)
    common.add_argument("--api-version", choices=sorted(VALID_API_VERSIONS), default=None)
    common.add_argument("--timeout", type=float, default=None)
    common.add_argument("--retries", type=int, default=0)

    parser = argparse.ArgumentParser(description="Liber SpeechAPI client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", parents=[common], help="Run health check")
    subparsers.add_parser("models", parents=[common], help="List server models")

    help_parser = subparsers.add_parser("help", parents=[common], help="Fetch v2 parameter help")
    help_parser.add_argument("function", nargs="?", default=None, choices=("tts", "asr", "vc"))
    help_parser.add_argument("model", nargs="?", default=None)
    help_parser.add_argument("--include", default=None)
    help_parser.add_argument("--format", choices=("json", "markdown"), default="json")

    asr_parser = subparsers.add_parser(
        "asr", parents=[common], help="Transcribe one or more audio files"
    )
    asr_parser.add_argument("audio_paths", nargs="+", help="Audio file(s) or a directory")
    asr_parser.add_argument("--language", default=None)
    asr_parser.add_argument("--task", default=None, choices=("transcribe", "translate"))
    asr_parser.add_argument(
        "--model",
        default=None,
        help="large-v3、large-v3-turbo 或 qwen3-asr-1.7b。不传则用配置；配置为 default 时跟随服务端环境变量",
    )
    asr_parser.add_argument("--output", choices=sorted(VALID_ASR_OUTPUTS), default=None)
    asr_parser.add_argument("--timestamps", choices=("none", "segment", "word"), default=None)
    asr_parser.add_argument("--initial-prompt", default=None)
    asr_parser.add_argument("--hotwords", default=None)
    asr_parser.add_argument("--beam-size", type=int, default=None)
    asr_parser.add_argument(
        "--vad-filter",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    asr_parser.add_argument(
        "--condition-on-previous-text",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    asr_parser.add_argument("--params", default=None, help="额外 JSON 参数")

    tts_parser = subparsers.add_parser("tts", parents=[common], help="Synthesize text")
    tts_parser.add_argument("text", help="Text to synthesize")
    tts_parser.add_argument("--language", default=None)
    tts_parser.add_argument("--model", default=None)
    tts_parser.add_argument("--format", choices=sorted(VALID_TTS_FORMATS), default=None)
    tts_parser.add_argument("--clone-audio", default=None, help="参考音频，v2 会先上传")
    tts_parser.add_argument("--telegram", action="store_true", help="Force Telegram ogg_opus output")
    tts_parser.add_argument("--speed", type=float, default=None)
    tts_parser.add_argument("--exaggeration", type=float, default=None)
    tts_parser.add_argument("--cfg-weight", type=float, default=None)
    tts_parser.add_argument("--temperature", type=float, default=None)
    tts_parser.add_argument("--top-p", type=float, default=None)
    tts_parser.add_argument("--top-k", type=int, default=None)
    tts_parser.add_argument("--repetition-penalty", type=float, default=None)
    tts_parser.add_argument("--min-p", type=float, default=None)
    tts_parser.add_argument(
        "--normalize-loudness",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    tts_parser.add_argument("--target-lufs", type=float, default=None)
    tts_parser.add_argument("--ref-start", type=float, default=None)
    tts_parser.add_argument("--ref-duration", type=float, default=None)
    tts_parser.add_argument("--params", default=None, help="额外 JSON 参数")
    tts_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: results/tts_YYYYMMDD_HHMMSS.wav)",
    )

    vc_parser = subparsers.add_parser("vc", parents=[common], help="Convert voice")
    vc_parser.add_argument("source", help="Source audio/video")
    vc_parser.add_argument("--prompt", required=True, help="Target voice reference audio")
    vc_parser.add_argument("--model", default=None)
    vc_parser.add_argument(
        "--convert-all",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="替换整段；默认跟随配置",
    )
    vc_parser.add_argument("--segments", default=None, help="JSON 数组 [{start,end}]")
    vc_parser.add_argument("--seed", type=int, default=None)
    vc_parser.add_argument("--diffusion-steps", type=int, default=None)
    vc_parser.add_argument("--inference-cfg-rate", type=float, default=None)
    vc_parser.add_argument("--denoise", action=argparse.BooleanOptionalAction, default=None)
    vc_parser.add_argument("--params", default=None, help="额外 JSON 参数")
    vc_parser.add_argument("--output", "-o", default=None)

    args = parser.parse_args()

    try:
        config = load_env(
            args.base_url,
            args.api_key,
            api_version_override=args.api_version,
        )
        if args.command == "health":
            result: Any = check_health(config, timeout=args.timeout, retries=args.retries)
        elif args.command == "models":
            result = list_models(config, timeout=args.timeout, retries=args.retries)
        elif args.command == "help":
            result = fetch_help(
                config,
                args.function,
                args.model,
                include=args.include,
                fmt=args.format,
                timeout=args.timeout,
                retries=args.retries,
            )
        elif args.command == "asr":
            paths = expand_audio_paths(args.audio_paths)
            if not paths:
                raise FileNotFoundError("No audio files found")
            if len(paths) > 1 and args.output:
                raise ValueError("--output 只能用于单个输入；批量结果写在输入文件旁边")
            options = _json_object(args.params)
            for key, value in {
                "timestamps": args.timestamps,
                "initial_prompt": args.initial_prompt,
                "hotwords": args.hotwords,
                "beam_size": args.beam_size,
                "vad_filter": args.vad_filter,
                "condition_on_previous_text": args.condition_on_previous_text,
            }.items():
                if value is not None:
                    options[key] = value

            items: list[Any] = []
            for path in paths:
                item = transcribe_file(
                    audio_path=str(path),
                    language=args.language,
                    task=args.task,
                    model=args.model,
                    output=args.output if len(paths) == 1 else None,
                    options=options,
                    base_url=args.base_url,
                    api_key=args.api_key,
                    timeout=args.timeout,
                    retries=args.retries,
                )
                if len(paths) > 1:
                    suffix = {
                        "json": ".json",
                        "text": ".txt",
                        "srt": ".srt",
                        "vtt": ".vtt",
                    }.get(args.output or "json", ".json")
                    out_path = path.with_suffix(suffix)
                    out_path.write_text(
                        json.dumps(item, ensure_ascii=False, indent=2)
                        if isinstance(item, dict)
                        else item,
                        encoding="utf-8",
                    )
                    items.append({"input": str(path), "output": str(out_path), "result": item})
                else:
                    items.append(item)
            result = items[0] if len(items) == 1 else items
        elif args.command == "tts":
            options = _json_object(args.params)
            for key, value in {
                "speed": args.speed,
                "exaggeration": args.exaggeration,
                "cfg_weight": args.cfg_weight,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "top_k": args.top_k,
                "repetition_penalty": args.repetition_penalty,
                "min_p": args.min_p,
                "normalize_loudness": args.normalize_loudness,
                "target_lufs": args.target_lufs,
                "ref_start": args.ref_start,
                "ref_duration": args.ref_duration,
            }.items():
                if value is not None:
                    options[key] = value
            result = synthesize_text(
                text=args.text,
                language=args.language,
                model=args.model,
                fmt=args.format,
                clone_audio=args.clone_audio,
                telegram=args.telegram,
                output_path=args.output,
                options=options,
                base_url=args.base_url,
                api_key=args.api_key,
                timeout=args.timeout,
                retries=args.retries,
            )
        elif args.command == "vc":
            options = _json_object(args.params)
            for key, value in {
                "seed": args.seed,
                "diffusion_steps": args.diffusion_steps,
                "inference_cfg_rate": args.inference_cfg_rate,
                "denoise": args.denoise,
            }.items():
                if value is not None:
                    options[key] = value
            result = convert_voice(
                source_path=args.source,
                prompt_path=args.prompt,
                model=args.model,
                convert_all=args.convert_all,
                segments=_segments_object(args.segments),
                output_path=args.output,
                options=options,
                base_url=args.base_url,
                api_key=args.api_key,
                timeout=args.timeout,
                retries=args.retries,
            )
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")

        if isinstance(result, str):
            print(result)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001 - CLI 统一转成退出码
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(_exit_code(exc))


if __name__ == "__main__":
    main()

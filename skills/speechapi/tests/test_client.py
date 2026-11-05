"""Liber SpeechAPI 客户端纯函数测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import liber_speech_client as client  # noqa: E402


def _config(tmp_path: Path, **overrides) -> dict:
    data = {
        "asr": {"language": "zh", "task": "transcribe", "model": "default"},
        "tts": {
            "model": "multilingual_v3",
            "language": "zh",
            "format": "wav",
            "audio_prompt_path": "default",
        },
        "global": {
            "voice_summary_limit": 100,
            "default_clone_audio": "tmp/clone.wav",
            "telegram_tts_format": "ogg_opus",
            "asr_output": "json",
        },
    }
    for section, values in overrides.items():
        data[section].update(values)
    return {"base_url": "http://speech:5555/api/v1", "api_key": "k", "config_json": data, "skill_dir": tmp_path}


def test_build_asr_params_omits_default() -> None:
    params = client.build_asr_params(_config(Path(".")), {})
    assert params == {"language": "zh", "task": "transcribe"}


def test_build_tts_params_includes_text() -> None:
    params = client.build_tts_params(_config(Path(".")), {"text": "hello"})
    assert params["text"] == "hello"
    assert params["model"] == "multilingual_v3"
    assert params["format"] == "wav"


def test_resolve_clone_audio_requires_existing_file(tmp_path: Path) -> None:
    config = _config(tmp_path, tts={"audio_prompt_path": "missing.wav"})
    assert client.resolve_clone_audio(config) is None

    clone = tmp_path / "clone.wav"
    clone.write_bytes(b"wav")
    config = _config(tmp_path, tts={"audio_prompt_path": "clone.wav"})
    assert client.resolve_clone_audio(config) == clone


def test_expand_audio_paths(tmp_path: Path) -> None:
    (tmp_path / "a.wav").write_bytes(b"a")
    (tmp_path / "b.mp3").write_bytes(b"b")
    (tmp_path / "note.txt").write_text("x")
    result = client.expand_audio_paths([str(tmp_path)])
    assert [path.name for path in result] == ["a.wav", "b.mp3"]


def test_exit_codes() -> None:
    assert client._exit_code(client.ConfigError("x")) == 2
    assert client._exit_code(FileNotFoundError("x")) == 2
    assert client._exit_code(ValueError("x")) == 2
    assert client._exit_code(client.ApiError("x")) == 4
    assert client._exit_code(RuntimeError("x")) == 1


def test_load_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIBER_API_BASE_URL", "http://env:5555/api/v1")
    monkeypatch.setenv("LIBER_API_KEY", "env-key")
    config_path = tmp_path / "speechapi_config.json"
    config_path.write_text(
        '{"asr": {"language": "en"}, "tts": {"format": "ogg_opus"}, "global": {}}',
        encoding="utf-8",
    )

    env = client.load_env(
        "http://override:5555/api/v1/", "override-key", str(config_path)
    )
    assert env["base_url"] == "http://override:5555/api/v1"
    assert env["api_key"] == "override-key"
    assert env["config_json"]["asr"]["language"] == "en"
    assert env["config_json"]["tts"]["format"] == "ogg_opus"
    # 未被用户文件覆盖的字段保留默认值
    assert env["config_json"]["global"]["asr_output"] == "json"


def test_list_models_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status_code = 200
        text = "{}"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"models": ["large-v3"], "default_tts_model": "multilingual_v3"}

    monkeypatch.setattr(client._session, "request", lambda *a, **k: Response())
    result = client.list_models(
        {"base_url": "http://speech:5555/api/v1", "api_key": "k"}
    )
    assert result["default_tts_model"] == "multilingual_v3"

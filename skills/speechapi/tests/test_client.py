"""Liber SpeechAPI 客户端纯函数测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import liber_speech_client as client


def _config(tmp_path: Path, **overrides) -> dict:
    data = {
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
    for section, values in overrides.items():
        data[section].update(values)
    return {
        "base_url": "http://speech:5555/api/v1",
        "origin": "http://speech:5555",
        "api_version": "v1",
        "api_key": "k",
        "config_json": data,
        "skill_dir": tmp_path,
    }


def test_split_api_base() -> None:
    assert client.split_api_base("http://h:5555/api/v1") == ("http://h:5555", "v1")
    assert client.split_api_base("http://h:5555/api/v2") == ("http://h:5555", "v2")
    assert client.split_api_base("http://h:5555") == ("http://h:5555", "auto")
    assert client.split_api_base("http://h:5555/api/v1/") == ("http://h:5555", "v1")


def test_build_asr_payload_omits_default() -> None:
    payload = client.build_asr_payload(_config(Path(".")), {})
    assert payload == {"language": "zh", "task": "transcribe"}


def test_build_asr_payload_merges_options() -> None:
    config = _config(
        Path("."),
        asr={"options": {"timestamps": "word", "vad_filter": True, "initial_prompt": "术语"}},
    )
    payload = client.build_asr_payload(config, {"hotwords": "LiberAstra"})
    assert payload["timestamps"] == "word"
    assert payload["vad_filter"] is True
    assert payload["initial_prompt"] == "术语"
    assert payload["hotwords"] == "LiberAstra"


def test_build_tts_payload_includes_text_and_options() -> None:
    config = _config(
        Path("."),
        tts={"options": {"speed": 0.9, "exaggeration": 0.7, "cfg_weight": 0.3}},
    )
    payload = client.build_tts_payload(config, {"text": "hello", "speed": 1.1})
    assert payload["text"] == "hello"
    assert payload["model"] == "multilingual_v3"
    assert payload["format"] == "wav"
    assert payload["speed"] == 1.1
    assert payload["exaggeration"] == 0.7
    assert payload["cfg_weight"] == 0.3
    assert "audio_prompt_path" not in payload


def test_build_vc_payload() -> None:
    config = _config(
        Path("."),
        vc={"options": {"diffusion_steps": 20, "seed": 42, "denoise": True}},
    )
    payload = client.build_vc_payload(
        config,
        {"file_id": "f_in", "prompt_file_id": "f_ref"},
    )
    assert payload["file_id"] == "f_in"
    assert payload["prompt_file_id"] == "f_ref"
    assert payload["model"] == "seed-vc"
    assert payload["convert_all"] is True
    assert payload["diffusion_steps"] == 20
    assert payload["seed"] == 42
    assert payload["denoise"] is True


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
        "http://override:5555/api/v2/", "override-key", str(config_path)
    )
    assert env["base_url"] == "http://override:5555/api/v2"
    assert env["origin"] == "http://override:5555"
    assert env["api_version"] == "v2"
    assert env["api_key"] == "override-key"
    assert env["config_json"]["asr"]["language"] == "en"
    assert env["config_json"]["tts"]["format"] == "ogg_opus"
    assert env["config_json"]["global"]["asr_output"] == "json"


def test_resolve_api_version(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(Path("."))
    config["api_version"] = "auto"

    class Response:
        status_code = 200

    monkeypatch.setattr(client, "_request", lambda *a, **k: Response())
    assert client.resolve_api_version(config) == "v2"

    class Missing:
        status_code = 404

    monkeypatch.setattr(client, "_request", lambda *a, **k: Missing())
    config["origin"] = "http://other:5555"
    config["api_version"] = "auto"
    assert client.resolve_api_version(config) == "v1"


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
        {
            "origin": "http://speech:5555",
            "api_version": "v1",
            "api_key": "k",
        }
    )
    assert result["default_tts_model"] == "multilingual_v3"

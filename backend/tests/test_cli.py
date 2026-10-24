"""astra CLI 远程模式端到端测试（uvicorn 真实线程服务器 + 临时配置目录）。"""

import json
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from typer.testing import CliRunner

from liberastra.cli import config as cli_config
from liberastra.cli.main import app
from liberastra.main import create_app

runner = CliRunner()


@pytest.fixture(scope="module")
def live_server(auth_header: dict[str, str]):  # 依赖：确保管理员已创建
    server_app = create_app()
    config = uvicorn.Config(server_app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_config, "CONFIG_PATH", tmp_path / "config.toml")


def _login(live_server: str) -> None:
    result = runner.invoke(
        app,
        ["login", "--server", live_server, "--username", "admin", "--password", "admin-pass-123"],
    )
    assert result.exit_code == 0, result.output


def test_login_and_config(live_server: str) -> None:
    _login(live_server)
    result = runner.invoke(app, ["--json", "config"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["server"] == live_server
    assert data["has_token"] is True

    # 登录后 provider list 用配置文件凭据
    result = runner.invoke(app, ["--json", "provider", "list"])
    assert result.exit_code == 0
    assert isinstance(json.loads(result.output), list)


def test_provider_commands(live_server: str) -> None:
    _login(live_server)
    add = runner.invoke(
        app,
        [
            "--json", "provider", "add",
            "--name", "cli-llm", "--type", "openai_compatible", "--base-url", "http://mock/v1",
        ],
    )
    assert add.exit_code == 0, add.output
    provider = json.loads(add.output)
    assert provider["type"] == "openai_compatible"

    test = runner.invoke(app, ["--json", "provider", "test", str(provider["id"])])
    assert test.exit_code == 4  # 无法连接 mock → 退出码 4
    assert json.loads(test.output)["ok"] is False


def test_tts_end_to_end(live_server: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """服务端 worker 与测试同进程，monkeypatch 对 runner 生效。"""
    from liberastra.services import tts as tts_service

    class _FakeTTS:
        async def synthesize(self, *, text: str, voice: str, **kwargs) -> bytes:
            return f"AUDIO:{voice}".encode()

    monkeypatch.setattr(tts_service, "build_tts_adapter", lambda record, **_kwargs: _FakeTTS())

    _login(live_server)
    add = runner.invoke(
        app,
        ["--json", "provider", "add", "--name", "cli-tts", "--type", "openai_tts",
         "--base-url", "http://mock/v1"],
    )
    provider_id = json.loads(add.output)["id"]

    out = tmp_path / "hello.mp3"
    result = runner.invoke(
        app,
        ["--json", "tts", "你好", "--voice", "af_heart", "--provider-id", str(provider_id),
         "-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.read_bytes() == b"AUDIO:af_heart"


def test_service_unavailable_exit_code() -> None:
    result = runner.invoke(app, ["--server", "http://127.0.0.1:9", "provider", "list"])
    assert result.exit_code == 3


def test_parse_params() -> None:
    from liberastra.cli.client import parse_params

    assert parse_params('{"a": 1}') == {"a": 1}
    assert parse_params(None) == {}


def test_mcp_server_builds() -> None:
    pytest.importorskip("fastmcp")
    from liberastra.mcp.server import create_mcp

    mcp = create_mcp()
    assert mcp.name == "LiberAstra"

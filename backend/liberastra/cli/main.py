"""astra CLI：远程模式（默认，HTTP 调用服务端）+ 本地 serve/doctor。

Agent 约定：--json 机器可读输出；退出码 0 成功 / 2 参数错误 / 3 服务不可用 / 4 任务失败；
--wait / --no-wait 控制是否等待任务完成；复杂参数可用 @file.json 或 stdin（-）。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from liberastra import __version__
from liberastra.cli import config as cli_config
from liberastra.cli.client import ApiClient, CliError
from liberastra.core.config import get_settings

app = typer.Typer(name="astra", help="LiberAstra：自托管 AIGC 聚合编排平台", no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)

_state: dict[str, Any] = {"server": None, "token": None, "json": False}


@app.callback()
def _global(
    server: str | None = typer.Option(None, help="服务端地址"),
    token: str | None = typer.Option(None, help="API Token"),
    json_out: bool = typer.Option(False, "--json", help="机器可读 JSON 输出（置于子命令前）"),
) -> None:
    """全局选项（--server / --token / --json）须放在子命令之前，如：astra --json job list。"""
    _state.update({"server": server, "token": token, "json": json_out})


def _client() -> ApiClient:
    return ApiClient.from_config(_state["server"], _state["token"])


def _emit(data: Any, render: Any = None) -> None:
    if _state["json"] or render is None:
        # 用裸 print：Rich 会把 JSON 里的方括号当作 markup 解析
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        render(data)


def _run(fn: Any) -> None:
    try:
        fn()
    except CliError as exc:
        err_console.print(f"[red]错误：{exc}[/red]")
        raise typer.Exit(exc.exit_code) from exc


# ---------- 本地命令 ----------


@app.command()
def serve(
    host: str | None = typer.Option(None, help="监听地址"),
    port: int | None = typer.Option(None, help="监听端口"),
    reload: bool = typer.Option(False, "--reload", help="开发模式自动重载"),
) -> None:
    """启动 API 服务（含前端静态托管）。"""
    settings = get_settings()
    uvicorn.run(
        "liberastra.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=reload,
    )


@app.command()
def doctor() -> None:
    """环境体检：配置、数据库、ffmpeg、服务端连通性。"""
    settings = get_settings()
    table = Table(title="LiberAstra doctor")
    table.add_column("检查项")
    table.add_column("结果")

    table.add_row("版本", __version__)
    table.add_row("数据目录", str(settings.data_dir.resolve()))
    table.add_row("数据库", settings.resolved_database_url)
    table.add_row("ffmpeg", shutil.which("ffmpeg") or "[red]未找到[/red]")

    try:
        from liberastra.core.db import engine

        with engine.connect():
            pass
        table.add_row("数据库连接", "[green]OK[/green]")
    except Exception as exc:  # noqa: BLE001
        table.add_row("数据库连接", f"[red]失败：{exc}[/red]")

    server, _ = cli_config.resolve(_state["server"], _state["token"])
    try:
        with _client() as client:
            health = client.health()
        table.add_row(f"服务端 {server}", f"[green]{health['status']} v{health['version']}[/green]")
    except CliError as exc:
        table.add_row(f"服务端 {server}", f"[red]{exc}[/red]")
    console.print(table)


@app.command()
def version() -> None:
    """打印版本号。"""
    console.print(__version__)


# ---------- 认证与配置 ----------


@app.command()
def login(
    server: str = typer.Option(cli_config.DEFAULT_SERVER, help="服务端地址"),
    token: str | None = typer.Option(None, help="已有 API Token（astra_...）"),
    username: str | None = typer.Option(None, help="用户名（密码登录）"),
    password: str | None = typer.Option(None, help="密码"),
) -> None:
    """登录并保存凭据到 ~/.liberastra/config.toml。"""

    def action() -> None:
        with ApiClient(server) as client:
            if token is None:
                if not username or not password:
                    raise CliError("请提供 --token，或 --username + --password")
                data = client.request(
                    "POST", "/api/v1/auth/login", json={"username": username, "password": password}
                )
                saved_token = data["access_token"]
            else:
                saved_token = token
            # 验证凭据可用
            client.set_token(saved_token)
            me = client.request("GET", "/api/v1/auth/me")
        cli_config.save(server, saved_token)
        _emit({"server": server, "user": me["username"]}, lambda d: console.print(
            f"[green]已登录 {d['user']} @ {d['server']}[/green]"))

    _run(action)


@app.command()
def config() -> None:
    """显示当前配置。"""
    server, token = cli_config.resolve(_state["server"], _state["token"])
    _emit({"server": server, "has_token": bool(token), "config_file": str(cli_config.CONFIG_PATH)})


# ---------- Provider ----------


provider_app = typer.Typer(help="服务提供方管理", no_args_is_help=True)
app.add_typer(provider_app, name="provider")


@provider_app.command("list")
def provider_list() -> None:
    def action() -> None:
        with _client() as client:
            providers = client.request("GET", "/api/v1/providers")

        def render(data: list) -> None:
            table = Table()
            for col in ("id", "名称", "类型", "base_url", "启用"):
                table.add_column(col)
            for p in data:
                table.add_row(str(p["id"]), p["name"], p["type"], p["base_url"], "✓" if p["enabled"] else "✗")
            console.print(table)

        _emit(providers, render)

    _run(action)


@provider_app.command("add")
def provider_add(
    name: str = typer.Option(..., "--name"),
    type_: str = typer.Option(..., "--type", help="类型，如 openai_compatible / openai_tts / comfyui"),
    base_url: str = typer.Option("", "--base-url"),
    api_key: str | None = typer.Option(None, "--api-key"),
) -> None:
    def action() -> None:
        with _client() as client:
            created = client.request(
                "POST", "/api/v1/providers",
                json={"name": name, "type": type_, "base_url": base_url, "api_key": api_key},
            )
        _emit(created, lambda d: console.print(f"[green]已创建 Provider #{d['id']} {d['name']}[/green]"))

    _run(action)


@provider_app.command("test")
def provider_test(provider_id: int) -> None:
    def action() -> None:
        with _client() as client:
            result = client.request("POST", f"/api/v1/providers/{provider_id}/test")
        _emit(result, lambda d: console.print(
            "[green]OK[/green] " + d["message"] if d["ok"] else "[red]失败[/red] " + d["message"]))
        if not result["ok"]:
            raise typer.Exit(4)

    _run(action)


@provider_app.command("models")
def provider_models(provider_id: int) -> None:
    def action() -> None:
        with _client() as client:
            models = client.request("GET", f"/api/v1/providers/{provider_id}/models")
        _emit(models, lambda d: console.print("\n".join(d) or "（空）"))

    _run(action)


# ---------- TTS / ASR ----------


@app.command()
def tts(
    text: str,
    voice: str = typer.Option(..., "--voice"),
    out: Path = typer.Option(Path("speech.mp3"), "-o", "--out"),
    provider_id: int | None = typer.Option(None, "--provider-id"),
    fmt: str = typer.Option("mp3", "--format"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """文字转语音。"""
    def action() -> None:
        with _client() as client:
            job = client.request(
                "POST", "/api/v1/tts",
                json={"text": text, "voice": voice, "format": fmt, "provider_id": provider_id},
            )
            if not wait:
                _emit(job)
                return
            final = client.wait_job(job["id"])
            saved = client.save_outputs(final, out, default_name="speech", kind="audio")
        _emit({"job_id": job["id"], "saved": [str(p) for p in saved]},
              lambda d: console.print(f"[green]已保存：{d['saved'][0]}[/green]"))

    _run(action)


@app.command()
def asr(
    file: Path,
    fmt: str = typer.Option("srt", "--format", "-f", help="txt/srt/vtt/json"),
    out: Path | None = typer.Option(None, "-o", "--out"),
    language: str | None = typer.Option(None, "--language"),
    provider_id: int | None = typer.Option(None, "--provider-id"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """语音转文字。"""
    def action() -> None:
        if not file.exists():
            raise CliError(f"文件不存在: {file}")
        with _client() as client:
            with file.open("rb") as fh:
                job = client.request(
                    "POST", "/api/v1/asr",
                    files={"file": (file.name, fh)},
                    data={
                        "formats": f"txt,{fmt}",
                        **({"language": language} if language else {}),
                        **({"provider_id": str(provider_id)} if provider_id else {}),
                    },
                )
            if not wait:
                _emit(job)
                return
            final = client.wait_job(job["id"])
            text_out = next((o for o in final["outputs"] if o.get("type") == "text"), None)
            target = [o for o in final["outputs"] if o.get("format") == fmt]
            saved = client.save_outputs(
                {**final, "outputs": target or final["outputs"]}, out, default_name=f"transcript.{fmt}"
            )
        result = {"job_id": job["id"], "text": text_out.get("content") if text_out else None,
                  "saved": [str(p) for p in saved]}
        _emit(result, lambda d: console.print(d["text"] or f"[green]已保存：{d['saved'][0]}[/green]"))

    _run(action)


# ---------- 图像 / 视频 ----------


image_app = typer.Typer(help="图像生成", no_args_is_help=True)
app.add_typer(image_app, name="image")


@image_app.command("gen")
def image_gen(
    prompt: str = typer.Option(..., "--prompt"),
    out: Path = typer.Option(Path("."), "-o", "--out", help="输出目录或文件"),
    workflow: str | None = typer.Option(None, "--workflow", help="ComfyUI 工作流包名"),
    width: int = typer.Option(1024, "--width"),
    height: int = typer.Option(1024, "--height"),
    seed: int = typer.Option(-1, "--seed"),
    provider_id: int | None = typer.Option(None, "--provider-id"),
    params: str | None = typer.Option(None, "--params", help="额外参数：JSON / @file.json / -"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """文生图。"""
    def action() -> None:
        from liberastra.cli.client import parse_params

        with _client() as client:
            job = client.request(
                "POST", "/api/v1/images/generate",
                json={
                    "prompt": prompt, "workflow": workflow, "width": width, "height": height,
                    "seed": seed, "provider_id": provider_id, "inputs": parse_params(params),
                },
            )
            if not wait:
                _emit(job)
                return
            final = client.wait_job(job["id"])
            saved = client.save_outputs(final, out, default_name="image", kind="image")
        _emit({"job_id": job["id"], "saved": [str(p) for p in saved]},
              lambda d: console.print(f"[green]已保存 {len(d['saved'])} 张：{d['saved'][0]}[/green]"))

    _run(action)


video_app = typer.Typer(help="视频创作", no_args_is_help=True)
app.add_typer(video_app, name="video")


@video_app.command("quick")
def video_quick(
    topic: str | None = typer.Option(None, "--topic"),
    script: str | None = typer.Option(None, "--script"),
    voice: str = typer.Option(..., "--voice"),
    aspect: str = typer.Option("9:16", "--aspect"),
    out: Path = typer.Option(Path("video.mp4"), "-o", "--out"),
    params: str | None = typer.Option(None, "--params", help="额外参数：JSON / @file.json / -"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """一句话出短视频（LLM 脚本 → 分镜 → 逐帧合成）。"""
    def action() -> None:
        from liberastra.cli.client import parse_params

        if not topic and not script:
            raise CliError("请提供 --topic 或 --script")
        with _client() as client:
            job = client.request(
                "POST", "/api/v1/videos/quick",
                json={"topic": topic, "script": script, "voice": voice, "aspect": aspect,
                      **parse_params(params)},
            )
            if not wait:
                _emit(job)
                return
            final = client.wait_job(job["id"], timeout=7200)
            saved = client.save_outputs(final, out, default_name="video", kind="video")
        _emit({"job_id": job["id"], "saved": [str(p) for p in saved]},
              lambda d: console.print(f"[green]已保存：{d['saved'][0]}[/green]"))

    _run(action)


# ---------- Job ----------


job_app = typer.Typer(help="任务管理", no_args_is_help=True)
app.add_typer(job_app, name="job")


@job_app.command("list")
def job_list(limit: int = typer.Option(20, "--limit")) -> None:
    def action() -> None:
        with _client() as client:
            jobs = client.request("GET", f"/api/v1/jobs?limit={limit}")

        def render(data: list) -> None:
            table = Table()
            for col in ("id", "类型", "状态", "进度", "创建时间"):
                table.add_column(col)
            for j in data:
                table.add_row(
                    j["id"][:8], j["kind"], j["status"],
                    f"{j['progress']:.0%}", j["created_at"][:19],
                )
            console.print(table)

        _emit(jobs, render)

    _run(action)


@job_app.command("get")
def job_get(job_id: str) -> None:
    def action() -> None:
        with _client() as client:
            _emit(client.request("GET", f"/api/v1/jobs/{job_id}"))

    _run(action)


@job_app.command("wait")
def job_wait(job_id: str) -> None:
    def action() -> None:
        with _client() as client:
            _emit(client.wait_job(job_id))

    _run(action)


@job_app.command("cancel")
def job_cancel(job_id: str) -> None:
    def action() -> None:
        with _client() as client:
            _emit(client.request("POST", f"/api/v1/jobs/{job_id}/cancel"))

    _run(action)


# ---------- Workflow ----------


workflow_app = typer.Typer(help="工作流包", no_args_is_help=True)
app.add_typer(workflow_app, name="workflow")


@workflow_app.command("list")
def workflow_list() -> None:
    def action() -> None:
        with _client() as client:
            packs = client.request("GET", "/api/v1/workflows")

        def render(data: list) -> None:
            table = Table()
            for col in ("名称", "能力", "来源", "参数"):
                table.add_column(col)
            for p in data:
                table.add_row(p["name"], p["capability"], p["source"], ", ".join(p["inputs"].keys()))
            console.print(table)

        _emit(packs, render)

    _run(action)


# ---------- MCP ----------


@app.command()
def mcp() -> None:
    """启动 MCP Server（stdio），把能力暴露为 Agent 工具。"""
    try:
        from liberastra.mcp.server import run_mcp
    except ImportError as exc:
        err_console.print("[red]缺少 fastmcp，请安装：pip install 'liberastra[mcp]'[/red]")
        raise typer.Exit(2) from exc
    run_mcp()


def main() -> None:
    app()


if __name__ == "__main__":
    main()

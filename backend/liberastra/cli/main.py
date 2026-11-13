"""astra CLI：远程模式（默认，HTTP 调用服务端）+ 本地 serve/doctor。

Agent 约定：--json 机器可读输出；退出码 0 成功 / 2 参数错误 / 3 服务不可用 / 4 任务失败；
--wait / --no-wait 控制是否等待任务完成；复杂参数可用 @file.json 或 stdin（-）。
"""

from __future__ import annotations

import json
import shutil
import sys
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
_pre: dict[str, Any] = {"server": None, "token": None, "json": False, "version": False}


def prepare_argv(argv: list[str]) -> tuple[list[str], dict[str, Any]]:
    """把全局选项从任意位置提出来，兼容 `astra job list --json`。"""
    cleaned: list[str] = []
    parsed: dict[str, Any] = {
        "server": None,
        "token": None,
        "json": False,
        "version": False,
    }
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--json":
            parsed["json"] = True
            index += 1
            continue
        if arg == "--version":
            parsed["version"] = True
            index += 1
            continue
        if arg in ("--server", "--token"):
            if index + 1 < len(argv):
                parsed[arg[2:]] = argv[index + 1]
                index += 2
                continue
            cleaned.append(arg)
            index += 1
            continue
        if arg.startswith("--server="):
            parsed["server"] = arg.split("=", 1)[1]
            index += 1
            continue
        if arg.startswith("--token="):
            parsed["token"] = arg.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(arg)
        index += 1
    return cleaned, parsed


@app.callback()
def _global(
    server: str | None = typer.Option(None, help="服务端地址"),
    token: str | None = typer.Option(None, help="API Token"),
    json_out: bool = typer.Option(False, "--json", help="机器可读 JSON 输出（可放在任意位置）"),
    version_flag: bool = typer.Option(False, "--version", is_eager=True, help="打印版本号"),
) -> None:
    """全局选项（--server / --token / --json / --version）可放在子命令前后。"""
    if version_flag:
        console.print(__version__)
        raise typer.Exit()
    server = server or _pre.get("server")
    token = token or _pre.get("token")
    _state.update(
        {"server": server, "token": token, "json": json_out or _pre.get("json", False)}
    )


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
        if _state["json"]:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                            "exit_code": exc.exit_code,
                        },
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
        else:
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
        # 只监视程序包。data/ 里的模型下载不能触发热重载，否则安装会被中途杀掉。
        reload_dirs=[str(Path(__file__).resolve().parents[1])] if reload else None,
    )


@app.command()
def doctor() -> None:
    """环境体检：配置、数据库、ffmpeg、服务端连通性。"""
    settings = get_settings()
    ffmpeg = shutil.which("ffmpeg")
    checks: list[dict[str, Any]] = [
        {"name": "版本", "ok": True, "detail": __version__},
        {"name": "数据目录", "ok": True, "detail": str(settings.data_dir.resolve())},
        {"name": "数据库", "ok": True, "detail": settings.resolved_database_url},
        {"name": "ffmpeg", "ok": bool(ffmpeg), "detail": ffmpeg or "未找到"},
    ]

    try:
        from liberastra.core.db import engine

        with engine.connect():
            pass
        checks.append({"name": "数据库连接", "ok": True, "detail": "OK"})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "数据库连接", "ok": False, "detail": f"失败：{exc}"})

    server, _ = cli_config.resolve(_state["server"], _state["token"])
    try:
        with _client() as client:
            health = client.health()
        checks.append(
            {
                "name": f"服务端 {server}",
                "ok": True,
                "detail": f"{health['status']} v{health['version']}",
            }
        )
    except CliError as exc:
        checks.append({"name": f"服务端 {server}", "ok": False, "detail": str(exc)})

    if _state["json"]:
        _emit({"ok": all(item["ok"] for item in checks), "checks": checks})
        return

    table = Table(title="LiberAstra doctor")
    table.add_column("检查项")
    table.add_column("结果")
    for item in checks:
        mark = "[green]OK[/green]" if item["ok"] else "[red]失败[/red]"
        table.add_row(item["name"], f"{mark} {item['detail']}")
    console.print(table)


@app.command()
def version() -> None:
    """打印版本号。"""
    _emit({"version": __version__}, lambda d: console.print(d["version"]))


@app.command()
def logout() -> None:
    """删除本地保存的凭据。"""
    cli_config.CONFIG_PATH.unlink(missing_ok=True)
    _emit(
        {"ok": True, "config_file": str(cli_config.CONFIG_PATH)},
        lambda _d: console.print("[green]已退出登录[/green]"),
    )


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


pack_app = typer.Typer(help="工作流包管理", no_args_is_help=True)
app.add_typer(pack_app, name="pack")


@pack_app.command("doctor")
def pack_doctor(
    name: str = typer.Argument(..., help="工作流包名"),
    provider: int | None = typer.Option(None, "--provider", help="ComfyUI Provider id"),
    strict: bool = typer.Option(False, "--strict", help="WARN 也返回非零"),
) -> None:
    """对工作流包做运行前体检。"""

    def action() -> None:
        params: dict[str, int] = {} if provider is None else {"provider_id": provider}
        with _client() as client:
            data = client.request("GET", f"/api/v1/workflows/{name}/doctor", params=params)

        def render(result: dict) -> None:
            table = Table(title=f"工作流包体检：{name}")
            table.add_column("检查项")
            table.add_column("结果")
            table.add_column("详情")
            marks = {
                "pass": "[green]通过[/green]",
                "warn": "[yellow]警告[/yellow]",
                "fail": "[red]失败[/red]",
                "skip": "[dim]跳过[/dim]",
            }
            for check in result.get("checks", []):
                table.add_row(
                    check.get("label", ""),
                    marks.get(check.get("status"), check.get("status", "")),
                    check.get("detail", ""),
                )
            console.print(table)
            console.print(f"结论：{marks.get(result.get('status'), result.get('status', ''))}")

        _emit(data, render)
        status = data.get("status")
        if status == "fail" or (strict and status == "warn"):
            raise typer.Exit(5)
        if status == "warn":
            raise typer.Exit(1)

    _run(action)


@app.command()
def tts(
    text: str,
    voice: str = typer.Option(..., "--voice"),
    out: Path = typer.Option(Path("speech.mp3"), "-o", "--out"),
    provider_id: int | None = typer.Option(None, "--provider-id"),
    fmt: str = typer.Option("mp3", "--format"),
    options: str | None = typer.Option(
        None, "--options", help='JSON 参数对象，如 {"speed":0.9,"exaggeration":0.7}'
    ),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """文字转语音。"""
    def action() -> None:
        parsed_options: dict[str, Any] = {}
        if options:
            try:
                loaded = json.loads(options)
            except json.JSONDecodeError as exc:
                raise CliError(f"--options 不是合法 JSON: {exc}") from exc
            if not isinstance(loaded, dict):
                raise CliError("--options 必须是 JSON 对象")
            parsed_options = loaded
        with _client() as client:
            job = client.request(
                "POST", "/api/v1/tts",
                json={
                    "text": text,
                    "voice": voice,
                    "format": fmt,
                    "provider_id": provider_id,
                    "options": parsed_options,
                },
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
                        "formats": fmt,
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


@image_app.command("edit")
def image_edit(
    prompt: str = typer.Option("", "--prompt"),
    images: list[Path] = typer.Option(..., "--image", "-i", help="输入图片，可重复"),
    workflow: str | None = typer.Option(None, "--workflow", help="工作流包名"),
    provider_id: int | None = typer.Option(None, "--provider-id"),
    params: str | None = typer.Option(None, "--params", help="额外参数：JSON / @file.json / -"),
    out: Path = typer.Option(Path("."), "-o", "--out", help="输出目录或文件"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """图生图 / 多图编辑。"""

    def action() -> None:
        from liberastra.cli.client import parse_params

        if not images:
            raise CliError("请至少提供一张 --image")
        for path in images:
            if not path.exists():
                raise CliError(f"文件不存在: {path}")

        data: dict[str, str] = {
            "prompt": prompt,
            "inputs": json.dumps(parse_params(params), ensure_ascii=False),
        }
        if workflow:
            data["workflow"] = workflow
        if provider_id is not None:
            data["provider_id"] = str(provider_id)

        handles = []
        try:
            files = []
            for path in images:
                handle = path.open("rb")
                handles.append(handle)
                files.append(("images", (path.name, handle)))
            with _client() as client:
                job = client.request("POST", "/api/v1/images/edit", files=files, data=data)
                if not wait:
                    _emit(job)
                    return
                final = client.wait_job(job["id"])
                saved = client.save_outputs(
                    final, out, default_name="image_edit", kind="image"
                )
        finally:
            for handle in handles:
                handle.close()

        _emit(
            {"job_id": job["id"], "saved": [str(path) for path in saved]},
            lambda d: console.print(
                f"[green]已保存 {len(d['saved'])} 张：{d['saved'][0]}[/green]"
            ),
        )

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


@video_app.command("i2v")
def video_i2v(
    image: Path = typer.Option(..., "--image", "-i", help="首帧或参考图"),
    prompt: str = typer.Option("", "--prompt"),
    workflow: str | None = typer.Option(None, "--workflow", help="工作流包名"),
    model: str | None = typer.Option(None, "--model", help="云端视频模型"),
    sub_capability: str = typer.Option(
        "i2v_first", "--sub-capability", help="i2v_first / i2v_flf / t2v"
    ),
    image_2: Path | None = typer.Option(None, "--image-2", help="尾帧或第二张参考图"),
    provider_id: int | None = typer.Option(None, "--provider-id"),
    params: str | None = typer.Option(None, "--params", help="额外参数：JSON / @file.json / -"),
    out: Path = typer.Option(Path("video.mp4"), "-o", "--out"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """图生视频（首帧 / 首尾帧 / 多参考）。"""

    def action() -> None:
        from liberastra.cli.client import parse_params

        if not image.exists():
            raise CliError(f"文件不存在: {image}")
        if not workflow and not model:
            raise CliError("请提供 --workflow 或 --model")

        data: dict[str, str] = {
            "prompt": prompt,
            "sub_capability": sub_capability,
            "inputs": json.dumps(parse_params(params), ensure_ascii=False),
        }
        if workflow:
            data["workflow"] = workflow
        if model:
            data["model"] = model
        if provider_id is not None:
            data["provider_id"] = str(provider_id)

        handles = []
        try:
            first = image.open("rb")
            handles.append(first)
            files = [("image", (image.name, first))]
            if image_2 is not None:
                if not image_2.exists():
                    raise CliError(f"文件不存在: {image_2}")
                second = image_2.open("rb")
                handles.append(second)
                files.append(("image_2", (image_2.name, second)))
            with _client() as client:
                job = client.request("POST", "/api/v1/videos/i2v", files=files, data=data)
                if not wait:
                    _emit(job)
                    return
                final = client.wait_job(job["id"], timeout=7200)
                saved = client.save_outputs(
                    final, out, default_name="video", kind="video"
                )
        finally:
            for handle in handles:
                handle.close()

        _emit(
            {"job_id": job["id"], "saved": [str(path) for path in saved]},
            lambda d: console.print(f"[green]已保存：{d['saved'][0]}[/green]"),
        )

    _run(action)


# ---------- Job ----------


job_app = typer.Typer(help="任务管理", no_args_is_help=True)
app.add_typer(job_app, name="job")


@job_app.command("list")
def job_list(
    limit: int = typer.Option(20, "--limit"),
    status: str | None = typer.Option(None, "--status", help="按状态过滤"),
    kind: str | None = typer.Option(None, "--kind", help="按任务类型过滤"),
) -> None:
    def action() -> None:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status_filter"] = status
        if kind:
            params["kind"] = kind
        with _client() as client:
            jobs = client.request("GET", "/api/v1/jobs", params=params)

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
def job_wait(
    job_id: str,
    timeout: float = typer.Option(3600.0, "--timeout", help="等待秒数"),
) -> None:
    def action() -> None:
        with _client() as client:
            _emit(client.wait_job(job_id, timeout=timeout))

    _run(action)


@job_app.command("cancel")
def job_cancel(job_id: str) -> None:
    def action() -> None:
        with _client() as client:
            _emit(client.request("POST", f"/api/v1/jobs/{job_id}/cancel"))

    _run(action)


@job_app.command("retry")
def job_retry(job_id: str) -> None:
    def action() -> None:
        with _client() as client:
            _emit(client.request("POST", f"/api/v1/jobs/{job_id}/retry"))

    _run(action)


# ---------- Workflow ----------


workflow_app = typer.Typer(help="工作流包", no_args_is_help=True)
app.add_typer(workflow_app, name="workflow")


@workflow_app.command("list")
def workflow_list(
    capability: str | None = typer.Option(None, "--capability", help="按能力过滤"),
) -> None:
    def action() -> None:
        with _client() as client:
            packs = client.request("GET", "/api/v1/workflows")
        if capability:
            packs = [pack for pack in packs if pack.get("capability") == capability]

        def render(data: list) -> None:
            table = Table()
            for col in ("名称", "能力", "来源", "参数"):
                table.add_column(col)
            for p in data:
                table.add_row(p["name"], p["capability"], p["source"], ", ".join(p["inputs"].keys()))
            console.print(table)

        _emit(packs, render)

    _run(action)


asset_app = typer.Typer(help="资产", no_args_is_help=True)
app.add_typer(asset_app, name="asset")


@asset_app.command("list")
def asset_list(
    kind: str | None = typer.Option(None, "--kind", help="image / video / audio 等，可逗号分隔"),
    job_id: str | None = typer.Option(None, "--job-id"),
    job_kind: str | None = typer.Option(None, "--job-kind"),
    limit: int = typer.Option(20, "--limit"),
    offset: int = typer.Option(0, "--offset"),
    include_hidden: bool = typer.Option(False, "--include-hidden"),
) -> None:
    def action() -> None:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if kind:
            params["kind"] = kind
        if job_id:
            params["job_id"] = job_id
        if job_kind:
            params["job_kind"] = job_kind
        if include_hidden:
            params["include_hidden"] = True
        with _client() as client:
            assets = client.request("GET", "/api/v1/assets", params=params)

        def render(data: list) -> None:
            table = Table()
            for col in ("id", "类型", "大小", "任务", "路径"):
                table.add_column(col)
            for asset in data:
                table.add_row(
                    str(asset["id"]),
                    asset["kind"],
                    str(asset["size"]),
                    (asset.get("job_id") or "")[:8],
                    asset["path"],
                )
            console.print(table)

        _emit(assets, render)

    _run(action)


@asset_app.command("download")
def asset_download(
    asset_id: int,
    out: Path = typer.Option(Path("."), "-o", "--out", help="输出目录或文件"),
) -> None:
    def action() -> None:
        with _client() as client:
            asset = client.request("GET", f"/api/v1/assets/{asset_id}")
            content = client.request_bytes(f"/api/v1/assets/{asset_id}/content")
        name = Path(asset.get("path") or f"asset_{asset_id}").name or f"asset_{asset_id}"
        target = out if out.suffix else out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        _emit(
            {"asset_id": asset_id, "saved": str(target)},
            lambda d: console.print(f"[green]已保存：{d['saved']}[/green]"),
        )

    _run(action)


@asset_app.command("delete")
def asset_delete(
    asset_id: int,
    yes: bool = typer.Option(False, "--yes", help="确认删除"),
) -> None:
    def action() -> None:
        if not yes:
            raise CliError("删除资产需要 --yes 确认")
        with _client() as client:
            client.request("DELETE", f"/api/v1/assets/{asset_id}")
        _emit(
            {"ok": True, "asset_id": asset_id},
            lambda d: console.print(f"[green]已删除资产 #{d['asset_id']}[/green]"),
        )

    _run(action)


voices_app = typer.Typer(help="音色库", no_args_is_help=True)
app.add_typer(voices_app, name="voices")


@voices_app.command("list")
def voices_list() -> None:
    def action() -> None:
        with _client() as client:
            voices = client.request("GET", "/api/v1/voices")

        def render(data: list) -> None:
            table = Table()
            for col in ("id", "名称", "默认", "provider", "voice_id"):
                table.add_column(col)
            for voice in data:
                table.add_row(
                    str(voice["id"]),
                    voice["name"],
                    "✓" if voice["is_default"] else "",
                    str(voice.get("provider_id") or ""),
                    voice.get("voice_id") or "",
                )
            console.print(table)

        _emit(voices, render)

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
    cleaned, parsed = prepare_argv(sys.argv[1:])
    _pre.clear()
    _pre.update(parsed)
    if parsed["version"]:
        console.print(__version__)
        raise SystemExit(0)
    sys.argv = [sys.argv[0], *cleaned]
    app()


if __name__ == "__main__":
    main()

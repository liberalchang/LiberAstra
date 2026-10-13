"""astra CLI 入口。M0 提供 serve / doctor / version，其余命令随里程碑补齐。"""

from __future__ import annotations

import shutil

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from liberastra import __version__
from liberastra.core.config import get_settings

app = typer.Typer(name="astra", help="LiberAstra：自托管 AIGC 聚合编排平台", no_args_is_help=True)
console = Console()


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
    """环境体检：配置、数据库、ffmpeg。"""
    settings = get_settings()
    table = Table(title="LiberAstra doctor")
    table.add_column("检查项")
    table.add_column("结果")

    table.add_row("版本", __version__)
    table.add_row("数据目录", str(settings.data_dir.resolve()))
    table.add_row("数据库", settings.resolved_database_url)
    table.add_row("主密钥", "已配置（env）" if settings.secret_key else "自动生成（data/.secret_key）")

    ffmpeg = shutil.which("ffmpeg")
    table.add_row("ffmpeg", ffmpeg or "[red]未找到[/red]")

    try:
        from liberastra.core.db import engine

        with engine.connect():
            pass
        table.add_row("数据库连接", "[green]OK[/green]")
    except Exception as exc:  # noqa: BLE001
        table.add_row("数据库连接", f"[red]失败：{exc}[/red]")

    static_dir = settings.resolved_static_dir
    table.add_row("前端产物", str(static_dir) if static_dir else "未构建（仅 API）")

    console.print(table)


@app.command()
def version() -> None:
    """打印版本号。"""
    console.print(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

"""本机附加服务插件：只负责安装标记和启停本地进程。

远端地址在「服务提供方」里配置，不由这里启动。
状态文件 data/plugins.json，字段：installed、enabled、port、device、models_dir、launch、pid、last_error。
模型目录固定为 data/plugins/<id>/models（Windows 安装包在 %LOCALAPPDATA%\\LiberAstra\\data 下）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.core.config import get_settings
from liberastra.models import Provider
from liberastra.providers import PROVIDER_TYPES

# 默认深度权重。安装时目录里没有 .pt / .pth 就下载这一份。
_DEPTH_WEIGHT = "dpt_swin2_large_384.pt"
_DEPTH_WEIGHT_URL = "https://github.com/isl-org/MiDaS/releases/download/v3_1/dpt_swin2_large_384.pt"
_DOWNLOAD_THREADS: dict[str, threading.Thread] = {}
_DOWNLOAD_LOCK = threading.Lock()
_ENV_THREADS: dict[str, threading.Thread] = {}
_ENV_LOCK = threading.Lock()
_ENV_PENDING: set[str] = set()
_ENV_ACTIVE = ""
_PROGRESS: dict[str, tuple[int, str]] = {}
_MODEL_PROGRESS: dict[str, tuple[int, str]] = {}
_STATE_LOCK = threading.RLock()
_NVIDIA: bool | None = None
_CUDA_TORCH_INDEX = "https://download.pytorch.org/whl/cu124"
_CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"

PLUGINS: dict[str, dict[str, Any]] = {
    "speech": {
        "name": "Liber Speech 语音服务",
        "description": "本机文字转语音与语音转文字。端口 5555。连接远程主机请到服务提供方配置。",
        "port": 5555,
        "provider_type": "liber_speech",
        "provider_name": "Liber Speech（本机）",
        "default_device": "auto",
    },
    "depth": {
        "name": "Liber Depth 深度图服务",
        "description": "本机 MiDaS 深度图。端口 5556。连接远程主机请到服务提供方配置。",
        "port": 5556,
        "provider_type": "liber_depth",
        "provider_name": "Liber Depth（本机）",
        "default_device": "cuda",
    },
}

_PROCS: dict[str, subprocess.Popen[bytes]] = {}


def depth_output_name(filename: str) -> str:
    """原文件名去后缀后加 _depth.png。"""
    stem = Path(filename or "image").stem.strip() or "image"
    return f"{Path(stem).name}_depth.png"


def _state_path() -> Path:
    path = get_settings().data_dir / "plugins.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _blank(plugin_id: str) -> dict[str, Any]:
    spec = PLUGINS[plugin_id]
    return {
        "installed": False,
        "enabled": False,
        "port": spec["port"],
        "device": spec["default_device"],
        "models_dir": "",
        "launch": "python",
        "pid": None,
        "last_error": "",
    }


def _legacy_models_path(raw: str) -> bool:
    """拒绝写死的本机权重目录。模型只放在数据目录约定路径。"""
    text = raw.replace("/", "\\").lower()
    return "naked-eye-3d-plus" in text


def plugin_models_dir(plugin_id: str) -> Path:
    """模型目录。开发时在 data/plugins/<id>/models，Windows 安装包在 %LOCALAPPDATA%\\LiberAstra\\data\\plugins\\<id>\\models。"""
    env_name = "LIBER_DEPTH_MODELS_DIR" if plugin_id == "depth" else "LIBER_SPEECH_MODELS_DIR"
    raw = os.environ.get(env_name, "").strip()
    if raw and not _legacy_models_path(raw):
        path = Path(raw).expanduser()
    else:
        path = get_settings().data_dir / "plugins" / plugin_id / "models"
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _install_root() -> Path | None:
    """Windows 安装包里 python.exe 在 runtime 下，上两级是安装目录。"""
    exe = Path(sys.executable).resolve()
    if exe.parent.name.lower() == "runtime":
        return exe.parents[1]
    return None


def plugin_code_dir(plugin_id: str) -> Path | None:
    """插件程序目录。先找仓库或安装目录里的 services/<id>，再找 Program Files 下的独立安装包。"""
    names = {"speech": "LiberSpeech", "depth": "LiberDepth"}
    candidates: list[Path] = []
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "services" / plugin_id)
    root = _install_root()
    if root is not None:
        candidates.append(root / "services" / plugin_id)
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    candidates.append(Path(program_files) / names[plugin_id])
    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if (path / "server.py").is_file() or (path / "docker-compose.yml").is_file():
            return path
    return None


def plugin_launch(code: Path | None) -> str:
    """带 install.ps1 的是已发布安装包，用 Docker。仓库里的 services 用插件自己的虚拟环境。"""
    if code is not None and (code / "install.ps1").is_file() and (code / "docker-compose.yml").is_file():
        return "docker"
    return "python"


def shared_runtime_dir() -> Path:
    """语音和深度共用的 Python 环境。

    开发时数据目录在 backend/data，热重载会监视它，所以环境放到用户目录，避免安装 PyTorch 时把服务重启掉。
    Windows 安装包的数据目录已经在 %LOCALAPPDATA%，环境就放在 data/plugins/runtime。
    """
    data = get_settings().data_dir.resolve()
    backend = Path(__file__).resolve().parents[2]
    try:
        data.relative_to(backend)
        inside_backend = True
    except ValueError:
        inside_backend = False
    if inside_backend:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return (Path(local) / "LiberAstra" / "plugin-runtime").resolve()
    return (data / "plugins" / "runtime").resolve()


def plugin_venv_dir(plugin_id: str) -> Path:
    """兼容旧调用。环境是各插件共用的，不再按插件各建一份。"""
    del plugin_id
    return shared_runtime_dir()


def _runtime_python() -> Path:
    root = shared_runtime_dir()
    if sys.platform == "win32":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def plugin_python(plugin_id: str) -> Path:
    del plugin_id
    return _runtime_python()


def _req_name(line: str) -> str:
    head = line.split("#", 1)[0].strip()
    if "@" in head:
        head = head.split("@", 1)[0].strip()
    head = re.split(r"[<>=!\[]", head, maxsplit=1)[0].strip()
    return head.lower().replace("_", "-")


def _filtered_requirements(plugin_id: str, source: Path, dest: Path) -> None:
    """共用环境里的 torch 只装一次。插件依赖清单里去掉它，避免再次下载或换成 CPU 版。"""
    del plugin_id
    skip = {"torch", "torchvision"}
    kept: list[str] = []
    for raw in source.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        if _req_name(text) in skip:
            continue
        kept.append(text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _nvidia_present() -> bool:
    global _NVIDIA
    if _NVIDIA is None:
        try:
            completed = subprocess.run(["nvidia-smi"], capture_output=True, check=False)  # noqa: S603
            _NVIDIA = completed.returncode == 0
        except OSError:
            _NVIDIA = False
    return _NVIDIA


def _torch_index() -> str:
    return _CUDA_TORCH_INDEX if _nvidia_present() else _CPU_TORCH_INDEX


def _base_stamp() -> str:
    return "cu124" if _nvidia_present() else "cpu"


def _packages_stamp(code: Path) -> str:
    req = code / "requirements.txt"
    body = req.read_bytes() if req.is_file() else b""
    return hashlib.sha256(body).hexdigest()[:16]


def _base_ready() -> bool:
    marker = shared_runtime_dir() / ".liber-base"
    if not marker.is_file() or not _runtime_python().is_file():
        return False
    return marker.read_text(encoding="utf-8").strip() == _base_stamp()


def _packages_ready(plugin_id: str, code: Path | None) -> bool:
    if code is None:
        return False
    marker = get_settings().data_dir / "plugins" / plugin_id / ".packages-ready"
    if not marker.is_file():
        return False
    return marker.read_text(encoding="utf-8").strip() == _packages_stamp(code)


def _env_ready(plugin_id: str, code: Path | None) -> bool:
    if code is None or plugin_launch(code) == "docker":
        return plugin_launch(code) == "docker"
    return _base_ready() and _packages_ready(plugin_id, code)


def _env_busy(plugin_id: str) -> bool:
    thread = _ENV_THREADS.get("shared")
    if thread is None or not thread.is_alive():
        return False
    with _ENV_LOCK:
        return plugin_id == _ENV_ACTIVE or plugin_id in _ENV_PENDING


def _env_status(plugin_id: str, code: Path | None) -> str:
    if plugin_launch(code) == "docker":
        return "docker"
    if _env_busy(plugin_id):
        return "installing"
    if _env_ready(plugin_id, code):
        return "ready"
    return "missing"


def load_state() -> dict[str, dict[str, Any]]:
    with _STATE_LOCK:
        path = _state_path()
        raw: dict[str, Any] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    raw = loaded
            except json.JSONDecodeError:
                raw = {}
        state: dict[str, dict[str, Any]] = {}
        for plugin_id in PLUGINS:
            current = _blank(plugin_id)
            saved = raw.get(plugin_id)
            if isinstance(saved, dict):
                current.update({key: saved.get(key, current[key]) for key in current})
            state[plugin_id] = current
        changed = False
        for plugin_id, row in state.items():
            wanted = str(plugin_models_dir(plugin_id))
            if row.get("models_dir") != wanted:
                row["models_dir"] = wanted
                changed = True
        if changed and path.is_file():
            _write_state(state)
        return state


def _write_state(state: dict[str, dict[str, Any]]) -> None:
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_state(state: dict[str, dict[str, Any]]) -> None:
    with _STATE_LOCK:
        _write_state(state)


def _log_path(plugin_id: str) -> Path:
    path = get_settings().data_dir / "plugin-logs" / f"{plugin_id}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _has_depth_weights(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    return any(path.is_file() and path.suffix.lower() in {".pt", ".pth"} for path in directory.iterdir())


def _model_status(plugin_id: str, directory: Path) -> str:
    thread = _DOWNLOAD_THREADS.get(plugin_id)
    if thread is not None and thread.is_alive():
        return "downloading"
    if plugin_id == "depth":
        return "ready" if _has_depth_weights(directory) else "missing"
    if directory.is_dir() and any(path.is_file() for path in directory.rglob("*")):
        return "ready"
    return "empty"


def _set_last_error(plugin_id: str, message: str) -> None:
    state = load_state()
    state[plugin_id]["last_error"] = message
    save_state(state)


def _download_default_depth_model() -> None:
    """把默认 MiDaS 权重流式写到约定目录。失败时把原因记到 last_error。"""
    directory = plugin_models_dir("depth")
    target = directory / _DEPTH_WEIGHT
    partial = directory / f"{_DEPTH_WEIGHT}.partial"
    try:
        request = urllib.request.Request(_DEPTH_WEIGHT_URL, headers={"User-Agent": "LiberAstra"})
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                got += len(chunk)
                if total > 0:
                    _MODEL_PROGRESS["depth"] = (min(99, int(got * 100 / total)), "model")
        partial.replace(target)
        _MODEL_PROGRESS.pop("depth", None)
        _set_last_error("depth", "")
    except Exception as exc:
        partial.unlink(missing_ok=True)
        _MODEL_PROGRESS.pop("depth", None)
        _set_last_error("depth", f"深度模型下载失败：{exc}")


def ensure_plugin_models(plugin_id: str) -> None:
    """安装后保证模型目录存在。深度目录没有权重时，在后台下载默认模型。"""
    plugin_models_dir(plugin_id)
    if plugin_id != "depth" or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if _has_depth_weights(plugin_models_dir("depth")):
        return
    with _DOWNLOAD_LOCK:
        thread = _DOWNLOAD_THREADS.get("depth")
        if thread is not None and thread.is_alive():
            return
        thread = threading.Thread(target=_download_default_depth_model, name="liber-depth-model", daemon=True)
        _DOWNLOAD_THREADS["depth"] = thread
        thread.start()


def _create_venv(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "venv", str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return
    uv = shutil.which("uv")
    if not uv:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or "无法创建插件虚拟环境")
    again = subprocess.run([uv, "venv", str(dest), "--python", sys.executable], capture_output=True, text=True, check=False)  # noqa: S603
    if again.returncode != 0:
        raise RuntimeError((again.stderr or again.stdout or "uv venv 失败").strip())


def _note_progress(plugin_id: str, percent: int, phase: str) -> None:
    bounded = max(0, min(100, percent))
    with _ENV_LOCK:
        targets = set(_ENV_PENDING)
        if _ENV_ACTIVE:
            targets.add(_ENV_ACTIVE)
        targets.add(plugin_id)
        for item in targets:
            _PROGRESS[item] = (bounded, phase)


def _parse_pip_fraction(text: str) -> float | None:
    """只看 pip 当前这一行。进度用 \\r 刷在同一行上，历史百分比不能盖住后面的体积进度。"""
    lines = text.replace("\r", "\n").splitlines()
    current = lines[-1] if lines else text
    percents = re.findall(r"(\d{1,3})%", current)
    if percents:
        return max(0.0, min(1.0, int(percents[-1]) / 100))
    amounts = re.findall(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*[KMG]B", current, flags=re.IGNORECASE)
    if not amounts:
        return None
    done, total = amounts[-1]
    whole = float(total)
    if whole <= 0:
        return None
    return max(0.0, min(1.0, float(done) / whole))


def _stream_command(log: Any, cmd: list[str], plugin_id: str, start: int, end: int, phase: str) -> None:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)  # noqa: S603
    assert proc.stdout is not None
    buffer = b""
    while True:
        chunk = proc.stdout.read(512)
        if not chunk:
            break
        log.write(chunk)
        log.flush()
        buffer = (buffer + chunk)[-6000:]
        fraction = _parse_pip_fraction(buffer.decode("utf-8", errors="replace"))
        if fraction is None:
            continue
        _note_progress(plugin_id, start + int((end - start) * fraction), phase)
    code = proc.wait()
    if code != 0:
        text = buffer.decode("utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        raise RuntimeError("\n".join(lines[-6:]) or "依赖安装失败")


def _adopt_legacy_runtime() -> None:
    """把已经开始安装的单插件环境挪到共用目录，避免再下一遍 PyTorch。"""
    dest = shared_runtime_dir()
    if _runtime_python().is_file() or dest.exists():
        return
    for plugin_id in ("depth", "speech"):
        legacy = get_settings().data_dir / "plugins" / plugin_id / "venv"
        python = legacy / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if not python.is_file():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(dest))
        return


def _ensure_shared_base(log: Any, plugin_id: str) -> None:
    if _base_ready():
        _note_progress(plugin_id, 70, "torch")
        return
    _adopt_legacy_runtime()
    runtime = shared_runtime_dir()
    py = _runtime_python()
    if not py.is_file():
        _note_progress(plugin_id, 2, "venv")
        _create_venv(runtime)
    if not py.is_file():
        raise RuntimeError("虚拟环境已创建，但找不到 python")
    _note_progress(plugin_id, 6, "venv")
    _stream_command(log, [str(py), "-m", "pip", "install", "--upgrade", "pip"], plugin_id, 6, 10, "venv")
    index = _torch_index()
    log.write(f"安装共用 PyTorch：{index}\n".encode())
    _note_progress(plugin_id, 10, "torch")
    _stream_command(
        log,
        [str(py), "-m", "pip", "install", "numpy", "torch", "torchvision", "--index-url", index],
        plugin_id,
        10,
        70,
        "torch",
    )
    (runtime / ".liber-base").write_text(_base_stamp(), encoding="utf-8")
    _note_progress(plugin_id, 70, "torch")


def _install_plugin_packages(log: Any, plugin_id: str, code: Path) -> None:
    if _packages_ready(plugin_id, code):
        _note_progress(plugin_id, 100, "packages")
        return
    py = _runtime_python()
    runtime = shared_runtime_dir()
    filtered = runtime / f"{plugin_id}-requirements.txt"
    _filtered_requirements(plugin_id, code / "requirements.txt", filtered)
    frozen = subprocess.run([str(py), "-m", "pip", "freeze"], capture_output=True, text=True, check=False)  # noqa: S603
    constraints = runtime / "base-constraints.txt"
    kept = [
        line.strip()
        for line in frozen.stdout.splitlines()
        if line.split("==", 1)[0].lower().replace("_", "-") in {"torch", "torchvision", "numpy"}
    ]
    constraints.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    command = [str(py), "-m", "pip", "install", "-r", str(filtered), "--upgrade-strategy", "only-if-needed"]
    if kept:
        command.extend(["-c", str(constraints)])
    _note_progress(plugin_id, 72, "packages")
    _stream_command(log, command, plugin_id, 72, 98, "packages")
    marker = get_settings().data_dir / "plugins" / plugin_id / ".packages-ready"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(_packages_stamp(code), encoding="utf-8")
    _note_progress(plugin_id, 100, "packages")


def _install_queued_envs() -> None:
    """先装共用的 PyTorch，再按插件补各自的依赖。已经有环境时直接跳过。"""
    global _ENV_ACTIVE
    while True:
        with _ENV_LOCK:
            if not _ENV_PENDING:
                _ENV_ACTIVE = ""
                return
            plugin_id = _ENV_PENDING.pop()
            _ENV_ACTIVE = plugin_id
        log_file = _log_path(plugin_id).open("ab")
        try:
            code = plugin_code_dir(plugin_id)
            if code is None or not (code / "requirements.txt").is_file():
                raise RuntimeError("找不到插件的 requirements.txt")
            log_file.write(f"\n准备 {plugin_id} 的共用 Python 环境\n".encode())
            _ensure_shared_base(log_file, plugin_id)
            _install_plugin_packages(log_file, plugin_id, code)
            _set_last_error(plugin_id, "")
        except Exception as exc:
            _set_last_error(plugin_id, f"插件环境安装失败：{exc}")
            _note_progress(plugin_id, 0, "")
        finally:
            log_file.close()
            with _ENV_LOCK:
                if _ENV_ACTIVE == plugin_id:
                    _ENV_ACTIVE = ""


def ensure_plugin_env(plugin_id: str) -> None:
    """已安装的插件如果还没有共用环境或自己的依赖，就在后台安装。测试里不下载。"""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    code = plugin_code_dir(plugin_id)
    if code is None or plugin_launch(code) == "docker":
        return
    if not (code / "requirements.txt").is_file() or _env_ready(plugin_id, code):
        return
    with _ENV_LOCK:
        _ENV_PENDING.add(plugin_id)
        _PROGRESS.setdefault(plugin_id, (1, "venv"))
        thread = _ENV_THREADS.get("shared")
        if thread is not None and thread.is_alive():
            return
        thread = threading.Thread(target=_install_queued_envs, name="liber-shared-env", daemon=True)
        _ENV_THREADS["shared"] = thread
        thread.start()


def _install_snapshot(plugin_id: str, code: Path | None, *, installed: bool, failed: bool) -> tuple[int, str]:
    """安装过程的进度和阶段。失败时不再显示进度。"""
    if failed:
        return (0, "")
    if _env_status(plugin_id, code) == "installing":
        return _PROGRESS.get(plugin_id, (1, "venv"))
    if _model_status(plugin_id, plugin_models_dir(plugin_id)) == "downloading":
        return _MODEL_PROGRESS.get(plugin_id, (1, "model"))
    if installed and not _env_ready(plugin_id, code) and plugin_launch(code) != "docker":
        return (1, "venv")
    return (0, "")


def _public(plugin_id: str, row: dict[str, Any]) -> dict[str, Any]:
    spec = PLUGINS[plugin_id]
    pid = row.get("pid")
    running = bool(row.get("enabled")) and (_pid_alive(pid) or _port_open(int(row["port"])))
    code = plugin_code_dir(plugin_id)
    models = plugin_models_dir(plugin_id)
    progress, phase = _install_snapshot(
        plugin_id,
        code,
        installed=bool(row["installed"]),
        failed=str(row.get("last_error") or "").startswith("插件环境安装失败"),
    )
    return {
        "id": plugin_id,
        "name": spec["name"],
        "description": spec["description"],
        "port": row["port"],
        "installed": bool(row["installed"]),
        "enabled": bool(row["enabled"]),
        "running": running,
        "device": row["device"],
        "models_dir": str(models),
        "code_dir": str(code) if code is not None else "",
        "launch": plugin_launch(code),
        "model_status": _model_status(plugin_id, models),
        "env_status": _env_status(plugin_id, code),
        "env_dir": "" if plugin_launch(code) == "docker" else str(shared_runtime_dir()),
        "install_progress": progress,
        "install_phase": phase,
        "last_error": row.get("last_error") or "",
    }


def list_plugins() -> list[dict[str, Any]]:
    state = load_state()
    for plugin_id, row in state.items():
        if row.get("installed"):
            ensure_plugin_models(plugin_id)
            ensure_plugin_env(plugin_id)
    return [_public(plugin_id, state[plugin_id]) for plugin_id in PLUGINS]


def _require(plugin_id: str) -> None:
    if plugin_id not in PLUGINS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未知插件")


def _local_provider(db: Session, owner_id: int, plugin_id: str) -> Provider | None:
    spec = PLUGINS[plugin_id]
    rows = db.scalars(
        select(Provider).where(Provider.owner_id == owner_id, Provider.type == spec["provider_type"])
    ).all()
    for row in rows:
        extra = row.extra or {}
        if extra.get("plugin_id") == plugin_id:
            return row
    return None


def _sync_provider(db: Session, owner_id: int, plugin_id: str, *, enabled: bool) -> None:
    spec = PLUGINS[plugin_id]
    info = PROVIDER_TYPES[spec["provider_type"]]
    row = _local_provider(db, owner_id, plugin_id)
    base_url = f"http://127.0.0.1:{spec['port']}"
    if row is None:
        row = Provider(
            name=spec["provider_name"],
            type=spec["provider_type"],
            base_url=base_url,
            capabilities=list(info.capabilities),
            enabled=enabled,
            extra={"plugin_local": True, "plugin_id": plugin_id},
            owner_id=owner_id,
            models=[],
        )
        db.add(row)
        from liberastra.services.providers import seed_model_catalog

        seed_model_catalog(row)
    else:
        row.enabled = enabled
        extra = dict(row.extra or {})
        extra["plugin_local"] = True
        extra["plugin_id"] = plugin_id
        row.extra = extra
        if not (row.base_url or "").strip():
            row.base_url = base_url
    db.commit()


def install_plugin(
    db: Session,
    owner_id: int,
    plugin_id: str,
    *,
    device: str | None = None,
) -> dict[str, Any]:
    _require(plugin_id)
    state = load_state()
    row = state[plugin_id]
    row["installed"] = True
    if device:
        row["device"] = device.strip()
    row["models_dir"] = str(plugin_models_dir(plugin_id))
    row["last_error"] = ""
    save_state(state)
    ensure_plugin_models(plugin_id)
    ensure_plugin_env(plugin_id)
    _sync_provider(db, owner_id, plugin_id, enabled=bool(row["enabled"]))
    return _public(plugin_id, row)


def uninstall_plugin(db: Session, owner_id: int, plugin_id: str) -> dict[str, Any]:
    _require(plugin_id)
    stop_process(plugin_id)
    state = load_state()
    row = state[plugin_id]
    row["installed"] = False
    row["enabled"] = False
    row["pid"] = None
    save_state(state)
    _sync_provider(db, owner_id, plugin_id, enabled=False)
    return _public(plugin_id, row)


def enable_plugin(db: Session, owner_id: int, plugin_id: str) -> dict[str, Any]:
    _require(plugin_id)
    state = load_state()
    row = state[plugin_id]
    if not row["installed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先安装插件")
    code = plugin_code_dir(plugin_id)
    if plugin_launch(code) != "docker" and not _env_ready(plugin_id, code):
        ensure_plugin_env(plugin_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="正在安装插件的 Python 环境，完成后才能启用。第一次会下载 PyTorch，可能要几分钟。",
        )
    try:
        pid = start_process(plugin_id, row)
    except HTTPException:
        raise
    except Exception as exc:
        row["enabled"] = False
        row["last_error"] = str(exc)
        save_state(state)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    row["enabled"] = True
    row["pid"] = pid
    row["last_error"] = ""
    save_state(state)
    _sync_provider(db, owner_id, plugin_id, enabled=True)
    return _public(plugin_id, load_state()[plugin_id])


def disable_plugin(db: Session, owner_id: int, plugin_id: str) -> dict[str, Any]:
    _require(plugin_id)
    stop_process(plugin_id)
    state = load_state()
    row = state[plugin_id]
    row["enabled"] = False
    row["pid"] = None
    save_state(state)
    _sync_provider(db, owner_id, plugin_id, enabled=False)
    return _public(plugin_id, row)


def _child_env(plugin_id: str, row: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    device = str(row.get("device") or "")
    models = str(plugin_models_dir(plugin_id))
    if plugin_id == "depth":
        env["LIBER_DEPTH_DEVICE"] = device or "cuda"
        env["LIBER_DEPTH_MODELS_DIR"] = models
        env["LIBER_DEPTH_RESULTS_DIR"] = str(get_settings().data_dir / "plugins" / "depth" / "results")
    else:
        env["LIBER_SPEECH_DEVICE"] = device or "auto"
        env["HF_HOME"] = models
        env["HUGGINGFACE_HUB_CACHE"] = models
        env["LIBER_SPEECH_MODELS_DIR"] = models
    return env


def start_process(plugin_id: str, row: dict[str, Any] | None = None) -> int | None:
    """启动本机插件。仓库里的 services 用当前 Python；带 install.ps1 的安装包用 Docker。"""
    spec = PLUGINS[plugin_id]
    state_row = row if row is not None else load_state()[plugin_id]
    port = int(state_row["port"])
    existing = _PROCS.get(plugin_id)
    if existing is not None and existing.poll() is None:
        return existing.pid
    pid = state_row.get("pid")
    if _pid_alive(pid) and _port_open(port):
        return int(pid)
    code = plugin_code_dir(plugin_id)
    launch = plugin_launch(code)
    state_row["launch"] = launch
    if launch == "docker":
        if _port_open(port):
            return None
        assert code is not None
        return _start_docker(plugin_id, code, state_row, port)
    if _port_open(port):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"端口 {port} 已被占用。若服务已手动启动，请到服务提供方连接，不必再启用本机插件。",
        )
    if code is None or not (code / "server.py").is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"找不到 {spec['name']} 程序。"
                f"开发目录是仓库 services/{plugin_id}；"
                "Windows 安装包的语音插件在 C:\\Program Files\\LiberSpeech，"
                "深度插件在安装目录 services\\depth 或 C:\\Program Files\\LiberDepth。"
            ),
        )
    log_file = _log_path(plugin_id).open("ab")
    kwargs: dict[str, Any] = {
        "cwd": str(code),
        "env": _child_env(plugin_id, state_row),
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    py = plugin_python(plugin_id)
    if not py.is_file():
        log_file.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="插件的 Python 环境还没安装完成。请先在插件页安装，等依赖装完再启用。",
        )
    proc = subprocess.Popen(  # noqa: S603
        [str(py), "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port)],
        **kwargs,
    )
    _PROCS[plugin_id] = proc
    if not _wait_ready(proc, port):
        tail = _log_tail(plugin_id)
        stop_process(plugin_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=tail or f"{spec['name']} 启动失败。请确认本机已安装该服务的 Python 依赖。",
        )
    return proc.pid


def _start_docker(plugin_id: str, code: Path, row: dict[str, Any], port: int) -> None:
    log_file = _log_path(plugin_id).open("ab")
    try:
        completed = subprocess.run(  # noqa: S603
            ["docker", "compose", "up", "-d"],
            cwd=str(code),
            env=_child_env(plugin_id, row),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    finally:
        log_file.close()
    if completed.returncode != 0 or not _wait_port(port, seconds=40):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_log_tail(plugin_id) or f"{PLUGINS[plugin_id]['name']} 的 Docker 启动失败。请确认已安装 Docker。",
        )
    return None


def _wait_port(port: int, *, seconds: float) -> bool:
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _port_open(port):
            return True
        time.sleep(0.4)
    return _port_open(port)


def _wait_ready(proc: subprocess.Popen[bytes], port: int) -> bool:
    import time

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        if _port_open(port):
            return True
        time.sleep(0.4)
    return _port_open(port)


def _log_tail(plugin_id: str) -> str:
    path = _log_path(plugin_id)
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-8:])


def stop_process(plugin_id: str, *, stop_docker: bool = True) -> None:
    code = plugin_code_dir(plugin_id)
    if plugin_launch(code) == "docker":
        if stop_docker and code is not None:
            subprocess.run(  # noqa: S603
                ["docker", "compose", "stop"],
                cwd=str(code),
                check=False,
                capture_output=True,
            )
        return
    proc = _PROCS.pop(plugin_id, None)
    pid = proc.pid if proc is not None and proc.poll() is None else None
    if pid is None:
        pid = load_state()[plugin_id].get("pid")
    if not pid or not _pid_alive(pid):
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], check=False, capture_output=True)
    else:
        import signal

        try:
            os.killpg(int(pid), signal.SIGTERM)
        except OSError:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except OSError:
                return
    if proc is not None:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def restore_enabled_plugins() -> None:
    """主服务启动时，把标记为启用的本机插件拉起来。"""
    from liberastra.core.db import SessionLocal

    state = load_state()
    db = SessionLocal()
    try:
        for plugin_id, row in state.items():
            if not row.get("installed") or not row.get("enabled"):
                continue
            try:
                row["pid"] = start_process(plugin_id, row)
                row["last_error"] = ""
            except HTTPException as exc:
                row["enabled"] = False
                row["pid"] = None
                row["last_error"] = str(exc.detail)
                _disable_providers(db, plugin_id)
        save_state(state)
    finally:
        db.close()


def _disable_providers(db: Session, plugin_id: str) -> None:
    spec = PLUGINS[plugin_id]
    rows = db.scalars(select(Provider).where(Provider.type == spec["provider_type"])).all()
    changed = False
    for row in rows:
        extra = row.extra or {}
        if extra.get("plugin_id") == plugin_id and row.enabled:
            row.enabled = False
            changed = True
    if changed:
        db.commit()


def stop_managed_plugins() -> None:
    """主服务退出时关掉由插件管理器拉起的进程。"""
    state = load_state()
    for plugin_id, row in state.items():
        if row.get("enabled") or _PROCS.get(plugin_id) is not None:
            stop_process(plugin_id, stop_docker=False)
            row["pid"] = None
    save_state(state)

"""astra CLI 远程 HTTP 客户端与 Agent 约定（稳定退出码、Job 等待、产物落盘）。

退出码：0 成功、2 参数错误（Typer 内置）、3 服务不可用、4 任务失败。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from liberastra.cli.config import resolve

TERMINAL = ("succeeded", "failed", "canceled")


class CliError(Exception):
    exit_code = 1


class ServiceUnavailable(CliError):
    exit_code = 3


class JobFailed(CliError):
    exit_code = 4


class ApiClient:
    def __init__(self, server: str, token: str | None = None, timeout: float = 60.0) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = httpx.Client(base_url=server, headers=headers, timeout=timeout)

    @classmethod
    def from_config(cls, server: str | None = None, token: str | None = None) -> ApiClient:
        host, tok = resolve(server, token)
        return cls(host, tok)

    def close(self) -> None:
        self._http.close()

    def set_token(self, token: str) -> None:
        self._http.headers["Authorization"] = f"Bearer {token}"

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ServiceUnavailable(f"无法连接服务端: {exc}") from exc
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text[:300])
            except ValueError:
                detail = resp.text[:300]
            if resp.status_code == 401:
                raise CliError("凭据无效，请先 astra login")
            raise CliError(f"HTTP {resp.status_code}: {detail}")
        if resp.status_code == 204:
            return None
        return resp.json()

    def request_bytes(self, path: str) -> bytes:
        try:
            resp = self._http.get(path)
        except httpx.HTTPError as exc:
            raise ServiceUnavailable(f"无法连接服务端: {exc}") from exc
        if resp.status_code >= 400:
            raise CliError(f"下载失败 HTTP {resp.status_code}")
        return resp.content

    # ---- Job ----

    def wait_job(self, job_id: str, timeout: float = 3600.0, poll: float = 1.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self.request("GET", f"/api/v1/jobs/{job_id}")
            if job["status"] in TERMINAL:
                if job["status"] != "succeeded":
                    raise JobFailed(f"任务 {job_id} {job['status']}: {job.get('error') or ''}")
                return job
            time.sleep(poll)
        raise JobFailed(f"等待任务 {job_id} 超时")

    def submit_and_wait(self, method: str, path: str, timeout: float = 3600.0, **kwargs: Any) -> dict:
        job = self.request(method, path, **kwargs)
        return self.wait_job(job["id"], timeout=timeout)

    # ---- 产物 ----

    def save_outputs(
        self, job: dict, out: Path | None, *, default_name: str, kind: str | None = None
    ) -> list[Path]:
        """下载 Job 的资产产物到本地。out 为文件路径（单产物）或目录（多产物）。"""
        entries = [
            o
            for o in job.get("outputs", [])
            if o.get("type") == "asset" and o.get("asset_id") and (kind is None or o.get("kind") == kind)
        ]
        if not entries:
            raise JobFailed("任务没有可下载的产物")
        saved: list[Path] = []
        single = len(entries) == 1
        for i, entry in enumerate(entries):
            content = self.request_bytes(f"/api/v1/assets/{entry['asset_id']}/content")
            if out is None:
                name = entry.get("filename") or f"{default_name}_{i}"
                target = Path.cwd() / name
            elif single and out.suffix:
                target = out
            else:
                out.mkdir(parents=True, exist_ok=True)
                target = out / (entry.get("filename") or f"{default_name}_{i}")
            target.write_bytes(content)
            saved.append(target)
        return saved

    def health(self) -> dict:
        return self.request("GET", "/healthz")


def parse_params(raw: str | None) -> dict:
    """参数来源：@file.json、stdin（-）或内联 JSON。"""
    if not raw:
        return {}
    if raw == "-":
        import sys

        raw = sys.stdin.read()
    elif raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(f"JSON 参数解析失败: {exc}") from exc
    if not isinstance(value, dict):
        raise CliError("JSON 参数必须是对象")
    return value

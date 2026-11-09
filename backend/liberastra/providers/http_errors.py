"""把 httpx 异常翻译成统一的 ProviderError 文案。"""

from __future__ import annotations

import httpx

from liberastra.providers.base import ProviderError


def http_provider_error(url: str, timeout: float, exc: httpx.HTTPError) -> ProviderError:
    """区分连接超时、读/写/池超时和普通连接失败。

    ConnectTimeout 是 TimeoutException 的子类，必须先判断。
    """
    if isinstance(exc, httpx.ConnectTimeout):
        return ProviderError(f"连接超时 {url}（>{timeout:.0f}s，ConnectTimeout）")
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError(f"请求超时 {url}（>{timeout:.0f}s，{type(exc).__name__}）")
    detail = str(exc).strip() or type(exc).__name__
    return ProviderError(f"无法连接 {url}: {detail}")

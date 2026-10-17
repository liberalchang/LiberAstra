"""HTML 分镜帧渲染：Playwright 在独立线程的 Proactor 事件循环里跑。

uvicorn 在 Windows 下可能使用 SelectorEventLoop（不支持创建子进程），
而 Playwright 启动浏览器必须 spawn 子进程。渲染因此放到独立线程：
该线程拥有自己的 ProactorEventLoop，与 ASGI 服务器的事件循环完全解耦，
同时规避「async_playwright 绑定到已关闭循环」一类问题。
"""

from __future__ import annotations

import asyncio
import sys
import threading

from liberastra.providers.base import ProviderError

_thread: threading.Thread | None = None
_loop: asyncio.AbstractEventLoop | None = None
_start_lock = threading.Lock()

# 以下都属于渲染线程的事件循环
_browser = None
_pw = None
_init_lock: asyncio.Lock | None = None


def _thread_main(ready: threading.Event) -> None:
    global _loop
    if sys.platform == "win32":
        asyncio.set_event_loop(asyncio.ProactorEventLoop())
    else:
        asyncio.set_event_loop(asyncio.new_event_loop())
    _loop = asyncio.get_event_loop()
    ready.set()
    _loop.run_forever()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _thread
    with _start_lock:
        if _loop is None or not _loop.is_running():
            ready = threading.Event()
            _thread = threading.Thread(
                target=_thread_main, args=(ready,), name="htmlframe-render", daemon=True
            )
            _thread.start()
            ready.wait()
            assert _loop is not None
    return _loop


async def _ensure_browser():  # noqa: ANN202  运行在渲染线程的循环里
    global _browser, _pw, _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    async with _init_lock:
        if _browser is not None and _browser.is_connected():
            return _browser
        from playwright.async_api import async_playwright

        _pw = await async_playwright().start()
        for channel in ("msedge", "chrome"):
            try:
                _browser = await _pw.chromium.launch(channel=channel)
                return _browser
            except Exception:  # noqa: BLE001 逐个尝试可用浏览器
                continue
        try:
            _browser = await _pw.chromium.launch()
            return _browser
        except Exception as exc:
            raise ProviderError(
                "渲染模板需要浏览器：请安装 Microsoft Edge 或 Google Chrome，"
                "或执行 `playwright install chromium` 安装自带浏览器。"
            ) from exc


# 渲染后按文本内容精确定位模板元素，做显隐/字号缩放（31 套模板类名各异，无法靠选择器统一）
# 同一段文案可能在模板里出现多处（中部卡片 + 底部等），必须全部处理；只作用于最深的匹配节点
_ADJUST_JS = """(opt) => {
  const norm = (s) => (s || "").replace(/\\s+/g, " ").trim();
  const findAll = (t) => {
    const target = norm(t);
    if (!target) return [];
    const matched = [...document.querySelectorAll("body *")].filter(
      (e) => norm(e.textContent) === target
    );
    // 祖先与后代同时匹配时只留后代（避免重复处理）；不同位置的多处副本都保留
    return matched.filter((e) => !matched.some((o) => o !== e && e.contains(o)));
  };
  const apply = (els, hide, scale) => {
    for (const el of els) {
      if (hide) el.style.visibility = "hidden";  // 保留占位，不塌陷排版
      if (scale && scale !== 1) {
        // 文案可能包在多层 span 里，容器与子元素一起缩放
        const targets = el.children.length ? [el, ...el.querySelectorAll("*")] : [el];
        for (const t of targets) {
          const cur = parseFloat(getComputedStyle(t).fontSize);
          if (cur) t.style.fontSize = `${cur * scale}px`;
        }
      }
    }
  };
  apply(findAll(opt.title), !!opt.hideTitle, opt.titleScale || 1);
  apply(findAll(opt.text), !!opt.hideText, opt.textScale || 1);
}"""


async def _render(html: str, width: int, height: int, fmt: str, adjust: dict | None) -> bytes:
    browser = await _ensure_browser()
    page = await browser.new_page(viewport={"width": width, "height": height})
    try:
        await page.set_content(html, wait_until="load")
        # 等网络字体/图片就绪；离线或资源失败时最多等 3 秒，不阻塞出帧
        try:
            await page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:  # noqa: BLE001
            pass
        if adjust:
            await page.evaluate(_ADJUST_JS, adjust)
        if fmt == "jpeg":
            return await page.screenshot(type="jpeg", quality=70)
        return await page.screenshot(type="png")
    finally:
        await page.close()


async def render_html(
    html: str,
    *,
    width: int,
    height: int,
    fmt: str = "png",
    adjust: dict | None = None,
) -> bytes:
    """把 HTML 按指定视口渲染并截图。fmt=png 用于出帧，jpeg(q70) 用于预览缩略图。

    adjust 可选：{"title": str, "text": str, "hideTitle": bool, "hideText": bool,
    "titleScale": float, "textScale": float}——按文本内容定位模板元素做显隐/缩放。
    可从任意事件循环调用：实际渲染在渲染线程里执行。
    """
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(_render(html, width, height, fmt, adjust), loop)
    return await asyncio.wrap_future(future)


async def close_browser() -> None:
    """进程退出前调用（lifespan shutdown）。从任意线程调用都安全。"""
    global _browser, _pw
    loop = _loop
    if loop is None:
        return

    async def _close() -> None:
        global _browser, _pw
        try:
            if _browser is not None:
                await _browser.close()
        except Exception:  # noqa: BLE001 关闭阶段的异常不影响退出
            pass
        _browser = None
        try:
            if _pw is not None:
                await _pw.stop()
        except Exception:  # noqa: BLE001
            pass
        _pw = None

    try:
        future = asyncio.run_coroutine_threadsafe(_close(), loop)
        await asyncio.wrap_future(future)
    except Exception:  # noqa: BLE001
        pass

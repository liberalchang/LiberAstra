"""认证二进制内容的缓存头：允许浏览器缓存，但每次使用前必须重新验证。"""

BINARY_CACHE = {"Cache-Control": "private, no-cache"}

"""ComfyUI 图像适配器：工作流包驱动（t2i / i2i / upscale / 修复等）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.providers.comfyui.workflow import (
    download_files,
    extract_files,
    run_workflow_pack,
)
from liberastra.services.workflows import WorkflowPack


class ComfyUIImage:
    def __init__(self, base_url: str, *, client: ComfyClient | None = None) -> None:
        self.client = client or ComfyClient(base_url)

    async def generate(
        self,
        *,
        pack: WorkflowPack,
        inputs: dict[str, Any],
        on_progress: Callable[[float], None] | None = None,
        use_ws: bool = True,
        wait_timeout: float | None = None,
    ) -> list[tuple[str, bytes]]:
        """按工作流包生成，返回 [(文件名, 字节)]。wait_timeout 为 None 时用默认 600 秒。"""
        outputs = await run_workflow_pack(
            self.client, pack, inputs, on_progress=on_progress, use_ws=use_ws, wait_timeout=wait_timeout
        )
        images = await download_files(self.client, extract_files(outputs, pack, ("images",)))
        if not images:
            raise ProviderError("ComfyUI 完成但未产出图像")
        return images

    async def test(self) -> str:
        return await self.client.test()

    async def list_models(self) -> list[str]:
        return await self.client.list_model_files()

    async def list_model_folder(self, folder: str) -> list[str]:
        return await self.client.list_model_folder(folder)

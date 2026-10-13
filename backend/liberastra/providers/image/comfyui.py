"""ComfyUI 图像适配器：工作流包驱动（t2i / i2i / upscale / 修复等）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.services.workflows import WorkflowPack, apply_inputs, inject_image_input
from liberastra.storage import resolve


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
    ) -> list[tuple[str, bytes]]:
        """按工作流包生成，返回 [(文件名, 字节)]。"""
        workflow = apply_inputs(pack, inputs)

        # 图像类输入：先上传 ComfyUI，再回填文件名
        for key, spec in pack.inputs.items():
            if spec.get("type") != "image" or key not in inputs:
                continue
            local_path = resolve(str(inputs[key]))
            if not local_path.exists():
                raise ProviderError(f"输入图像不存在: {inputs[key]}")
            comfy_name = await self.client.upload_image(
                local_path.name, local_path.read_bytes()
            )
            inject_image_input(workflow, pack, key, comfy_name)

        prompt_id = await self.client.queue_prompt(workflow)
        result = await self.client.wait_result(
            prompt_id, on_progress=on_progress, use_ws=use_ws
        )

        outputs = result.get("outputs", {})
        images: list[tuple[str, bytes]] = []
        node_ids = [str(pack.outputs["node"])] if pack.outputs.get("node") else list(outputs)
        for node_id in node_ids:
            for img in outputs.get(node_id, {}).get("images", []):
                content = await self.client.download(
                    img["filename"], img.get("subfolder", ""), img.get("type", "output")
                )
                images.append((img["filename"], content))
        if not images:
            raise ProviderError("ComfyUI 完成但未产出图像")
        return images

    async def test(self) -> str:
        return await self.client.test()

    async def list_models(self) -> list[str]:
        return await self.client.list_checkpoints()

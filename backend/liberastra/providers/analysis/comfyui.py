"""ComfyUI 素材分析适配器：analysis 能力的工作流包驱动（AILab_QwenVL 等视觉节点）。"""

from __future__ import annotations

from typing import Any

from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.providers.comfyui.workflow import extract_texts, run_workflow_pack
from liberastra.services.workflows import WorkflowPack


class ComfyUIAnalysis:
    """跑分析工作流包，返回素材的文本描述。"""

    def __init__(self, base_url: str, *, client: ComfyClient | None = None) -> None:
        self.client = client or ComfyClient(base_url)

    async def analyze(
        self,
        *,
        pack: WorkflowPack,
        inputs: dict[str, Any],
        wait_timeout: float | None = None,
    ) -> str:
        """按工作流包分析素材，返回描述文本。"""
        outputs = await run_workflow_pack(self.client, pack, inputs, wait_timeout=wait_timeout)
        texts = extract_texts(outputs, pack)
        if not texts:
            raise ProviderError("分析工作流完成但未产出文本（检查展示节点输出）")
        return "\n".join(texts)

    async def test(self) -> str:
        return await self.client.test()

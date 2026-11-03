"""PoseStudio 工作流包与上传前预处理的接线测试。"""

import asyncio
import uuid
from io import BytesIO

from PIL import Image, ImageDraw

from liberastra.core.config import get_settings
from liberastra.providers.comfyui.workflow import run_workflow_pack
from liberastra.services.workflows import WorkflowPack, get_pack


class _FakeClient:
    max_upload_bytes = 10**9

    def __init__(self) -> None:
        self.uploaded: list[tuple[str, bytes]] = []
        self.workflow: dict | None = None

    async def upload_image(self, filename: str, content: bytes, *, overwrite: bool = True) -> str:
        self.uploaded.append((filename, content))
        return filename

    async def queue_prompt(self, workflow: dict) -> str:
        self.workflow = workflow
        return "pid-pose"

    async def wait_result(self, prompt_id: str, **kwargs) -> dict:
        return {"outputs": {}}


def test_posestudio_pack_wires_person_and_pose_control() -> None:
    pack = get_pack("qwen_image_21_posestudio")

    assert pack.inputs["image"]["label"] == "人物照"
    assert pack.inputs["image"]["node"] == "7"
    assert pack.inputs["image_2"]["label"] == "姿势参考图"
    assert pack.inputs["image_2"]["node"] == "6"
    assert pack.inputs["image_2"]["preprocess"] == "pose_control"
    assert pack.workflow["2"]["class_type"] == "LoraLoaderModelOnly"
    assert pack.workflow["2"]["inputs"]["lora_name"] == "VNCCS_QI2_PoseStudioV1.1.safetensors"
    assert pack.workflow["8"]["class_type"] == "TextEncodeQwenImage21"
    assert pack.workflow["8"]["inputs"]["images.image_1"] == ["6", 0]
    assert pack.workflow["8"]["inputs"]["images.image_2"] == ["7", 0]
    assert pack.workflow["9"]["class_type"] == "GetImageSize"
    assert pack.workflow["10"]["class_type"] == "EmptyLatentImage"
    assert pack.workflow["10"]["inputs"]["width"] == ["9", 0]
    assert pack.workflow["10"]["inputs"]["height"] == ["9", 1]
    assert pack.workflow["11"]["inputs"]["steps"] == 25
    assert pack.workflow["11"]["inputs"]["cfg"] == 1
    assert "LoraLoaderModelOnly" in (pack.requirements.get("nodes") or [])


def test_posestudio_gen_pack_has_single_pose_slot() -> None:
    pack = get_pack("qwen_image_21_posestudio_gen")

    assert "image_2" not in pack.inputs
    assert pack.inputs["image"]["node"] == "6"
    assert pack.inputs["image"]["preprocess"] == "pose_control"
    assert "images.image_2" not in pack.workflow["8"]["inputs"]
    assert "t-shirt" in pack.inputs["prompt"]["default"]
    assert "trousers" in pack.inputs["prompt"]["default"]
    assert "t-shirt" in pack.workflow["8"]["inputs"]["prompt"]


def test_pose_control_is_cropped_before_upload() -> None:
    image = Image.new("RGB", (400, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([120, 60, 280, 540], outline="black", width=4)
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    name = f"pose-{uuid.uuid4().hex}.png"
    relative = f"uploads/{name}"
    target = get_settings().data_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(buffer.getvalue())

    pack = WorkflowPack(
        name="pose-test",
        capability="i2i",
        description="",
        inputs={
            "image": {
                "node": "1",
                "field": "inputs.image",
                "type": "image",
                "required": True,
                "preprocess": "pose_control",
            }
        },
        outputs={},
        workflow={"1": {"class_type": "LoadImage", "inputs": {"image": "example.png"}}},
        source="builtin",
    )
    client = _FakeClient()

    asyncio.run(run_workflow_pack(client, pack, {"image": relative}))

    assert len(client.uploaded) == 1
    uploaded_name, uploaded_bytes = client.uploaded[0]
    assert uploaded_name.endswith("_pose.png")
    assert uploaded_bytes != buffer.getvalue()
    assert client.workflow is not None
    assert client.workflow["1"]["inputs"]["image"] == uploaded_name

    cropped = Image.open(BytesIO(uploaded_bytes))
    assert cropped.width < image.width
    assert cropped.height < image.height

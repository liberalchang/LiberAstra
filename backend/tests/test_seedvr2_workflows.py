"""SeedVR2 图片增强与视频增强工作流包结构。"""

from liberastra.providers.catalog import pack_sub_capability
from liberastra.services.workflows import get_pack


def test_seedvr2_image_pack() -> None:
    pack = get_pack("seedvr2_3b_image_restore")
    assert pack.capability == "upscale"
    assert pack.inputs["image"]["required"] is True
    assert pack.inputs["model_name"]["default"] == "seedvr2_ema_3b_fp16.safetensors"
    assert pack.inputs["vae_name"]["default"] == "ema_vae_fp16.safetensors"
    assert pack.workflow["3"]["class_type"] == "SeedVR2LoadDiTModel"
    assert pack.workflow["4"]["class_type"] == "SeedVR2LoadVAEModel"
    assert pack.workflow["5"]["class_type"] == "SeedVR2VideoUpscaler"
    assert pack.workflow["5"]["inputs"]["batch_size"] == 1
    assert pack.workflow["6"]["class_type"] == "SaveImage"
    assert "SeedVR2VideoUpscaler" in (pack.requirements.get("nodes") or [])
    assert pack_sub_capability(pack.name, pack.capability, 1) == "upscale"


def test_seedvr2_video_pack() -> None:
    pack = get_pack("seedvr2_3b_video_restore")
    assert pack.capability == "v2v"
    assert pack.inputs["video"]["required"] is True
    assert pack.inputs["batch_size"]["default"] == 5
    assert pack.inputs["batch_size"]["step"] == 4
    assert pack.workflow["2"]["class_type"] == "GetVideoComponents"
    assert pack.workflow["5"]["class_type"] == "SeedVR2VideoUpscaler"
    assert pack.workflow["5"]["inputs"]["batch_size"] == 5
    assert pack.workflow["6"]["class_type"] == "VHS_VideoCombine"
    assert pack.workflow["6"]["inputs"]["frame_rate"] == ["2", 2]
    assert pack.workflow["6"]["inputs"]["audio"] == ["2", 1]
    assert pack_sub_capability(pack.name, pack.capability, 0) == "video_upscale"

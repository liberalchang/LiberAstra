"""视频流水线测试：快速创作（真实 ffmpeg + 假 Provider）、i2v、自定义素材。"""

import asyncio
import base64
import io
import json
import shutil
import wave

import pytest
from fastapi.testclient import TestClient

from liberastra.pipelines import quick, simple

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="需要 ffmpeg")


def _wav_bytes(seconds: float = 0.3, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


class _FakeLLM:
    async def chat(self, *, model: str, messages: list, **kwargs) -> str:
        system = messages[0]["content"]
        await asyncio.sleep(0)
        if "分镜的口播文案" in system or "口播文案" in system:
            return json.dumps({"title": "测试视频", "segments": ["第一句口播", "第二句口播"]})
        return json.dumps(
            {
                "frames": [
                    {"text": "第一句口播", "visual": "蓝色天空"},
                    {"text": "第二句口播", "visual": "绿色草地"},
                ]
            }
        )


class _FakeTTS:
    async def synthesize(self, *, text: str, voice: str, **kwargs) -> bytes:
        await asyncio.sleep(0)
        return _wav_bytes()


async def _fake_produce_images(provider, **kwargs):  # noqa: ANN001, ANN202
    await asyncio.sleep(0)
    return [("frame.png", PNG_1PX)]


@pytest.fixture()
def video_providers(client: TestClient, auth_header: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quick, "build_llm_adapter", lambda record, **_kw: _FakeLLM())
    monkeypatch.setattr(quick, "build_tts_adapter", lambda record, **_kwargs: _FakeTTS())
    monkeypatch.setattr(quick, "produce_images", _fake_produce_images)
    monkeypatch.setattr(simple, "build_llm_adapter", lambda record, **_kw: _FakeLLM())
    monkeypatch.setattr(simple, "build_tts_adapter", lambda record, **_kwargs: _FakeTTS())

    for name, ptype in (("llm", "openai_compatible"), ("tts", "openai_tts"), ("img", "openai_images")):
        resp = client.post(
            "/api/v1/providers",
            json={"name": name, "type": ptype, "base_url": "http://mock/v1"},
            headers=auth_header,
        )
        assert resp.status_code == 201


def test_quick_video_with_script(
    client: TestClient, auth_header: dict[str, str], video_providers: None
) -> None:
    resp = client.post(
        "/api/v1/videos/quick?wait=true",
        json={
            "script": "第一句口播\n第二句口播",
            "split_mode": "line",
            "voice": "v1",
            "aspect": "1:1",
        },
        headers=auth_header,
        timeout=120,
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]

    kinds = [o.get("kind") for o in job["outputs"]]
    assert "storyboard" in kinds and "video" in kinds

    video_asset = next(o for o in job["outputs"] if o.get("kind") == "video")
    content = client.get(f"/api/v1/assets/{video_asset['asset_id']}/content", headers=auth_header)
    assert content.status_code == 200
    assert len(content.content) > 100

    storyboard_asset = next(o for o in job["outputs"] if o.get("kind") == "storyboard")
    sb = client.get(f"/api/v1/assets/{storyboard_asset['asset_id']}/content", headers=auth_header)
    frames = sb.json()["frames"]
    assert frames[0]["visual"] == "蓝色天空"


def test_quick_video_storyboard_only(
    client: TestClient, auth_header: dict[str, str], video_providers: None
) -> None:
    resp = client.post(
        "/api/v1/videos/quick?wait=true",
        json={"topic": "三只小猪", "voice": "v1", "storyboard_only": True},
        headers=auth_header,
        timeout=60,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    assert all(o.get("kind") == "storyboard" for o in job["outputs"])


def test_quick_video_optimize_visuals_off(
    client: TestClient, auth_header: dict[str, str], video_providers: None
) -> None:
    """关闭画面提示词优化时，visual 等于口播原文（不走 STORYBOARD LLM）。"""
    resp = client.post(
        "/api/v1/videos/quick?wait=true",
        json={
            "script": "第一句口播\n第二句口播",
            "split_mode": "line",
            "voice": "v1",
            "aspect": "1:1",
            "optimize_visuals": False,
            "storyboard_only": True,
        },
        headers=auth_header,
        timeout=60,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    storyboard_asset = next(o for o in job["outputs"] if o.get("kind") == "storyboard")
    sb = client.get(f"/api/v1/assets/{storyboard_asset['asset_id']}/content", headers=auth_header)
    frames = sb.json()["frames"]
    assert frames[0]["text"] == "第一句口播"
    assert frames[0]["visual"] == "第一句口播"
    assert frames[1]["visual"] == "第二句口播"


def test_quick_video_with_provided_storyboard(
    client: TestClient, auth_header: dict[str, str], video_providers: None
) -> None:
    resp = client.post(
        "/api/v1/videos/quick?wait=true",
        json={
            "storyboard": {
                "title": "编辑后",
                "frames": [{"text": "人工修改的一句", "visual": "红色背景"}],
            },
            "voice": "v1",
            "aspect": "16:9",
        },
        headers=auth_header,
        timeout=120,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]


def test_i2v_job(
    client: TestClient, auth_header: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeVideo:
        def __init__(self, base_url: str) -> None:
            pass

        async def generate(self, **kwargs):  # noqa: ANN003, ANN202
            await asyncio.sleep(0)
            return [("out.mp4", b"MP4DATA")], []

    monkeypatch.setattr(simple, "ComfyUIVideo", _FakeVideo)

    provider = client.post(
        "/api/v1/providers",
        json={"name": "comfy", "type": "comfyui", "base_url": "http://mock:8188"},
        headers=auth_header,
    ).json()
    pack = client.post(
        "/api/v1/workflows/import",
        json={
            "name": "i2v_pack",
            "capability": "i2v",
            "workflow": {"1": {"class_type": "N", "inputs": {"image": "", "prompt": ""}}},
            "inputs": {
                "image": {"node": "1", "field": "inputs.image", "type": "image"},
                "prompt": {"node": "1", "field": "inputs.prompt", "type": "str"},
            },
            "outputs": {"node": "1"},
        },
        headers=auth_header,
    )
    assert pack.status_code == 201

    resp = client.post(
        "/api/v1/videos/i2v?wait=true",
        files={"image": ("a.png", PNG_1PX, "image/png")},
        data={"workflow": "i2v_pack", "prompt": "动起来", "provider_id": str(provider["id"])},
        headers=auth_header,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    assert job["outputs"][0]["kind"] == "video"


def test_assets_video(client: TestClient, auth_header: dict[str, str], video_providers: None) -> None:
    resp = client.post(
        "/api/v1/videos/assets?wait=true",
        files=[("images", ("a.png", PNG_1PX, "image/png")), ("images", ("b.png", PNG_1PX, "image/png"))],
        data={"script": "第一句\n第二句", "voice": "v1", "aspect": "1:1"},
        headers=auth_header,
        timeout=120,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    # 无 BGM 时最终文件名是 concat.mp4；有 BGM 才写成 final.mp4
    assert job["outputs"][0]["filename"] in ("concat.mp4", "final.mp4")
    assert job["outputs"][0]["kind"] == "video"


def test_assets_subtitle_rejected(client: TestClient, auth_header: dict[str, str]) -> None:
    files = [("images", ("a.png", PNG_1PX, "image/png"))]
    bad_color = client.post(
        "/api/v1/videos/assets",
        files=files,
        data={"script": "一句", "subtitle_color": "yellow"},
        headers=auth_header,
    )
    assert bad_color.status_code == 400
    bad_size = client.post(
        "/api/v1/videos/assets",
        files=files,
        data={"script": "一句", "subtitle_size": "200"},
        headers=auth_header,
    )
    assert bad_size.status_code == 400


def test_assets_subtitle_style(
    client: TestClient, auth_header: dict[str, str], video_providers: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []
    original = simple.ffmpeg.make_segment

    async def spy(**kwargs):  # noqa: ANN003, ANN202
        seen.append(kwargs)
        await original(**kwargs)

    monkeypatch.setattr(simple.ffmpeg, "make_segment", spy)
    resp = client.post(
        "/api/v1/videos/assets?wait=true",
        files=[("images", ("a.png", PNG_1PX, "image/png"))],
        data={
            "script": "第一句",
            "voice": "v1",
            "aspect": "1:1",
            "show_subtitle": "true",
            "subtitle_size": "28",
            "subtitle_color": "#FFCC00",
        },
        headers=auth_header,
        timeout=120,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    assert job["params"]["show_subtitle"] is True
    assert job["params"]["subtitle_size"] == 28
    assert job["params"]["subtitle_color"] == "#FFCC00"
    assert seen[0]["subtitle"] is not None
    assert seen[0]["subtitle_size"] == 28
    assert seen[0]["subtitle_color"] == "#FFCC00"


def test_assets_subtitle_off(
    client: TestClient, auth_header: dict[str, str], video_providers: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []
    original = simple.ffmpeg.make_segment

    async def spy(**kwargs):  # noqa: ANN003, ANN202
        seen.append(kwargs)
        await original(**kwargs)

    monkeypatch.setattr(simple.ffmpeg, "make_segment", spy)
    resp = client.post(
        "/api/v1/videos/assets?wait=true",
        files=[("images", ("a.png", PNG_1PX, "image/png"))],
        data={"script": "第一句", "voice": "v1", "aspect": "1:1", "show_subtitle": "false"},
        headers=auth_header,
        timeout=120,
    )
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    assert job["params"]["show_subtitle"] is False
    assert seen and seen[0]["subtitle"] is None

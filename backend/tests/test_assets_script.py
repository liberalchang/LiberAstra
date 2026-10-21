"""看素材写文案：分段校验、分析包是否齐、接口缺包时直接拒绝。"""

from fastapi.testclient import TestClient

from liberastra.pipelines.simple import analysis_pack_gaps, segments_from_reply
from liberastra.providers.base import ProviderError


def test_analysis_pack_gaps() -> None:
    image = [{"kind": "image"}]
    video = [{"kind": "video"}]
    assert analysis_pack_gaps(image, "", "") == "有图片素材，请选择图片分析工作流"
    assert analysis_pack_gaps(video, "img", "") == "有视频素材，请选择视频分析工作流"
    assert analysis_pack_gaps(image + video, "img", "vid") == ""


def test_segments_from_reply_requires_one_line_per_clip() -> None:
    assert segments_from_reply({"segments": [" 第一句 ", "第二句"]}, 2) == ["第一句", "第二句"]
    try:
        segments_from_reply({"segments": ["只有一句"]}, 2)
    except ProviderError as exc:
        assert "不一致" in str(exc)
    else:
        raise AssertionError("数量不对时应失败")


def test_assets_script_requires_analysis_pack(client: TestClient, auth_header: dict[str, str]) -> None:
    resp = client.post(
        "/api/v1/videos/assets/script",
        headers=auth_header,
        files={"images": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert resp.status_code == 400
    assert "图片分析" in resp.json()["detail"]


def test_avatar_workflow_packs_registered(client: TestClient, auth_header: dict[str, str]) -> None:
    from liberastra.services.workflows import apply_inputs, get_pack, inject_image_input

    resp = client.get("/api/v1/workflows?capability=avatar", headers=auth_header)
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert {"minimax_h3_avatar", "minimax_h3_avatar_uncensored"} <= names

    pack = get_pack("minimax_h3_avatar")
    wf = apply_inputs(
        pack,
        {
            "image": "uploads/person.png",
            "audio": "outputs/1/voiceover.mp3",
            "prompt": "人物说话",
            "width": 768,
            "height": 1344,
            "length": 124,
        },
    )
    inject_image_input(wf, pack, "image", "person.png")
    inject_image_input(wf, pack, "audio", "voiceover.mp3")
    assert wf["114"]["inputs"]["image"] == "person.png"
    assert wf["115"]["inputs"]["audio"] == "voiceover.mp3"
    assert wf["105:105"]["class_type"] == "MiniMaxH3AddGuide"
    assert wf["105:16"]["inputs"]["conditioning"] == ["105:105", 0]
    assert wf["105:91"]["inputs"]["audio"] == ["115", 0]


def test_motion_workflow_packs_registered(client: TestClient, auth_header: dict[str, str]) -> None:
    from liberastra.services.workflows import apply_inputs, get_pack, inject_image_input

    resp = client.get("/api/v1/workflows?capability=motion", headers=auth_header)
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert {"minimax_h3_motion", "minimax_h3_motion_uncensored"} <= names

    pack = get_pack("minimax_h3_motion")
    wf = apply_inputs(
        pack,
        {
            "video": "uploads/ref.mp4",
            "image": "uploads/target.png",
            "prompt": "让 <Picture 1> 复刻 <Video 1> 动作",
            "width": 768,
            "height": 1344,
            "length": 124,
        },
    )
    inject_image_input(wf, pack, "video", "ref.mp4")
    inject_image_input(wf, pack, "image", "target.png")
    assert wf["115"]["inputs"]["video"] == "ref.mp4"
    assert wf["114"]["inputs"]["image"] == "target.png"
    assert wf["105:104"]["class_type"] == "MiniMaxH3ReferenceToVideo"
    assert wf["105:104"]["inputs"]["ref_images.ref_image_0"] == ["114", 0]
    assert wf["105:104"]["inputs"]["ref_videos.ref_video_0"] == ["115", 0]



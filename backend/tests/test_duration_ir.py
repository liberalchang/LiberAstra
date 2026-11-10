"""时长 IR 回归：内置包上的帧数与旧实现逐位一致。"""

from __future__ import annotations

import math
import random

from liberastra.media.timeline import (
    DurationSpec,
    duration_limits,
    duration_spec_for_model,
    duration_spec_for_pack,
    frames_for_duration,
    max_aligned_seconds,
    resolve_duration,
)
from liberastra.models import Provider
from liberastra.services.model_media import resolve_video_duration
from liberastra.services.workflows import list_packs


def test_pack_frame_resolution_matches_legacy() -> None:
    random.seed(0)
    checked = 0
    for pack in list_packs():
        spec = duration_spec_for_pack(pack)
        if spec is None:
            continue
        raw = pack.inputs.get("length") or pack.inputs.get("frames")
        fps = float(pack.fps)
        minimum = float(raw.get("min") or 1) / fps
        maximum = float(raw.get("max") or 600) / fps
        samples = [
            minimum,
            maximum,
            (minimum + maximum) / 2,
            minimum + (maximum - minimum) * 0.37,
            random.uniform(minimum, maximum),
        ]
        for seconds in samples:
            old = frames_for_duration(seconds, fps, raw)
            new = resolve_duration(spec, seconds)
            assert new.frames == old, f"{pack.name} {seconds:.4f}s: {new.frames} != {old}"
            assert math.isclose(new.seconds or 0, old / fps, rel_tol=1e-9)
            checked += 1
        limits = duration_limits(spec)
        assert limits is not None
        assert math.isclose(limits["max"], max_aligned_seconds(fps, raw), rel_tol=1e-9)
    assert checked > 0


def test_alignment_is_not_reported_as_clamped() -> None:
    spec = DurationSpec(
        unit="frames",
        fps=24,
        minimum=73,
        maximum=362,
        align_base=17,
        align_offset=5,
    )
    result = resolve_duration(spec, 9.58)
    assert result.frames == 243
    assert result.clamped is False
    assert result.reason == "aligned"


def test_unaligned_max_clamps_to_largest_valid_frame() -> None:
    spec = DurationSpec(
        unit="frames",
        fps=24,
        minimum=73,
        maximum=360,
        align_base=17,
        align_offset=5,
    )
    raw = {"min": 73, "max": 360, "align_base": 17, "align_offset": 5}
    result = resolve_duration(spec, 15.5)
    assert result.frames == 345
    assert result.clamped is True
    assert result.reason == "clamped_max"
    # 旧实现会返回未对齐的 max=360；这是本次有意修正的差异。
    assert frames_for_duration(15.5, 24, raw) == 360


def test_seconds_model_resolution() -> None:
    auto = duration_spec_for_model({"min": -1, "max": 30, "type": "int"})
    assert auto is not None
    resolved = resolve_duration(auto, -1)
    assert resolved.value == -1
    assert resolved.seconds is None
    assert resolved.reason == "auto"
    assert resolve_duration(auto, 5).value == 5

    spec = duration_spec_for_model({"min": 1, "max": 30, "type": "int"})
    assert spec is not None
    assert resolve_duration(spec, 5.6).value == 6
    clamped = resolve_duration(spec, 40)
    assert clamped.value == 30
    assert clamped.clamped is True


def test_cloud_video_duration_records_clamp() -> None:
    provider = Provider(
        id=1,
        name="ark",
        type="volcengine_ark",
        base_url="http://ark",
        extra={},
    )
    inputs = {"duration": 40}
    result = resolve_video_duration(provider, inputs)
    assert inputs["duration"] == 30
    assert result is not None
    assert result["clamped"] is True
    assert result["value"] == 30

    auto_inputs = {"duration": -1}
    auto = resolve_video_duration(provider, auto_inputs)
    assert auto_inputs["duration"] == -1
    assert auto is not None
    assert auto["reason"] == "auto"


def test_workflow_pack_api_exposes_duration_limits(client, auth_header) -> None:  # noqa: ANN001
    resp = client.get("/api/v1/workflows?capability=i2v", headers=auth_header)
    assert resp.status_code == 200
    pack = next(item for item in resp.json() if item["name"] == "minimax_h3_i2v")
    limits = pack["duration_limits"]
    assert limits["align_base"] == 17
    assert limits["align_offset"] == 5
    assert limits["fps"] == 24
    assert math.isclose(limits["min"], 73 / 24, rel_tol=1e-9)
    assert math.isclose(limits["max"], 362 / 24, rel_tol=1e-9)

"""画布逐镜音频计划：顺序校验、上一镜尾音和全片氛围底切片。"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Canvas, CanvasNodeRun, User
from liberastra.providers.base import ProviderError
from liberastra.schemas.canvas import CanvasRunIn
from liberastra.services import canvas_audio
from liberastra.services.canvas_audio import AudioPlanRuntime, validate_audio_plan


def _graph() -> dict:
    return {
        "nodes": [
            {
                "id": "n1",
                "type": "function",
                "data": {"pack": "minimax_h3_i2v_ref", "values": {"length": "124"}},
            },
            {
                "id": "n2",
                "type": "function",
                "data": {"pack": "minimax_h3_i2v_ref", "values": {"length": "124"}},
            },
            {"id": "concat", "type": "concat", "data": {"mediaKind": "video"}},
        ],
        "edges": [],
    }


def _owner(db) -> User:
    user = db.scalar(select(User).where(User.username == "admin"))
    assert user is not None
    return user


def _asset(db, user: User, kind: str, path: str) -> Asset:
    asset = Asset(kind=kind, path=path, owner_id=user.id, origin="output")
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _canvas(db, user: User, canvas_id: str) -> None:
    db.add(Canvas(id=canvas_id, name="audio test", graph={}, owner_id=user.id))
    db.commit()


def _run(db, canvas_id: str, node_id: str, asset_id: int) -> CanvasNodeRun:
    row = CanvasNodeRun(
        canvas_id=canvas_id,
        node_id=node_id,
        status="succeeded",
        asset_ids=[asset_id],
    )
    db.add(row)
    db.commit()
    return row


def test_audio_plan_validation_requires_all_shot_nodes(client, auth_header) -> None:
    db = SessionLocal()
    try:
        user = _owner(db)
        graph = _graph()
        with pytest.raises(ProviderError, match="缺少逐镜视频节点"):
            validate_audio_plan(
                db, graph, {"n1", "n2", "concat"}, user.id,
                {"strategy": "previous_tail", "order": ["n1"]},
            )
        with pytest.raises(ProviderError, match="不是功能节点"):
            validate_audio_plan(
                db, graph, {"n1", "n2", "concat"}, user.id,
                {"strategy": "previous_tail", "order": ["n1", "n2", "concat"]},
            )
    finally:
        db.close()


def test_previous_tail_injects_previous_asset(client, auth_header, monkeypatch) -> None:
    db = SessionLocal()
    calls: list[tuple[str, float, str]] = []

    async def fake_extract(source, seconds, out):  # noqa: ANN001
        calls.append((str(source), seconds, str(out)))
        out.write_bytes(b"tail")

    monkeypatch.setattr(canvas_audio.ffmpeg, "extract_audio_tail", fake_extract)
    try:
        user = _owner(db)
        video = _asset(db, user, "video", "outputs/test/prev.mp4")
        canvas_id = "canvas-audio-prev"
        _canvas(db, user, canvas_id)
        runs = {"n1": _run(db, canvas_id, "n1", video.id)}
        graph = _graph()
        runtime = AudioPlanRuntime(
            db, canvas_id, graph, "run-prev", user.id,
            {"strategy": "previous_tail", "ref_seconds": 5, "order": ["n1", "n2"]},
        )
        first = asyncio.run(runtime.plan_for_node(graph["nodes"][0], runs))
        second = asyncio.run(runtime.plan_for_node(graph["nodes"][1], runs))
        assert first is None
        assert second is not None
        assert second.path == "outputs/run-prev/audio/n2_prev.wav"
        assert second.signature["source_asset"] == video.id
        assert calls and calls[0][1] == 5
    finally:
        db.close()


def test_global_bed_slices_by_previous_actual_duration(client, auth_header, monkeypatch) -> None:
    db = SessionLocal()
    calls: list[tuple[float, float, str]] = []

    async def fake_probe(path):  # noqa: ANN001
        return 30.0 if str(path).endswith("bed.mp3") else 5.0

    async def fake_slice(audio, start, duration, out):  # noqa: ANN001
        calls.append((start, duration, str(out)))
        out.write_bytes(b"bed")

    monkeypatch.setattr(canvas_audio.ffmpeg, "probe_duration", fake_probe)
    monkeypatch.setattr(canvas_audio.ffmpeg, "slice_audio", fake_slice)
    try:
        user = _owner(db)
        video = _asset(db, user, "video", "outputs/test/prev.mp4")
        bed = _asset(db, user, "audio", "bgm/bed.mp3")
        canvas_id = "canvas-audio-bed"
        _canvas(db, user, canvas_id)
        runs = {"n1": _run(db, canvas_id, "n1", video.id)}
        graph = _graph()
        runtime = AudioPlanRuntime(
            db, canvas_id, graph, "run-bed", user.id,
            {
                "strategy": "global_bed",
                "bed_asset_id": bed.id,
                "bed_fill": "loop",
                "order": ["n1", "n2"],
            },
        )
        injection = asyncio.run(runtime.plan_for_node(graph["nodes"][1], runs))
        assert injection is not None
        assert injection.path == "outputs/run-bed/audio/n2_bed.wav"
        assert injection.signature["start"] == 5.0
        assert calls and calls[0][0] == 5.0
    finally:
        db.close()


def test_canvas_run_request_audio_plan_schema() -> None:
    request = CanvasRunIn(
        node_ids=["n2"],
        audio_plan={
            "strategy": "previous_tail",
            "ref_seconds": 6,
            "seam_fade_ms": 80,
            "order": ["n1", "n2"],
        },
    )
    assert request.audio_plan is not None
    assert request.audio_plan.strategy == "previous_tail"
    assert request.audio_plan.order == ["n1", "n2"]
    assert request.audio_plan.seam_fade_ms == 80

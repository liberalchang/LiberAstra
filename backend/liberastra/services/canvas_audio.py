"""画布逐镜音频计划：上一镜尾音、全片氛围底和接缝淡化。

计划只属于一次画布执行，不写回节点图。动态音频在提交每个逐镜视频任务前解析成
`ref_audio` 路径；A2/B 的 Extender 参数仍走普通 pack 输入。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.media import ffmpeg
from liberastra.models import Asset, CanvasNodeRun
from liberastra.providers.base import ProviderError
from liberastra.services.workflows import WorkflowPack, get_pack
from liberastra.storage import resolve


@dataclass
class AudioInjection:
    signature: dict[str, Any]
    path: str | None
    note: str


def _node_pack(node: dict[str, Any]) -> WorkflowPack | None:
    data = node.get("data") or {}
    if str(data.get("targetType") or "") == "model":
        return None
    name = str(data.get("pack") or data.get("targetId") or "").strip()
    if not name:
        return None
    try:
        return get_pack(name)
    except ProviderError:
        return None


def _is_single_shot_pack(pack: WorkflowPack | None) -> bool:
    return bool(pack and "ref_audio" in pack.inputs and "clips_json" not in pack.inputs)


def _node_map(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(node["id"]): node for node in graph.get("nodes") or []}


def validate_audio_plan(
    db: Session,
    graph: dict[str, Any],
    scope: set[str],
    owner_id: int,
    plan: dict[str, Any] | None,
) -> None:
    """在创建任务前校验顺序、节点和 bed 资产，避免跑到一半才用错音频。"""
    if not plan:
        return
    strategy = str(plan.get("strategy") or "native")
    if strategy == "native":
        return
    if strategy not in {"previous_tail", "global_bed"}:
        raise ProviderError("音频策略只能是 native / previous_tail / global_bed")
    order = [str(x) for x in plan.get("order") or []]
    if not order:
        raise ProviderError("逐镜音频连续性需要提供镜头执行顺序")
    if len(set(order)) != len(order):
        raise ProviderError("音频计划的镜头顺序不能重复")
    nodes = _node_map(graph)
    scope_set = {str(x) for x in scope}
    for node_id in order:
        if node_id not in scope_set:
            raise ProviderError(f"音频顺序里的节点不在本次执行范围: {node_id}")
        node = nodes.get(node_id)
        if node is None or node.get("type") != "function":
            raise ProviderError(f"音频顺序里的节点不是功能节点: {node_id}")
        pack = _node_pack(node)
        if not _is_single_shot_pack(pack):
            raise ProviderError(
                f"节点 {node_id} 不是支持参考音频的逐镜 i2v 包；A2/B 请使用 Extender 参数"
            )
    # 本次范围内的逐镜视频节点必须全部排进顺序，避免漏镜后尾音/切片错位。
    for node_id in scope_set:
        node = nodes.get(node_id)
        if node is not None and node.get("type") == "function" and _is_single_shot_pack(_node_pack(node)):
            if node_id not in order:
                raise ProviderError(f"音频顺序缺少逐镜视频节点: {node_id}")
    if strategy == "global_bed":
        bed_id = plan.get("bed_asset_id")
        if bed_id in (None, ""):
            raise ProviderError("全片氛围底需要选择音频")
        asset = db.get(Asset, int(bed_id))
        if asset is None or asset.owner_id != owner_id or asset.kind != "audio":
            raise ProviderError("全片氛围底音频不存在或不是音频资产")


class AudioPlanRuntime:
    def __init__(
        self,
        db: Session,
        canvas_id: str,
        graph: dict[str, Any],
        run_id: str,
        owner_id: int,
        plan: dict[str, Any] | None,
    ) -> None:
        self.db = db
        self.canvas_id = canvas_id
        self.nodes = _node_map(graph)
        self.order = [str(x) for x in (plan or {}).get("order") or []]
        self.run_id = run_id
        self.owner_id = owner_id
        self.plan = plan or {}
        self.strategy = str(self.plan.get("strategy") or "native")
        self.ref_seconds = float(self.plan.get("ref_seconds") or 5)
        self.bed_asset_id = self.plan.get("bed_asset_id")
        self.bed_fill = str(self.plan.get("bed_fill") or "loop")
        self.bed_mode = str(self.plan.get("bed_mode") or "mix")
        self.seam_fade_ms = max(0, min(200, int(self.plan.get("seam_fade_ms") or 0)))
        self._pack_cache: dict[str, WorkflowPack | None] = {}

    @property
    def active(self) -> bool:
        return self.strategy in {"previous_tail", "global_bed"}

    def _pack(self, node_id: str) -> WorkflowPack | None:
        if node_id not in self._pack_cache:
            node = self.nodes.get(node_id)
            self._pack_cache[node_id] = _node_pack(node) if node else None
        return self._pack_cache[node_id]

    def _first_video_asset(self, run: CanvasNodeRun | None) -> Asset | None:
        if run is None or run.status != "succeeded":
            return None
        for asset_id in run.asset_ids or []:
            asset = self.db.get(Asset, int(asset_id))
            if asset is not None and asset.kind == "video":
                return asset
        return None

    def _planned_duration(self, node_id: str) -> float:
        node = self.nodes.get(node_id) or {}
        values = (node.get("data") or {}).get("values") or {}
        pack = self._pack(node_id)
        fps = float((pack.fps if pack else None) or 24)
        raw = values.get("length") if "length" in values else values.get("frames")
        try:
            if raw not in (None, ""):
                return max(0.05, float(raw) / max(fps, 1.0))
            if values.get("duration") not in (None, ""):
                return max(0.05, float(values["duration"]))
        except (TypeError, ValueError):
            pass
        return 5.0

    async def _actual_duration(self, node_id: str, runs: dict[str, CanvasNodeRun]) -> float:
        run = runs.get(node_id)
        if run is None:
            run = self.db.scalar(
                select(CanvasNodeRun).where(
                    CanvasNodeRun.canvas_id == self.canvas_id,
                    CanvasNodeRun.node_id == node_id,
                )
            )
        asset = self._first_video_asset(run)
        if asset is not None:
            try:
                return await ffmpeg.probe_duration(resolve(asset.path))
            except Exception:  # noqa: BLE001
                pass
        return self._planned_duration(node_id)

    async def _global_start(self, index: int, runs: dict[str, CanvasNodeRun]) -> float:
        start = 0.0
        for prev_id in self.order[:index]:
            start += await self._actual_duration(prev_id, runs)
        return start

    async def plan_for_node(
        self,
        node: dict[str, Any],
        runs: dict[str, CanvasNodeRun],
    ) -> AudioInjection | None:
        if not self.active:
            return None
        node_id = str(node.get("id") or "")
        if node_id not in self.order:
            return None
        pack = _node_pack(node)
        if not _is_single_shot_pack(pack):
            return None
        index = self.order.index(node_id)
        if self.strategy == "previous_tail":
            if index == 0:
                return None
            prev_id = self.order[index - 1]
            prev_asset = self._first_video_asset(runs.get(prev_id))
            if prev_asset is None:
                return AudioInjection(
                    signature={"strategy": "previous_tail", "degraded": "previous_missing"},
                    path=None,
                    note="上一镜没有可用视频，已降级为模型原生音频",
                )
            rel = f"outputs/{self.run_id}/audio/{node_id}_prev.wav"
            out = resolve(rel)
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                await ffmpeg.extract_audio_tail(resolve(prev_asset.path), self.ref_seconds, out)
            except Exception as exc:  # noqa: BLE001
                return AudioInjection(
                    signature={
                        "strategy": "previous_tail",
                        "source_asset": prev_asset.id,
                        "degraded": str(exc),
                    },
                    path=None,
                    note="上一镜尾音提取失败，已降级为模型原生音频",
                )
            return AudioInjection(
                signature={
                    "strategy": "previous_tail",
                    "source_asset": prev_asset.id,
                    "seconds": round(self.ref_seconds, 3),
                },
                path=rel,
                note=f"上一镜尾音 {self.ref_seconds:g}s",
            )

        if self.bed_asset_id in (None, ""):
            return None
        bed = self.db.get(Asset, int(self.bed_asset_id))
        if bed is None or bed.kind != "audio":
            return AudioInjection(
                signature={"strategy": "global_bed", "degraded": "bed_missing"},
                path=None,
                note="全片氛围底音频不存在，已降级为模型原生音频",
            )
        try:
            bed_path = resolve(bed.path)
            bed_duration = await ffmpeg.probe_duration(bed_path)
        except Exception as exc:  # noqa: BLE001
            return AudioInjection(
                signature={"strategy": "global_bed", "degraded": str(exc)},
                path=None,
                note="全片氛围底读取失败，已降级为模型原生音频",
            )
        start = await self._global_start(index, runs)
        duration = self._planned_duration(node_id)
        rel = f"outputs/{self.run_id}/audio/{node_id}_bed.wav"
        out = resolve(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        if start >= bed_duration:
            if self.bed_fill == "silence":
                await ffmpeg.make_silence(out, duration)
                return AudioInjection(
                    signature={
                        "strategy": "global_bed",
                        "source_asset": bed.id,
                        "start": round(start, 3),
                        "duration": round(duration, 3),
                        "fill": "silence",
                    },
                    path=rel,
                    note="全片氛围底已用尽，本镜补静音参考",
                )
            start = start % max(bed_duration, 0.05)
        await ffmpeg.slice_audio(bed_path, start, duration, out)
        return AudioInjection(
            signature={
                "strategy": "global_bed",
                "source_asset": bed.id,
                "start": round(start, 3),
                "duration": round(duration, 3),
                "fill": self.bed_fill,
            },
            path=rel,
            note=f"全片氛围底 {start:.1f}s–{min(start + duration, bed_duration):.1f}s",
        )

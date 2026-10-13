"""字幕导出：分段结果 → txt / srt / vtt / json。"""

from __future__ import annotations

import json

from liberastra.providers.base import ASRResult


def _ts_srt(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_vtt(seconds: float) -> str:
    return _ts_srt(seconds).replace(",", ".")


def to_txt(result: ASRResult) -> str:
    return result.text + "\n"


def to_srt(result: ASRResult) -> str:
    blocks = []
    for i, seg in enumerate(result.segments, 1):
        blocks.append(f"{i}\n{_ts_srt(seg.start)} --> {_ts_srt(seg.end)}\n{seg.text}")
    return "\n\n".join(blocks) + "\n"


def to_vtt(result: ASRResult) -> str:
    blocks = ["WEBVTT", ""]
    for seg in result.segments:
        blocks.append(f"{_ts_vtt(seg.start)} --> {_ts_vtt(seg.end)}\n{seg.text}")
    return "\n\n".join(blocks) + "\n"


def to_json(result: ASRResult) -> str:
    return json.dumps(
        {
            "text": result.text,
            "language": result.language,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text} for s in result.segments
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


EXPORTERS = {"txt": to_txt, "srt": to_srt, "vtt": to_vtt, "json": to_json}

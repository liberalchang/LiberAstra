"""字幕导出：分段结果 → txt / srt / vtt / json。"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from liberastra.providers.base import ASRResult, ASRSegment


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


_SRT_TIME = re.compile(r"(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})")
_HTML_TAG = re.compile(r"<[^>]+>")


def _parse_time(value: str) -> float:
    match = _SRT_TIME.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"时间格式无效: {value.strip()}")
    hours, minutes, seconds, millis = match.groups()
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int((millis + "000")[:3]) / 1000.0
    )


def parse_srt(path: str | Path, duration: float) -> tuple[list[ASRSegment], float]:
    """解析 srt，返回字幕段和覆盖率。格式错误或越界直接报错。"""
    raw = Path(path).read_bytes()
    text = ""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        raise ValueError("srt 文件为空或编码无法识别")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("srt 文件为空")

    segments: list[tuple[float, float, str]] = []
    for block_index, block in enumerate(re.split(r"\n\s*\n", text), 1):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        time_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        parts = lines[time_index].split("-->")
        if len(parts) != 2:
            raise ValueError(f"srt 第 {block_index} 段时间格式无效")
        start = _parse_time(parts[0])
        end = _parse_time(parts[1].split()[0] if parts[1].split() else parts[1])
        body = "\n".join(lines[time_index + 1 :]).strip()
        body = html.unescape(_HTML_TAG.sub("", body)).strip()
        if end - start < 0.02:
            continue
        segments.append((start, end, body))

    if not segments:
        raise ValueError("srt 没有有效字幕段")
    segments.sort(key=lambda item: item[0])
    merged: list[tuple[float, float, str]] = []
    for start, end, body in segments:
        # 字幕相邻不等同重叠：保留原 cue 边界，只在真正重叠时合并。
        if merged and start < merged[-1][1] - 0.001:
            prev_start, prev_end, prev_body = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end), (prev_body + "\n" + body).strip())
        else:
            merged.append((start, end, body))

    coverage_end = max(end for _, end, _ in merged)
    if coverage_end > duration + 0.5:
        raise ValueError(
            f"srt 最后时间戳 {coverage_end:.2f}s 超出音频时长 {duration:.2f}s"
        )
    result = [
        ASRSegment(
            start=max(0.0, min(duration, start)),
            end=max(0.0, min(duration, end)),
            text=body,
        )
        for start, end, body in merged
    ]
    covered = sum(segment.end - segment.start for segment in result)
    coverage = max(0.0, min(1.0, covered / duration)) if duration > 0 else 0.0
    return result, coverage


EXPORTERS = {"txt": to_txt, "srt": to_srt, "vtt": to_vtt, "json": to_json}

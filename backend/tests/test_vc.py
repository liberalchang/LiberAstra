"""换音相关纯函数与 srt 解析测试。"""

from __future__ import annotations

import pytest

from liberastra.media.subtitles import parse_srt


def _write_srt(tmp_path, text: str, encoding: str = "utf-8"):  # noqa: ANN001
    path = tmp_path / "sample.srt"
    path.write_bytes(text.encode(encoding))
    return path


def test_parse_srt_normal_and_coverage(tmp_path) -> None:  # noqa: ANN001
    path = _write_srt(
        tmp_path,
        "1\n00:00:00,000 --> 00:00:01,500\n你好\n\n"
        "2\n00:00:01,500 --> 00:00:03,000\n世界\n",
    )
    segments, coverage = parse_srt(path, 3.0)
    assert [(segment.start, segment.end, segment.text) for segment in segments] == [
        (0.0, 1.5, "你好"),
        (1.5, 3.0, "世界"),
    ]
    assert coverage == 1.0


def test_parse_srt_bom_gb18030_and_html(tmp_path) -> None:  # noqa: ANN001
    path = _write_srt(
        tmp_path,
        "1\n00:00:00,000 --> 00:00:02,000\n<i>你好</i>\n",
        encoding="gb18030",
    )
    segments, _coverage = parse_srt(path, 4.0)
    assert segments[0].text == "你好"


def test_parse_srt_merges_overlap_and_skips_zero_length(tmp_path) -> None:  # noqa: ANN001
    path = _write_srt(
        tmp_path,
        "1\n00:00:00,000 --> 00:00:01,000\nA\n\n"
        "2\n00:00:00,980 --> 00:00:02,000\nB\n\n"
        "3\n00:00:02,000 --> 00:00:02,000\nC\n",
    )
    segments, _coverage = parse_srt(path, 2.0)
    assert len(segments) == 1
    assert segments[0].start == 0.0
    assert segments[0].end == 2.0
    assert segments[0].text == "A\nB"


def test_parse_srt_rejects_beyond_duration(tmp_path) -> None:  # noqa: ANN001
    path = _write_srt(tmp_path, "1\n00:00:00,000 --> 00:00:09,000\nA\n")
    with pytest.raises(ValueError, match="超出音频时长"):
        parse_srt(path, 3.0)


def test_parse_srt_rejects_empty(tmp_path) -> None:  # noqa: ANN001
    path = _write_srt(tmp_path, "")
    with pytest.raises(ValueError):
        parse_srt(path, 3.0)

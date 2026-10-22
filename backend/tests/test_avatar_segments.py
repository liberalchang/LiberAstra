"""数字人口播：帧数吸附、按句分段、尾帧衔接。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from liberastra.pipelines.simple import (
    avatar_segment_prompt,
    frames_for_duration,
    max_aligned_seconds,
    max_reference_video_seconds,
    motion_windows,
    render_avatar_takes,
    split_avatar_script,
    split_text_half,
)

H3 = {"align_base": 17, "align_offset": 5, "min": 73, "max": 362}


def test_motion_windows_follow_aligned_frames() -> None:
    assert max_reference_video_seconds(24, H3) == 362 / 24
    short = motion_windows(5.0, 24, H3)
    assert short
    assert all(frames % 17 == 5 for _, frames in short)
    assert sum(frames for _, frames in short) <= int(5 * 24)
    long = motion_windows(20.0, 24, H3)
    assert long[0] == (0.0, 362)
    assert len(long) >= 2
    assert motion_windows(0.1, 24, H3) == []


def test_frames_snap_to_h3_grid() -> None:
    # 5 秒 → 120 帧，向上到 7*17+5 = 124
    assert frames_for_duration(5.0, 24, H3) == 124
    # 短于最短帧数时抬到 73
    assert frames_for_duration(0.2, 24, H3) == 73
    # 超过上限时停在对齐后的最大帧数
    assert frames_for_duration(20, 24, H3) == 362
    assert max_aligned_seconds(24, H3) == 362 / 24


def test_split_keeps_short_sentences_together() -> None:
    text = "今天天气很好。我们去公园。你看这朵花。"
    assert split_avatar_script(text, 12) == [text]


def test_split_long_sentence_on_commas() -> None:
    text = f"{'甲' * 40}，{'乙' * 40}。"
    assert split_avatar_script(text, 12) == [f"{'甲' * 40}，", f"{'乙' * 40}。"]


def test_hard_split_keeps_space_between_words() -> None:
    word = "abcdefghijklmnop"
    text = (f"{word} " * 40).strip()
    parts = split_avatar_script(text, 12)
    # 按段 split，跨段的首尾空格可以去掉；段内被合并的单词不能粘在一起
    words = [token for part in parts for token in part.split()]
    assert words == [word] * 40


def test_split_long_sentence_on_commas_then_chars() -> None:
    long_clause = "甲" * 80
    parts = split_avatar_script(f"{long_clause}。好。", 12)
    assert parts[0] == "甲" * 51
    assert parts[1].startswith("甲" * 29)
    assert parts[1].endswith("好。")
    assert "".join(parts).count("甲") == 80


def test_split_text_half_prefers_punctuation() -> None:
    halves = split_text_half("前半句很长很长，后半句也不短。")
    assert halves == ["前半句很长很长，", "后半句也不短。"]


def test_prompt_uses_only_this_line() -> None:
    prompt = avatar_segment_prompt("第二句。", "")
    assert "第二句。" in prompt
    assert "第一句" not in prompt


def test_render_chains_last_frame_and_overrides_length(tmp_path: Path) -> None:
    seen: list[dict[str, Any]] = []
    trimmed: list[float] = []

    async def generate(inputs: dict[str, Any], on_progress) -> list[tuple[str, bytes]]:
        seen.append(dict(inputs))
        on_progress(1.0)
        return [("a.mp4", f"v{len(seen)}".encode())]

    async def trim(src: Path, dst: Path, seconds: float, fps: float) -> None:
        assert fps == 24
        trimmed.append(seconds)
        dst.write_bytes(src.read_bytes())

    async def last_frame(video: Path, png: Path) -> None:
        assert video.exists()
        png.write_bytes(b"\x89PNG")

    async def concat(paths: list[Path], out: Path, list_file: Path) -> None:
        list_file.write_text("ok", encoding="utf-8")
        out.write_bytes(b"".join(path.read_bytes() for path in paths))

    def work(name: str) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    final = asyncio.run(
        render_avatar_takes(
            takes=[
                ("第一句。", "outputs/job/voiceover_00.mp3", 5.0),
                ("第二句。", "outputs/job/voiceover_01.mp3", 6.0),
            ],
            first_image="characters/face.png",
            base_inputs={"length": 124, "width": 512},
            length_spec=H3,
            fps=24,
            image_key="image",
            audio_key="audio",
            custom_prompt="",
            generate=generate,
            work=work,
            rel_of=lambda path: f"outputs/job/{path.name}",
            report=lambda _progress, _step: None,
            cancelled=lambda: False,
            trim=trim,
            last_frame=last_frame,
            concat=concat,
        )
    )

    assert seen[0]["image"] == "characters/face.png"
    assert seen[0]["audio"] == "outputs/job/voiceover_00.mp3"
    assert seen[0]["width"] == 512
    assert seen[0]["length"] == frames_for_duration(5.1, 24, H3)
    assert seen[1]["image"] == "outputs/job/take_00_last.png"
    assert seen[1]["length"] == frames_for_duration(6.1, 24, H3)
    assert seen[1]["length"] != 124
    assert abs(trimmed[0] - (5.0 + 1 / 24)) < 1e-6
    assert abs(trimmed[1] - (6.0 + 1 / 24)) < 1e-6
    assert "第二句。" in seen[1]["prompt"]
    assert "第一句" not in seen[1]["prompt"]
    assert final is not None
    assert final.read_bytes() == b"v1v2"

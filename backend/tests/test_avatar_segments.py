"""数字人口播：帧数吸附、按句分段、尾帧衔接。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from liberastra.pipelines.simple import (
    MotionWindow,
    avatar_segment_prompt,
    frames_for_duration,
    max_aligned_seconds,
    max_reference_video_seconds,
    motion_prompt,
    motion_windows,
    render_avatar_takes,
    render_motion_takes,
    slice_audio_takes,
    split_avatar_script,
    split_text_half,
)

H3 = {"align_base": 17, "align_offset": 5, "min": 73, "max": 362}
MOTION = {"align_base": 17, "align_offset": 5, "min": 73, "max": 124}


def test_motion_windows_follow_aligned_frames() -> None:
    assert max_reference_video_seconds(24, H3) == 362 / 24
    short = motion_windows(5.0, 24, H3)
    assert short
    assert all(window.frames % 17 == 5 for window in short)
    assert sum(window.trim_seconds for window in short) == pytest.approx(5.0, abs=0.05)
    long = motion_windows(20.0, 24, H3)
    assert long[0].start == 0.0
    assert long[0].frames == 362
    assert len(long) >= 2
    assert motion_windows(0.1, 24, H3) == []


def test_motion_windows_short_video_is_one_segment() -> None:
    windows = motion_windows(3.0, 24, MOTION)
    assert len(windows) == 1
    assert windows[0].frames >= 73
    assert windows[0].frames <= 124
    assert windows[0].trim_seconds == pytest.approx(3.0)
    assert windows[0].keep_last is False


def test_motion_windows_does_not_emit_tiny_tails() -> None:
    for total in (1.0, 2.333333, 3.0, 5.25, 7.0, 12.051):
        windows = motion_windows(total, 24, MOTION)
        assert windows, total
        assert all(window.frames >= 73 for window in windows), total
        kept = sum(window.trim_seconds for window in windows)
        assert kept <= total + 0.01, total
        assert total - kept <= 5 / 24 + 0.01, total


def test_motion_windows_long_video_tail_uses_full_window() -> None:
    windows = motion_windows(12.051, 24, MOTION)
    assert len(windows) == 3
    assert windows[-1].frames == 124
    assert windows[-1].keep_last is True
    assert windows[-1].start == pytest.approx(12.051 - 124 / 24, abs=0.01)
    assert windows[-1].trim_seconds == pytest.approx(12.051 - 248 / 24, abs=0.05)


def test_render_motion_trims_tail_from_end(tmp_path: Path) -> None:
    trims: list[tuple[float, float]] = []

    async def generate(inputs: dict[str, Any], on_progress) -> list[tuple[str, bytes]]:
        on_progress(1.0)
        return [("a.mp4", b"v")]

    async def slice_video(video: Path, start: float, duration: float, out: Path, **_kwargs: Any) -> None:
        out.write_bytes(f"{start}:{duration}".encode())

    async def trim(
        src: Path, dst: Path, seconds: float, fps: float, *, start: float = 0.0
    ) -> None:
        trims.append((seconds, start))
        dst.write_bytes(src.read_bytes())

    async def concat(paths: list[Path], out: Path, *, list_file: Path) -> None:
        out.write_bytes(b"".join(path.read_bytes() for path in paths))

    final = asyncio.run(
        render_motion_takes(
            source=tmp_path / "ref.mp4",
            image_paths=["face.png"],
            prompt_text="跟着动",
            base_inputs={},
            windows=[
                MotionWindow(0.0, 124, 124 / 24),
                MotionWindow(5.0, 124, 1.0, keep_last=True),
            ],
            fps=24,
            video_key="video",
            image_keys=["image"],
            generate=generate,
            work=lambda name: tmp_path / name,
            rel_of=lambda path: path.name,
            report=lambda _progress, _step: None,
            cancelled=lambda: False,
            slice_video=slice_video,
            trim_video=trim,
            concat=concat,
        )
    )
    assert final is not None
    assert trims[0] == pytest.approx((124 / 24, 0.0))
    assert trims[1][0] == pytest.approx(1.0)
    assert trims[1][1] == pytest.approx(124 / 24 - 1.0)


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


def test_prompt_without_spoken_line_keeps_visual_only() -> None:
    assert "台词" not in avatar_segment_prompt("", "缓慢推近")
    assert avatar_segment_prompt("", "缓慢推近") == "缓慢推近"
    assert "口型" in avatar_segment_prompt("", "")


def test_slice_audio_takes_follow_probed_duration(tmp_path: Path) -> None:
    calls: list[tuple[float, float]] = []

    async def _probe_short(_path: Path) -> float:
        return 5.0

    async def probe(path: Path) -> float:
        if path.name.startswith("avatar_a_"):
            return 8.0
        return 20.0

    async def slice_audio(audio: Path, start: float, duration: float, out: Path) -> None:
        calls.append((start, duration))
        out.write_bytes(b"a")

    takes = asyncio.run(
        slice_audio_takes(
            tmp_path / "in.mp3",
            ceiling=8,
            rel_path="outputs/in.mp3",
            work=lambda name: tmp_path / name,
            rel_of=lambda path: path.name,
            probe=probe,
            slice_audio=slice_audio,
        )
    )
    assert [item[0] for item in takes] == ["", "", ""]
    assert calls == [(0.0, 8), (8.0, 8), (16.0, 4.0)]
    short = asyncio.run(
        slice_audio_takes(
            tmp_path / "short.mp3",
            ceiling=15,
            rel_path="outputs/short.mp3",
            work=lambda name: tmp_path / name,
            rel_of=lambda path: f"rel/{path.name}",
            probe=_probe_short,
            slice_audio=slice_audio,
        )
    )
    assert short == [("", "outputs/short.mp3", 5.0)]


def test_render_motion_keeps_target_images_across_segments(tmp_path: Path) -> None:
    seen: list[dict[str, Any]] = []

    async def generate(inputs: dict[str, Any], on_progress) -> list[tuple[str, bytes]]:
        seen.append(dict(inputs))
        on_progress(1.0)
        return [("a.mp4", f"v{len(seen)}".encode())]

    async def slice_video(video: Path, start: float, duration: float, out: Path, **_kwargs: Any) -> None:
        out.write_bytes(b"ref")

    async def trim(
        src: Path, dst: Path, seconds: float, fps: float, *, start: float = 0.0
    ) -> None:
        dst.write_bytes(src.read_bytes())

    async def last_frame(video: Path, png: Path, fps: float = 24) -> None:
        png.write_bytes(b"png")

    async def concat(paths: list[Path], out: Path, *, list_file: Path) -> None:
        list_file.write_text("ok", encoding="utf-8")
        out.write_bytes(b"".join(path.read_bytes() for path in paths))

    def work(name: str) -> Path:
        return tmp_path / name

    final = asyncio.run(
        render_motion_takes(
            source=tmp_path / "ref.mp4",
            image_paths=["face.png", "side.png"],
            prompt_text="跟着动",
            base_inputs={"length": 50, "width": 512},
            windows=[(0.0, 124), (5.0, 90)],
            fps=24,
            video_key="video",
            image_keys=["image", "image_2", "image_3"],
            generate=generate,
            work=work,
            rel_of=lambda path: path.name,
            report=lambda _progress, _step: None,
            cancelled=lambda: False,
            slice_video=slice_video,
            trim_video=trim,
            last_frame=last_frame,
            concat=concat,
        )
    )
    assert final is not None and final.exists()
    assert seen[0]["length"] == 124
    assert seen[0]["image"] == "face.png"
    assert seen[0]["image_2"] == "side.png"
    assert "image_3" not in seen[0]
    assert seen[1]["length"] == 90
    assert seen[1]["image"] == "face.png"
    assert seen[1]["image_2"] == "side.png"
    assert seen[1]["image_3"] == "tail_00.png"
    assert "<Picture 3>" in seen[1]["prompt"]


def test_motion_prompt_pins_identity_to_pictures() -> None:
    text = motion_prompt("", 3)
    assert "<Picture 1>" in text
    assert "<Picture 2>" in text
    assert "<Picture 3>" in text
    assert "<Video 1>" in text
    assert "不要复制视频中人物的脸、发型或服装" in text
    assert "不要中途换脸或换装" in text

    with_extra = motion_prompt("", 5)
    assert "<Picture 4>" in with_extra
    assert "<Picture 5>" in with_extra

    tagged = "让 <Picture 1> 复刻 <Video 1> 的动作"
    assert motion_prompt(tagged, 3) == tagged

    untagged = motion_prompt("人物转身", 1)
    assert untagged.endswith("人物转身")
    assert "不要复制视频人物的脸、发型或服装" in untagged


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

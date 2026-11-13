from __future__ import annotations

from pathlib import Path

import postprocess
import pytest


def test_filters() -> None:
    assert postprocess.speed_filter(0.9) == "atempo=0.9"
    assert postprocess.loudnorm_filter(-16) == "loudnorm=I=-16:TP=-1.5:LRA=11"
    with pytest.raises(postprocess.PostProcessError) as info:
        postprocess.speed_filter(0.4)
    assert info.value.code == "invalid_speed"
    with pytest.raises(postprocess.PostProcessError):
        postprocess.loudnorm_filter(-3)


def test_build_commands(tmp_path: Path) -> None:
    source = tmp_path / "a.wav"
    target = tmp_path / "b.wav"
    speed = postprocess.build_speed_command(source, target, 0.9)
    assert "atempo=0.9" in speed
    assert "pcm_s16le" in speed

    loudnorm = postprocess.build_loudnorm_command(source, target, -16)
    assert "loudnorm=I=-16:TP=-1.5:LRA=11" in loudnorm

    sliced = postprocess.build_slice_command(source, target, 1.5, 2.0)
    assert sliced[sliced.index("-ss") + 1] == "1.5"
    assert sliced[sliced.index("-t") + 1] == "2"

    no_duration = postprocess.build_slice_command(source, target, 1.5)
    assert "-t" not in no_duration


def test_apply_speed_skips_one(tmp_path: Path, monkeypatch) -> None:
    called: list[list[str]] = []
    monkeypatch.setattr(postprocess, "_run", lambda args: called.append(args))
    path = tmp_path / "a.wav"
    path.write_bytes(b"x")
    assert postprocess.apply_speed(path, 1.0) == path
    assert called == []


def test_apply_speed_replaces_output(tmp_path: Path, monkeypatch) -> None:
    def fake_run(args: list[str]) -> None:
        Path(args[-1]).write_bytes(b"processed")

    monkeypatch.setattr(postprocess, "_run", fake_run)
    path = tmp_path / "a.wav"
    path.write_bytes(b"original")
    postprocess.apply_speed(path, 0.9)
    assert path.read_bytes() == b"processed"


def test_apply_loudnorm_replaces_output(tmp_path: Path, monkeypatch) -> None:
    def fake_run(args: list[str]) -> None:
        Path(args[-1]).write_bytes(b"normalized")

    monkeypatch.setattr(postprocess, "_run", fake_run)
    path = tmp_path / "a.wav"
    path.write_bytes(b"original")
    postprocess.apply_loudnorm(path, -16)
    assert path.read_bytes() == b"normalized"

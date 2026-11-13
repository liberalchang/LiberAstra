from __future__ import annotations

import engine
import pytest


def test_normalize_segments_merge_and_minimum() -> None:
    segments = [
        {"start": 0.0, "end": 1.0},
        {"start": 1.2, "end": 2.0},
        {"start": 5.0, "end": 5.01},
    ]
    default = engine._normalize_segments(segments, 10.0)
    assert default == [(0.0, 1.0), (1.2, 2.0)]

    merged = engine._normalize_segments(segments, 10.0, merge_gap=0.3)
    assert merged == [(0.0, 2.0)]

    minimum = engine._normalize_segments(segments, 10.0, min_segment=1.0)
    assert minimum == [(0.0, 1.0)]


def test_plan_windows_uses_custom_window_and_context() -> None:
    windows = engine._plan_windows([(0.0, 10.0)], 20.0, max_window=5.0, context=0.1)
    assert windows == [
        (0.0, 5.1, 0.0, 5.0),
        (4.9, 10.1, 5.0, 10.0),
    ]


def test_pad_segments_expands_and_merges() -> None:
    assert engine._pad_segments([(1.0, 2.0)], 10.0, 0.5) == [(0.5, 2.5)]
    assert engine._pad_segments([(1.0, 2.0), (2.2, 3.0)], 10.0, 0.2) == [(0.8, 3.2)]


def test_prepare_reference_trims(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")

    source = tmp_path / "ref.wav"
    sf.write(source, np.zeros(24000, dtype=np.float32), 24000, subtype="PCM_16")
    target = engine._prepare_reference(
        source,
        ref_start=0.0,
        ref_duration=0.0,
        ref_max_len=0.5,
        temp_dir=tmp_path,
    )
    assert target != source
    data, sample_rate = sf.read(target)
    assert sample_rate == 24000
    assert 0.45 <= len(data) / sample_rate <= 0.55


def test_prepare_reference_returns_original_when_no_trim(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")

    source = tmp_path / "ref.wav"
    sf.write(source, np.zeros(12000, dtype=np.float32), 24000, subtype="PCM_16")
    target = engine._prepare_reference(
        source,
        ref_start=0.0,
        ref_duration=0.0,
        ref_max_len=25.0,
        temp_dir=tmp_path,
    )
    assert target == source

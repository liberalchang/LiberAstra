"""语音服务 HTTP 契约：不加载模型。"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SPEECH_DIR = Path(__file__).resolve().parents[2] / "services" / "speech"
sys.path.insert(0, str(SPEECH_DIR))

import engine  # noqa: E402
import server  # noqa: E402


def test_resolve_device_cpu() -> None:
    assert engine.resolve_device("cpu") == "cpu"


def test_health_auth_and_result_name(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("LIBER_SPEECH_RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("LIBER_SPEECH_API_KEY", "secret")
    client = TestClient(server.app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["asr_ready"] is False
    assert body["tts_ready"] is False

    denied = client.post("/api/v1/tts/synthesize", data={"text": "你好", "language": "zh"})
    assert denied.status_code == 401

    missing = client.get("/api/v1/results/notes.txt", headers={"Authorization": "Bearer secret"})
    assert missing.status_code == 400


def test_vc_catalog_and_default(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("LIBER_SPEECH_VC_MODEL", "seed_vc")
    assert engine.default_vc_model() == "seed-vc"
    assert [item["id"] for item in engine.vc_catalog()] == ["chatterbox", "seed-vc"]


def test_vc_window_planning() -> None:
    merged = engine._normalize_segments(
        [{"start": 0, "end": 1}, {"start": 1.02, "end": 2}],
        10.0,
    )
    assert merged == [(0.0, 2.0)]
    windows = engine._plan_windows([(0.0, 2.0)], 10.0)
    assert len(windows) == 1
    assert windows[0][0] == 0.0
    assert windows[0][1] == pytest.approx(2.15)
    assert windows[0][2:] == (0.0, 2.0)
    long_windows = engine._plan_windows([(0.0, 45.0)], 45.0)
    assert len(long_windows) == 3
    assert long_windows[0][2] == 0.0
    assert long_windows[-1][3] == 45.0


def test_separate_unavailable_without_weights(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.delenv("LIBER_SPEECH_DEMUCS_DIR", raising=False)
    assert engine.separate_available() is False


def test_save_audio_transposes_channels(tmp_path) -> None:  # noqa: ANN001
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    data = np.zeros((2, 100), dtype=np.float32)
    data[0] = 0.25
    path = tmp_path / "stereo.wav"
    server._save_audio(path, data, 8000)
    loaded, sample_rate = sf.read(path, always_2d=True)
    assert sample_rate == 8000
    assert loaded.shape == (100, 2)


def test_dac_stub_install_is_idempotent() -> None:
    names = ("dac", "dac.nn", "dac.nn.quantize")
    saved = {name: sys.modules.pop(name, None) for name in names}
    try:
        engine._install_dac_stub()
        engine._install_dac_stub()
        assert "dac.nn.quantize" in sys.modules
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

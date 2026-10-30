"""插件安装标记与深度图文件名。不启动本机推理进程。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from liberastra.services.plugins import depth_output_name


def test_depth_output_name() -> None:
    assert depth_output_name("photo.jpg") == "photo_depth.png"
    assert depth_output_name("a.b.png") == "a.b_depth.png"
    assert depth_output_name("") == "image_depth.png"


def test_liber_depth_is_registered(client: TestClient, auth_header: dict[str, str]) -> None:
    resp = client.get("/api/v1/capabilities", headers=auth_header)
    assert resp.status_code == 200
    types = {item["type"]: item for item in resp.json()["provider_types"]}
    assert types["liber_depth"]["default_base_url"] == "http://127.0.0.1:5556"
    assert "depth" in types["liber_depth"]["capabilities"]
    assert "image" in types["liber_depth"]["model_kinds"]


def test_plugin_install_and_depth_naming(
    client: TestClient, auth_header: dict[str, str], monkeypatch
) -> None:
    denied = client.post("/api/v1/plugins/speech/enable", headers=auth_header, json={})
    assert denied.status_code == 400

    missing = client.post("/api/v1/plugins/missing/install", headers=auth_header, json={})
    assert missing.status_code == 404

    installed = client.post("/api/v1/plugins/depth/install", headers=auth_header, json={})
    assert installed.status_code == 200
    body = installed.json()
    assert body["installed"] is True
    assert body["enabled"] is False
    assert body["launch"] == "python"
    assert "naked-eye" not in body["models_dir"].lower()
    assert body["models_dir"].replace("\\", "/").endswith("plugins/depth/models")
    assert body["model_status"] in {"missing", "ready", "empty"}
    assert body["env_status"] == "missing"
    assert body["install_phase"] == "venv"
    assert body["install_progress"] == 1
    assert body["env_dir"].replace("\\", "/").endswith("plugins/runtime")

    provider_id = None
    try:
        providers = client.get("/api/v1/providers", headers=auth_header).json()
        depth = next(
            item
            for item in providers
            if item["type"] == "liber_depth" and (item.get("extra") or {}).get("plugin_id") == "depth"
        )
        provider_id = depth["id"]
        assert "dpt_swin2_large_384" in (depth.get("models") or [])
        turned_on = client.patch(
            f"/api/v1/providers/{provider_id}",
            headers=auth_header,
            json={"enabled": True},
        )
        assert turned_on.status_code == 200

        class _Fake:
            async def convert_depth(
                self,
                content: bytes,
                filename: str,
                *,
                model: str = "",
                device: str = "",
            ):
                return "ignored.png", b"\x89PNG\r\n\x1a\nfake"

        monkeypatch.setattr("liberastra.api.routes.images.build_adapter", lambda record, **kwargs: _Fake())
        resp = client.post(
            "/api/v1/images/depth",
            headers=auth_header,
            data={"provider_id": str(provider_id), "model": "dpt_swin2_large_384", "device": "cpu"},
            files=[
                ("images", ("photo.jpg", b"not-a-real-jpeg", "image/jpeg")),
                ("images", ("shot.png", b"not-a-real-png", "image/png")),
            ],
        )
        assert resp.status_code == 200, resp.text
        names = [item["meta"]["source_name"] for item in resp.json()]
        assert names == ["photo_depth.png", "shot_depth.png"]
    finally:
        client.post("/api/v1/plugins/depth/uninstall", headers=auth_header)
        if provider_id is not None:
            client.delete(f"/api/v1/providers/{provider_id}", headers=auth_header)


def test_models_dir_ignores_legacy_path(monkeypatch) -> None:
    monkeypatch.setenv(
        "LIBER_DEPTH_MODELS_DIR",
        r"D:\BaiduSyncdisk\mydir\2d图片视频转3d\naked-eye-3d-plus\models",
    )
    from liberastra.services.plugins import plugin_models_dir

    path = str(plugin_models_dir("depth"))
    assert "naked-eye" not in path.lower()
    assert path.replace("\\", "/").endswith("plugins/depth/models")
    speech = str(plugin_models_dir("speech"))
    assert speech.replace("\\", "/").endswith("plugins/speech/models")


def test_depth_requirements_leave_torch_for_the_gpu_index(tmp_path) -> None:
    from liberastra.services.plugins import _filtered_requirements

    source = tmp_path / "requirements.txt"
    source.write_text("numpy>=1.26\n# 注释\ntorch\ntorchvision\ntimm>=1.0\n", encoding="utf-8")
    dest = tmp_path / "venv" / "requirements.install.txt"
    _filtered_requirements("depth", source, dest)
    text = dest.read_text(encoding="utf-8")
    assert "numpy>=1.26" in text
    assert "timm>=1.0" in text
    assert "torch" not in text


def test_shared_runtime_and_pip_progress() -> None:
    from liberastra.services.plugins import _parse_pip_fraction, shared_runtime_dir

    assert _parse_pip_fraction("Collecting torch\n  45%") == 0.45
    assert _parse_pip_fraction(" 12.5/100.0 MB") == 0.125
    assert _parse_pip_fraction("100%\r 12.5/100.0 MB") == 0.125
    assert str(shared_runtime_dir()).replace("\\", "/").endswith("plugins/runtime")

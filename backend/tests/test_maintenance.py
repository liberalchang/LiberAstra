"""M6 打磨测试：清理策略、备份导出、系统信息、新示例工作流包。"""

import io
import zipfile
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Job, User
from liberastra.services.maintenance import cleanup_old_data
from liberastra.services.workflows import list_packs
from liberastra.storage import create_asset, save_bytes


def _make_job(db, owner_id: int, days_ago: float) -> Job:
    job = Job(
        kind="test.echo", status="succeeded", progress=1.0, owner_id=owner_id,
        finished_at=datetime.now(UTC) - timedelta(days=days_ago),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_cleanup_old_data(client: TestClient, auth_header: dict[str, str]) -> None:
    db = SessionLocal()
    try:
        owner = db.query(User).first()
        old_job = _make_job(db, owner.id, days_ago=10)
        save_bytes(b"old-output", f"outputs/{old_job.id}/old.txt")
        old_asset = create_asset(
            db, kind="text", rel_path=f"outputs/{old_job.id}/old.txt",
            job_id=old_job.id, owner_id=owner.id,
        )
        fresh_job = _make_job(db, owner.id, days_ago=1)

        result = cleanup_old_data(db, retention_days=7)
        assert result["jobs"] == 1
        assert result["assets"] == 1

        assert db.get(Job, old_job.id) is None
        assert db.get(Asset, old_asset.id) is None
        assert db.get(Job, fresh_job.id) is not None
        from liberastra.storage import resolve

        assert not resolve(f"outputs/{old_job.id}").exists()
    finally:
        db.close()


def test_system_info_and_backup(client: TestClient, auth_header: dict[str, str]) -> None:
    info = client.get("/api/v1/system/info", headers=auth_header).json()
    assert info["version"] == "1.0.5"
    assert info["counts"]["users"] >= 1

    resp = client.get("/api/v1/system/backup", headers=auth_header)
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any(name.endswith(".db") for name in names)  # 数据库在备份中
    assert not any("logs/" in name for name in names)


def test_example_packs_load() -> None:
    packs = {p.name: p for p in list_packs()}
    assert "t2i_basic" in packs
    assert "upscale_basic" in packs
    assert "i2v_basic" not in packs  # 已移除：无对应单一 wan2.2_i2v checkpoint
    assert packs["upscale_basic"].inputs["image"]["type"] == "image"
    assert "minimax_h3_i2v" in packs
    assert packs["minimax_h3_i2v"].accel.get("node") == "105:200"
    assert "minimax_h3_i2v_enhancer" in packs
    assert packs["minimax_h3_i2v_enhancer"].capability == "i2v"
    assert packs["minimax_h3_i2v_enhancer"].accel.get("node") == "105:200"
    assert packs["minimax_h3_i2v_enhancer"].outputs.get("texts")
    assert packs["minimax_h3_t2v"].capability == "t2v"
    assert packs["minimax_h3_t2v_enhancer"].capability == "t2v"
    assert packs["minimax_h3_t2v_enhancer"].outputs.get("texts")
    assert "image" not in packs["minimax_h3_t2v"].inputs
    assert "image" not in packs["minimax_h3_t2v_enhancer"].inputs
    assert packs["minimax_h3_t2v_uncensored"].capability == "t2v"
    assert "image" not in packs["minimax_h3_t2v_uncensored"].inputs
    assert packs["minimax_h3_i2v_uncensored"].capability == "i2v"
    assert "image" in packs["minimax_h3_i2v_uncensored"].inputs
    assert packs["minimax_h3_i2v_uncensored"].accel.get("lora", {}).get("recommended", "").endswith(
        "minimax_h3_turbo_v4_step600_ema.safetensors"
    )
    assert packs["minimax_h3_t2v_uncensored"].accel.get("lora", {}).get("recommended", "").endswith(
        "minimax_h3_turbo_v4_step600_ema.safetensors"
    )

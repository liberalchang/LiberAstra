"""清理策略：删除超过保留期的已结束任务及其产物目录与资产记录。"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.models import Asset, Job
from liberastra.models.job import TERMINAL_STATUSES
from liberastra.storage import resolve


def cleanup_old_data(db: Session, retention_days: int) -> dict[str, int]:
    """删除 finished_at 早于截止时间的终态任务、其 outputs 目录与关联资产。"""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    old_jobs = db.scalars(
        select(Job).where(
            Job.status.in_(TERMINAL_STATUSES),
            Job.finished_at.is_not(None),
            Job.finished_at < cutoff,
        )
    ).all()

    removed_jobs = 0
    removed_assets = 0
    for job in old_jobs:
        try:
            output_dir = resolve(f"outputs/{job.id}")
            if output_dir.exists():
                shutil.rmtree(output_dir)
        except ValueError:
            pass
        for asset in db.scalars(select(Asset).where(Asset.job_id == job.id)).all():
            db.delete(asset)
            removed_assets += 1
        db.delete(job)
        removed_jobs += 1
    db.commit()
    if removed_jobs:
        logger.info("清理过期数据：{} 个任务、{} 个资产", removed_jobs, removed_assets)
    return {"jobs": removed_jobs, "assets": removed_assets}

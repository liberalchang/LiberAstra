"""视频流水线包：向 JobManager 注册所有视频任务类型。"""

from liberastra.jobs.manager import JobManager
from liberastra.pipelines.quick import run_quick_job
from liberastra.pipelines.simple import (
    run_assets_job,
    run_avatar_job,
    run_i2v_job,
    run_motion_job,
)


def register_video_jobs(manager: JobManager) -> None:
    manager.register("video.quick", run_quick_job)
    manager.register("video.i2v", run_i2v_job)
    manager.register("video.avatar", run_avatar_job)
    manager.register("video.motion", run_motion_job)
    manager.register("video.assets", run_assets_job)

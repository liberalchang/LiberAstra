"""运行时偏好设置：存 app_settings 表，界面上可改，下一个任务起生效。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from liberastra.models import AppSetting

# key -> (默认值, 下限, 上限)，单位均为秒
SPECS: dict[str, tuple[int, int, int]] = {
    # ComfyUI 出图/出视频的等待上限：本地视频（如 MiniMax H3）常需 20–60 分钟，可在系统设置再调大
    "comfy_wait_timeout_seconds": (3600, 60, 14400),
    # 同步接口（wait=true）等待任务终态的上限
    "api_wait_timeout_seconds": (300, 30, 3600),
    # LLM（Ollama / OpenAI 兼容）单次 chat 读超时；大模型冷启动易超过 60s
    "llm_request_timeout_seconds": (300, 30, 3600),
    # 同主机服务串行执行：0=并行（默认），1=同一台主机上的 Provider 任务互斥
    "serial_same_host": (0, 0, 1),
}


def get_pref(db: Session, key: str) -> int:
    default, _, _ = SPECS[key]
    row = db.get(AppSetting, key)
    if row is None:
        return default
    try:
        return int(row.value)
    except ValueError:
        return default


def set_pref(db: Session, key: str, value: int) -> int:
    """写入并按 SPECS 界定的范围钳位，返回实际生效值。"""
    _, lo, hi = SPECS[key]
    clamped = max(lo, min(hi, value))
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=str(clamped)))
    else:
        row.value = str(clamped)
    db.commit()
    return clamped


def all_prefs(db: Session) -> dict[str, int]:
    return {key: get_pref(db, key) for key in SPECS}

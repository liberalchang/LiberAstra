"""运行时偏好设置：存 app_settings 表，界面上可改，下一个任务起生效。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from liberastra.models import AppSetting

# key -> (默认值, 下限, 上限)，单位均为秒（或 0/1 开关）
SPECS: dict[str, tuple[int, int, int]] = {
    # ComfyUI 出图/出视频的等待上限：本地视频（如 MiniMax H3）常需 20–60 分钟，可在系统设置再调大
    "comfy_wait_timeout_seconds": (3600, 60, 14400),
    # 同步接口（wait=true）等待任务终态的上限
    "api_wait_timeout_seconds": (300, 30, 3600),
    # LLM（Ollama / OpenAI 兼容）单次 chat 读超时；大模型冷启动易超过 60s
    "llm_request_timeout_seconds": (300, 30, 3600),
    # 同主机服务串行执行：0=并行（默认），1=同一台主机上的 Provider 任务互斥
    "serial_same_host": (0, 0, 1),
    # 默认 LLM Provider id；0=自动取第一个启用的 llm Provider
    "default_llm_provider_id": (0, 0, 2_147_483_647),
    # 角色定妆照图像 Provider id；0=自动取第一个启用的 image Provider
    "default_character_provider_id": (0, 0, 2_147_483_647),
}

# 字符串偏好：key -> 默认值
STR_SPECS: dict[str, str] = {
    # 默认 LLM 模型名；空则用 Provider.extra.model 或已拉取列表首项
    "default_llm_model": "",
    # 角色四段式定妆照使用的文生图工作流包
    "default_character_workflow": "qwen_image_21",
    # 一张参考图时用的图生图工作流包
    "default_character_i2i_workflow": "qwen_image_21_edit",
    # 两到三张参考图时用的多图编辑工作流包
    "default_character_i2i_multi_workflow": "qwen_image_21_edit_multi",
    # Liber Speech 默认模型包。功能页不单独选模型。
    "default_speech_model": "multilingual_v3",
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


def get_str_pref(db: Session, key: str) -> str:
    default = STR_SPECS[key]
    row = db.get(AppSetting, key)
    if row is None:
        return default
    return row.value


def set_str_pref(db: Session, key: str, value: str) -> str:
    """写入字符串偏好，返回实际生效值。"""
    if key not in STR_SPECS:
        raise KeyError(f"未知字符串偏好: {key}")
    text = value if value is not None else STR_SPECS[key]
    if key == "default_speech_model":
        from liberastra.providers.speech.liber_speech import canonical_speech_model

        text = canonical_speech_model(text.strip() or STR_SPECS[key])
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=text))
    else:
        row.value = text
    db.commit()
    return text


def all_prefs(db: Session) -> dict[str, int | str]:
    out: dict[str, int | str] = {key: get_pref(db, key) for key in SPECS}
    for key in STR_SPECS:
        out[key] = get_str_pref(db, key)
    return out

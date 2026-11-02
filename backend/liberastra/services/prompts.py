"""提示词库与优化：内置 prompts/（随包或仓库）→ 用户 data/prompts/；按 task/scene/workflow 组装 system。"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from sqlalchemy.orm import Session

from liberastra.core.config import get_settings
from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Job
from liberastra.providers.base import ProviderError
from liberastra.services.canvas_graph import translate_prompt_slots
from liberastra.services.providers import build_llm_adapter, pick_llm_with_model
from liberastra.services.workflows import get_pack


def _builtin_dir() -> Path:
    """优先读随包分发的内置目录；源码/可编辑安装回落到仓库 prompts/。"""
    packaged = Path(__file__).resolve().parent.parent / "prompts"
    if (packaged / "tasks.yaml").exists() and (packaged / "scenes.yaml").exists():
        return packaged
    return Path(__file__).resolve().parents[2] / "prompts"


def _user_dir() -> Path:
    return get_settings().data_dir / "prompts"


_MISSING_BUILTIN_WARNED = False
_PRUNED_DATA_DIR: Path | None = None
# 1.0.8 及更早版本首次启动会把内置文件整份复制到 data/prompts。
# 这些条目与当时的默认内容完全相同，升级时清掉，避免旧默认遮住新模板。
_LEGACY_TASK_HASHES = {
    "t2i": "bf8ac28ab8104b283108df3934b8a4a8afc8bacf03762f8912cc417d47b1a914",
    "i2i": "25e7bee4b9f83b8d1cdb12c1f2db0f67b88c7d4a71b815142dfda9e15f42e618",
    "upscale": "50c193b132a9b8218d7aafefd5b819c188684b9318668a0abbba6a9b26f9fd93",
    "i2v": "d98514ffab8b974815ef86750d7e068bcccdb14606d985c01c24cb4d7ce7257e",
    "t2v": "dc7a6aa3dbe3d091b8e57ccb09124e6360643e8019e3e90ff360e89d00890568",
    "quick_visual": "c60638b7b53074bb429c6392ae7b3e3d2d8a477354adae05480879a39376d11e",
    "motion": "c28fdb4b724c3d048d80afb87743d83d9b647326beaeb06228df56b8c37f1ff3",
    "quick_topic": "a4cc9aa734925ad0bd8a6612448a9cc2ee0f5aec11da13986cfaabdc4c53de86",
    "assets_topic": "8b0fc25fd4b2679db37bfe8b3e0ce487032af260d2c2f4c195d81187a04a0cc7",
    "character_sheet": "17e94c856481fd472b344d378584e296bcf8a56d59ecb2ee3a1a5c7ce06de3be",
}
_LEGACY_SCENE_HASHES = {
    "auto": "19d7fe3f3b6d3844f3033de95b509dacbde8ebdbb67c8429e3d381f251223ee4",
    "photo": "9cf75d9a57a868b1b3aa3173f15cabf7abdada7414d72a2f771ff64c60024d17",
    "poster": "e1be6cc4cc5c246b0102c74bd744589f121055711b775df35292e1be9c5dc249",
    "illustration": "3e013ad19b5a013b0a20dc1e78aa79582dd4fcbd420e1e184cc36db37c55566c",
    "product": "e93c1a6478ebf454a24967cf37191251effa0c7463e93dd339ca1befe9e09959",
    "character": "de3f2b4d388412898270ff5c7e9635077c1356a423fbd6fa384b9669841a7e4a",
    "infographic": "7276872616ed5409ee2d63850c7a0ea610ce24656f93c80d4846464e329e674f",
    "architecture": "988150a55bcb82729ec3ba385728a3ef5377ceef3ac1c5a9fc55b5f0886fd269",
    "cinematic_video": "9f73bac06ae3d17cabe474f8ec80b8e115e5dea8ae5f30eec050595bff243e6f",
}


def ensure_prompt_store() -> Path:
    """确保 data/prompts 存在；新装只建空覆盖层，内置条目仍从内置目录读取。"""
    global _MISSING_BUILTIN_WARNED
    user = _user_dir()
    user.mkdir(parents=True, exist_ok=True)
    builtin = _builtin_dir()
    available = (builtin / "tasks.yaml").exists() and (builtin / "scenes.yaml").exists()
    if not available and not _MISSING_BUILTIN_WARNED:
        logger.warning("内置提示词目录缺失，恢复默认将拒绝删除用户副本: {}", builtin)
        _MISSING_BUILTIN_WARNED = True
    elif available:
        _MISSING_BUILTIN_WARNED = False
    for name, section in (("tasks.yaml", "tasks"), ("scenes.yaml", "scenes")):
        dest = user / name
        if dest.exists():
            continue
        dest.write_text(
            yaml.safe_dump(
                {"version": 1, section: {}},
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    if available:
        _prune_legacy_overrides()
    return user


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProviderError(f"提示词文件解析失败 {path.name}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _section(filename: str, section_key: str) -> dict[str, Any]:
    data = _load_yaml(_builtin_dir() / filename)
    section = data.get(section_key) or {}
    return section if isinstance(section, dict) else {}


def _user_section(filename: str, section_key: str) -> dict[str, Any]:
    ensure_prompt_store()
    data = _load_yaml(_user_dir() / filename)
    section = data.get(section_key) or {}
    return section if isinstance(section, dict) else {}


def _merged_section(filename: str, section_key: str) -> dict[str, Any]:
    """内置为底，用户文件同名条目覆盖。"""
    base = dict(_section(filename, section_key))
    base.update(_user_section(filename, section_key))
    return base


def _task_signature(task_id: str, spec: Any) -> tuple[str, tuple[str, ...], str]:
    if not isinstance(spec, dict):
        return ("", (), "")
    caps = spec.get("capabilities") or []
    if not isinstance(caps, (list, tuple, set)):
        caps = []
    return (
        str(spec.get("name") or task_id).strip(),
        tuple(sorted({str(item).strip() for item in caps if str(item).strip()})),
        str(spec.get("system") or "").strip(),
    )


def _scene_signature(scene_id: str, spec: Any) -> tuple[str, str]:
    if not isinstance(spec, dict):
        return ("", "")
    return (
        str(spec.get("name") or scene_id).strip(),
        str(spec.get("append") or "").strip(),
    )


def _signature_hash(signature: tuple[Any, ...]) -> str:
    payload = json.dumps(signature, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _is_legacy_task(task_id: str, spec: Any) -> bool:
    return _LEGACY_TASK_HASHES.get(task_id) == _signature_hash(
        _task_signature(task_id, spec)
    )


def _is_legacy_scene(scene_id: str, spec: Any) -> bool:
    return _LEGACY_SCENE_HASHES.get(scene_id) == _signature_hash(
        _scene_signature(scene_id, spec)
    )


def _prune_legacy_overrides() -> None:
    global _PRUNED_DATA_DIR
    user = _user_dir()
    if _PRUNED_DATA_DIR == user:
        return
    _PRUNED_DATA_DIR = user
    groups = (
        ("tasks.yaml", "tasks", _LEGACY_TASK_HASHES, _task_signature),
        ("scenes.yaml", "scenes", _LEGACY_SCENE_HASHES, _scene_signature),
    )
    for filename, section_key, legacy_hashes, signature in groups:
        path = user / filename
        if not path.exists():
            continue
        data = _load_yaml(path)
        section = dict(data.get(section_key) or {})
        removed = [
            entry_id
            for entry_id, spec in section.items()
            if legacy_hashes.get(entry_id)
            and legacy_hashes[entry_id] == _signature_hash(signature(entry_id, spec))
        ]
        if not removed:
            continue
        for entry_id in removed:
            del section[entry_id]
        data[section_key] = section
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        logger.info(
            "已清理旧版内置副本 {}: {}", filename, ", ".join(str(item) for item in removed)
        )


def _task_origin(
    task_id: str, user: dict[str, Any], builtin: dict[str, Any]
) -> str:
    if task_id not in user:
        return "builtin"
    if task_id not in builtin:
        return "user"
    if _is_legacy_task(task_id, user[task_id]):
        return "builtin"
    return (
        "customized"
        if _task_signature(task_id, user[task_id])
        != _task_signature(task_id, builtin[task_id])
        else "builtin"
    )


def _scene_origin(
    scene_id: str, user: dict[str, Any], builtin: dict[str, Any]
) -> str:
    if scene_id not in user:
        return "builtin"
    if scene_id not in builtin:
        return "user"
    if _is_legacy_scene(scene_id, user[scene_id]):
        return "builtin"
    return (
        "customized"
        if _scene_signature(scene_id, user[scene_id])
        != _scene_signature(scene_id, builtin[scene_id])
        else "builtin"
    )


def list_tasks() -> list[dict[str, Any]]:
    builtin = _section("tasks.yaml", "tasks")
    user = _user_section("tasks.yaml", "tasks")
    tasks = {**builtin, **user}
    out: list[dict[str, Any]] = []
    for tid, spec in tasks.items():
        if not isinstance(spec, dict):
            continue
        origin = _task_origin(tid, user, builtin)
        out.append(
            {
                "id": tid,
                "name": spec.get("name", tid),
                "capabilities": list(spec.get("capabilities") or []),
                "system": str(spec.get("system") or ""),
                "custom": origin != "builtin",
                "origin": origin,
            }
        )
    return out


def list_scenes() -> list[dict[str, Any]]:
    builtin = _section("scenes.yaml", "scenes")
    user = _user_section("scenes.yaml", "scenes")
    scenes = {**builtin, **user}
    out: list[dict[str, Any]] = []
    for sid, spec in scenes.items():
        if not isinstance(spec, dict):
            continue
        origin = _scene_origin(sid, user, builtin)
        out.append(
            {
                "id": sid,
                "name": spec.get("name", sid),
                "append": str(spec.get("append") or ""),
                "custom": origin != "builtin",
                "origin": origin,
            }
        )
    return out


def get_task_system(task: str) -> str:
    tasks = _merged_section("tasks.yaml", "tasks")
    spec = tasks.get(task) or tasks.get("t2i")
    if not isinstance(spec, dict):
        return "你是提示词专家。扩写用户输入为高质量提示词。直接输出提示词，不要解释。"
    return str(spec.get("system") or "").strip()


def get_scene_append(scene: str | None) -> str:
    if not scene or scene == "auto":
        scenes = _merged_section("scenes.yaml", "scenes")
        auto = scenes.get("auto")
        if isinstance(auto, dict):
            return str(auto.get("append") or "").strip()
        return ""
    scenes = _merged_section("scenes.yaml", "scenes")
    spec = scenes.get(scene)
    if not isinstance(spec, dict):
        return ""
    return str(spec.get("append") or "").strip()


def _set_user_entry(
    filename: str, section_key: str, entry_id: str, spec: dict[str, Any]
) -> None:
    ensure_prompt_store()
    path = _user_dir() / filename
    data = _load_yaml(path)
    section = dict(data.get(section_key) or {})
    section[entry_id] = spec
    data["version"] = data.get("version", 1)
    data[section_key] = section
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _remove_user_entry(filename: str, section_key: str, entry_id: str) -> bool:
    ensure_prompt_store()
    path = _user_dir() / filename
    data = _load_yaml(path)
    section = dict(data.get(section_key) or {})
    if entry_id not in section:
        return False
    del section[entry_id]
    data[section_key] = section
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return True


def upsert_task(
    task_id: str, *, name: str, system: str, capabilities: list[str] | None = None
) -> str:
    """写入用户覆盖；与内置一致时不写覆盖，返回 builtin/customized/user。"""
    ensure_prompt_store()
    raw_caps: Any = capabilities or []
    if isinstance(raw_caps, str):
        raw_caps = [raw_caps]
    cleaned_caps = [str(item).strip() for item in raw_caps if str(item).strip()]
    spec = {"name": name, "capabilities": cleaned_caps, "system": system}
    builtin = _section("tasks.yaml", "tasks")
    user = _user_section("tasks.yaml", "tasks")
    is_builtin = task_id in builtin
    same_as_builtin = is_builtin and _task_signature(task_id, spec) == _task_signature(
        task_id, builtin[task_id]
    )
    if same_as_builtin:
        _remove_user_entry("tasks.yaml", "tasks", task_id)
        return "builtin"
    origin = _task_origin(task_id, user, builtin)
    if task_id in user and _task_signature(task_id, spec) == _task_signature(
        task_id, user[task_id]
    ):
        return origin
    _set_user_entry("tasks.yaml", "tasks", task_id, spec)
    return "user" if not is_builtin else "customized"


def upsert_scene(scene_id: str, *, name: str, append: str) -> str:
    """写入用户覆盖；与内置一致时不写覆盖，返回 builtin/customized/user。"""
    ensure_prompt_store()
    spec = {"name": name, "append": append}
    builtin = _section("scenes.yaml", "scenes")
    user = _user_section("scenes.yaml", "scenes")
    is_builtin = scene_id in builtin
    same_as_builtin = is_builtin and _scene_signature(
        scene_id, spec
    ) == _scene_signature(scene_id, builtin[scene_id])
    if same_as_builtin:
        _remove_user_entry("scenes.yaml", "scenes", scene_id)
        return "builtin"
    origin = _scene_origin(scene_id, user, builtin)
    if scene_id in user and _scene_signature(
        scene_id, spec
    ) == _scene_signature(scene_id, user[scene_id]):
        return origin
    _set_user_entry("scenes.yaml", "scenes", scene_id, spec)
    return "user" if not is_builtin else "customized"


def _delete_override(
    filename: str,
    section_key: str,
    entry_id: str,
    kind_label: str,
    *,
    mode: str = "reset",
) -> None:
    """reset 删除内置覆盖；delete 删除用户自建项。两种操作严格分开。"""
    if mode not in ("reset", "delete"):
        raise ProviderError("未知的模板删除模式")
    ensure_prompt_store()
    builtin = _section(filename, section_key)
    user = _user_section(filename, section_key)
    if entry_id not in user:
        raise ProviderError(f"{kind_label} {entry_id} 未被自定义")
    if mode == "reset" and entry_id not in builtin:
        raise ProviderError(
            f"{kind_label} {entry_id} 不是内置模板，恢复默认会删除用户副本；请使用删除"
        )
    if mode == "delete" and entry_id in builtin:
        raise ProviderError(
            f"{kind_label} {entry_id} 是内置模板，不能删除；请使用恢复默认"
        )
    _remove_user_entry(filename, section_key, entry_id)


def delete_task_override(task_id: str, *, mode: str = "reset") -> None:
    _delete_override("tasks.yaml", "tasks", task_id, "功能模板", mode=mode)


def delete_scene_override(scene_id: str, *, mode: str = "reset") -> None:
    _delete_override("scenes.yaml", "scenes", scene_id, "场景预设", mode=mode)


def import_prompts(payload: dict[str, Any]) -> dict[str, int]:
    """导入 YAML/JSON 结构：{tasks: {...}, scenes: {...}}。与内置一致的不写覆盖。"""
    ensure_prompt_store()
    n_tasks = n_scenes = 0
    tasks = payload.get("tasks")
    if isinstance(tasks, dict):
        for tid, spec in tasks.items():
            if isinstance(spec, dict) and spec.get("system"):
                upsert_task(
                    str(tid),
                    name=str(spec.get("name") or tid),
                    system=str(spec["system"]),
                    capabilities=spec.get("capabilities") or [],
                )
                n_tasks += 1
    scenes = payload.get("scenes")
    if isinstance(scenes, dict):
        for sid, spec in scenes.items():
            if isinstance(spec, dict):
                upsert_scene(
                    str(sid),
                    name=str(spec.get("name") or sid),
                    append=str(spec.get("append") or ""),
                )
                n_scenes += 1
    return {"tasks": n_tasks, "scenes": n_scenes}


def _guess_prompt_language(text: str) -> str:
    """粗判用户输入语言，指导优化输出中/英。"""
    if not text or not text.strip():
        return "跟随用户输入语言"
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin = sum(1 for ch in text if ("a" <= ch.lower() <= "z"))
    if cjk >= 2 and cjk >= latin:
        return "中文（用户输入以中文为主，请输出中文提示词）"
    if latin >= 8 and latin > cjk * 2:
        return "English（user input is mostly English; write the optimized prompt in English）"
    return "跟随用户输入的主要语言；中英混排时以用户主体语言为准"


def _workflow_context(workflow: str | None, aspect: str | None) -> str:
    if not workflow and not aspect:
        return ""
    parts: list[str] = []
    if aspect:
        ratio = aspect.strip()
        orient = ""
        if ratio in ("9:16", "3:4", "2:3"):
            orient = "竖屏"
        elif ratio in ("16:9", "4:3", "3:2"):
            orient = "横屏"
        elif ratio in ("1:1",):
            orient = "方形"
        parts.append(f"目标画幅：{ratio}" + (f"（{orient}）" if orient else "") + "，构图与景别需匹配画幅。")
    if not workflow:
        return "\n".join(parts)
    try:
        from liberastra.services.workflows import get_pack

        pack = get_pack(workflow)
    except Exception:  # noqa: BLE001
        parts.append(f"工作流包：{workflow}（未能加载详情）")
        return "\n".join(parts)

    parts.append(f"工作流包：{pack.name}（capability={pack.capability}）")
    # llm_note 是给优化器的技术上下文(事实密度优先);缺省回落用户向 description
    note = (pack.llm_note or "").strip() or pack.description
    if note:
        parts.append(f"包说明：{note}")
    # 收集默认模型/checkpoint 名，便于家族识别与展示
    model_hints: list[str] = []
    for key, spec in (pack.inputs or {}).items():
        if not isinstance(spec, dict):
            continue
        default = spec.get("default")
        if isinstance(default, str) and default.strip() and (
            "model" in key.lower()
            or "ckpt" in key.lower()
            or "checkpoint" in key.lower()
            or "unet" in key.lower()
            or key.lower() in ("ckpt_name", "unet_name", "model_name")
        ):
            model_hints.append(f"{key}={default}")
    if model_hints:
        parts.append("默认模型/权重：" + "；".join(model_hints[:6]))
    family = _detect_family(pack, model_hints)
    if family:
        parts.append(f"模型家族格式要求：{family}")
    else:
        parts.append(
            "未识别到明确模型家族：请用自然语言清晰描述；"
            "若像 Stable Diffusion 标签风格则可用逗号分隔，否则优先完整句子。"
        )
    nodes = pack.requirements.get("nodes") if isinstance(pack.requirements, dict) else None
    if isinstance(nodes, list) and "MiniMaxH3PromptEnhancer" in nodes:
        parts.append(
            "该包内置 Guide 提示词增强器：请保持提示词精炼、只写核心主体/运动/音效，避免过长扩写。"
        )
    return "\n".join(parts)


def _detect_family(pack: Any, model_hints: list[str] | None = None) -> str:  # noqa: ANN401
    # llm_note 技术事实也参与家族识别(description 改为通俗版后信号变弱,这里补强)
    blob = f"{pack.name} {pack.description} {getattr(pack, 'llm_note', '')} ".lower()
    for hint in model_hints or []:
        blob += f" {hint.lower()}"
    for key, default in (pack.inputs or {}).items():
        if isinstance(default, dict) and default.get("default"):
            blob += f" {default['default']}"
        blob += f" {key}"
    if "minimax_h3" in blob or "minimax-h3" in blob or "hailuo" in blob:
        return (
            "MiniMax H3：用完整镜头散文，不要逗号标签堆叠。"
            "必须写明运镜术语（推、拉、摇、移、跟、升、降、环绕或固定镜头），"
            "并单独一行以「背景音：」写出同步环境声。语言跟随用户输入。"
        )
    if "qwen_image" in blob or "qwen-image" in blob or "qwen_image" in pack.name.lower():
        return (
            "Qwen-Image：自然语言长句；图内中文必须用引号逐字给出；"
            "中文用户用中文写提示词即可。"
        )
    if "flux" in blob:
        return "Flux：偏英文自然语言亦可中文；强调主体、光线与构图，少用 SD 权重语法。"
    if "gpt-image" in blob or "dall-e" in blob or "dalle" in blob:
        return "GPT-Image / DALL·E 类：自然语言完整句子；语言跟随用户。"
    if (
        pack.name == "t2i_basic"
        or "sdxl" in blob
        or "sd1" in blob
        or "stable-diffusion" in blob
        or "stable_diffusion" in blob
    ):
        return (
            "Stable Diffusion / SDXL：可用英文逗号分隔视觉标签与画质词"
            "（如 masterpiece, best quality）；中文用户若输入中文可输出中文标签或中英混排，"
            "避免复杂权重除非用户已在用。"
        )
    return ""


def build_system_prompt(
    task: str,
    *,
    scene: str | None = None,
    workflow: str | None = None,
    aspect: str | None = None,
    extra_context: str | None = None,
    user_prompt: str = "",
) -> str:
    """组装优化用 system：功能模板(task) + 场景叠加(scene) + 工作流/画幅 + 语言。"""
    tasks = _merged_section("tasks.yaml", "tasks")
    spec = tasks.get(task) if isinstance(tasks.get(task), dict) else None
    task_name = (spec or {}).get("name", task) if isinstance(spec, dict) else task

    header = (
        f"【当前功能】task={task}（{task_name}）。"
        "必须按该功能的任务模板扩写；下方「场景」只叠加风格倾向，不能替换功能目标。"
    )
    lang = _guess_prompt_language(user_prompt)
    chunks = [
        header,
        f"【输出语言】{lang}",
        get_task_system(task),
    ]
    scene_append = get_scene_append(scene)
    if scene_append:
        chunks.append("【场景预设】\n" + scene_append)
    wf = _workflow_context(workflow, aspect)
    if wf:
        chunks.append("【当前工作流上下文】\n" + wf)
    if extra_context and extra_context.strip():
        chunks.append("【额外上下文】\n" + extra_context.strip())
    chunks.append(
        "直接输出优化后的提示词正文，不要前言、不要 markdown 代码块、不要解释。"
    )
    return "\n\n".join(c for c in chunks if c.strip())


def _prompt_in_pack_words(prompt: str, workflow: str | None) -> str:
    """优化前先把槽位名换成这个包认识的称呼，模型才知道指的是哪张图。"""
    if not workflow or not prompt.strip():
        return prompt
    try:
        pack = get_pack(workflow)
    except ProviderError:
        return prompt
    return translate_prompt_slots(prompt, pack.inputs)


def _optimize_messages(
    *,
    prompt: str,
    task: str,
    scene: str | None,
    workflow: str | None,
    aspect: str | None,
    extra_context: str | None,
) -> list[dict[str, str]]:
    prompt = _prompt_in_pack_words(prompt, workflow)
    system = build_system_prompt(
        task,
        scene=scene,
        workflow=workflow,
        aspect=aspect,
        extra_context=extra_context,
        user_prompt=prompt,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]


async def optimize_prompt(
    db: Session,
    *,
    prompt: str,
    task: str = "t2i",
    scene: str | None = None,
    workflow: str | None = None,
    aspect: str | None = None,
    extra_context: str | None = None,
    provider_id: int | None = None,
    model: str = "",
) -> dict[str, str]:
    """用默认/指定 LLM 按 task + 工作流上下文优化提示词。"""
    ensure_prompt_store()
    provider, resolved_model = pick_llm_with_model(db, provider_id, model)
    adapter = build_llm_adapter(provider, db=db)
    messages = _optimize_messages(
        prompt=prompt,
        task=task,
        scene=scene,
        workflow=workflow,
        aspect=aspect,
        extra_context=extra_context,
    )
    try:
        text = await adapter.chat(model=resolved_model, messages=messages)
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"提示词优化失败: {exc}") from exc
    return {
        "optimized": (text or "").strip(),
        "provider_name": provider.name,
        "model": resolved_model,
    }


async def optimize_prompt_stream(
    db: Session,
    *,
    prompt: str,
    task: str = "t2i",
    scene: str | None = None,
    workflow: str | None = None,
    aspect: str | None = None,
    extra_context: str | None = None,
    provider_id: int | None = None,
    model: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """流式优化：先 yield meta，再逐段 yield token，最后 yield done。

    事件形如 ``{"event": "meta"|"token"|"done"|"error", ...}``。
    Ollama（/v1）与多数 OpenAI 兼容服务支持 ``stream: true``；若适配器无
    ``chat_stream`` 则回退为整段一次返回。
    """
    ensure_prompt_store()
    provider, resolved_model = pick_llm_with_model(db, provider_id, model)
    adapter = build_llm_adapter(provider, db=db)
    messages = _optimize_messages(
        prompt=prompt,
        task=task,
        scene=scene,
        workflow=workflow,
        aspect=aspect,
        extra_context=extra_context,
    )
    yield {
        "event": "meta",
        "provider_name": provider.name,
        "model": resolved_model,
    }
    try:
        stream_fn = getattr(adapter, "chat_stream", None)
        if callable(stream_fn):
            async for piece in stream_fn(model=resolved_model, messages=messages):
                if piece:
                    yield {"event": "token", "text": piece}
        else:
            text = await adapter.chat(model=resolved_model, messages=messages)
            if text:
                yield {"event": "token", "text": text}
        yield {"event": "done"}
    except ProviderError as exc:
        yield {"event": "error", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        yield {"event": "error", "message": f"提示词优化失败: {exc}"}


def _optimize_output(
    *, content: str, provider_name: str, model: str
) -> dict[str, Any]:
    return {
        "type": "text",
        "content": content,
        "provider_name": provider_name,
        "model": model,
    }


async def run_optimize_prompt_job(
    db: Session, job: Job, ctx: JobContext
) -> list[dict[str, Any]]:
    """prompt.optimize：流式调用 LLM，增量写入 job.outputs 供前端轮询。"""
    ensure_prompt_store()
    params = job.params or {}
    provider, resolved_model = pick_llm_with_model(
        db, job.provider_id, job.model or params.get("model") or ""
    )
    adapter = build_llm_adapter(provider, db=db)
    messages = _optimize_messages(
        prompt=str(params.get("prompt") or ""),
        task=str(params.get("task") or "t2i"),
        scene=params.get("scene"),
        workflow=params.get("workflow"),
        aspect=params.get("aspect"),
        extra_context=params.get("extra_context"),
    )
    ctx.report(db, job, progress=0.05, step="optimize")

    assembled = ""
    last_emit = 0.0
    meta_name, meta_model = provider.name, resolved_model

    def _flush(progress: float) -> None:
        job.outputs = [
            _optimize_output(
                content=assembled, provider_name=meta_name, model=meta_model
            )
        ]
        ctx.report(db, job, progress=progress)

    try:
        stream_fn = getattr(adapter, "chat_stream", None)
        if callable(stream_fn):
            async for piece in stream_fn(model=resolved_model, messages=messages):
                if ctx.cancelled():
                    break
                if not piece:
                    continue
                assembled += piece
                now = time.monotonic()
                if now - last_emit >= 0.35:
                    last_emit = now
                    # 软上限 0.9，终态由 JobManager 置 1.0
                    _flush(min(0.9, 0.05 + len(assembled) / 2500))
        else:
            assembled = await adapter.chat(model=resolved_model, messages=messages)
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"提示词优化失败: {exc}") from exc

    final = (assembled or "").strip()
    return [
        _optimize_output(content=final, provider_name=meta_name, model=meta_model)
    ]


def register_prompt_jobs(manager: JobManager) -> None:
    manager.register("prompt.optimize", run_optimize_prompt_job)

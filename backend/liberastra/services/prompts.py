"""提示词库与优化：内置 backend/prompts/ → 用户 data/prompts/；按 task/scene/workflow 组装 system。"""

from __future__ import annotations

import shutil
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from liberastra.core.config import get_settings
from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Job
from liberastra.providers.base import ProviderError
from liberastra.services.providers import build_llm_adapter, pick_llm_with_model


def _builtin_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts"


def _user_dir() -> Path:
    return get_settings().data_dir / "prompts"


def ensure_prompt_store() -> Path:
    """确保 data/prompts 存在；缺失时从内置目录复制种子文件。"""
    user = _user_dir()
    user.mkdir(parents=True, exist_ok=True)
    builtin = _builtin_dir()
    for name in ("tasks.yaml", "scenes.yaml"):
        dest = user / name
        src = builtin / name
        if not dest.exists() and src.exists():
            shutil.copy2(src, dest)
    return user


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProviderError(f"提示词文件解析失败 {path.name}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _merged_section(filename: str, section_key: str) -> dict[str, Any]:
    """内置为底，用户文件同名条目覆盖。"""
    ensure_prompt_store()
    builtin = _load_yaml(_builtin_dir() / filename)
    user = _load_yaml(_user_dir() / filename)
    base = dict(builtin.get(section_key) or {})
    override = user.get(section_key) or {}
    if isinstance(override, dict):
        base.update(override)
    return base


def _user_section_keys(filename: str, section_key: str) -> set[str]:
    """用户覆盖文件里实际存在的条目 id(用于「已自定义」标记)。"""
    ensure_prompt_store()
    user = _load_yaml(_user_dir() / filename)
    section = user.get(section_key) or {}
    return set(section) if isinstance(section, dict) else set()


def list_tasks() -> list[dict[str, Any]]:
    custom = _user_section_keys("tasks.yaml", "tasks")
    tasks = _merged_section("tasks.yaml", "tasks")
    out: list[dict[str, Any]] = []
    for tid, spec in tasks.items():
        if not isinstance(spec, dict):
            continue
        out.append(
            {
                "id": tid,
                "name": spec.get("name", tid),
                "capabilities": list(spec.get("capabilities") or []),
                "system": str(spec.get("system") or ""),
                "custom": tid in custom,
            }
        )
    return out


def list_scenes() -> list[dict[str, Any]]:
    custom = _user_section_keys("scenes.yaml", "scenes")
    scenes = _merged_section("scenes.yaml", "scenes")
    out: list[dict[str, Any]] = []
    for sid, spec in scenes.items():
        if not isinstance(spec, dict):
            continue
        out.append(
            {
                "id": sid,
                "name": spec.get("name", sid),
                "append": str(spec.get("append") or ""),
                "custom": sid in custom,
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


def upsert_task(task_id: str, *, name: str, system: str, capabilities: list[str] | None = None) -> None:
    ensure_prompt_store()
    path = _user_dir() / "tasks.yaml"
    data = _load_yaml(path)
    tasks = dict(data.get("tasks") or {})
    tasks[task_id] = {
        "name": name,
        "capabilities": capabilities or [],
        "system": system,
    }
    data["version"] = data.get("version", 1)
    data["tasks"] = tasks
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def upsert_scene(scene_id: str, *, name: str, append: str) -> None:
    ensure_prompt_store()
    path = _user_dir() / "scenes.yaml"
    data = _load_yaml(path)
    scenes = dict(data.get("scenes") or {})
    scenes[scene_id] = {"name": name, "append": append}
    data["version"] = data.get("version", 1)
    data["scenes"] = scenes
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _delete_override(filename: str, section_key: str, entry_id: str, kind_label: str) -> None:
    """删除用户覆盖条目(= 恢复默认)。内置条目本身不可删:未被自定义时报错。"""
    ensure_prompt_store()
    path = _user_dir() / filename
    data = _load_yaml(path)
    section = dict(data.get(section_key) or {})
    if entry_id not in section:
        raise ProviderError(f"{kind_label} {entry_id} 未被自定义，内置模板不可删除")
    del section[entry_id]
    data[section_key] = section
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def delete_task_override(task_id: str) -> None:
    _delete_override("tasks.yaml", "tasks", task_id, "功能模板")


def delete_scene_override(scene_id: str) -> None:
    _delete_override("scenes.yaml", "scenes", scene_id, "场景预设")


def import_prompts(payload: dict[str, Any]) -> dict[str, int]:
    """导入 YAML/JSON 结构：{tasks: {...}, scenes: {...}}。"""
    ensure_prompt_store()
    n_tasks = n_scenes = 0
    tasks = payload.get("tasks")
    if isinstance(tasks, dict):
        path = _user_dir() / "tasks.yaml"
        data = _load_yaml(path)
        merged = dict(data.get("tasks") or {})
        for tid, spec in tasks.items():
            if isinstance(spec, dict) and spec.get("system"):
                merged[str(tid)] = spec
                n_tasks += 1
        data["tasks"] = merged
        data["version"] = data.get("version", 1)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    scenes = payload.get("scenes")
    if isinstance(scenes, dict):
        path = _user_dir() / "scenes.yaml"
        data = _load_yaml(path)
        merged = dict(data.get("scenes") or {})
        for sid, spec in scenes.items():
            if isinstance(spec, dict):
                merged[str(sid)] = spec
                n_scenes += 1
        data["scenes"] = merged
        data["version"] = data.get("version", 1)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
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
            "MiniMax H3：自然语言；结构为「画面主体与环境 + 镜头运动 + 时序动作 + 同步环境音/音效/对白」；"
            "音视频联合生成友好；语言跟随用户输入。"
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


def _optimize_messages(
    *,
    prompt: str,
    task: str,
    scene: str | None,
    workflow: str | None,
    aspect: str | None,
    extra_context: str | None,
) -> list[dict[str, str]]:
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
